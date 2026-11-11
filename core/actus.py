"""
Les actualités du briefing de démarrage (demande d'un utilisateur, 01/11 : « l'actu du monde ne m'intéresse
pas, je préfère la locale »).

Réglage "actus" de memory/interface.json :
    (absent)  ou "locale"  les actualités de TA ville (celle que Jarvis a apprise) : c'est le défaut,
                           et si Jarvis ne connaît pas encore ta ville, ce sont les actualités générales
    ""  ou "monde"         les actualités de France et du monde
    "Dunkerque"            ou n'importe quel mot : une région, un sujet, une équipe...
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
GENERALE = "actualités France monde aujourd'hui"


def _lire_json(chemin: Path) -> dict:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return {}


def ville_apprise() -> str:
    entree = (_lire_json(BASE / "memory" / "long_term.json").get("identity") or {}).get("city") or {}
    return (entree.get("value", "") if isinstance(entree, dict) else str(entree)).strip()


def requete_actus(reglage, ville: str = "") -> str:
    """La recherche à lancer pour le briefing. `reglage` = valeur de "actus", `ville` = ville apprise."""
    voulu = str(reglage or "").strip()
    if voulu.lower() in ("", "monde", "france", "general", "général", "generale", "générale"):
        return GENERALE
    if voulu.lower() in ("locale", "local", "ville", "ma ville"):
        return f"actualités {ville} aujourd'hui" if ville else GENERALE
    return f"actualités {voulu} aujourd'hui"


def requete_du_briefing() -> str:
    reglage = _lire_json(BASE / "memory" / "interface.json").get("actus", "locale")   # défaut : locale
    return requete_actus(reglage, ville_apprise())
