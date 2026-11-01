"""
Le fichier que la personne a déposé sur l'interface (bug de Jibis Lucius, 01/11) :
Jarvis répondait « je n'ai pas de souvenir de ce fichier » et cherchait dans sa mémoire
personnelle au lieu d'ouvrir le fichier déposé.
"""
import re
import unicodedata

_MOTS = ("fichier", "file", "document", "pdf", "word", "excel", "powerpoint", "pptx", "docx",
         "xlsx", "csv", "image", "photo", "envoye", "envoyes", "depose", "uploade", "upload",
         "joint", "jointe", "jointes", "joints")


def _simple(t: str) -> str:
    t = unicodedata.normalize("NFD", str(t).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def parle_d_un_fichier(texte: str) -> bool:
    """Vrai si la question ressemble à « le fichier que je t'ai envoyé »."""
    mots = set(re.findall(r"[a-z0-9]+", _simple(texte)))
    return any(m in mots for m in _MOTS)


def indice_fichier(question: str, fichier_depose: str | None) -> str:
    """Phrase à mettre devant le résultat de recall_memory quand la question parle d'un fichier
    et qu'un fichier est déposé sur l'interface. Vide sinon."""
    if not fichier_depose or not parle_d_un_fichier(question):
        return ""
    return (f"[UPLOADED FILE] The user dropped this file on the interface: {fichier_depose}. "
            "This is the file they mean. Do NOT say you have no memory of it: call the "
            "file_processor tool now (it uses this file automatically) to read, summarize or "
            "answer questions about it.")
