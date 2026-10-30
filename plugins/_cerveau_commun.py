"""
Outils communs pour lire le cerveau de l'utilisateur (le wiki Obsidian tenu par Claude Code).
Pas un plugin : le nom commence par « cerveau_commun » et n'a pas de PLUGIN, il est
seulement importé par cerveau_chercher.py, cerveau_lire.py et cerveau_noter.py.
"""
import re
import unicodedata
from datetime import datetime
from pathlib import Path

def _chemin_cerveau() -> Path:
    """Dossier du cerveau : réglage "cerveau" de memory/interface.json, sinon Documents\\Cerveau."""
    try:
        import json
        r = json.loads((Path(__file__).resolve().parent.parent / "memory" / "interface.json").read_text(encoding="utf-8"))
        if r.get("cerveau"):
            return Path(r["cerveau"]).expanduser()
    except Exception:
        pass
    return Path.home() / "Documents" / "Cerveau"


CERVEAU = _chemin_cerveau()
WIKI = CERVEAU / "wiki"
CARNET = Path(__file__).resolve().parent.parent / "memory" / "carnet-cerveau.md"   # Windows interdit à ce Python d'écrire dans Documents
FICHE = WIKI / "fiche-cerveau.md"

MAX_REPONSE = 3500   # caractères renvoyés à Gemini par appel


def simple(texte: str) -> str:
    texte = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


def mots(texte: str) -> list[str]:
    return [m for m in re.findall(r"[a-z0-9]+", simple(texte)) if len(m) >= 3]


def pages() -> list[Path]:
    return sorted(WIKI.rglob("*.md"))


def nom(page: Path) -> str:
    return page.relative_to(WIKI).with_suffix("").as_posix()


def chercher(question: str, combien: int = 3) -> list[tuple[int, Path, str]]:
    cles = set(mots(question))
    if not cles:
        return []
    resultats = []
    for page in pages():
        try:
            texte = page.read_text(encoding="utf-8")
        except Exception:
            continue
        corps = simple(texte)
        titre = simple(nom(page))
        score = sum(corps.count(c) + 5 * titre.count(c) for c in cles)
        if score:
            resultats.append((score, page, texte))
    resultats.sort(key=lambda r: r[0], reverse=True)
    return resultats[:combien]


def extrait(texte: str, question: str, taille: int = 1100) -> str:
    """Le passage de la page qui contient le plus de mots de la question."""
    cles = set(mots(question))
    lignes = [l for l in texte.splitlines() if l.strip() and not l.startswith("---")]
    meilleur, score_max = 0, -1
    for i in range(len(lignes)):
        bloc = simple(" ".join(lignes[i:i + 8]))
        score = sum(bloc.count(c) for c in cles)
        if score > score_max:
            meilleur, score_max = i, score
    return "\n".join(lignes[meilleur:meilleur + 12])[:taille]


def lire(nom_page: str) -> tuple[Path | None, str]:
    cible = simple(nom_page).replace(" ", "-")
    for page in pages():
        if cible in simple(nom(page)):
            return page, page.read_text(encoding="utf-8")
    return None, ""


def noter(note: str) -> None:
    quand = datetime.now().strftime("%Y-%m-%d %H:%M")
    with CARNET.open("a", encoding="utf-8") as f:
        f.write(f"- [ ] {quand} : {note.strip()}\n")
