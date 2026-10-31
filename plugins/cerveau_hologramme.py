"""
Plugin : le cerveau en hologramme (version 1.1), avec HOLO de Zubair Trabzada
(zubair-trabzada/holo-gestures, licence MIT), passé aux couleurs bleues de Jarvis FR.

    « Jarvis, montre-moi le cerveau en hologramme »     « Jarvis, ouvre l'hologramme »
    « Jarvis, ferme l'hologramme »

Les dossiers du cerveau deviennent des bulles lumineuses, les pages des cartes. Avec une webcam,
on les manipule avec la main (pincer pour ouvrir, lancer, écarter deux mains pour zoomer) ;
sans webcam, tout se fait à la souris. HOLO tourne seulement sur ce PC (petit serveur local,
port 4890), ne fait que LIRE le cerveau, et les images de la caméra ne quittent jamais la page.
"""
import json
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from plugins._cerveau_commun import WIKI

HOLO = Path(__file__).resolve().parent.parent / "holo"
PORT = 4890
ADRESSE = f"http://localhost:{PORT}/"
CREATE_NO_WINDOW = 0x08000000

PLUGIN = {
    "name": "cerveau_hologramme",
    "description": (
        "Opens (or closes) the user's second brain as a 3D HOLOGRAM on screen: brain folders "
        "become glowing orbs, notes become cards. With a webcam the user moves them with hand "
        "gestures; without one, with the mouse. Use for 'montre-moi le cerveau en hologramme', "
        "'ouvre l'hologramme', 'affiche le cerveau en 3D', 'hologramme du cerveau', "
        "'ferme l'hologramme'. After calling it, say in one short sentence that the hologram "
        "is on screen and how to use it (hand or mouse)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "open | close"},
        },
        "required": [],
    },
}


def _serveur_actif() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
            return True
    except OSError:
        return False


def _python_sans_fenetre() -> str:
    exe = Path(sys.executable)
    pw = exe.with_name("pythonw.exe")
    return str(pw if pw.exists() else exe)


def _demarrer_serveur() -> bool:
    if _serveur_actif():
        return True
    # HOLO lit le dossier wiki du cerveau de l'utilisateur (même réglage que Jarvis)
    try:
        (HOLO / "holo.json").write_text(json.dumps({"folder": WIKI.as_posix()}), encoding="utf-8")
    except Exception:
        pass
    subprocess.Popen([_python_sans_fenetre(), str(HOLO / "server.py")], cwd=str(HOLO),
                     creationflags=CREATE_NO_WINDOW,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(25):
        if _serveur_actif():
            return True
        time.sleep(0.2)
    return False


def _arreter_serveur() -> None:
    # le seul programme qui écoute sur 4890 est le serveur HOLO lancé par ce plugin
    sortie = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                            encoding="oem", errors="ignore", creationflags=CREATE_NO_WINDOW).stdout or ""
    for ligne in sortie.splitlines():
        morceaux = ligne.split()
        if len(morceaux) >= 5 and morceaux[1].endswith(f":{PORT}") and morceaux[3] == "LISTENING":
            subprocess.run(["taskkill", "/PID", morceaux[4], "/F"], capture_output=True,
                           creationflags=CREATE_NO_WINDOW)


def _navigateur() -> str | None:
    """Chrome ou Edge en mode « application » (sans barre d'adresse), sinon le navigateur par défaut."""
    for chemin in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                   r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"):
        if Path(chemin).exists():
            return chemin
    return shutil.which("chrome") or shutil.which("msedge")


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = (parameters.get("action") or "open").strip().lower()
    if action in ("close", "ferme", "fermer", "stop"):
        _arreter_serveur()
        return "Hologram closed. The user can close the browser window."
    if not (HOLO / "server.py").exists():
        return f"HOLO is missing: {HOLO} not found. Re-run the installation line to repair Jarvis."
    if not _demarrer_serveur():
        return "The hologram server did not start (port 4890)."
    nav = _navigateur()
    if nav:
        subprocess.Popen([nav, f"--app={ADRESSE}", "--start-maximized"])
    else:
        webbrowser.open(ADRESSE)
    return ("Brain hologram opened on screen. With a webcam: pinch an orb to open it, throw cards, "
            "spread two hands to zoom. Without a webcam: click an orb, drag cards with the mouse, "
            "click a card to read it, press R to tidy up.")
