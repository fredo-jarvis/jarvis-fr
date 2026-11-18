"""
core/apps_linux.py — applications Linux à partir des fichiers .desktop (freedesktop).

Sert à l'indexation (index_pc.py) et au lancement (actions/open_app.py, actions/open_anything.py).
Aucune dépendance : les .desktop sont lus avec configparser, le lancement passe par `gio launch`
(fourni avec GNOME) qui gère Flatpak, Snap et les arguments %U/%F comme le menu des applications.
"""
from __future__ import annotations

import configparser
import os
import shlex
import shutil
import subprocess
import unicodedata
from pathlib import Path


def _dossiers() -> list[Path]:
    home = Path.home()
    data_home = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    data_dirs = (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    racines = [data_home, *map(Path, data_dirs), Path("/var/lib/flatpak/exports/share"),
               home / ".local/share/flatpak/exports/share", Path("/var/lib/snapd/desktop")]
    vus, res = set(), []
    for r in racines:
        d = r / "applications"
        if str(d) not in vus and d.is_dir():
            vus.add(str(d))
            res.append(d)
    return res


def _lire(chemin: Path) -> dict | None:
    cp = configparser.RawConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    try:
        cp.read(chemin, encoding="utf-8")
        e = cp["Desktop Entry"]
    except Exception:
        return None
    if e.get("Type") != "Application" or e.get("NoDisplay", "").lower() == "true" \
            or e.get("Hidden", "").lower() == "true" or not e.get("Name"):
        return None
    noms = list(dict.fromkeys(n for n in (e["Name"], e.get("Name[fr]")) if n))
    generiques = list(dict.fromkeys(n for n in (e.get("GenericName[fr]"), e.get("GenericName")) if n))
    return {"id": chemin.stem, "path": str(chemin), "names": noms, "generic": generiques,
            "exec": e.get("Exec", ""), "keywords": e.get("Keywords[fr]", e.get("Keywords", ""))}


def lister() -> list[dict]:
    """Applications visibles, la première occurrence d'un identifiant l'emporte (ordre XDG)."""
    vus, res = set(), []
    for d in _dossiers():
        for f in sorted(d.rglob("*.desktop")):
            ident = f.stem
            if ident in vus:
                continue
            app = _lire(f)
            if app:
                vus.add(ident)
                res.append(app)
    return res


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    for c in "-_.()[]":
        t = t.replace(c, " ")
    return " ".join(t.split())


def trouver(nom: str, apps: list[dict] | None = None) -> dict | None:
    """Application dont le nom, l'identifiant ou la commande correspond exactement (sans accent ni casse).

    Les noms génériques (« Navigateur Web », « Text Editor ») ne servent que s'ils désignent une seule application."""
    q = _norm(nom)
    if not q:
        return None
    apps = apps if apps is not None else lister()
    for app in apps:
        binaire = _norm(Path(shlex.split(app["exec"])[0]).name) if app["exec"].strip() else ""
        cles = [_norm(n) for n in app["names"]] + [_norm(app["id"].split(".")[-1]), _norm(app["id"]), binaire]
        if q in cles:
            return app
    generiques = [a for a in apps if q in [_norm(g) for g in a["generic"]]]
    return generiques[0] if len(generiques) == 1 else None


def lancer_desktop(chemin: str) -> bool:
    """Lance un .desktop comme le ferait le menu ; vrai si `gio launch` accepte la commande."""
    gio = shutil.which("gio")
    if not gio:
        return False
    # `gio launch` reste en vie tant que l'application tourne : s'il n'a pas échoué après quelques
    # secondes, l'application est lancée.
    try:
        p = subprocess.Popen([gio, "launch", chemin], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        try:
            return p.wait(timeout=3) == 0
        except subprocess.TimeoutExpired:
            return True
    except Exception:
        return False


def ouvrir(chemin: str) -> None:
    """Équivalent de os.startfile : .desktop → lanceur, sinon fichier/dossier → application par défaut."""
    if chemin.endswith(".desktop"):
        if lancer_desktop(chemin):
            return
        raise RuntimeError(f"échec du lancement de {chemin}")
    opener = shutil.which("xdg-open")
    if not opener:
        raise RuntimeError("xdg-open introuvable")
    subprocess.Popen([opener, chemin], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
