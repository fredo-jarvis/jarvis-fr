"""
Plugin : lire sa boîte Gmail à la voix (lecture seule).

    « Jarvis, j'ai des nouveaux mails ? »      « Jarvis, lis-moi le mail de Julie »
    « Jarvis, cherche le mail de la banque »   « Jarvis, lis le deuxième »

Branchement (une seule fois) : double-cliquer sur Brancher-Gmail.bat, qui demande l'adresse
Gmail et un « mot de passe d'application » Google (pas le vrai mot de passe), et les garde
dans config/api_keys.json (jamais partagé). Jarvis ne peut ni envoyer, ni effacer, ni déplacer
un mail : il lit seulement.
"""
import email
import imaplib
import json
from email.header import decode_header, make_header
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
_DERNIERS: list[bytes] = []          # numéros des mails de la dernière liste, pour « lis le deuxième »

PLUGIN = {
    "name": "gmail_lire",
    "description": (
        "Read the user's Gmail inbox, read-only. Use it when the user asks about their emails: "
        "'j'ai des nouveaux mails ?', 'lis-moi mes mails', 'cherche le mail de X', "
        "'lis le premier / le deuxième'. action='nouveaux' lists unread mails, "
        "action='chercher' searches with 'recherche' (a name, a word, an address), "
        "action='lire' reads mail number 'numero' from the last list. "
        "It can never send, delete or move a mail. If Gmail is not connected yet, "
        "explain the answer to the user simply."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "nouveaux, chercher ou lire"},
            "recherche": {"type": "STRING", "description": "Pour chercher : un nom, un mot ou une adresse"},
            "numero": {"type": "INTEGER", "description": "Pour lire : le numéro dans la dernière liste (1 = le premier)"},
        },
        "required": ["action"],
    },
}

NON_BRANCHE = (
    "Gmail n'est pas encore branché. Pour le faire : ouvre le dossier de Jarvis et double-clique "
    "sur Brancher-Gmail.bat. Il te demandera ton adresse Gmail et un mot de passe d'application "
    "Google, que tu crées sur myaccount.google.com/apppasswords (il faut avoir la validation en "
    "deux étapes activée). Ensuite, relance-moi."
)


def _texte(v) -> str:
    try:
        return str(make_header(decode_header(v or "")))
    except Exception:
        return v or ""


def _connexion():
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    adresse, mdp = cfg.get("gmail_adresse"), cfg.get("gmail_mot_de_passe_app")
    if not adresse or not mdp:
        return None
    m = imaplib.IMAP4_SSL("imap.gmail.com", timeout=20)
    m.login(adresse, mdp)
    m.select("INBOX", readonly=True)
    return m


def _entete(m, num: bytes) -> str:
    _t, data = m.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
    msg = email.message_from_bytes(data[0][1])
    de = _texte(msg.get("From")).split("<")[0].strip().strip('"') or _texte(msg.get("From"))
    return f"de {de} : « {_texte(msg.get('Subject')) or 'sans objet'} »"


def _corps(m, num: bytes) -> str:
    _t, data = m.fetch(num, "(BODY.PEEK[])")
    msg = email.message_from_bytes(data[0][1])
    morceaux = []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
            try:
                morceaux.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace"))
            except Exception:
                pass
    texte = " ".join(" ".join(morceaux).split())
    return texte[:1500] or "(ce mail n'a pas de texte simple à lire)"


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = (parameters.get("action") or "nouveaux").lower()
    try:
        m = _connexion()
    except imaplib.IMAP4.error:
        return ("Gmail refuse la connexion : le mot de passe d'application n'est pas bon. "
                "Relance Brancher-Gmail.bat pour le retaper.")
    except Exception as e:
        return f"Je n'arrive pas à joindre Gmail : {e}"
    if m is None:
        return NON_BRANCHE
    try:
        if action == "lire":
            n = int(parameters.get("numero") or 1)
            if not 1 <= n <= len(_DERNIERS):
                return "Je n'ai pas de liste de mails en tête : demande-moi d'abord tes nouveaux mails ou une recherche."
            num = _DERNIERS[n - 1]
            return f"Mail {_entete(m, num)}. Voici ce qu'il dit : {_corps(m, num)}"
        if action == "chercher":
            mot = (parameters.get("recherche") or "").replace('"', "")
            if not mot:
                return "Que dois-je chercher dans tes mails ?"
            _t, data = m.search("UTF-8", "TEXT", f'"{mot}"'.encode("utf-8"))
        else:
            _t, data = m.search(None, "UNSEEN")
        nums = data[0].split()[::-1][:5]
        _DERNIERS[:] = nums
        if not nums:
            return "Aucun nouveau mail." if action != "chercher" else "Je n'ai trouvé aucun mail avec ça."
        total = len(data[0].split())
        lignes = [f"{i}. {_entete(m, num)}" for i, num in enumerate(nums, 1)]
        debut = (f"Tu as {total} mail{'s' if total > 1 else ''} non lu{'s' if total > 1 else ''}"
                 if action != "chercher" else f"J'ai trouvé {total} mail{'s' if total > 1 else ''}")
        return debut + (", voici les plus récents : " if total > 1 else " : ") + " ; ".join(lignes) + \
            ". Dis-moi lequel lire."
    finally:
        try:
            m.logout()
        except Exception:
            pass
