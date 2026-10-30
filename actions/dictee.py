# -*- coding: utf-8 -*-
"""
Dictee (ajout de la version francaise) : creer un fichier texte, puis ecrire dedans
ce que l'utilisateur dicte, phrase apres phrase. Le fichier est enregistre a chaque ajout,
le texte s'affiche en direct dans la fenetre de JARVIS, et "montre" l'ouvre
dans le Bloc-notes.
"""
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
STATE = BASE / "memory" / "dictee_en_cours.json"


def _desktop() -> Path:
    try:
        from actions.file_controller import _get_desktop
        return Path(_get_desktop())
    except Exception:
        return Path.home() / "Desktop"


def _documents() -> Path:
    try:
        from actions.file_controller import _get_documents
        return Path(_get_documents())
    except Exception:
        return Path.home() / "Documents"


def _load() -> str:
    try:
        return json.loads(STATE.read_text(encoding="utf-8")).get("fichier", "")
    except Exception:
        return ""


def _save(path: str) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"fichier": path}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _clean_name(name: str) -> str:
    name = (name or "").strip().strip('"').strip("'")
    if not name:
        name = "Note du " + datetime.now().strftime("%d-%m-%Y %Hh%M")
    name = re.sub(r'[<>:"/\\|?*]', "-", name)
    if not os.path.splitext(name)[1]:
        name += ".txt"
    return name


def _where(lieu: str) -> Path:
    l = (lieu or "").lower()
    if "doc" in l:
        return _documents()
    if "telech" in l or "téléch" in l or "download" in l:
        p = Path("D:/téléchargement")
        return p if p.exists() else Path.home() / "Downloads"
    return _desktop()


def _show(player, path: Path) -> None:
    if not player:
        return
    try:
        txt = path.read_text(encoding="utf-8")
        player.show_content(f"DICTEE — {path.name}", txt or "(fichier vide)")
    except Exception:
        pass


def _open_notepad(path: Path) -> None:
    try:
        subprocess.Popen(["notepad.exe", str(path)])
    except Exception:
        try:
            os.startfile(str(path))
        except Exception:
            pass


def dictee(parameters=None, player=None, **_) -> str:
    p = parameters or {}
    action = (p.get("action") or "").lower().strip()
    texte = p.get("text") or p.get("texte") or ""

    if action in ("start", "nouveau", "create", "creer"):
        dossier = _where(p.get("where", ""))
        dossier.mkdir(parents=True, exist_ok=True)
        cible = dossier / _clean_name(p.get("name", ""))
        if not cible.exists():
            cible.write_text("", encoding="utf-8")
        _save(str(cible))
        if texte:
            with open(cible, "a", encoding="utf-8") as f:
                f.write(texte.strip() + "\n")
        _show(player, cible)
        return (f"Fichier texte '{cible.name}' cree dans {dossier}. La dictee est ouverte : "
                f"tout ce que l'utilisateur dicte maintenant doit etre ajoute avec "
                f"action='add' et le texte EXACT qu'il a dit. Confirme-lui en une phrase courte.")

    fichier = _load()
    if action in ("add", "ecrire", "write", "append"):
        if not fichier:
            return "Aucune dictee en cours : utilise d'abord action='start' avec un nom de fichier."
        if not texte.strip():
            return "Rien a ecrire."
        cible = Path(fichier)
        with open(cible, "a", encoding="utf-8") as f:
            f.write(texte.strip() + "\n")
        _show(player, cible)
        return f"Ecrit et enregistre dans {cible.name}. Ne repete pas le texte, dis juste 'C'est note'."

    if action in ("undo", "efface", "annuler"):
        if not fichier:
            return "Aucune dictee en cours."
        cible = Path(fichier)
        lignes = cible.read_text(encoding="utf-8").splitlines()
        if lignes:
            lignes.pop()
        cible.write_text("\n".join(lignes) + ("\n" if lignes else ""), encoding="utf-8")
        _show(player, cible)
        return "Derniere phrase effacee."

    if action in ("read", "lire"):
        if not fichier:
            return "Aucune dictee en cours."
        return "Contenu du fichier :\n" + Path(fichier).read_text(encoding="utf-8")[:3000]

    if action in ("show", "montre", "open", "ouvrir"):
        if not fichier:
            return "Aucune dictee en cours."
        _open_notepad(Path(fichier))
        return f"Fichier {Path(fichier).name} ouvert dans le Bloc-notes."

    if action in ("stop", "fin", "terminer"):
        if not fichier:
            return "Aucune dictee en cours."
        _save("")
        _open_notepad(Path(fichier))
        return f"Dictee terminee. Le fichier {Path(fichier).name} est enregistre et ouvert dans le Bloc-notes."

    return "Action inconnue. Utilise start | add | undo | read | show | stop."


TOOL = {
    "name": "dictee",
    "description": (
        "Dictation into a text file. Use when the user asks to create/open a new text file "
        "(fichier texte, note, document texte) and/or to write what he says into it. "
        "start = create the .txt (on the desktop by default) and begin dictation; "
        "add = append EXACTLY what the user just dictated (his words, corrected punctuation, "
        "nothing added); undo = delete the last sentence; read = read it back; "
        "show = open it in Notepad; stop = end dictation and open it in Notepad. "
        "While a dictation is active, every sentence the user says that is not a command "
        "to you must be written with action='add'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "start | add | undo | read | show | stop"},
            "name":   {"type": "STRING", "description": "File name for start (e.g. 'liste de courses')"},
            "where":  {"type": "STRING", "description": "bureau (default) | documents | telechargements"},
            "text":   {"type": "STRING", "description": "Text to write (for add, or initial text for start)"},
        },
        "required": ["action"],
    },
    "handler": dictee,
}
