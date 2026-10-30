"""
Plugin : mode humour (écrit pour l'utilisateur le 2026-10-25, idée reprise du « modo ácido »
de jgm-source/jarvis-opensource).

    « Jarvis, active le mode humour »      « Jarvis, sois drôle »
    « Jarvis, arrête l'humour »            « Jarvis, le mode humour est allumé ? »

Allumé : Jarvis glisse une remarque pince-sans-rire à la fin de ses réponses, façon
Jarvis des films. Jamais sur un sujet sérieux, jamais sur la santé, la famille,
l'argent ou le physique de l'utilisateur. Le choix est gardé dans memory/humour.json et
main.py le rappelle à Jarvis à chaque démarrage.
"""
import json
from pathlib import Path

FICHIER = Path(__file__).resolve().parent.parent / "memory" / "humour.json"

CONSIGNE_ON = (
    "HUMOUR MODE IS ON: from now on, end most replies with one short, dry, deadpan "
    "witty remark in the style of JARVIS from the Iron Man films (British-butler "
    "understatement, gentle teasing, never mean). Never joke about anything serious, "
    "nor about the user's health, family, money or appearance. Speak French."
)
CONSIGNE_OFF = "HUMOUR MODE IS OFF: go back to your normal warm, friendly tone without the witty asides."

PLUGIN = {
    "name": "mode_humour",
    "description": (
        "Turns Jarvis's HUMOUR mode on or off, or tells whether it is on. Use for "
        "'active le mode humour', 'sois drôle', 'fais de l'humour', 'mode blagueur', "
        "'mode pince-sans-rire', 'arrête l'humour', 'désactive le mode humour', "
        "'redeviens sérieux', 'le mode humour est allumé ?'. After calling it, confirm "
        "in one short sentence (with a first witty remark if it was switched on)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "on | off | status"},
        },
        "required": ["action"],
    },
}


def est_actif() -> bool:
    try:
        return bool(json.loads(FICHIER.read_text(encoding="utf-8")).get("actif"))
    except Exception:
        return False


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = (parameters.get("action") or "status").strip().lower()
    actif = est_actif()
    if action in ("status", "etat", "état"):
        return "Humour mode is ON." if actif else "Humour mode is OFF."
    veut = action in ("on", "active", "activer", "allume", "true", "1", "oui")
    try:
        FICHIER.write_text(json.dumps({"actif": veut}), encoding="utf-8")
    except Exception as e:
        return f"Could not save the humour setting: {e}"
    if player:
        try:
            player.write_log("JARVIS: mode humour " + ("activé" if veut else "désactivé"))
        except Exception:
            pass
    return CONSIGNE_ON if veut else CONSIGNE_OFF
