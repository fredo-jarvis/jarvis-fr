r"""
Jarvis OS, le tableau de bord du cerveau (écrit par Jarvis Claude le 07/11/2026, code original,
idée tirée de la vidéo « AI OS » de Pav Rusovs).

Règle de Pav reprise : la page MONTRE, elle ne GARDE rien. Tout est lu dans les fichiers du wiki
(à chaque appel) : si le tableau casse, tu ne perds rien. Jarvis ne coche jamais une tâche
à ta place : ce module ne fait que lire.

Servi par galaxie/server.py :  http://localhost:4719/tableau   (données : /api/tableau)
"""
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

MAX_TEXTE = 240
COMPTEUR = re.compile(r"compteur 90 jours\s*:\s*d[ée]but le (\d{1,2})/(\d{1,2})/(\d{4})", re.I)
TACHE = re.compile(r"^\s*(?:\d+\.|[-*])\s*\[( |x|X)\]\s*(.+)$")
DATE_SEANCE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(.+)\.md$")


def nettoyer(texte: str) -> str:
    """Enlève le gras, les liens [[page|texte]] et le code, pour une ligne lisible à l'écran."""
    texte = re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), texte)
    texte = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", texte)
    texte = texte.replace("**", "").replace("`", "").replace("__", "")
    texte = " ".join(texte.split())
    return texte if len(texte) <= MAX_TEXTE else texte[:MAX_TEXTE - 1].rstrip() + "…"


def _lire(fichier: Path) -> str:
    try:
        return fichier.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def lire_taches(fichier: Path) -> list[dict]:
    """Les cases non cochées de a-faire.md, avec leur rubrique.
    « pour_moi » : la tâche t'attend (elle commence par « Moi : » ou par ton prénom)."""
    rubrique, sortie = "", []
    for ligne in _lire(fichier).splitlines():
        if ligne.startswith("## "):
            rubrique = nettoyer(ligne[3:]).strip()
            continue
        m = TACHE.match(ligne)
        if not m or m.group(1).lower() == "x":
            continue
        texte = nettoyer(m.group(2))
        if texte:
            sortie.append({"rubrique": rubrique, "texte": texte,
                           "pour_moi": _pour_moi(texte)})
    return sortie


def _prenom() -> str:
    """Le prénom appris par Jarvis (memory/long_term.json), pour reconnaître les tâches qui t'attendent."""
    try:
        ident = json.loads((Path(__file__).resolve().parent.parent / "memory" / "long_term.json")
                           .read_text(encoding="utf-8")).get("identity") or {}
        for cle in ("name", "first_name", "prenom", "prénom"):
            v = ident.get(cle)
            v = v.get("value", "") if isinstance(v, dict) else v
            if v and str(v).strip():
                return str(v).strip()
    except (OSError, ValueError):
        pass
    return ""


def _pour_moi(texte: str) -> bool:
    mots = ["moi", "utilisateur"] + ([re.escape(_prenom())] if _prenom() else [])
    return bool(re.match(r"^(?:\d+\.\s*)?(?:" + "|".join(mots) + r")\b", texte, re.I))


def lire_promesses(fichier: Path) -> list[dict]:
    """Les promesses non tenues de promesses-en-attente.md (format « - [ ] échéance — promesse »)."""
    sortie = []
    for ligne in _lire(fichier).splitlines():
        m = TACHE.match(ligne)
        if m and m.group(1) == " ":
            texte = nettoyer(m.group(2))
            echeance, _, reste = texte.partition(" — ")
            sortie.append({"echeance": echeance.strip() if reste else "", "texte": (reste or texte).strip()})
    return sortie


def compteur_90(fichier: Path, aujourdhui: date | None = None) -> dict:
    """Le compteur d'un objectif de 90 jours. Il démarre quand une ligne
    « Compteur 90 jours : début le JJ/MM/AAAA » est écrite dans objectif.md (titre = première ligne « # »)."""
    aujourdhui = aujourdhui or date.today()
    m = COMPTEUR.search(_lire(fichier))
    if not m:
        return {"commence": False, "jour": 0, "total": 90,
                "texte": "Pas encore commencé : écris ton objectif dans wiki/objectif.md.", "nom": _nom_objectif(fichier)}
    debut = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    jour = max(0, min(90, (aujourdhui - debut).days))
    return {"commence": True, "jour": jour, "total": 90, "debut": debut.isoformat(),
            "texte": f"Jour {jour} sur 90.", "nom": _nom_objectif(fichier)}


def _nom_objectif(fichier: Path) -> str:
    m = re.search(r"^#\s+(.+)$", _lire(fichier), re.M)
    return nettoyer(m.group(1))[:40] if m else "Mon objectif"


def seances(dossier: Path, combien: int = 6) -> list[dict]:
    """Les dernières pages de conversation (une par séance), les plus récentes d'abord."""
    sortie = []
    for f in sorted(dossier.glob("*.md"), reverse=True):
        m = DATE_SEANCE.match(f.name)
        if m:
            sortie.append({"date": f"{m.group(1)}-{m.group(2)}-{m.group(3)}",
                           "sujet": m.group(4).replace("-", " "), "chemin": f"conversations/{f.name}"})
        if len(sortie) >= combien:
            break
    return sortie


def dates_des_pages(wiki: Path) -> dict:
    """Date de dernière modification de chaque page (pour la vue « Chronologie »)."""
    sortie = {}
    for p in wiki.rglob("*.md"):
        if not any(x.startswith(".") for x in p.parts):
            try:
                sortie[p.relative_to(wiki).as_posix()] = int(p.stat().st_mtime)
            except OSError:
                pass
    return sortie


RAPPELS = Path.home() / ".jarvis" / "reminders"
NOM_RAPPEL = re.compile(r"^JARVISReminder_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})\d{2}\.py$")


def _decoder(texte: str) -> str:
    """Le message est écrit comme une chaîne Python (« C\u00e9cile ») : on le remet en lettres normales."""
    try:
        return json.loads(f'"{texte}"')
    except ValueError:
        return texte


def rappels_programmes(dossier: Path = RAPPELS, maintenant: datetime | None = None) -> list[dict]:
    """Les rappels à venir que Jarvis a programmés (un petit fichier par rappel, la date est dans son nom).
    Lecture seule : rien n'est lancé ni modifié."""
    maintenant = maintenant or datetime.now()
    sortie = []
    for f in Path(dossier).glob("JARVISReminder_*.py") if Path(dossier).is_dir() else []:
        m = NOM_RAPPEL.match(f.name)
        if not m:
            continue
        quand = datetime(*(int(x) for x in m.groups()))
        if quand < maintenant:
            continue
        message = re.search(r'^message\s*=\s*"(.*)"\s*$', _lire(f)[:2000], re.M)
        sortie.append({"quand": quand.isoformat(timespec="minutes"),
                       "texte": nettoyer(_decoder(message.group(1))) if message else "Rappel de Jarvis"})
    return sorted(sortie, key=lambda r: r["quand"])


def agenda_google(jours: int = 14) -> dict:
    """Les rendez-vous des 14 prochains jours, si Google est connecté dans la galaxie."""
    try:
        from core import google_compte
        return {"ok": True, "evenements": google_compte.agenda(jours)}
    except Exception as e:                       # pas connecté, pas d'Internet… le tableau marche quand même
        return {"ok": False, "evenements": [], "erreur": str(e)[:200] or "Agenda indisponible."}


def sante(cerveau: dict, seances_: list[dict]) -> dict:
    pages = [n for n in cerveau["nodes"] if n["kind"] == "note" and str(n.get("path", "wiki/")).startswith("wiki/")]
    orphelines = [n["label"] for n in pages if n["liens"] <= 1]          # seul lien : son domaine
    return {"pages": len(pages), "liens": len(cerveau["links"]), "orphelines": len(orphelines),
            "exemples_orphelines": orphelines[:8], "points": len(cerveau["nodes"]),
            "derniere_seance": seances_[0]["date"] if seances_ else ""}


def donnees_tableau(wiki: Path, cerveau: dict | None = None, avec_google: bool = True) -> dict:
    """Tout ce que montre le tableau, relu dans les fichiers à chaque appel."""
    from galaxie import cerveau_carte
    cerveau = cerveau if cerveau is not None else cerveau_carte.construire()
    taches = lire_taches(wiki / "a-faire.md")
    seances_ = seances(wiki / "conversations")
    maintenant = datetime.now()
    return {
        "maintenant": maintenant.isoformat(timespec="seconds"),
        "semaine": maintenant.isocalendar()[1],
        "cerveau": cerveau,
        "routines": cerveau_carte.routines() if cerveau is not None else [],
        "a_faire": [t for t in taches if not t["pour_moi"]],
        "attend_moi": [t for t in taches if t["pour_moi"]],
        "promesses": lire_promesses(wiki / "promesses-en-attente.md"),
        "compteur": compteur_90(wiki / "objectif.md"),
        "seances": seances_,
        "rappels": rappels_programmes(),
        "agenda": agenda_google() if avec_google else {"ok": False, "evenements": [], "erreur": "Non demandé."},
        "sante": sante(cerveau, seances_),
        "horizon": (maintenant + timedelta(days=14)).date().isoformat(),
    }
