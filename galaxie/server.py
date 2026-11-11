r"""
Interface de Jarvis : la galaxie du cerveau, http://localhost:4719 (écrit par Jarvis Claude le 04/11/2026, code original).

Quand Jarvis tourne, ce serveur vit dans Jarvis (voir pont.py) et la page devient son interface.
Seul, il montre la galaxie :  .venv2\Scripts\python.exe galaxie\server.py --ouvrir   (ou Lancer-Galaxie.bat)

Le serveur reste sur ce PC (127.0.0.1) et ne fait que LIRE le wiki. Bibliothèque standard seulement,
aucune page extérieure : la galaxie s'affiche sans Internet.
"""
import ctypes
import json
import re
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
sys.path.insert(0, str(RACINE))

PORT = 4719
ADRESSE = f"http://localhost:{PORT}/"
from plugins._cerveau_commun import WIKI   # le cerveau de l'utilisateur (réglage "cerveau" ou Documents\Cerveau)
COMPETENCES = Path.home() / ".claude" / "skills"
OUTILS = WIKI.parent / "outils"
PLUGINS = RACINE / "plugins"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
MAX_QUESTION = 2000
MAX_EXTRAIT = 700

GROUPES = {
    "conversations": ("Conversations", "#34d399"), "projets": ("Projets", "#fbbf24"),
    "concepts": ("Concepts", "#f59e0b"), "entites": ("Entités", "#a78bfa"),
    "sources": ("Sources", "#fb923c"), "syntheses": ("Synthèses", "#e879a8"),
    "racine": ("Pages", "#e5e7eb"), "competences": ("Compétences", "#60a5fa"),
    "outils": ("Outils", "#ec4899"),
}

PONT = None                # le lien avec le vrai Jarvis, quand le serveur tourne dans Jarvis


def _simple(texte: str) -> str:
    texte = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in texte if unicodedata.category(c) != "Mn").replace(" ", "-")


def _sans_entete(texte: str) -> str:
    if texte.startswith("---"):
        fin = texte.find("\n---", 3)
        if fin != -1:
            return texte[fin + 4:].lstrip()
    return texte


def _lisible(texte: str) -> str:
    return re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), texte)


def _description_competence(dossier: Path) -> str:
    try:
        m = re.search(r"^description:\s*(.+)$", (dossier / "SKILL.md").read_text(encoding="utf-8", errors="ignore")[:3000], re.M)
        return m.group(1).strip(" \"'")[:MAX_EXTRAIT] if m else ""
    except OSError:
        return ""


def _doc_python(fichier: Path) -> str:
    try:
        m = re.search(r'"""(.*?)"""', fichier.read_text(encoding="utf-8", errors="ignore")[:3000], re.S)
        return " ".join(m.group(1).split())[:MAX_EXTRAIT] if m else ""
    except OSError:
        return ""


def _elements_en_plus() -> list[tuple[str, str, str]]:
    """Les compétences de Claude et les outils de Jarvis, pour que la galaxie montre tout ce qu'il sait faire."""
    elements = []
    if COMPETENCES.is_dir():
        for d in sorted(COMPETENCES.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                elements.append((d.name, "competences", _description_competence(d)))
    for dossier in (PLUGINS, OUTILS):
        if dossier.is_dir():
            for f in sorted(dossier.glob("*.py")):
                if not f.name.startswith("_"):
                    elements.append((f.stem, "outils", _doc_python(f)))
    return elements


def construire_graphe(dossier: Path = WIKI, extras: bool = False) -> dict:
    """Une étoile par page, un trait par lien [[page]]. Les liens vers une page qui n'existe pas sont ignorés.
    Avec extras : aussi les compétences et les outils, reliés à une étoile centrale de leur catégorie."""
    pages = sorted(p for p in Path(dossier).rglob("*.md") if not any(x.startswith(".") for x in p.parts))
    noeuds, par_nom, textes = [], {}, []
    for page in pages:
        rel = page.relative_to(dossier)
        try:
            texte = page.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        groupe = rel.parts[0] if len(rel.parts) > 1 and rel.parts[0] in GROUPES else "racine"
        corps = _sans_entete(texte)
        noeuds.append({"id": len(noeuds), "chemin": rel.as_posix(), "nom": page.stem, "groupe": groupe,
                       "extrait": _lisible(corps)[:MAX_EXTRAIT], "liens": 0})
        par_nom.setdefault(_simple(page.stem), noeuds[-1]["id"])
        textes.append(corps)
    deja = set()

    def relier(a: int, b: int):
        paire = (min(a, b), max(a, b))
        if a != b and paire not in deja:
            deja.add(paire)
            noeuds[a]["liens"] += 1
            noeuds[b]["liens"] += 1

    for n, corps in zip(noeuds, textes):
        for cible in re.findall(r"\[\[([^\]|#]+)", corps):
            autre = par_nom.get(_simple(cible.strip().split("/")[-1]))
            if autre is not None:
                relier(n["id"], autre)
    if extras:
        centres = {}
        for nom, groupe, description in _elements_en_plus():
            if groupe not in centres:
                noeuds.append({"id": len(noeuds), "chemin": "", "nom": GROUPES[groupe][0], "groupe": groupe,
                               "extrait": f"Tout ce qui se trouve dans : {GROUPES[groupe][0]}.", "liens": 0})
                centres[groupe] = noeuds[-1]["id"]
                if "index" in par_nom:
                    relier(par_nom["index"], centres[groupe])
            noeuds.append({"id": len(noeuds), "chemin": "", "nom": nom, "groupe": groupe, "extrait": description, "liens": 0})
            relier(noeuds[-1]["id"], centres[groupe])
            # Une page du wiki qui porte le même nom : on les relie.
            page = par_nom.get(_simple(nom))
            if page is not None:
                relier(noeuds[-1]["id"], page)
    return {"noeuds": noeuds, "traits": [{"a": a, "b": b} for a, b in sorted(deja)],
            "groupes": {k: {"nom": v[0], "couleur": v[1]} for k, v in GROUPES.items()}}


def lire_note(chemin: str, dossier: Path = WIKI) -> str | None:
    """Rend le texte d'une note du wiki, et rien d'autre : le chemin doit désigner un .md existant DANS le wiki."""
    if not chemin or not chemin.endswith(".md"):
        return None
    base = Path(dossier).resolve()
    cible = (base / chemin).resolve()
    if base not in cible.parents or not cible.is_file():
        return None
    return _lisible(_sans_entete(cible.read_text(encoding="utf-8")))


def hote_autorise(hote: str | None, origine: str | None = None) -> bool:
    """Une page Internet ne doit pas pouvoir parler à ce serveur : seules les adresses locales de ce port passent."""
    permis = {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}
    if (hote or "") not in permis:
        return False
    if origine and urlparse(origine).netloc not in permis:
        return False
    return True


MAX_VOIX = 16000 * 2 * 15       # 15 secondes au micro de la télé
_histoire: list[dict] = []
_verrou = threading.Lock()


def repondre_question(question: str) -> dict:
    """Pose la question au cerveau local (quand Jarvis n'est pas lancé). Lève ValueError si impossible."""
    from core import cerveau_local
    from plugins._cerveau_commun import WIKI as wiki_commun, chercher
    question = (question or "").strip()[:MAX_QUESTION]
    if not question:
        raise ValueError("Écris d'abord une question.")
    ok, detail = cerveau_local.pret()
    if not ok:
        raise ValueError(detail)
    debut = time.time()
    with _verrou:
        reponse = cerveau_local.repondre(question, _histoire, lambda _phrase: None)
    sources = [p.relative_to(wiki_commun).as_posix() for _s, p, _t in chercher(question, 2)]
    return {"reponse": reponse, "sources": sources, "secondes": round(time.time() - debut, 1), "modele": detail}


def etat() -> dict:
    from core import cerveau_local
    ok, detail = cerveau_local.pret(lancer=False)
    return {"pret": ok, "detail": detail, "modele": cerveau_local.modele()}


class Page(BaseHTTPRequestHandler):
    server_version = "Galaxie"
    sys_version = ""

    def log_message(self, *_):
        pass

    def _envoyer(self, code: int, corps: bytes, genre: str):
        self.send_response(code)
        self.send_header("Content-Type", genre)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(corps)

    def _json(self, code: int, objet):
        self._envoyer(code, json.dumps(objet, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _permis(self) -> bool:
        if hote_autorise(self.headers.get("Host"), self.headers.get("Origin")):
            return True
        self._json(403, {"erreur": "Refusé."})
        return False

    def do_GET(self):
        if not self._permis():
            return
        url = urlparse(self.path)
        if url.path == "/":
            self._envoyer(200, (ICI / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/tableau":
            self._envoyer(200, (ICI / "tableau.html").read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/tableau":
            from galaxie import tableau
            self._json(200, tableau.donnees_tableau(WIKI))
        elif url.path == "/api/lire":
            from galaxie import cerveau_carte
            texte = cerveau_carte.lire_element(parse_qs(url.query).get("cle", [""])[0])
            self._json(200, {"texte": texte}) if texte is not None else self._json(404, {"erreur": "Fichier introuvable."})
        elif url.path == "/api/graphe":
            self._json(200, construire_graphe(extras=True))
        elif url.path == "/api/etat":
            self._json(200, etat())
        elif url.path == "/api/jarvis":
            if PONT is None:
                self._json(200, {"branche": False})
                return
            try:
                depuis = int(parse_qs(url.query).get("depuis", ["0"])[0])
            except ValueError:
                depuis = 0
            self._json(200, PONT.photo(depuis))
        elif url.path == "/api/jarvis/son":
            if PONT is None:
                self._json(409, {"erreur": "Jarvis n'est pas lancé."})
                return
            morceau = PONT.son_tele()
            if morceau is None:
                self.send_response(204)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(morceau[1])))
            self.send_header("X-Taux", str(morceau[0]))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(morceau[1])
        elif url.path == "/api/google/etat":
            try:
                from core import google_compte
            except ImportError:                  # Google n'est pas dans cette version : la case est cachée
                self._json(200, {"etat": "absent"})
                return
            self._json(200, google_compte.etat())
        elif url.path == "/api/note":
            texte = lire_note(parse_qs(url.query).get("chemin", [""])[0])
            self._json(200, {"texte": texte}) if texte is not None else self._json(404, {"erreur": "Note introuvable."})
        else:
            self._json(404, {"erreur": "Introuvable."})

    def _voix(self):
        taille = int(self.headers.get("Content-Length") or 0)
        donnees = self.rfile.read(min(taille, MAX_VOIX * 2))
        if self.headers.get("Content-Type") != "application/octet-stream":
            self._json(415, {"erreur": "Refusé."})
        elif taille > MAX_VOIX:
            self._json(413, {"erreur": "Phrase trop longue."})
        elif PONT is None:
            self._json(409, {"erreur": "Jarvis n'est pas lancé."})
        else:
            self._json(200, {"texte": PONT.voix_tele(donnees)})

    def _corps(self) -> dict:
        taille = min(int(self.headers.get("Content-Length") or 0), 20000)
        donnees = json.loads(self.rfile.read(taille) or b"{}")
        return donnees if isinstance(donnees, dict) else {}

    def do_POST(self):
        if not self._permis():
            return
        if self.path == "/api/arreter":
            if PONT is not None:
                self._json(409, {"erreur": "Jarvis utilise ce serveur."})
                return
            self._json(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        try:
            if self.path == "/api/jarvis/voix":
                self._voix()
                return
            d = self._corps()
            if self.path == "/api/google/connecter":
                from core import google_compte
                google_compte.connecter(ouvrir_adresse)
                self._json(200, {"ok": True})
            elif self.path == "/api/google/deconnecter":
                from core import google_compte
                google_compte.deconnecter()
                self._json(200, {"ok": True})
            elif self.path == "/api/question":
                self._json(200, repondre_question(str(d.get("question", ""))))
            elif PONT is None:
                self._json(409, {"erreur": "Jarvis n'est pas lancé."})
            elif self.path == "/api/jarvis/commande":
                PONT.commande(str(d.get("texte", "")))
                self._json(200, {"ok": True})
            elif self.path == "/api/jarvis/cerveau":
                self._json(200, {"message": PONT.changer_cerveau(str(d.get("cerveau", "")))})
            elif self.path == "/api/jarvis/confirmer":
                PONT.confirmer(d.get("accepte") is True)
                self._json(200, {"ok": True})
            elif self.path == "/api/jarvis/muet":
                PONT.muet(d.get("muet") is True)
                self._json(200, {"ok": True})
            elif self.path == "/api/jarvis/couper":
                PONT.couper()
                self._json(200, {"ok": True})
            elif self.path == "/api/jarvis/hologramme":
                PONT.hologramme()
                self._json(200, {"ok": True})
            else:
                self._json(404, {"erreur": "Introuvable."})
        except ValueError as e:
            self._json(400, {"erreur": str(e)})
        except RuntimeError as e:               # messages de connexion Google, écrits pour l'utilisateur
            self._json(409, {"erreur": str(e)})
        except Exception as e:
            print("[Galaxie]", type(e).__name__, file=sys.stderr)
            self._json(503, {"erreur": "Jarvis n'a pas pu le faire."})


def arreter_ancien() -> None:
    """Remplace un ancien serveur seul encore ouvert, pour ne jamais servir une vieille version."""
    try:
        q = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/arreter", data=b"", method="POST")
        urllib.request.urlopen(q, timeout=1).read()
        time.sleep(0.6)
    except OSError:
        pass


def jarvis_deja_la() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/jarvis", timeout=1) as r:
            return bool(json.load(r).get("branche"))
    except (OSError, ValueError):
        return False


def arguments_chrome() -> str:
    profil = ICI / ".fenetre-chrome"            # profil à part : la fenêtre ne se mélange pas à ton Chrome
    return f'--app={ADRESSE} "--user-data-dir={profil}" --no-first-run --start-maximized'


def ouvrir_fenetre() -> bool:
    """Ouvre la page dans sa propre fenêtre, sans barre d'adresse.
    Pas de subprocess.Popen : main.py le force sans fenêtre (CREATE_NO_WINDOW) et Chrome ne s'afficherait pas.
    Pas de raccourci non plus : Windows affichait un avertissement de sécurité à chaque ouverture (04/11)."""
    if not CHROME.exists():
        webbrowser.open(ADRESSE)
        return False
    code = ctypes.windll.shell32.ShellExecuteW(None, "open", str(CHROME), arguments_chrome(), None, 3)  # 3 = agrandie
    if code <= 32:
        raise OSError(f"Windows n'a pas lancé Chrome (code {code})")
    return True


def ouvrir_adresse(adresse: str) -> None:
    """Ouvre une page dans le navigateur habituel : la connexion Google doit se faire là où tu es connecté."""
    if ctypes.windll.shell32.ShellExecuteW(None, "open", adresse, None, None, 1) <= 32:
        raise OSError("Windows n'a pas ouvert le navigateur")
    from galaxie import placement
    threading.Thread(target=placement.amener_devant, daemon=True, name="connexion-devant").start()


def demarrer_dans_jarvis(pont) -> bool:
    """Lance le serveur dans Jarvis. Rend faux si le port est pris : Jarvis continue quand même de marcher."""
    global PONT
    arreter_ancien()
    try:
        serveur = ThreadingHTTPServer(("127.0.0.1", PORT), Page)
    except OSError as e:
        print("[Galaxie] port occupé :", e, file=sys.stderr)
        return False
    PONT = pont
    threading.Thread(target=serveur.serve_forever, daemon=True, name="galaxie").start()
    return True


def main():
    if jarvis_deja_la():                        # Jarvis tourne : on ouvre seulement sa fenêtre
        if "--ouvrir" in sys.argv:
            ouvrir_fenetre()
        return
    arreter_ancien()
    serveur = ThreadingHTTPServer(("127.0.0.1", PORT), Page)
    if "--ouvrir" in sys.argv:
        threading.Timer(0.3, ouvrir_fenetre).start()
    serveur.serve_forever()


if __name__ == "__main__":
    main()
