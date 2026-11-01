"""
Les fichiers que la personne a donnés à Jarvis, retenus d'une séance à l'autre (question de Fredo,
01/11 : « à chaque session je dois lui refournir le fichier, il ne le garde pas en mémoire »).

Tout reste sur ce PC, dans memory/fichiers/ : une copie de chaque fichier (pour le retrouver même
s'il a été déplacé ou effacé) et index.json, la liste. Les 30 derniers fichiers sont gardés.
"""
import hashlib
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MAX_FICHIERS = 30
MAX_COPIE = 25 * 1024 * 1024    # au-delà de 25 Mo : on retient seulement où il se trouve


def _dossier() -> Path:
    return BASE / "memory" / "fichiers"


def _charger() -> list:
    try:
        return json.loads((_dossier() / "index.json").read_text(encoding="utf-8"))
    except Exception:
        return []


def _sauver(entrees: list) -> None:
    _dossier().mkdir(parents=True, exist_ok=True)
    (_dossier() / "index.json").write_text(json.dumps(entrees, ensure_ascii=False, indent=1), encoding="utf-8")


def _mots(texte: str) -> set:
    t = unicodedata.normalize("NFD", str(texte).lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return {m for m in re.findall(r"[a-z0-9]+", t) if len(m) >= 3}


def _chemin_utilisable(entree: dict) -> str | None:
    """L'original s'il existe encore, sinon la copie gardée."""
    for cle in ("chemin", "copie"):
        if entree.get(cle) and Path(entree[cle]).is_file():
            return entree[cle]
    return None


def retenir(chemin) -> dict | None:
    """Ajoute le fichier à la liste (en tête). Ne lève jamais d'erreur."""
    try:
        path = Path(chemin).resolve()
        if not path.is_file() or _dossier().resolve() in path.parents:
            return None
        entrees = [e for e in _charger() if e.get("chemin") != str(path)]
        copie = ""
        if path.stat().st_size <= MAX_COPIE:
            _dossier().mkdir(parents=True, exist_ok=True)
            cible = _dossier() / f"{hashlib.sha1(str(path).encode('utf-8')).hexdigest()[:10]}_{path.name}"
            shutil.copy2(path, cible)
            copie = str(cible)
        entree = {"nom": path.name, "chemin": str(path), "copie": copie,
                  "date": datetime.now().strftime("%Y-%m-%d")}
        entrees.insert(0, entree)
        for ancienne in entrees[MAX_FICHIERS:]:
            if ancienne.get("copie"):
                Path(ancienne["copie"]).unlink(missing_ok=True)
        _sauver(entrees[:MAX_FICHIERS])
        return entree
    except Exception as e:
        print(f"[Fichiers] {chemin} non retenu : {e}")
        return None


def liste() -> list:
    return [e for e in _charger() if _chemin_utilisable(e)]


def retrouver(texte: str = "", dernier_si_rien: bool = False) -> str | None:
    """Le chemin du fichier retenu dont le nom ressemble le plus au texte."""
    entrees = liste()
    if not entrees:
        return None
    voulus = _mots(texte)
    meilleur, score_max = None, 0
    for e in entrees:                      # le plus récent d'abord : il gagne en cas d'égalité
        score = len(voulus & _mots(Path(e["nom"]).stem))
        if score > score_max:
            meilleur, score_max = e, score
    if meilleur:
        return _chemin_utilisable(meilleur)
    return _chemin_utilisable(entrees[0]) if dernier_si_rien else None


def indice(question: str, fichier_depose: str | None = None) -> str:
    """Phrase à mettre devant le résultat de recall_memory quand la question parle d'un fichier."""
    from core.fichier_depose import indice_fichier, parle_d_un_fichier
    trouve = retrouver(question)
    if trouve:
        return (f"[KNOWN FILE] The user gave you this file earlier and you still have it: {Path(trouve).name}. "
                f"Call file_processor now with file_path set to: {trouve}")
    deja = indice_fichier(question, fichier_depose)
    if deja:
        return deja
    noms = [e["nom"] for e in liste()]
    if noms and parle_d_un_fichier(question):
        return ("[KNOWN FILES] Files the user gave you earlier, which you still have: " + ", ".join(noms[:15])
                + ". If one of them is the file they mean, call file_processor with file_path set to its name.")
    return ""


def bloc_pour_prompt() -> str:
    """Ce que Jarvis sait au démarrage de chaque séance (vide s'il n'a encore reçu aucun fichier)."""
    entrees = liste()
    if not entrees:
        return ""
    lignes = "\n".join(f"- {e['nom']} ({e['date']})" for e in entrees[:15])
    return ("[KNOWN FILES]\nFiles the user gave you in earlier sessions. You still have them, kept on this PC: "
            "never ask the user to send them again. To read one or answer a question about it, call "
            f"file_processor with file_path set to its name.\n{lignes}\n\n")
