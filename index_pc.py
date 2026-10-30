# -*- coding: utf-8 -*-
"""
Indexeur du PC pour JARVIS (Mark-LV).

Construit memory/pc_index.json avec trois listes :
  - apps    : applications (raccourcis du menu Démarrer + fichiers .exe)
  - folders : dossiers utiles (utilisateur, racines des disques)
  - files   : fichiers courants (documents, images, etc.)

Relance-le quand tu veux rafraîchir l'index :
    .venv\\Scripts\\python.exe index_pc.py
"""
import json
import os
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
INDEX_PATH = BASE / "memory" / "pc_index.json"
USER = Path.home()

# Dossiers à ne pas parcourir (gain de temps, évite les poubelles/venv/caches)
_SKIP = {
    "node_modules", ".git", "__pycache__", "$recycle.bin", "system volume information",
    "windows", "programdata", "appdata", ".venv", "venv", "site-packages", "dist-info",
    "ms-playwright", ".cache", ".dsh", "windowsapps", "modifiablewindowsapps",
    "win32", "lib", "scripts", "include", "pysqlite2", "pythonwin", "isapi", "adodbapi",
    "common files", "internet explorer", "windows defender", "windows nt", "windows mail",
    "windows media player", "windows photo viewer", "windowspowershell", "dotnet", "intel",
    "nvidia corporation", "microsoft gameinput", "riotservice", ".idea", ".vscode",
    ".git", ".svn", "temp", "tmp", "logs",
}

# Extensions de fichiers utiles à référencer
_FILE_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md",
    ".csv", ".json", ".xml", ".py", ".js", ".html", ".htm", ".mp3", ".wav", ".flac",
    ".mp4", ".mkv", ".avi", ".mov", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
    ".zip", ".rar", ".7z", ".exe", ".msi", ".iso", ".torrent",
}

_MAX_APPS = 4000
_MAX_FOLDERS = 2500
_MAX_FILES = 8000


def _is_skip(name: str) -> bool:
    n = name.lower()
    return n in _SKIP or n.startswith(".") or n.startswith("$")


def _add(collection, seen, name, path, limit):
    if len(collection) >= limit:
        return
    key = str(path).lower()
    if key in seen:
        return
    seen.add(key)
    collection.append({"name": name, "path": str(path)})


def _scan_exes(root: Path, apps, seen, maxdepth, limit):
    stack = [(root, 0)]
    while stack and len(apps) < limit:
        d, depth = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if depth < maxdepth and not _is_skip(e.name):
                        stack.append((Path(e.path), depth + 1))
                elif e.name.lower().endswith(".exe"):
                    _add(apps, seen, Path(e.path).stem, e.path, limit)
            except OSError:
                continue


def collect_apps(apps, seen):
    # 1) Raccourcis du menu Démarrer (les plus fiables : nom + lanceur)
    start_menus = [
        Path(os.environ.get("ProgramData", "")) / "Microsoft/Windows/Start Menu/Programs",
        USER / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs",
    ]
    for sm in start_menus:
        if not sm.exists():
            continue
        for lnk in sm.rglob("*.lnk"):
            name = lnk.stem
            low = name.lower()
            if low in {"uninstall", "desinstaller", "desinstall", "readme", "license", "help", "website"}:
                continue
            _add(apps, seen, name, lnk, _MAX_APPS)

    # 2) .exe de Program Files et de AppData\Local\Programs
    for root in [
        Path("C:/Program Files"),
        Path("C:/Program Files (x86)"),
        USER / "AppData/Local/Programs",
    ]:
        if root.exists():
            _scan_exes(root, apps, seen, maxdepth=3, limit=_MAX_APPS)

    # 3) .exe du disque D: (jeux, etc.)
    d = Path("D:/")
    if d.exists():
        _scan_exes(d, apps, seen, maxdepth=4, limit=_MAX_APPS)

    # 4) .exe directement à la racine du profil (rare mais possible)
    for child in USER.iterdir():
        try:
            if child.is_file() and child.name.lower().endswith(".exe"):
                _add(apps, seen, child.stem, child, _MAX_APPS)
        except OSError:
            continue


def collect_folders(folders, seen):
    # Dossiers racine des disques
    for drv in ["C:/", "D:/"]:
        p = Path(drv)
        if not p.exists():
            continue
        for child in p.iterdir():
            try:
                if child.is_dir() and not _is_skip(child.name):
                    _add(folders, seen, child.name, child, _MAX_FOLDERS)
            except OSError:
                continue

    # Dossiers du profil utilisateur (niveau 1)
    for child in USER.iterdir():
        try:
            if child.is_dir() and not _is_skip(child.name):
                _add(folders, seen, child.name, child, _MAX_FOLDERS)
        except OSError:
            continue

    # Sous-dossiers importants (niveau 2) : Desktop, Documents, Downloads, Pictures, Videos, Music
    for root in [
        USER / "Desktop", USER / "Documents", USER / "Downloads",
        USER / "Pictures", USER / "Videos", USER / "Music", USER / "OneDrive",
    ]:
        if not root.exists():
            continue
        for child in root.iterdir():
            try:
                if child.is_dir() and not _is_skip(child.name):
                    _add(folders, seen, child.name, child, _MAX_FOLDERS)
            except OSError:
                continue


def collect_files(files, seen):
    roots = [
        USER / "Desktop", USER / "Documents", USER / "Downloads",
        USER / "Pictures", USER / "Videos", USER / "Music",
    ]
    for root in roots:
        if not root.exists():
            continue
        stack = [(root, 0)]
        while stack and len(files) < _MAX_FILES:
            d, depth = stack.pop()
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if depth < 3 and not _is_skip(e.name):
                            stack.append((Path(e.path), depth + 1))
                    elif e.is_file(follow_symlinks=False):
                        ext = Path(e.path).suffix.lower()
                        if ext in _FILE_EXTS:
                            _add(files, seen, Path(e.path).stem, e.path, _MAX_FILES)
                except OSError:
                    continue


# Alias français/anglais pour les dossiers standards de l'utilisateur
_FOLDER_ALIASES = {
    "pictures":   ["photos", "images", "mes images"],
    "music":      ["musique", "ma musique"],
    "videos":     ["vidéos", "videos", "films", "mes vidéos"],
    "downloads":  ["téléchargements", "telechargements"],
    "desktop":    ["bureau"],
    "documents":  ["mes documents"],
    "onedrive":   ["one drive"],
}


def _add_folder_aliases(folders, seen):
    """Ajoute des entrées alias (noms français) pointant vers les mêmes dossiers."""
    extra = []
    for f in folders:
        base = f["name"].lower().strip()
        for key, aliases in _FOLDER_ALIASES.items():
            if base == key or base.endswith("/" + key) or base == key:
                for alias in aliases:
                    entry = {"name": alias, "path": f["path"]}
                    k = (alias + f["path"]).lower()
                    if k not in seen:
                        seen.add(k)
                        extra.append(entry)
                break
    folders.extend(extra)


def main():
    apps, folders, files = [], [], []
    seen_apps, seen_folders, seen_files = set(), set(), set()
    t0 = time.time()

    print("[index] Analyse des applications...")
    collect_apps(apps, seen_apps)
    print(f"[index]   apps    : {len(apps)}")

    print("[index] Analyse des dossiers...")
    collect_folders(folders, seen_folders)
    _add_folder_aliases(folders, seen_folders)
    print(f"[index]   folders : {len(folders)}")

    print("[index] Analyse des fichiers...")
    collect_files(files, seen_files)
    print(f"[index]   files   : {len(files)}")

    index = {
        "apps": apps,
        "folders": folders,
        "files": files,
        "built": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    size_kb = INDEX_PATH.stat().st_size / 1024
    print(f"[index] Index écrit : {INDEX_PATH} ({size_kb:.0f} Ko) en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
