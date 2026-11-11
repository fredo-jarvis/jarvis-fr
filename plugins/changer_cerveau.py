"""
Plugin : passer Jarvis sur son cerveau local (Ollama, sur le PC) ou le remettre en ligne.

    « Jarvis, passe sur ton cerveau local »

Une fois en local, Gemini est coupé : on repasse en ligne en disant ou tapant « repasse sur ton cerveau en ligne ».
"""

PLUGIN = {
    "name": "changer_cerveau",
    "description": (
        "Switches Jarvis to its LOCAL brain (Ollama on this PC, offline, free) or back online. Use ONLY when the user "
        "explicitly asks: 'passe sur ton cerveau local', 'passe en local', 'mode hors ligne'. Never for a question about "
        "the local brain. After calling it, say nothing more: this conversation closes and the local voice takes over."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"cerveau": {"type": "STRING", "description": "'local' or 'cloud'"}},
        "required": ["cerveau"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        if player is None or not hasattr(player, "changer_cerveau"):
            return "Je ne peux pas changer de cerveau pour le moment."
        voulu = "local" if str((parameters or {}).get("cerveau", "")).strip().lower() == "local" else "cloud"
        return player.changer_cerveau(voulu)
    except Exception as e:
        return f"Je n'ai pas réussi à changer de cerveau : {e}"
