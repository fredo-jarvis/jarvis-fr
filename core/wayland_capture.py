"""
core/wayland_capture.py — capture d'écran sous Wayland via le portail XDG Screenshot.

Sous Wayland, ni `mss` ni `pyautogui.screenshot` ne peuvent lire l'écran. Le portail
`org.freedesktop.portal.Screenshot` (service de la session, aucun service ajouté) fait la capture
pour le compte de l'application. GNOME demande l'autorisation la première fois ; l'utilisateur peut
refuser : on le dit explicitement, on ne simule jamais une capture.

Linux/Wayland seulement. Dépendance : `jeepney` (pur Python, déjà présent avec `keyring`).
"""
from __future__ import annotations

import os
import secrets
import sys
from collections import deque
from urllib.parse import unquote, urlparse

DELAI_S = 60.0            # le temps de répondre à la fenêtre d'autorisation de GNOME
_BUS = "org.freedesktop.portal.Desktop"
_CHEMIN = "/org/freedesktop/portal/desktop"
_IFACE = "org.freedesktop.portal.Screenshot"


class CaptureErreur(RuntimeError):
    """etat : « indisponible », « refuse », « annule », « delai » ou « erreur »."""

    def __init__(self, etat: str, detail: str = ""):
        self.etat = etat
        super().__init__(MESSAGES.get(etat, etat) + (f" ({detail})" if detail else ""))


MESSAGES = {
    "indisponible": "Capture d'écran indisponible : portail XDG Screenshot introuvable sur cette session.",
    "refuse": "Capture d'écran refusée : autorise Jarvis à faire des captures dans la fenêtre de GNOME.",
    "annule": "Capture d'écran annulée.",
    "delai": "Capture d'écran : pas de réponse du portail à temps.",
    "erreur": "Capture d'écran impossible : erreur du portail.",
}


def actif() -> bool:
    """Vrai sur une session Linux Wayland : c'est là que mss et pyautogui ne fonctionnent pas."""
    return sys.platform.startswith("linux") and bool(os.environ.get("WAYLAND_DISPLAY"))


def _demander(delai: float = DELAI_S) -> str:
    """Appelle le portail et renvoie le chemin du fichier PNG produit."""
    try:
        from jeepney import DBusAddress, MatchRule, message_bus, new_method_call
        from jeepney.io.blocking import Proxy, open_dbus_connection
    except Exception as e:
        raise CaptureErreur("indisponible", type(e).__name__)
    try:
        conn = open_dbus_connection(bus="SESSION")
    except Exception as e:
        raise CaptureErreur("indisponible", type(e).__name__)
    try:
        jeton = "jarvis_" + secrets.token_hex(6)
        expediteur = conn.unique_name.lstrip(":").replace(".", "_")
        requete = f"{_CHEMIN}/request/{expediteur}/{jeton}"
        regle = MatchRule(type="signal", interface="org.freedesktop.portal.Request", member="Response",
                          path=requete)
        Proxy(message_bus, conn).AddMatch(regle)
        file = deque()
        conn.filter(regle, queue=file)
        adresse = DBusAddress(_CHEMIN, bus_name=_BUS, interface=_IFACE)
        appel = new_method_call(adresse, "Screenshot", "sa{sv}",
                                ("", {"handle_token": ("s", jeton), "interactive": ("b", False)}))
        try:
            conn.send_and_get_reply(appel, timeout=10)
        except Exception as e:
            raise CaptureErreur("indisponible", type(e).__name__)
        try:
            msg = conn.recv_until_filtered(file, timeout=delai)
        except TimeoutError:
            raise CaptureErreur("delai")
        code, resultats = msg.body
        if code == 1:
            raise CaptureErreur("annule")
        if code != 0:
            raise CaptureErreur("refuse" if code == 2 else "erreur", f"code {code}")
        uri = resultats.get("uri", (None, None))[1]
        if not uri or not uri.startswith("file://"):
            raise CaptureErreur("erreur", "pas de fichier")
        return unquote(urlparse(uri).path)
    finally:
        conn.close()


def capturer(delai: float = DELAI_S):
    """Capture tout le bureau et renvoie une image PIL RGB. Lève CaptureErreur."""
    from PIL import Image
    chemin = _demander(delai)
    try:
        with Image.open(chemin) as im:
            image = im.convert("RGB")
            image.load()
        return image
    except OSError as e:
        raise CaptureErreur("erreur", type(e).__name__)
    finally:
        try:
            os.unlink(chemin)         # fichier créé par le portail pour nous seuls
        except OSError:
            pass
