"""
core/wayland_input.py — frappes clavier sous Wayland via le portail XDG RemoteDesktop.

Sous Wayland, `pyautogui` ne touche que les fenêtres XWayland. Le portail
`org.freedesktop.portal.RemoteDesktop` permet à GNOME, avec l'autorisation de l'utilisateur, de
recevoir des frappes destinées à n'importe quelle application. Ici : CLAVIER SEULEMENT (ni clic,
ni pointeur).

Principes
- Une seule connexion D-Bus et une seule session pour toute la durée de vie du processus, gérées par
  un fil unique ; chaque frappe n'est qu'un appel `NotifyKeyboardKeysym` sur cette session.
- Keysym et non keycode : le keysym désigne un caractère, GNOME le convertit selon la disposition
  active (AZERTY, accents, AltGr), alors qu'un keycode est une position physique.
- Le jeton de restauration évite la fenêtre d'autorisation aux lancements suivants. Il n'est jamais
  affiché ni journalisé, et n'est pas une preuve de session : seule la réponse `Start` du portail
  rend la session active.
- Aucun succès simulé : refus, portail absent, session perdue → (False, message explicite).
  Un refus n'est jamais redemandé en boucle.
- Une combinaison tente toujours de relâcher toutes les touches qu'elle a enfoncées.

Linux/Wayland seulement ; dépendance : jeepney.
"""
from __future__ import annotations

import json
import os
import queue
import re
import secrets
import sys
import threading
from collections import deque
from pathlib import Path

_BUS = "org.freedesktop.portal.Desktop"
_CHEMIN = "/org/freedesktop/portal/desktop"
_IFACE = "org.freedesktop.portal.RemoteDesktop"
APP_ID = "io.github.fredo_jarvis.JarvisFR"      # doit correspondre à un fichier .desktop de ce nom
_PAS = 0.05
DELAI_AUTORISATION_S = 120.0

ETATS = {
    "inactif": "Clavier Wayland non démarré.",
    "attente": "Clavier Wayland : en attente de l'autorisation de GNOME.",
    "actif": "Clavier Wayland actif.",
    "indisponible": "Clavier Wayland indisponible : portail RemoteDesktop introuvable.",
    "sans_app": "Clavier Wayland indisponible : fichier .desktop de Jarvis introuvable "
                f"({APP_ID}.desktop dans ~/.local/share/applications).",
    "refuse": "Clavier Wayland refusé : GNOME n'a pas autorisé Jarvis à envoyer des frappes "
              "(relance Jarvis pour redemander).",
    "ferme": "Clavier Wayland : la session a été perdue (fermée ou portail disparu), la frappe n'a PAS été envoyée.",
    "erreur": "Clavier Wayland impossible : erreur du portail.",
}

_KEYSYMS = {
    "ctrl": 0xFFE3, "control": 0xFFE3, "shift": 0xFFE1, "alt": 0xFFE9, "altgr": 0xFE03,
    "super": 0xFFEB, "win": 0xFFEB, "windows": 0xFFEB, "meta": 0xFFEB,
    "enter": 0xFF0D, "return": 0xFF0D, "tab": 0xFF09, "esc": 0xFF1B, "escape": 0xFF1B,
    "space": 0x20, "backspace": 0xFF08, "delete": 0xFFFF, "del": 0xFFFF, "insert": 0xFF63,
    "home": 0xFF50, "left": 0xFF51, "up": 0xFF52, "right": 0xFF53, "down": 0xFF54,
    "pageup": 0xFF55, "pagedown": 0xFF56, "end": 0xFF57, "capslock": 0xFFE5, "printscreen": 0xFF61,
    "volumeup": 0x1008FF13, "volumedown": 0x1008FF11, "volumemute": 0x1008FF12,
}
_KEYSYMS.update({f"f{n}": 0xFFBD + n for n in range(1, 13)})


def actif() -> bool:
    return sys.platform.startswith("linux") and bool(os.environ.get("WAYLAND_DISPLAY"))


def keysym_de(nom: str) -> int | None:
    """Nom de touche (« ctrl », « f5 », « a », « é », « € ») -> keysym. None si inconnu."""
    if not isinstance(nom, str) or not nom:
        return None
    k = _KEYSYMS.get(nom.lower())
    if k is not None:
        return k
    if len(nom) == 1:
        return keysym_de_caractere(nom)
    return None


def keysym_de_caractere(c: str) -> int:
    if c == "\n":
        return _KEYSYMS["enter"]
    if c == "\t":
        return _KEYSYMS["tab"]
    cp = ord(c)
    if 0x20 <= cp <= 0x7E or 0xA0 <= cp <= 0xFF:
        return cp                    # latin-1 : keysym = point de code
    return _xkb_keysym(cp) or 0x01000000 + cp      # Unicode


def _xkb_keysym(cp: int) -> int | None:
    """Keysym officiel d'un caractère (œ -> 0x13bd, € -> 0x20ac) : le keysym « 0x01000000 + cp » n'est pas
    reconnu par GNOME quand un keysym historique existe pour la disposition (latin9)."""
    try:
        import ctypes
        f = ctypes.CDLL("libxkbcommon.so.0").xkb_utf32_to_keysym
        f.restype, f.argtypes = ctypes.c_uint32, [ctypes.c_uint32]
        k = f(cp)
        return int(k) or None
    except Exception:
        return None


_CODE_INF_SUP = 86          # touche « < > » (evdev KEY_102ND) des claviers ISO


def _disposition_fr() -> bool:
    """Vrai si la disposition GNOME active est française (xkb « fr… »). GNOME convertit mal les keysyms
    « < » et « > » sur cette disposition (il tape « w » et « x ») : on utilise alors la touche physique."""
    try:
        import ast
        import subprocess
        def lire(cle):
            return subprocess.run(["gsettings", "get", "org.gnome.desktop.input-sources", cle],
                                  capture_output=True, text=True, timeout=2).stdout.strip()
        sources = ast.literal_eval(lire("sources").replace("@a(ss) ", ""))
        courant = int(lire("current").replace("uint32", "").strip() or 0)
        return sources[courant][0] == "xkb" and sources[courant][1].lower().startswith("fr")
    except Exception:
        return False


def _groupe(c: str, fr: bool) -> list[tuple[str, int]]:
    if fr and c == "<":
        return [("c", _CODE_INF_SUP)]
    if fr and c == ">":
        return [("s", _KEYSYMS["shift"]), ("c", _CODE_INF_SUP)]
    return [("s", keysym_de_caractere(c))]


def _dossier_etat() -> Path:
    base = os.environ.get("JARVIS_STATE_DIR")
    return Path(base) if base else Path.home() / ".local" / "state" / "jarvis-fr"


def _fichier_jeton() -> Path:
    return _dossier_etat() / "remotedesktop.json"


def _lire_jeton() -> str | None:
    try:
        v = json.loads(_fichier_jeton().read_text(encoding="utf-8")).get("restore_token")
        return v if isinstance(v, str) and 0 < len(v) < 512 else None
    except Exception:
        return None


def _ecrire_jeton(jeton: str | None) -> None:
    """Écriture atomique 0600 ; jeton None = oubli. Ne lève jamais."""
    try:
        from core.coffre import ecrire_atomique
        chemin = _fichier_jeton()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        if jeton is None:
            chemin.unlink(missing_ok=True)
        else:
            ecrire_atomique(chemin, json.dumps({"restore_token": jeton}))
    except Exception:
        pass


class _Fin(Exception):
    def __init__(self, etat):
        self.etat = etat


class ClavierWayland:
    def __init__(self):
        self.etat = "inactif"
        self._stop = threading.Event()
        self._pret = threading.Event()
        self._cmds: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._conn = None
        self._session = None
        self._enfoncees: list[tuple[str, int]] = []

    # ── cycle de vie ────────────────────────────────────────────────────────

    def demarrer(self, attente: float = DELAI_AUTORISATION_S + 10) -> bool:
        """Ouvre la session (fenêtre d'autorisation de GNOME si nécessaire). Vrai si actif.
        Un refus (ou une autorisation restée sans réponse) n'est pas redemandé : relancer Jarvis pour réessayer."""
        if self.etat == "actif" and self._vivant():
            return True
        if self.etat in ("refuse", "erreur"):
            return False
        self.arreter()
        self._stop.clear()
        self._pret.clear()
        self.etat = "attente"
        self._thread = threading.Thread(target=self._boucle, name="clavier-portail", daemon=True)
        self._thread.start()
        self._pret.wait(attente)
        return self.etat == "actif"

    def arreter(self) -> None:
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=3.0)
        if self.etat in ("actif", "attente", "ferme"):
            self.etat = "inactif"

    def _vivant(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── API de frappe : renvoie toujours (ok, message), ne lève jamais ──────

    def taper(self, texte: str, intervalle: float = 0.0) -> tuple[bool, str]:
        if not isinstance(texte, str) or texte == "":
            return False, "Rien à taper."
        fr = _disposition_fr()
        return self._jouer("texte", [_groupe(c, fr) for c in texte], intervalle)

    def touche(self, nom: str) -> tuple[bool, str]:
        k = keysym_de(nom)
        if k is None:
            return False, f"Touche inconnue : {nom!r}."
        return self._jouer("combo", [("s", k)])

    def combinaison(self, *noms: str) -> tuple[bool, str]:
        if not noms:
            return False, "Aucune touche."
        ks = [keysym_de(n) for n in noms]
        if None in ks:
            return False, f"Touche inconnue : {noms[ks.index(None)]!r}."
        return self._jouer("combo", [("s", k) for k in ks])

    def keycode(self, code: int, maj: bool = False) -> tuple[bool, str]:
        """Touche physique (code evdev, ex. 86 = touche « < > » d'un clavier ISO), avec Maj optionnel.
        Dépend de la disposition : réservé aux cas où le keysym n'est pas fiable."""
        if not isinstance(code, int) or not 1 <= code <= 767:
            return False, f"Code de touche invalide : {code!r}."
        pas = ([("s", _KEYSYMS["shift"])] if maj else []) + [("c", code)]
        return self._jouer("combo", pas)

    def _jouer(self, mode, keysyms, intervalle=0.0) -> tuple[bool, str]:
        if self.etat == "ferme" or (self.etat == "actif" and not self._vivant()):
            self.etat = "ferme"
            msg = ETATS["ferme"]
            self.etat = "inactif"           # le prochain appel tentera de rouvrir (jeton, sinon autorisation)
            return False, msg
        if self.etat != "actif":
            return False, ETATS.get(self.etat, ETATS["erreur"])
        fait = threading.Event()
        res: dict = {}
        self._cmds.put((mode, keysyms, intervalle, fait, res))
        if not fait.wait(5.0 + 0.05 * len(keysyms) * (1 + intervalle * 20)):
            return False, "Clavier Wayland : pas de réponse du portail, frappe non confirmée."
        return res["ok"], res["msg"]

    # ── fil du portail ──────────────────────────────────────────────────────

    def _boucle(self) -> None:
        try:
            self._executer()
        except _Fin as f:
            self._terminer(f.etat)
        except Exception:
            self._terminer("erreur" if self.etat == "attente" else "ferme")
        finally:
            self._relacher_tout()
            c, self._conn = self._conn, None
            try:
                if c is not None:
                    c.close()
            except Exception:
                pass
            if self.etat == "actif":
                self.etat = "inactif"      # arrêt demandé
            self._pret.set()
            self._vider_commandes()

    def _terminer(self, etat) -> None:
        if etat:
            self.etat = etat
        self._pret.set()

    def _vider_commandes(self) -> None:
        while True:
            try:
                _, _, _, fait, res = self._cmds.get_nowait()
            except queue.Empty:
                return
            res.update(ok=False, msg=ETATS["ferme"])
            fait.set()

    def _executer(self) -> None:
        try:
            from jeepney import DBusAddress, MatchRule, message_bus, new_method_call
            from jeepney.io.blocking import Proxy, open_dbus_connection
            conn = open_dbus_connection(bus="SESSION")
        except Exception:
            raise _Fin("indisponible")
        self._conn = conn
        file: deque = deque()
        proxy = Proxy(message_bus, conn)
        for iface, membre in (("org.freedesktop.portal.Request", "Response"),
                              ("org.freedesktop.portal.Session", "Closed")):
            regle = MatchRule(type="signal", interface=iface, member=membre)
            proxy.AddMatch(regle)
            conn.filter(regle, queue=file)
        regle = MatchRule(type="signal", sender="org.freedesktop.DBus", interface="org.freedesktop.DBus",
                          member="NameOwnerChanged")
        regle.add_arg_condition(0, _BUS)
        proxy.AddMatch(regle)
        conn.filter(regle, queue=file)

        def appel(iface, methode, signature, corps):
            adresse = DBusAddress(_CHEMIN, bus_name=_BUS, interface=iface)
            rep = conn.send_and_get_reply(new_method_call(adresse, methode, signature, corps), timeout=10)
            if rep.header.message_type.name == "error":
                raise RuntimeError("erreur D-Bus")
            return rep

        try:
            appel("org.freedesktop.host.portal.Registry", "Register", "sa{sv}", (APP_ID, {}))
        except Exception:
            raise _Fin("sans_app")

        moi = conn.unique_name.lstrip(":").replace(".", "_")

        def requete(methode, signature, corps_sans_jeton, delai):
            """Appelle une méthode du portail qui répond par un signal Response ; renvoie (code, résultats)."""
            jeton = "jarvis_" + secrets.token_hex(6)
            chemin = f"{_CHEMIN}/request/{moi}/{jeton}"
            try:
                appel(_IFACE, methode, signature, corps_sans_jeton(jeton))
            except Exception:
                raise _Fin("indisponible")
            t = 0.0
            while t < delai and not self._stop.is_set():
                try:
                    m = conn.recv_until_filtered(file, timeout=0.5)
                except TimeoutError:
                    t += 0.5
                    continue
                if self._est_perte(m):
                    raise _Fin("ferme")
                if m.header.fields.get(1) == chemin:
                    return m.body
            raise _Fin(None if self._stop.is_set() else "erreur")

        def ouvrir(jeton_restauration):
            code, res = requete("CreateSession", "a{sv}", lambda j: ({
                "handle_token": ("s", j), "session_handle_token": ("s", j + "_s")},), 20)
            if code != 0:
                raise _Fin("refuse")
            session = res["session_handle"][1]
            opts = {"types": ("u", 1), "persist_mode": ("u", 2)}      # clavier ; mémorisé jusqu'à révocation
            if jeton_restauration:
                opts["restore_token"] = ("s", jeton_restauration)
            code, _ = requete("SelectDevices", "oa{sv}",
                              lambda j: (session, dict(opts, handle_token=("s", j))), 20)
            if code != 0:
                return session, code, {}
            code, res = requete("Start", "osa{sv}",
                                lambda j: (session, "", {"handle_token": ("s", j)}), DELAI_AUTORISATION_S)
            return session, code, res

        jeton = _lire_jeton()
        session, code, res = ouvrir(jeton)
        if code == 2 and jeton:            # jeton périmé ou rejeté : un seul nouvel essai, sans jeton
            _ecrire_jeton(None)
            session, code, res = ouvrir(None)
        if code != 0:
            raise _Fin("refuse")
        peripheriques = res.get("devices", ("u", 0))[1]
        if not peripheriques & 1:
            raise _Fin("refuse")           # le portail n'a pas accordé le clavier
        nouveau = res.get("restore_token", (None, None))[1]
        if isinstance(nouveau, str) and nouveau:
            _ecrire_jeton(nouveau)
        self._session = session
        self.etat = "actif"                # seulement après la confirmation du portail
        self._pret.set()

        def notifier(touche, etat):
            genre, valeur = touche
            methode = "NotifyKeyboardKeycode" if genre == "c" else "NotifyKeyboardKeysym"
            appel(_IFACE, methode, "oa{sv}iu", (session, {}, valeur, etat))

        self._notifier = notifier
        while not self._stop.is_set():
            try:
                m = conn.recv_until_filtered(file, timeout=_PAS)
                if self._est_perte(m):
                    raise _Fin("ferme")
            except TimeoutError:
                pass
            try:
                mode, keysyms, intervalle, fait, res = self._cmds.get_nowait()
            except queue.Empty:
                continue
            try:
                self._executer_commande(mode, keysyms, intervalle)
                res.update(ok=True, msg="")
            except Exception:
                self.etat = "ferme"
                res.update(ok=False, msg=ETATS["ferme"])
                fait.set()
                raise _Fin("ferme")
            fait.set()

    def _est_perte(self, m) -> bool:
        membre = m.header.fields.get(3)
        if membre == "NameOwnerChanged":
            return len(m.body) >= 3 and m.body[2] == ""
        if membre == "Closed":
            return m.header.fields.get(1) in (None, self._session)
        return False

    # ── envoi des touches (dans le fil du portail) ──────────────────────────

    def _envoyer(self, touche: tuple[str, int], etat: int) -> None:
        if etat:
            self._enfoncees.append(touche)      # noté avant l'envoi : relâché même si l'envoi échoue
        self._notifier(touche, etat)
        if not etat and touche in self._enfoncees:
            self._enfoncees.remove(touche)

    def _executer_commande(self, mode, keysyms, intervalle) -> None:
        try:
            if mode == "texte":
                for groupe in keysyms:          # un caractère = une ou plusieurs touches
                    for k in groupe:
                        self._envoyer(k, 1)
                    for k in reversed(groupe):
                        self._envoyer(k, 0)
                    if intervalle:
                        self._stop.wait(intervalle)
            else:
                for k in keysyms:
                    self._envoyer(k, 1)
                for k in reversed(keysyms):
                    self._envoyer(k, 0)
        finally:
            self._relacher_tout()

    def _relacher_tout(self) -> None:
        """Tente de relâcher chaque touche encore enfoncée, même si l'une des relâches échoue."""
        notifier = getattr(self, "_notifier", None)
        while self._enfoncees:
            k = self._enfoncees.pop()
            try:
                if notifier is not None:
                    notifier(k, 0)
            except Exception:
                pass


_instance: ClavierWayland | None = None
_verrou = threading.Lock()


def clavier() -> ClavierWayland:
    global _instance
    with _verrou:
        if _instance is None:
            _instance = ClavierWayland()
        return _instance


def garantir() -> ClavierWayland:
    """Session prête si possible : ouverture à la première demande, réutilisée ensuite."""
    c = clavier()
    if c.etat != "actif" or not c._vivant():
        c.demarrer()
    return c
