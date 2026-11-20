"""Branche Gmail à Jarvis (lecture seule). Lancé par Brancher-Gmail.bat.

Demande l'adresse Gmail et un mot de passe d'application Google, vérifie qu'ils marchent,
puis les garde dans config/api_keys.json — le mot de passe chiffré par Windows, jamais en clair.
"""
import getpass
import imaplib
import json
import webbrowser
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"

print("=== Brancher Gmail à Jarvis (lecture seule) ===\n")
print("Il te faut un « mot de passe d'application » Google (16 lettres), PAS ton vrai mot de passe.")
print("1. La validation en deux étapes doit être activée sur ton compte Google.")
print("2. La page pour créer le mot de passe d'application va s'ouvrir : donne-lui le nom « Jarvis ».\n")
input("Appuie sur Entrée pour ouvrir la page Google...")
webbrowser.open("https://myaccount.google.com/apppasswords")

adresse = input("\nTon adresse Gmail : ").strip()
mdp = getpass.getpass("Le mot de passe d'application (il ne s'affiche pas, c'est normal) : ").replace(" ", "")

print("\nVérification auprès de Gmail...")
try:
    m = imaplib.IMAP4_SSL("imap.gmail.com", timeout=20)
    m.login(adresse, mdp)
    m.logout()
except Exception as e:
    print(f"\nÇa n'a pas marché : {e}\nVérifie l'adresse et le mot de passe d'application, puis relance.")
    input("\nAppuie sur Entrée pour fermer.")
    raise SystemExit(1)

try:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
except Exception:
    cfg = {}
cfg["gmail_adresse"] = adresse
# 1.1.3 : le mot de passe d'application n'est plus jamais écrit en clair (chiffré par Windows)
import sys
sys.path.insert(0, str(CONFIG.parent.parent))
from core import coffre
chiffre, etat = coffre.proteger(mdp)
ancienne_ref = str(cfg.get("gmail_mot_de_passe_app_chiffre", ""))
if chiffre:
    cfg.pop("gmail_mot_de_passe_app", None)
    cfg["gmail_mot_de_passe_app_chiffre"] = chiffre
else:
    if ancienne_ref.startswith(coffre.PREFIXE_TROUSSEAU) or etat == "conflit":
        # Jamais de clair à la place d'une référence au trousseau, ni d'écrasement d'une entrée différente.
        print(f"\nTrousseau inaccessible ou entrée existante différente ({etat}) : rien n'a été modifié."
              "\nDéverrouille le trousseau (ou supprime l'entrée « jarvis-fr » dans Mots de passe et clés) puis relance.")
        input("\nAppuie sur Entrée pour fermer.")
        raise SystemExit(1)
    if sys.platform != "win32":
        print(f"\n⚠ Trousseau indisponible ({etat}) : le mot de passe sera écrit EN CLAIR dans {CONFIG} (permissions 0600).")
    cfg.pop("gmail_mot_de_passe_app_chiffre", None)
    cfg["gmail_mot_de_passe_app"] = mdp      # repli : fichier réservé à ton compte (ci-dessous)
CONFIG.parent.mkdir(parents=True, exist_ok=True)
coffre.ecrire_atomique(CONFIG, json.dumps(cfg, indent=2, ensure_ascii=False))
print("\nC'est branché ! Relance Jarvis et demande-lui : « j'ai des nouveaux mails ? »")
input("\nAppuie sur Entrée pour fermer.")
