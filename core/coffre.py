"""
core/coffre.py — les secrets ne sont plus jamais écrits en clair sur le disque (1.1.3).

Sous Windows, le secret est chiffré par Windows lui-même (DPAPI, la même protection que les mots
de passe enregistrés de Windows) : le texte chiffré n'est lisible que par TA session Windows, sur
CE PC. Copié ailleurs (sauvegarde, clé USB, partage, dépôt), le fichier ne révèle rien.

Ce n'est pas une protection contre un programme malveillant qui tourne déjà sous ta session :
rien ne l'est complètement. C'est pour ça que Gmail passe par un « mot de passe d'application »
(révocable à tout moment chez Google) et que Jarvis n'y fait que de la lecture.

Hors Windows, on ne sait pas chiffrer sans dépendance : `chiffrer` renvoie None et l'appelant
garde l'ancien comportement (fichier lisible seulement par l'utilisateur).
"""
from __future__ import annotations

import base64
import ctypes
import sys

PREFIXE = "dpapi:"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _Blob:
    buf = ctypes.create_string_buffer(data, len(data))
    b = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    b._buf = buf          # garde le tampon en vie
    return b


def disponible() -> bool:
    return sys.platform == "win32"


def chiffrer(texte: str) -> str | None:
    """Renvoie « dpapi:… » (base64), ou None si le chiffrement n'est pas disponible."""
    if not disponible() or texte is None:
        return None
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    entree, sortie = _blob(texte.encode("utf-8")), _Blob()
    # CRYPTPROTECT_UI_FORBIDDEN = 0x1 : jamais de fenêtre
    if not crypt32.CryptProtectData(ctypes.byref(entree), "Jarvis", None, None, None, 0x1, ctypes.byref(sortie)):
        return None
    try:
        brut = ctypes.string_at(sortie.pbData, sortie.cbData)
    finally:
        kernel32.LocalFree(sortie.pbData)
    return PREFIXE + base64.b64encode(brut).decode("ascii")


def dechiffrer(valeur: str) -> str | None:
    """Rend le secret en clair (en mémoire seulement), ou None s'il est illisible ici."""
    if not valeur or not valeur.startswith(PREFIXE) or not disponible():
        return None
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    try:
        entree = _blob(base64.b64decode(valeur[len(PREFIXE):]))
    except Exception:
        return None
    sortie = _Blob()
    if not crypt32.CryptUnprotectData(ctypes.byref(entree), None, None, None, None, 0x1, ctypes.byref(sortie)):
        return None
    try:
        return ctypes.string_at(sortie.pbData, sortie.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(sortie.pbData)
