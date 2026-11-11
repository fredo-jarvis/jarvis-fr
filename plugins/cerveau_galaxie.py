r"""
Plugin : la galaxie du cerveau, http://localhost:4719 (refait le 04/11/2026, code dans galaxie\).

    « Jarvis, montre-moi la galaxie du cerveau »     « Jarvis, ferme la galaxie »

Chaque page du cerveau devient une étoile en 3D, reliée à celles qu'elle cite. Tout reste sur ce PC,
la page ne charge rien depuis Internet et ne fait que lire le wiki.
"""
import subprocess
import sys
from pathlib import Path

SERVEUR = Path(__file__).resolve().parent.parent / "galaxie" / "server.py"
PORT = 4719
CREATE_NO_WINDOW = 0x08000000

PLUGIN = {
    "name": "cerveau_galaxie",
    "description": (
        "Opens (or closes) the user's second brain as a 3D GALAXY in a local page (localhost:4719): every brain page is a "
        "star linked to the pages it mentions, with search, filters, an inspector and a box to ask the local brain. Use "
        "for 'montre-moi la galaxie du cerveau', 'ouvre la galaxie', 'carte du cerveau', 'mon cerveau en étoiles', "
        "'ferme la galaxie'. Different from cerveau_hologramme (the orbs). After calling it, say in one short sentence "
        "that the galaxy is on screen."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "open | close"}},
        "required": [],
    },
}


def _python_sans_fenetre() -> str:
    exe = Path(sys.executable)
    pw = exe.with_name("pythonw.exe")
    return str(pw if pw.exists() else exe)


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = (parameters.get("action") or "open").strip().lower()
    if action in ("close", "ferme", "fermer", "stop"):
        return "The galaxy is Jarvis' main interface, so it stays open. The user can close its window if they want."
    if not SERVEUR.exists():
        return f"The galaxy is missing: {SERVEUR} not found."
    subprocess.Popen([_python_sans_fenetre(), str(SERVEUR), "--ouvrir"], creationflags=CREATE_NO_WINDOW,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "Brain galaxy opened on localhost:4719."
