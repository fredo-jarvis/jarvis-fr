# -*- coding: utf-8 -*-
"""
Ouvre n'importe quoi sur le PC à partir de son nom : application, dossier ou
fichier. S'appuie sur l'index memory/pc_index.json (construit par index_pc.py).

Action auto-découverte par core.action_loader (comme les autres actions).
"""
import difflib
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INDEX_PATH = BASE / "memory" / "pc_index.json"

_cache = None


def _load_index():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            _cache = {"apps": [], "folders": [], "files": []}
    return _cache


import time
import unicodedata

def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    for ch in "-_.()[]":
        t = t.replace(ch, " ")
    return " ".join(t.split())


def _stem(t: str) -> str:
    """nom sans extension (ex. 'rapport.pdf' -> 'rapport')"""
    base, ext = os.path.splitext(t)
    return base if ext and len(ext) <= 5 else t


# ── Dossier courant (ajout Claude) : le dernier dossier ouvert, pour chercher DEDANS
STATE = BASE / "memory" / "dernier_dossier.json"
_SKIP = {".venv", ".venv2", "venv", "node_modules", "__pycache__", ".git", "appdata",
         "$recycle.bin", "system volume information", "windows", ".pipcache", "site-packages"}


def _get_last() -> str:
    try:
        p = json.loads(STATE.read_text(encoding="utf-8")).get("dossier", "")
        return p if p and os.path.isdir(p) else ""
    except Exception:
        return ""


def _set_last(path: str) -> None:
    try:
        d = path if os.path.isdir(path) else os.path.dirname(path)
        STATE.write_text(json.dumps({"dossier": d}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _roots() -> list:
    home = Path.home()
    out = []
    try:
        from actions.file_controller import _get_desktop, _get_documents, _get_downloads
        out += [Path(_get_desktop()), Path(_get_documents()), Path(_get_downloads())]
    except Exception:
        out += [home / "Desktop", home / "Documents", home / "Downloads"]
    out += [home / "Pictures", home / "Videos", home / "Music", Path("D:/téléchargement"), Path("D:/")]
    seen, res = set(), []
    for r in out:
        k = str(r).lower()
        if k not in seen and r.exists():
            seen.add(k); res.append(r)
    return res


def _walk(root, max_depth: int, deadline: float):
    """Parcourt dossiers + fichiers (profondeur limitee, temps limite)."""
    root = str(root)
    base_depth = root.rstrip("\\/").count(os.sep)
    for cur, dirs, files in os.walk(root):
        if time.monotonic() > deadline:
            return
        depth = cur.count(os.sep) - base_depth
        dirs[:] = [d for d in dirs if d.lower() not in _SKIP and not d.startswith(".")]
        if depth >= max_depth:
            dirs[:] = []
        for d in dirs:
            yield ("folders", d, os.path.join(cur, d))
        for f in files:
            yield ("files", f, os.path.join(cur, f))


def _live_search(name: str, roots, max_depth: int, seconds: float):
    best, best_s, deadline = None, 0, time.monotonic() + seconds
    for r in roots:
        for cat, nm, path in _walk(r, max_depth, deadline):
            sc = max(_score(name, nm), _score(name, _stem(nm)))
            if cat == "folders":
                sc += 1  # a egalite, on prefere le dossier
            if sc > best_s:
                best_s, best = sc, (cat, {"name": nm, "path": path})
                if sc >= 101:
                    return best, best_s
    return best, best_s


# ── Index COMPLET du PC, construit en arriere-plan au demarrage (ajout Claude) ──
import threading
_FULL = []            # (nom_normalise, categorie, nom, chemin)
_FULL_READY = threading.Event()
FAIL_LOG = BASE / "memory" / "echecs_ouverture.log"


def _drives() -> list:
    out = [Path.home()]
    for letter in "DEFGH":
        p = Path(f"{letter}:/")
        try:
            if p.exists():
                out.append(p)
        except Exception:
            pass
    return out


def _build_full_index() -> None:
    items = []
    try:
        for root in _drives():
            for cat, nm, path in _walk(root, 12, time.monotonic() + 240):
                items.append((_norm(_stem(nm)), cat, nm, path))
                if len(items) > 600000:
                    break
    except Exception:
        pass
    _FULL[:] = items
    _FULL_READY.set()
    print(f"[open_anything] index complet : {len(items)} dossiers/fichiers")


def _start_indexer() -> None:
    def loop():
        while True:
            _build_full_index()
            time.sleep(3600)          # remis a jour toutes les heures
    threading.Thread(target=loop, daemon=True, name="pc-indexer").start()


def _full_search(name: str):
    q = _norm(_stem(name))
    if not q or not _FULL:
        return None, 0
    words = q.split()
    best, best_s = None, 0
    for n, cat, nm, path in _FULL:
        if n == q:
            sc = 100
        elif q in n or all(w in n for w in words):
            sc = 80 - min(15, len(n) - len(q)) // 3
        elif n[:3] == q[:3] or any(w in n for w in words if len(w) > 3):
            sc = _score(q, n)
        else:
            continue
        if cat == "folders":
            sc += 1
        if sc > best_s:
            best_s, best = sc, (cat, {"name": nm, "path": path})
    return best, best_s


def _clean_request(name: str) -> tuple:
    """'le dossier Mark-LV' -> ('Mark-LV', 'folders')"""
    want = None
    t = name.strip()
    low = _norm(t)
    for mot, cat in (("dossier", "folders"), ("repertoire", "folders"), ("fichier", "files"),
                     ("document", "files"), ("application", "apps"), ("logiciel", "apps"),
                     ("programme", "apps")):
        if low.startswith(mot + " ") or (" " + mot + " ") in (" " + low + " ")[:len(mot) + 12]:
            want = cat
    for pre in ("ouvre ", "ouvrir ", "le dossier ", "la dossier ", "le fichier ", "le document ",
                "l'application ", "le logiciel ", "le programme ", "mon ", "ma ", "mes ", "le ", "la ", "les "):
        if t.lower().startswith(pre):
            t = t[len(pre):]
    return t.strip(" .\"'"), want


def _log_fail(name: str, reponse: str) -> None:
    try:
        with open(FAIL_LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M ") + f"{name!r} -> {reponse}\n")
    except Exception:
        pass


def _score(query: str, name: str) -> int:
    q = _norm(query)
    n = _norm(name)
    if not q or not n:
        return 0
    if n == q:
        return 100
    if n.startswith(q):
        return 88
    if q in n:
        return 76
    if n in q:
        return 62
    qwords = q.split()
    nwords = n.split()
    if len(qwords) > 1 and all(w in n for w in qwords):
        return 78
    ratio = difflib.SequenceMatcher(None, q, n).ratio()
    if ratio >= 0.75:
        return int(ratio * 70)
    if ratio >= 0.6:
        return int(ratio * 55)
    return 0


def _open(path: str) -> None:
    # os.startfile gère .exe, .lnk, dossier et fichier (comme un double-clic).
    os.startfile(path)


def open_anything(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    name = (parameters or {}).get("name", "").strip()
    name, _want = _clean_request(name)
    if not name:
        return "Dis-moi quel élément ouvrir (application, dossier ou fichier)."

    label_of = {"apps": "application", "folders": "dossier", "files": "fichier"}

    def _go(cat, item, where=""):
        try:
            _open(item["path"])
            _set_last(item["path"])
            return (f"Ouvert : {item['name']} ({label_of.get(cat, 'élément')}){where}. "
                    f"Chemin : {item['path']}")
        except Exception as e:
            return f"Impossible d'ouvrir {item['name']} : {e}"

    # 1) D'abord DANS le dossier demande, ou dans le dernier dossier ouvert (ajout Claude)
    dossier = (parameters or {}).get("folder", "").strip()
    inside = []
    if dossier:
        if os.path.isdir(dossier):
            inside = [Path(dossier)]
        else:
            hit, sc = _live_search(dossier, _roots(), 4, 4.0)
            if hit and sc >= 70 and hit[0] == "folders":
                inside = [Path(hit[1]["path"])]
    elif _get_last():
        inside = [Path(_get_last())]
    if inside:
        hit, sc = _live_search(name, inside, 3, 3.0)
        if hit and sc >= 70:
            return _go(*hit, where=f" dans {inside[0].name}")

    index = _load_index()

    best = None
    best_score = 0
    # Légère préférence aux applications, puis dossiers, puis fichiers.
    for cat, weight in (("apps", 1.0), ("folders", 0.96), ("files", 0.92)):
        for item in index.get(cat, []):
            s = _score(name, item["name"]) * weight
            if s > best_score:
                best_score = s
                best = (cat, item)

    # 2) Index (applications, dossiers et fichiers connus)
    if best is not None and best_score >= 70:
        return _go(*best)

    # 3) Index complet du PC (tout le profil + disques D:, E:...)
    if not _FULL_READY.is_set():
        _FULL_READY.wait(timeout=8)
    hit, sc = _full_search(name)
    if hit and sc >= 62:
        return _go(*hit)

    # 4) Recherche en direct (si l'index n'est pas encore pret)
    hit, sc = _live_search(name, _roots(), 5, 6.0)
    if hit and sc >= 62:
        return _go(*hit)

    if best is not None and best_score >= 58:
        return _go(*best)
    if best is None:
        _log_fail(name, "rien trouve")
        return f"Je n'ai trouvé aucun élément correspondant à « {name} »."

    # Match faible : propose les meilleures correspondances au lieu d'ouvrir au hasard.
    candidates = []
    for cat, weight in (("apps", 1.0), ("folders", 0.96), ("files", 0.92)):
        for it in index.get(cat, []):
            s = _score(name, it["name"]) * weight
            if s >= 40:
                candidates.append((s, it["name"]))
    candidates.sort(key=lambda x: -x[0])
    top = [n for _, n in candidates[:5]]
    if top:
        _log_fail(name, "propositions: " + ", ".join(top))
        return f"Je n'ai pas trouvé exactement « {name} ». Tu veux dire : {', '.join(top)} ?"
    _log_fail(name, "rien trouve")
    return f"Je n'ai trouvé aucun élément correspondant à « {name} »."


# ── Déclaration d'outil (auto-découverte) ─────────────────────────────────────
TOOL = {
    "name": "open_anything",
    "description": (
        "Opens any application, folder, or file on this computer by name, using a "
        "local index of installed programs, folders and files. Use this whenever the "
        "user asks to open, launch or start something local by name (an app, a game, "
        "a folder, a document) — for websites use browser_control instead. "
        "It REMEMBERS the last folder it opened and searches INSIDE it first, so for "
        "'ouvre le dossier X qui est dedans' / 'ouvre le fichier Y' just call it again with "
        "the new name. If the user names the parent folder, pass it in 'folder'. Never "
        "double-click on the screen to open a file or folder: use this tool."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "Name of the app, folder or file to open (e.g. 'Steam', 'Photos', 'cv')",
            },
            "folder": {
                "type": "STRING",
                "description": "Optional: the folder to look inside (name or full path), e.g. 'jarvis'",
            }
        },
        "required": ["name"],
    },
    "handler": open_anything,
}

_start_indexer()
