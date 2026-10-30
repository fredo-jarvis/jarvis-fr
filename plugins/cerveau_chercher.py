"""
Plugin : chercher dans le cerveau de l'utilisateur (wiki Obsidian tenu par Claude Code).
"""
from plugins._cerveau_commun import MAX_REPONSE, chercher, extrait, nom

PLUGIN = {
    "name": "chercher_cerveau",
    "description": (
        "Search the user's second brain (his Obsidian wiki kept by Claude Code) for "
        "projects, decisions, past conversations, YouTube episodes, to-do list, "
        "people and lessons learned. Use it whenever the user asks what was decided, "
        "where a project stands, what was said before, or anything about his "
        "projects that is not in the summary sheet. Pass the question in French. "
        "Answer from the returned text only, and say so if nothing was found. "
        "Do NOT use recall_memory for these topics; use this tool."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "question": {"type": "STRING", "description": "Ce que l'utilisateur veut savoir, en mots clés français"},
        },
        "required": ["question"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    question = (parameters.get("question") or "").strip()
    try:
        trouves = chercher(question)
        if not trouves:
            return f"Rien trouvé dans le cerveau pour « {question} »."
        morceaux = [f"[Page {nom(page)}]\n{extrait(texte, question)}" for _, page, texte in trouves]
        reponse = "Extraits du cerveau :\n\n" + "\n\n".join(morceaux)
    except Exception as e:
        return f"Je n'ai pas pu lire le cerveau : {e}"
    if player:
        try:
            player.write_log(f"JARVIS: cerveau consulté ({question})")
        except Exception:
            pass
    return reponse[:MAX_REPONSE]
