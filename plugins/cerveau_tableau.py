r"""
Plugin : le tableau de bord du cerveau, http://localhost:4719/tableau (07/11/2026, code dans galaxie\tableau.*).

    « Jarvis, montre-moi le tableau de bord »     « Jarvis, ouvre le tableau du cerveau »

Une page qui MONTRE sans rien garder : le cerveau en anneaux (un point par page), aujourd'hui, les 14 prochains
jours, ce qui t'attend, tes promesses, les dernières séances. Tout est relu dans le wiki.
"""
import ctypes
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SERVEUR = RACINE / "galaxie" / "server.py"
ADRESSE = "http://localhost:4719/tableau"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
CREATE_NO_WINDOW = 0x08000000

PLUGIN = {
    "name": "cerveau_tableau",
    "description": (
        "Opens the user's brain DASHBOARD (localhost:4719/tableau): the brain as rings (one dot per wiki page), today, "
        "the next 14 days, what is waiting for the user, their promises, the last sessions, brain health. Use for "
        "'montre-moi le tableau de bord', 'ouvre le tableau du cerveau', 'mon tableau de bord', 'qu'est-ce qui "
        "m'attend sur le tableau'. Different from cerveau_galaxie (3D stars). After calling it, say in one short "
        "sentence that the dashboard is on screen."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
}


def _serveur_la() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:4719/api/etat", timeout=1):
            return True
    except OSError:
        return False


def run(parameters: dict, player=None, session_memory=None) -> str:
    if not _serveur_la():
        if not SERVEUR.exists():
            return f"The dashboard is missing: {SERVEUR} not found."
        exe = Path(sys.executable)
        pw = exe.with_name("pythonw.exe")
        subprocess.Popen([str(pw if pw.exists() else exe), str(SERVEUR)], creationflags=CREATE_NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20):
            time.sleep(0.25)
            if _serveur_la():
                break
    if CHROME.exists():
        profil = RACINE / "galaxie" / ".fenetre-chrome"
        args = f'--app={ADRESSE} "--user-data-dir={profil}" --no-first-run --start-maximized'
        if ctypes.windll.shell32.ShellExecuteW(None, "open", str(CHROME), args, None, 3) > 32:
            return "Brain dashboard opened on screen."
    import webbrowser
    webbrowser.open(ADRESSE)
    return "Brain dashboard opened in the browser."
