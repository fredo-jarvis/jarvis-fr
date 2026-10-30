"""
Plugin : noter quelque chose dans le carnet du cerveau.
Le Jarvis vocal n'écrit jamais dans les pages du wiki : il écrit dans le carnet,
et Claude Code range ensuite les notes dans le cerveau.
"""
from plugins._cerveau_commun import noter

PLUGIN = {
    "name": "noter_dans_cerveau",
    "description": (
        "Write a note in the user's second-brain notebook so Claude Code files it "
        "in the wiki later. Use it when the user says 'note ça dans le cerveau', "
        "'retiens ça pour Claude', 'dis à Claude que…', or gives an idea, a "
        "decision or a task for his projects. Write the note in French, one clear "
        "sentence. For small personal facts about the user themselves, save_memory is fine."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "note": {"type": "STRING", "description": "La note à garder, en une phrase claire en français"},
        },
        "required": ["note"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    note = (parameters.get("note") or "").strip()
    if not note:
        return "Il n'y avait rien à noter."
    try:
        noter(note)
    except Exception as e:
        return f"Je n'ai pas pu écrire dans le carnet : {e}"
    if player:
        try:
            player.write_log(f"JARVIS: noté dans le carnet du cerveau")
        except Exception:
            pass
    return "C'est noté dans le carnet du cerveau. Claude Code le rangera à la prochaine séance."
