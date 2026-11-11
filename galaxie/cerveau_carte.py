r"""
La carte du cerveau pour le tableau de bord (07/11/2026, code original de Jarvis Claude).

Inspirée de la « carte 5 » du guide MAPS de Pav Rusovs : chaque fichier est un point, chaque lien un trait,
et chaque point a une SORTE (kind), une COUCHE (layer) et un DOMAINE (area).

    sortes  : root, area, note, project, skill, memory, routine, run, app
    couches : core, skills, memory, routines, apps, runs

Tout est relu dans les vrais fichiers à chaque appel (rien n'est gardé) et rien n'est jamais écrit.
"""
import json
import re
import subprocess
import unicodedata
from datetime import date, datetime
from pathlib import Path

from plugins._cerveau_commun import CERVEAU as BRAIN, WIKI   # le cerveau de l'utilisateur
MARK = Path(__file__).resolve().parent.parent                       # Desktop\jarvis\Mark-LV
SKILLS = Path.home() / ".claude" / "skills"
MEMOIRE = Path.home() / ".claude" / "projects" / "".join(c if c.isalnum() else "-" for c in str(BRAIN)) / "memory"
RAPPELS = Path.home() / ".jarvis" / "reminders"
CARNET = MARK / "memory" / "carnet-cerveau.md"
MAX_NOTE = 220
MAX_LECTURE = 200_000

# Domaines du cerveau : couleur, lettre du moyeu, nom affiché.
DOMAINES = {
    "projets":   {"nom": "Projets",   "lettre": "P", "couleur": "#f5a524"},
    "seances":   {"nom": "Séances",   "lettre": "S", "couleur": "#3fd68f"},
    "savoirs":   {"nom": "Savoirs",   "lettre": "K", "couleur": "#7c8cff"},
    "personnes": {"nom": "Personnes", "lettre": "F", "couleur": "#c084fc"},
    "pilotage":  {"nom": "Pilotage",  "lettre": "O", "couleur": "#ff6b6b"},
    "jarvis":    {"nom": "Jarvis",    "lettre": "J", "couleur": "#38bdf8"},
    "systeme":   {"nom": "Système",   "lettre": "C", "couleur": "#a3acb9"},
}
DOSSIER_VERS_DOMAINE = {"projets": "projets", "conversations": "seances", "concepts": "savoirs",
                        "syntheses": "savoirs", "sources": "savoirs", "entites": "personnes"}

# Lectures autorisées : préfixe de clé → dossier racine et extensions permises.
RACINES = {
    "wiki": (WIKI, (".md",)),
    "brain": (BRAIN, (".md",)),                    # CLAUDE.md seulement (voir lire_element)
    "skill": (SKILLS, (".md",)),
    "memoire": (MEMOIRE, (".md",)),
    "plugin": (MARK / "plugins", (".py",)),
    "outil": (BRAIN / "outils", (".py",)),
    "jcore": (MARK / "core", (".py",)),
    "prod": (BRAIN / "productions", (".md", ".txt")),
}
EXTENSIONS_PROD = {".md", ".txt", ".py", ".html", ".json", ".mp4", ".png", ".jpg", ".wav", ".mp3", ".srt", ".pdf"}


def _simple(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").replace(" ", "-")


def _lire(f: Path, limite: int = 6000) -> str:
    try:
        return f.read_text(encoding="utf-8", errors="ignore")[:limite]
    except OSError:
        return ""


def _mtime(f: Path) -> int:
    try:
        return int(f.stat().st_mtime)
    except OSError:
        return 0


def _note_de(texte: str) -> str:
    """Une phrase d'aperçu : description du frontmatter, sinon la première ligne de texte."""
    m = re.search(r"^description:\s*(.+)$", texte[:3000], re.M)
    if m:
        brut = m.group(1)
    else:
        corps = re.sub(r"^---.*?\n---\s*", "", texte, flags=re.S)
        lignes = [l for l in corps.splitlines() if l.strip() and not l.startswith(("#", ">", "|", "```", "---"))]
        brut = lignes[0] if lignes else ""
    brut = re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]", lambda x: x.group(2) or x.group(1), brut)
    brut = " ".join(brut.replace("**", "").replace("`", "").strip(" \"'-").split())
    return brut[:MAX_NOTE]


def _docstring(f: Path) -> str:
    m = re.search(r'"""(.*?)"""', _lire(f, 3000), re.S)
    return " ".join(m.group(1).split())[:MAX_NOTE] if m else ""


class Carte:
    def __init__(self):
        self.noeuds, self.liens, self.index, self._paires = [], [], {}, set()

    def ajouter(self, cle: str, **champs) -> int:
        if cle in self.index:
            return self.index[cle]
        champs.setdefault("note", "")
        champs.setdefault("changed", 0)
        champs.setdefault("lecture", "")
        self.noeuds.append({"id": len(self.noeuds), "cle": cle, "liens": 0, **champs})
        self.index[cle] = len(self.noeuds) - 1
        return self.index[cle]

    def relier(self, a: int, b: int):
        if a is None or b is None or a == b:
            return
        p = (min(a, b), max(a, b))
        if p in self._paires:
            return
        self._paires.add(p)
        self.liens.append({"s": a, "t": b})
        self.noeuds[a]["liens"] += 1
        self.noeuds[b]["liens"] += 1


def _seances_et_sauvegardes(depot: Path, log: Path) -> list[dict]:
    """Les « runs » : chaque entrée du journal du cerveau et chaque sauvegarde (commit git) du cerveau."""
    sortie = []
    for m in re.finditer(r"^## \[(\d{4}-\d{2}-\d{2})\] (\w+) \| (.+)$", _lire(log, 400_000), re.M):
        sortie.append({"date": m.group(1), "type": m.group(2), "titre": m.group(3).strip()[:140]})
    try:
        r = subprocess.run(["git", "-C", str(depot), "log", "--format=%ad|%s", "--date=short", "-n", "400"],
                           capture_output=True, text=True, encoding="utf-8", timeout=10, creationflags=0x08000000)
        for ligne in r.stdout.splitlines():
            d, _, s = ligne.partition("|")
            if re.match(r"\d{4}-\d{2}-\d{2}$", d):
                sortie.append({"date": d, "type": "sauvegarde", "titre": s.strip()[:140]})
    except (OSError, subprocess.SubprocessError):
        pass
    return sortie


def routines(aujourdhui: date | None = None) -> list[dict]:
    """Ce qui tourne tout seul ou à chaque séance, avec un statut tiré d'une preuve réelle (fichier, date)."""
    aujourdhui = aujourdhui or date.today()
    jour = lambda ts: datetime.fromtimestamp(ts).date() if ts else None
    sortie = []
    m = None
    for m in re.finditer(r"rang[ée] le (\d{1,2})/(\d{1,2})", _lire(CARNET, 400_000)):
        pass
    fait = bool(m) and (int(m.group(1)), int(m.group(2))) == (aujourdhui.day, aujourdhui.month)
    sortie.append({"nom": "rangement-du-carnet", "quand": "début de séance", "machine": "PC",
                   "statut": "FAIT" if fait else "À FAIRE", "page": "jarvis-mark-lv",
                   "note": "Range dans le wiki les notes prises par Jarvis." + (f" Dernier rangement : {m.group(1)}/{m.group(2)}." if m else "")})
    fiche = jour(_mtime(WIKI / "fiche-cerveau.md"))
    sortie.append({"nom": "fiche-cerveau", "quand": "fin de séance", "machine": "PC",
                   "statut": "FAIT" if fiche == aujourdhui else "À FAIRE", "page": "fiche-cerveau",
                   "note": "Fiche courte que le Jarvis vocal lit à chaque démarrage." + (f" Mise à jour le {fiche:%d/%m}." if fiche else "")})
    seances_dir = WIKI / "conversations"
    derniere = max((_mtime(f) for f in seances_dir.glob("*.md")), default=0)
    sortie.append({"nom": "page-de-seance", "quand": "pendant la séance", "machine": "PC",
                   "statut": "FAIT" if jour(derniere) == aujourdhui else "À FAIRE", "page": "index",
                   "note": "Résumé de chaque discussion dans wiki/conversations, mis à jour au fil de l'eau."})
    for f in sorted(RAPPELS.glob("JARVISReminder_*.py")) if RAPPELS.is_dir() else []:
        x = re.match(r"JARVISReminder_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})", f.name)
        if not x:
            continue
        quand = datetime(*(int(v) for v in x.groups()))
        if quand.date() < aujourdhui:
            continue
        msg = re.search(r'^message\s*=\s*"(.*)"', _lire(f, 2000), re.M)
        try:
            texte = json.loads(f'"{msg.group(1)}"') if msg else "Rappel"
        except ValueError:
            texte = msg.group(1)
        sortie.append({"nom": "rappel", "quand": f"{quand:%d/%m %H:%M}", "machine": "PC", "statut": "PROGRAMMÉ",
                       "page": "", "note": texte})
    return sortie


def construire(aujourdhui: date | None = None) -> dict:
    c = Carte()
    racine = c.ajouter("racine", kind="root", label="CLAUDE.md", area="systeme", layer="core",
                       path=str(BRAIN / "CLAUDE.md"), lecture="brain:CLAUDE.md",
                       note="Le chef d'orchestre : dit à Claude Code où vit chaque chose.", changed=_mtime(BRAIN / "CLAUDE.md"))
    moyeux = {}
    for cle, d in DOMAINES.items():
        moyeux[cle] = c.ajouter(f"domaine:{cle}", kind="area", label=d["nom"], area=cle, layer="core",
                                path="", note=f"Domaine « {d['nom']} » du cerveau.")
        c.relier(racine, moyeux[cle])

    # Pages du wiki (couche mémoire)
    pages = sorted(p for p in WIKI.rglob("*.md") if not any(x.startswith(".") for x in p.relative_to(WIKI).parts))
    par_nom, textes = {}, {}
    for p in pages:
        rel = p.relative_to(WIKI)
        dossier = rel.parts[0] if len(rel.parts) > 1 else ""
        domaine = DOSSIER_VERS_DOMAINE.get(dossier, "pilotage")
        if domaine == "projets" and "jarvis" in p.stem:
            domaine = "jarvis"
        texte = _lire(p, 200_000)
        i = c.ajouter(f"wiki:{rel.as_posix()}", kind="note", label=p.stem, area=domaine, layer="memory",
                      path=f"wiki/{rel.as_posix()}", lecture=f"wiki:{rel.as_posix()}", note=_note_de(texte),
                      changed=_mtime(p))
        c.relier(i, moyeux[domaine])
        par_nom.setdefault(_simple(p.stem), i)
        textes[i] = texte
    if "index" in par_nom:
        c.relier(racine, par_nom["index"])
    for i, texte in textes.items():
        for cible in re.findall(r"\[\[([^\]|#]+)", texte):
            c.relier(i, par_nom.get(_simple(cible.strip().split("/")[-1])))

    # Productions (projets réels sur le disque)
    prod = BRAIN / "productions"
    for d in sorted(x for x in prod.iterdir() if x.is_dir() and not x.name.startswith(("_", "."))) if prod.is_dir() else []:
        domaine = "jarvis" if "jarvis" in d.name else "projets"
        i = c.ajouter(f"prod:{d.name}", kind="project", label=d.name, area=domaine, layer="memory",
                      path=f"productions/{d.name}", note="Dossier de production.", changed=_mtime(d))
        c.relier(i, moyeux[domaine])
        c.relier(i, par_nom.get(_simple(d.name)))

        # Les fichiers du dossier (deux niveaux) : chaque point est un vrai fichier
        for f in sorted(x for x in d.rglob("*") if x.is_file() and x.suffix.lower() in EXTENSIONS_PROD
                        and len(x.relative_to(d).parts) <= 2 and not any(m.startswith((".", "_")) for m in x.relative_to(d).parts))[:40]:
            rel = f.relative_to(prod).as_posix()
            j = c.ajouter(f"prodf:{rel}", kind="note", label=f.name, area=domaine, layer="memory", path=f"productions/{rel}",
                          lecture=f"prod:{rel}" if f.suffix.lower() in (".md", ".txt") else "",
                          note=_note_de(_lire(f)) if f.suffix.lower() in (".md", ".txt") else f"Fichier {f.suffix[1:].upper()} du projet {d.name}.",
                          changed=_mtime(f))
            c.relier(j, i)

    # Le code de Jarvis (cœur du programme)
    for f in sorted((MARK / "core").glob("*.py")) if (MARK / "core").is_dir() else []:
        if f.name.startswith("_"):
            continue
        i = c.ajouter(f"jcore:{f.name}", kind="note", label=f.name, area="jarvis", layer="memory", path=f"jarvis/core/{f.name}",
                      lecture=f"jcore:{f.name}", note=_docstring(f) or "Module du programme Jarvis.", changed=_mtime(f))
        c.relier(i, moyeux["jarvis"])

    # Mémoire de Claude
    for f in sorted(MEMOIRE.glob("*.md")) if MEMOIRE.is_dir() else []:
        if f.name == "MEMORY.md":
            continue
        i = c.ajouter(f"memoire:{f.name}", kind="memory", label=f.stem, area="systeme", layer="memory",
                      path=f"mémoire de Claude/{f.name}", lecture=f"memoire:{f.name}", note=_note_de(_lire(f)),
                      changed=_mtime(f))
        c.relier(i, moyeux["systeme"])

    # Compétences de Claude (couche skills)
    for d in sorted(x for x in SKILLS.iterdir() if x.is_dir() and not x.name.startswith(".")) if SKILLS.is_dir() else []:
        i = c.ajouter(f"skill:{d.name}", kind="skill", label=d.name, area="systeme", layer="skills",
                      path=f"compétences/{d.name}/SKILL.md", lecture=f"skill:{d.name}/SKILL.md" if (d / "SKILL.md").is_file() else "",
                      note=_note_de(_lire(d / "SKILL.md")), changed=_mtime(d / "SKILL.md"))
        c.relier(i, moyeux["systeme"])
        c.relier(i, par_nom.get(_simple(d.name)))

    # Applications : plugins de Jarvis et outils du cerveau (couche apps)
    for dossier, prefixe, domaine in ((MARK / "plugins", "plugin", "jarvis"), (BRAIN / "outils", "outil", "systeme")):
        for f in sorted(dossier.glob("*.py")) if dossier.is_dir() else []:
            if f.name.startswith("_"):
                continue
            i = c.ajouter(f"{prefixe}:{f.name}", kind="app", label=f.stem, area=domaine, layer="apps",
                          path=f"{'jarvis/plugins' if prefixe == 'plugin' else 'outils'}/{f.name}",
                          lecture=f"{prefixe}:{f.name}", note=_docstring(f), changed=_mtime(f))
            c.relier(i, moyeux[domaine])

    # Routines (couche routines)
    for k, r in enumerate(routines(aujourdhui)):
        i = c.ajouter(f"routine:{k}:{r['nom']}", kind="routine", label=r["nom"], area="pilotage", layer="routines",
                      path="", note=f"{r['quand']} · {r['statut']} · {r['note']}")
        c.relier(i, racine)
        c.relier(i, par_nom.get(_simple(r["page"])) if r["page"] else None)

    # Runs : séances du journal et sauvegardes du cerveau
    runs = _seances_et_sauvegardes(BRAIN, WIKI / "log.md")
    for k, r in enumerate(runs):
        i = c.ajouter(f"run:{k}", kind="run", label=r["titre"], area="seances" if r["type"] != "sauvegarde" else "systeme",
                      layer="runs", path="", note=f"{r['date']} · {r['type']}", jour=r["date"], type=r["type"])
        c.relier(i, racine)

    compte = {}
    for n in c.noeuds:
        compte.setdefault(n["area"], 0)
        if n["kind"] not in ("area", "root"):
            compte[n["area"]] += 1
    domaines = {k: {**v, "nombre": compte.get(k, 0)} for k, v in DOMAINES.items()}
    return {"nodes": c.noeuds, "links": c.liens, "areas": domaines,
            "kinds": {k: sum(1 for n in c.noeuds if n["kind"] == k) for k in
                      ("note", "project", "memory", "skill", "app", "routine", "run")}}


def lire_element(cle: str) -> str | None:
    """Rend le texte d'un fichier de la carte, en lecture seule, et seulement dans les dossiers autorisés."""
    prefixe, _, chemin = (cle or "").partition(":")
    if prefixe not in RACINES or not chemin:
        return None
    base, extensions = RACINES[prefixe]
    if prefixe == "brain" and chemin != "CLAUDE.md":
        return None
    morceaux = Path(chemin).parts
    # Pas de « .. », pas de chemin absolu : on reste dans le dossier (les compétences liées ailleurs restent lisibles).
    if Path(chemin).is_absolute() or ":" in chemin or any(m in ("..", "") for m in morceaux) or "\\" in chemin:
        return None
    cible = base / Path(*morceaux)
    if cible.suffix.lower() not in extensions or not cible.is_file():
        return None
    return cible.read_text(encoding="utf-8", errors="ignore")[:MAX_LECTURE]
