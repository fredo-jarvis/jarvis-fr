"""
Outils communs pour lire le cerveau de l'utilisateur (le wiki Obsidian tenu par Claude Code).
Pas un plugin : le nom commence par « cerveau_commun » et n'a pas de PLUGIN, il est
seulement importé par cerveau_chercher.py, cerveau_lire.py et cerveau_noter.py.
"""
import re
import unicodedata
from datetime import datetime
from pathlib import Path

def _documents() -> Path:
    """Le vrai dossier Documents de Windows, le même que l'installateur (souvent dans OneDrive)."""
    try:
        import ctypes
        tampon = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, tampon) == 0 and tampon.value:
            return Path(tampon.value)
    except Exception:
        pass
    return Path.home() / "Documents"


def _chemin_cerveau() -> Path:
    """Dossier du cerveau : réglage "cerveau" de memory/interface.json, sinon Documents\\Cerveau."""
    try:
        import json
        r = json.loads((Path(__file__).resolve().parent.parent / "memory" / "interface.json").read_text(encoding="utf-8"))
        if r.get("cerveau"):
            return Path(r["cerveau"]).expanduser()
    except Exception:
        pass
    return _documents() / "Cerveau"


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


# ── Les deux seules pages que le Jarvis vocal écrit lui-même (version 1.1) ────────────────
# Sans Claude Code, le cerveau restait vide : Jarvis tient donc à jour la page « Moi »
# (ce qu'il sait de l'utilisateur) et ajoute une ligne au journal à chaque fin de séance.
# Tout le reste du wiki reste rangé par Claude Code, à partir du carnet.

TITRES = {"identity": "Qui je suis", "preferences": "Ce que j'aime", "projects": "Mes projets",
          "relationships": "Mes proches", "wishes": "Mes envies", "notes": "Notes"}
CLES = {"name": "Prénom", "first_name": "Prénom", "address_preference": "Comment m'appeler",
        "city": "Ville", "job": "Travail", "email": "Mail", "language": "Langue",
        "hobbies": "Loisirs", "current_projects": "Projets en cours"}


VALEURS_VIDES = ("", "unknown", "inconnu", "inconnue", "n/a", "none", "non renseigné",
                 "not provided", "not specified")


def valeur_vide(valeur) -> bool:
    """Vrai si la personne a passé la question : rien à garder (test du 31/10 : « unknown »)."""
    return str(valeur).strip().lower() in VALEURS_VIDES


def page_moi(memoire: dict) -> None:
    """Réécrit wiki/entites/moi.md à partir de la mémoire de Jarvis."""
    lignes = ["# Moi", "", "Page tenue à jour par Jarvis à partir de ce qu'il a appris sur moi.",
              f"Dernière mise à jour : {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    for cat, titre in TITRES.items():
        faits = memoire.get(cat) or {}
        if not isinstance(faits, dict) or not faits:
            continue
        lignes += [f"## {titre}", ""]
        for cle, entree in faits.items():
            valeur = entree.get("value", "") if isinstance(entree, dict) else str(entree)
            if valeur:
                lignes.append(f"- **{CLES.get(cle, cle.replace('_', ' ').capitalize())}** : {valeur}")
        lignes.append("")
    try:
        (WIKI / "entites").mkdir(parents=True, exist_ok=True)
        (WIKI / "entites" / "moi.md").write_text("\n".join(lignes), encoding="utf-8")
    except Exception as e:
        print(f"[Cerveau] page Moi non écrite : {e}")


def journal(resume: str) -> None:
    """Ajoute une entrée « session » au journal du cerveau (wiki/log.md)."""
    try:
        with (WIKI / "log.md").open("a", encoding="utf-8") as f:
            f.write(f"\n## [{datetime.now().strftime('%Y-%m-%d')}] session | {resume.strip()}\n")
    except Exception as e:
        print(f"[Cerveau] journal non écrit : {e}")
