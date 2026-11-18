"""
core/wayland_shortcuts.py — raccourci global (push-to-talk) via le portail XDG GlobalShortcuts.

Sous Wayland une application ne peut pas lire le clavier hors de sa fenêtre. Le portail
`org.freedesktop.portal.GlobalShortcuts` enregistre un raccourci auprès de GNOME, qui envoie les
signaux `Activated` (touche enfoncée) et `Deactivated` (touche relâchée). GNOME demande à
l'utilisateur de valider l'enregistrement et peut lui faire choisir une autre touche : la touche
demandée n'est qu'une préférence.

Un seul fil et une seule session D-Bus pour toute la durée de vie. Rien ne lève vers l'appelant :
refus, portail absent, session fermée ou portail disparu aboutissent à `etat` explicite et à un
relâchement de la touche (jamais de mode écoute bloqué). Linux/Wayland seulement ; dépendance : jeepney.
"""
from __future__ import annotations

import os
import secrets
import sys
import threading
from collections import deque
from typing import Callable

_BUS = "org.freedesktop.portal.Desktop"
_CHEMIN = "/org/freedesktop/portal/desktop"
_IFACE = "org.freedesktop.portal.GlobalShortcuts"
_ID = "jarvis-push-to-talk"
APP_ID = "io.github.jeromecamilleri.JarvisFR"   # doit correspondre à un fichier .desktop de ce nom
_PAS = 0.5                 # période de contrôle de l'arrêt dans la boucle de réception

_TOUCHES = {"ctrl": "CTRL", "shift": "SHIFT", "alt": "ALT", "space": "space", "f8": "F8",
            "f9": "F9", "f10": "F10", "capslock": "Caps_Lock", "insert": "Insert"}

ETATS = {
    "inactif": "Raccourci global non démarré.",
    "attente": "Raccourci global : en attente de la réponse de GNOME.",
    "actif": "Raccourci global actif.",
    "indisponible": "Raccourci global indisponible : portail GlobalShortcuts introuvable.",
    "sans_app": "Raccourci global indisponible : fichier .desktop de Jarvis introuvable "
                f"({APP_ID}.desktop dans ~/.local/share/applications).",
    "refuse": "Raccourci global refusé par GNOME : le raccourci reste limité à la fenêtre de Jarvis.",
    "ferme": "Raccourci global perdu (session ou portail fermé) : retour au raccourci de fenêtre.",
    "erreur": "Raccourci global impossible : erreur du portail.",
}


def actif() -> bool:
    return sys.platform.startswith("linux") and bool(os.environ.get("WAYLAND_DISPLAY"))


def trigger(chord) -> str:
    """('ctrl','space') -> 'CTRL+space' (format de préférence du portail)."""
    return "+".join(_TOUCHES.get(k, k) for k in chord)


class RaccourciGlobal:
    """Appelle on_change(True/False) à l'activation / désactivation du raccourci."""

    def __init__(self, on_change: Callable[[bool], None], chord=("ctrl", "space")):
        self._on_change = on_change
        self._chord = tuple(chord)
        self._stop = threading.Event()
        self._pret = threading.Event()      # posé dès que le résultat de l'enregistrement est connu
        self._thread: threading.Thread | None = None
        self._conn = None
        self.etat = "inactif"
        self.trigger_obtenu = ""

    def demarrer(self, attente: float = 30.0) -> bool:
        """Enregistre le raccourci. Attend la décision de GNOME au plus `attente` s. Vrai si actif."""
        self.arreter()
        self._stop.clear()
        self._pret.clear()
        self.etat = "attente"
        self._thread = threading.Thread(target=self._boucle, name="ptt-portail", daemon=True)
        self._thread.start()
        self._pret.wait(attente)
        return self.etat == "actif"

    def arreter(self) -> None:
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=2.0)
        self._relacher()
        if self.etat in ("actif", "attente"):
            self.etat = "inactif"

    # ── interne ─────────────────────────────────────────────────────────────

    def _relacher(self) -> None:
        try:
            self._on_change(False)
        except Exception:
            pass

    def _fin(self, etat: str) -> None:
        self.etat = etat
        self._pret.set()
        self._relacher()        # jamais bloqué en écoute si le portail disparaît

    def _boucle(self) -> None:
        try:
            self._executer()
        except Exception:
            if self.etat in ("attente", "actif"):
                self._fin("erreur" if self.etat == "attente" else "ferme")
        finally:
            c, self._conn = self._conn, None
            try:
                if c is not None:
                    c.close()
            except Exception:
                pass
            if self.etat == "actif":      # arrêt demandé : la session est fermée avec la connexion
                self.etat = "inactif"
            self._pret.set()

    def _executer(self) -> None:
        try:
            from jeepney import DBusAddress, MatchRule, message_bus, new_method_call
            from jeepney.io.blocking import Proxy, open_dbus_connection
            conn = open_dbus_connection(bus="SESSION")
        except Exception:
            return self._fin("indisponible")
        self._conn = conn
        file: deque = deque()
        proxy = Proxy(message_bus, conn)
        for iface, membre in (("org.freedesktop.portal.Request", "Response"),
                              (_IFACE, "Activated"), (_IFACE, "Deactivated"),
                              ("org.freedesktop.portal.Session", "Closed")):
            regle = MatchRule(type="signal", interface=iface, member=membre)
            proxy.AddMatch(regle)
            conn.filter(regle, queue=file)
        regle = MatchRule(type="signal", sender="org.freedesktop.DBus", interface="org.freedesktop.DBus",
                          member="NameOwnerChanged")
        regle.add_arg_condition(0, _BUS)
        proxy.AddMatch(regle)
        conn.filter(regle, queue=file)

        registre = DBusAddress(_CHEMIN, bus_name=_BUS, interface="org.freedesktop.host.portal.Registry")
        try:
            rep = conn.send_and_get_reply(new_method_call(registre, "Register", "sa{sv}", (APP_ID, {})),
                                          timeout=10)
            if rep.header.message_type.name == "error":
                return self._fin("sans_app")
        except Exception:
            return self._fin("indisponible")

        adresse = DBusAddress(_CHEMIN, bus_name=_BUS, interface=_IFACE)
        moi = conn.unique_name.lstrip(":").replace(".", "_")

        def requete(methode, signature, corps, jeton):
            chemin = f"{_CHEMIN}/request/{moi}/{jeton}"
            try:
                conn.send_and_get_reply(new_method_call(adresse, methode, signature, corps), timeout=10)
            except Exception:
                raise _Fin("indisponible")
            return chemin

        def reponse(chemin, delai):
            t = 0.0
            while t < delai and not self._stop.is_set():
                try:
                    m = conn.recv_until_filtered(file, timeout=_PAS)
                except TimeoutError:
                    t += _PAS
                    continue
                if self._est_fin_portail(m):
                    raise _Fin("ferme")
                if m.header.fields.get(1) == chemin:      # champ PATH
                    return m.body
            raise _Fin("erreur") if not self._stop.is_set() else _Fin(None)

        try:
            jeton = "jarvis_" + secrets.token_hex(6)
            chemin = requete("CreateSession", "a{sv}", ({"handle_token": ("s", jeton),
                             "session_handle_token": ("s", jeton + "_s")},), jeton)
            code, res = reponse(chemin, 20)
            if code != 0:
                raise _Fin("refuse")
            session = res["session_handle"][1]

            jeton = "jarvis_" + secrets.token_hex(6)
            souhait = {"description": ("s", "Push-to-talk Jarvis"),
                       "preferred_trigger": ("s", trigger(self._chord))}
            chemin = requete("BindShortcuts", "oa(sa{sv})sa{sv}",
                             (session, [(_ID, souhait)], "", {"handle_token": ("s", jeton)}), jeton)
            code, res = reponse(chemin, 120)       # l'utilisateur peut devoir valider une fenêtre
            if code != 0:
                raise _Fin("refuse")
            for ident, props in res.get("shortcuts", (None, []))[1]:
                if ident == _ID:
                    self.trigger_obtenu = props.get("trigger_description", ("s", ""))[1]
        except _Fin as f:
            if f.etat:
                self._fin(f.etat)
            return
        self.etat = "actif"
        self._pret.set()

        while not self._stop.is_set():
            try:
                m = conn.recv_until_filtered(file, timeout=_PAS)
            except TimeoutError:
                continue
            if self._est_fin_portail(m):
                return self._fin("ferme")
            membre = m.header.fields.get(3)           # champ MEMBER
            if membre == "Closed":
                return self._fin("ferme")
            if membre in ("Activated", "Deactivated") and m.body[1] == _ID:
                try:
                    self._on_change(membre == "Activated")
                except Exception:
                    pass

    @staticmethod
    def _est_fin_portail(m) -> bool:
        if m.header.fields.get(3) == "NameOwnerChanged":
            return len(m.body) >= 3 and m.body[2] == ""
        return False


class _Fin(Exception):
    def __init__(self, etat):
        self.etat = etat
