"""
core/coffre.py — les secrets ne sont plus jamais écrits en clair sur le disque (1.1.3).

Sous Windows, le secret est chiffré par Windows lui-même (DPAPI, la même protection que les mots
de passe enregistrés de Windows) : le texte chiffré n'est lisible que par TA session Windows, sur
CE PC. Copié ailleurs (sauvegarde, clé USB, partage, dépôt), le fichier ne révèle rien.

Ce n'est pas une protection contre un programme malveillant qui tourne déjà sous ta session :
rien ne l'est complètement. C'est pour ça que Gmail passe par un « mot de passe d'application »
(révocable à tout moment chez Google) et que Jarvis n'y fait que de la lecture.

Sous Linux, le secret est rangé dans le trousseau de session (Secret Service : GNOME Keyring) et le
fichier de configuration ne contient qu'une référence « keyring:jarvis-fr/<nom> ». Si le trousseau est
verrouillé ou absent, `chiffrer` renvoie None et l'appelant garde l'ancien comportement (fichier lisible
seulement par l'utilisateur) : jamais de secret supprimé ni de référence remplacée par du clair.
Un secret déjà présent dans le trousseau avec une autre valeur n'est jamais écrasé.
"""
from __future__ import annotations

import base64
import ctypes
import os
import re
import sys
import tempfile
import threading
from pathlib import Path

PREFIXE = "dpapi:"
SERVICE = "jarvis-fr"
PREFIXE_TROUSSEAU = "keyring:" + SERVICE + "/"
NOM_DEFAUT = "gmail_mot_de_passe_app"
DELAI_S = 20.0          # attente maximale d'un trousseau verrouillé (fenêtre de déverrouillage)
_NOM = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class CoffreErreur(Exception):
    """etat : « verrouille », « indisponible », « conflit » ou « invalide »."""

    def __init__(self, etat: str, detail: str = ""):
        super().__init__(f"{etat}: {detail}" if detail else etat)
        self.etat = etat


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _Blob:
    buf = ctypes.create_string_buffer(data, len(data))
    b = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    b._buf = buf          # garde le tampon en vie
    return b


def _dpapi() -> bool:
    """Vrai sous Windows : chemin DPAPI, inchangé. Ne dit rien d'un trousseau Linux."""
    return sys.platform == "win32"


_SONDE = "__sonde_jarvis__"        # nom jamais écrit : on ne fait que le lire


def etat() -> str:
    """État réel du coffre sur ce poste : « disponible », « verrouille » (trousseau verrouillé ou sans
    réponse en DELAI_S) ou « indisponible » (aucun backend, ni trousseau). Mêmes états que proteger().
    Linux : lecture d'une entrée inexistante, donc rien n'est créé ni modifié ; peut durer jusqu'à DELAI_S."""
    if _dpapi():
        return "disponible"
    if not sys.platform.startswith("linux"):
        return "indisponible"
    try:
        _executer(_backend().get_password, SERVICE, _SONDE)
        return "disponible"
    except CoffreErreur as e:
        return e.etat


def disponible() -> bool:
    """Vrai si un secret peut être rangé et relu maintenant (DPAPI sous Windows, trousseau déverrouillé
    sous Linux). Ne pas utiliser pour choisir DPAPI : voir _dpapi()."""
    return etat() == "disponible"


def _backend():
    try:
        import keyring
        from keyring.backends import fail
        kr = keyring.get_keyring()
    except Exception as e:
        raise CoffreErreur("indisponible", type(e).__name__)
    if isinstance(kr, fail.Keyring) or getattr(kr, "priority", 1) < 1:
        raise CoffreErreur("indisponible", "aucun trousseau")
    return keyring


def _executer(fn, *args):
    """Appel au trousseau borné à DELAI_S : un trousseau verrouillé attend sinon indéfiniment."""
    res: dict = {}

    def travail():
        try:
            res["v"] = fn(*args)
        except BaseException as e:
            res["e"] = e

    t = threading.Thread(target=travail, daemon=True, name="coffre-trousseau")
    t.start()
    t.join(DELAI_S)
    if t.is_alive():
        raise CoffreErreur("verrouille", f"pas de réponse en {DELAI_S:.0f} s")
    if "e" in res:
        e = res["e"]
        nom = type(e).__name__
        raise CoffreErreur("verrouille" if "Locked" in nom else "indisponible", nom)
    return res.get("v")


def _nom_de_reference(valeur: str) -> str | None:
    if not valeur or not valeur.startswith(PREFIXE_TROUSSEAU):
        return None
    nom = valeur[len(PREFIXE_TROUSSEAU):]
    return nom if _NOM.match(nom) else None


def proteger(texte: str, nom: str = NOM_DEFAUT) -> tuple[str | None, str]:
    """Range le secret. Renvoie (référence ou None, état) ; état « disponible » si réussi,
    sinon « verrouille », « indisponible », « conflit » ou « invalide ». Ne lève jamais."""
    if texte is None:
        return None, "invalide"
    if _dpapi():
        ref = chiffrer(texte)
        return ref, "disponible" if ref else "indisponible"
    if not sys.platform.startswith("linux"):
        return None, "indisponible"
    if not _NOM.match(nom or "") or texte == "":
        return None, "invalide"
    try:
        kr = _backend()
        existant = _executer(kr.get_password, SERVICE, nom)
        if existant is not None and existant != texte:
            return None, "conflit"          # jamais d'écrasement
        if existant is None:
            _executer(kr.set_password, SERVICE, nom, texte)
            if _executer(kr.get_password, SERVICE, nom) != texte:
                return None, "indisponible"
        return PREFIXE_TROUSSEAU + nom, "disponible"
    except CoffreErreur as e:
        return None, e.etat


def chiffrer(texte: str, nom: str = NOM_DEFAUT) -> str | None:
    """Windows : « dpapi:… » (base64). Linux : « keyring:jarvis-fr/<nom> » après stockage et relecture
    exacte dans le trousseau. None si indisponible (trousseau absent, verrouillé, conflit)."""
    if not _dpapi():
        return proteger(texte, nom)[0] if texte is not None else None
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
    nom = _nom_de_reference(valeur) if sys.platform.startswith("linux") else None
    if nom:
        try:
            return _executer(_backend().get_password, SERVICE, nom)
        except CoffreErreur:
            return None
    if not valeur or not valeur.startswith(PREFIXE) or not _dpapi():
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


def ecrire_atomique(chemin, texte: str, mode: int = 0o600) -> None:
    """Écrit via un fichier temporaire du même dossier puis os.replace : l'original reste intact en cas d'erreur."""
    chemin = Path(chemin)
    fd, tmp = tempfile.mkstemp(dir=str(chemin.parent), prefix=chemin.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(texte)
            f.flush()
            os.fsync(f.fileno())
        if not sys.platform.startswith("win"):
            os.chmod(tmp, mode)
        os.replace(tmp, chemin)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
