"""
Plugin : lire une page précise du cerveau de l'utilisateur.
"""
from plugins._cerveau_commun import MAX_REPONSE, lire, nom

PLUGIN = {
    "name": "lire_page_cerveau",
    "description": (
        "Read one page of the user's second brain by its name, for example "
        "'a-faire' (to-do list), 'mes-projets', 'idees', "
        "'index', 'log'. Use it after chercher_cerveau when one "
        "page needs to be read in more detail, or when the user names a page."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "page": {"type": "STRING", "description": "Nom ou morceau du nom de la page, par exemple a-faire"},
        },
        "required": ["page"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    demande = (parameters.get("page") or "").strip()
    try:
        page, texte = lire(demande)
    except Exception as e:
        return f"Je n'ai pas pu lire le cerveau : {e}"
    if not page:
        return f"Aucune page du cerveau ne s'appelle « {demande} »."
    if len(texte) > MAX_REPONSE:
        texte = texte[:MAX_REPONSE] + "\n[... page coupée, demander une recherche plus précise]"
    return f"[Page {nom(page)}]\n{texte}"
