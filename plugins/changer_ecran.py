"""
Plugin : changer Jarvis d'écran (quand on a plusieurs écrans).

    « Jarvis, passe sur l'écran suivant »     « Jarvis, change d'écran »     « mets-toi sur mon autre écran »

Même chose que la touche F3. Chaque demande envoie Jarvis sur l'écran d'après, en faisant le tour.
"""

PLUGIN = {
    "name": "changer_ecran",
    "description": (
        "Moves Jarvis' window to the NEXT monitor when the user has several screens. Use for "
        "'change d'écran', 'passe sur l'écran suivant', 'mets-toi sur mon deuxième écran', "
        "'déplace-toi sur l'autre écran', 'move to the next screen'. Each call goes one screen "
        "further and loops around. Say in one short sentence that you moved."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        if player is None or not hasattr(player, "changer_ecran"):
            return "Je ne peux pas changer d'écran pour le moment."
        if not player.changer_ecran():
            return "Je ne vois qu'un seul écran sur ce PC."
        return "C'est fait, je passe sur l'écran suivant."
    except Exception as e:
        return f"Je n'ai pas réussi à changer d'écran : {e}"
