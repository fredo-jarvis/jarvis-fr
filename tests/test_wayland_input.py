import json
import os
import stat
import sys
import threading
import time
import types

import pytest

from core import wayland_input as wi

CHEMIN = "/org/freedesktop/portal/desktop"
JETON = "JETON-SECRET-XYZ"


class Msg:
    def __init__(self, membre, corps, chemin=None, erreur=False):
        self.header = types.SimpleNamespace(
            fields={3: membre, 1: chemin},
            message_type=types.SimpleNamespace(name="error" if erreur else "method_return"))
        self.body = corps


class FauxBus:
    def __init__(self):
        self.unique_name = ":1.7"
        self.events, self.appels, self.notifs = [], [], []
        self.cv = threading.Condition()
        self.closed = False
        self.start_code = 0
        self.start_codes = None          # liste de codes successifs pour Start
        self.devices = 1
        self.register_ok = True
        self.echec_notif_apres = None    # n-ième notification qui échoue
        self.jetons_recus = []

    def push(self, m):
        with self.cv:
            self.events.append(m)
            self.cv.notify_all()

    def send_and_get_reply(self, appel, timeout=None):
        methode, corps = appel
        self.appels.append(methode)
        if methode == "Register":
            return Msg("", (), erreur=not self.register_ok)
        if methode in ("NotifyKeyboardKeysym", "NotifyKeyboardKeycode"):
            if self.echec_notif_apres is not None and len(self.notifs) >= self.echec_notif_apres:
                self.echec_notif_apres = None
                return Msg("", (), erreur=True)
            self.notifs.append((corps[2], corps[3]) if methode == "NotifyKeyboardKeysym" else ("code", corps[2], corps[3]))
            return Msg("", ())
        opts = corps[0] if methode == "CreateSession" else corps[-1] if methode == "Start" else corps[1]
        chemin = f"{CHEMIN}/request/1_7/{opts['handle_token'][1]}"
        if methode == "CreateSession":
            self.push(Msg("Response", (0, {"session_handle": ("s", "/sess/9")}), chemin))
        elif methode == "SelectDevices":
            self.jetons_recus.append(opts.get("restore_token", (None, None))[1])
            assert opts["types"] == ("u", 1)
            self.push(Msg("Response", (0, {}), chemin))
        else:
            code = self.start_codes.pop(0) if self.start_codes else self.start_code
            res = {"devices": ("u", self.devices), "restore_token": ("s", JETON)} if code == 0 else {}
            self.push(Msg("Response", (code, res), chemin))
        return Msg("", ())

    def filter(self, regle, queue=None):
        pass

    def recv_until_filtered(self, file, timeout=None):
        fin = time.monotonic() + (timeout or 0)
        with self.cv:
            while not self.events:
                reste = fin - time.monotonic()
                if reste <= 0:
                    raise TimeoutError
                self.cv.wait(min(reste, 0.02))
            return self.events.pop(0)

    def close(self):
        self.closed = True


@pytest.fixture
def bus(monkeypatch, tmp_path):
    b = FauxBus()
    jeepney = types.ModuleType("jeepney")
    jeepney.DBusAddress = lambda *a, **k: None
    jeepney.message_bus = None
    jeepney.new_method_call = lambda adresse, m, sig, corps: (m, corps)

    class Regle:
        def __init__(self, **k): pass
        def add_arg_condition(self, *a): pass
    jeepney.MatchRule = Regle
    blocking = types.ModuleType("jeepney.io.blocking")
    blocking.Proxy = lambda *a: types.SimpleNamespace(AddMatch=lambda r: None)
    blocking.open_dbus_connection = lambda bus="SESSION": b
    monkeypatch.setitem(sys.modules, "jeepney", jeepney)
    monkeypatch.setitem(sys.modules, "jeepney.io", types.ModuleType("jeepney.io"))
    monkeypatch.setitem(sys.modules, "jeepney.io.blocking", blocking)
    monkeypatch.setenv("JARVIS_STATE_DIR", str(tmp_path / "etat"))
    return b


def clavier(attente=5):
    c = wi.ClavierWayland()
    return c, c.demarrer(attente=attente)


def attend(cond, delai=2):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_keysyms_azerty_accents_ponctuation():
    assert wi.keysym_de_caractere("a") == 0x61
    assert wi.keysym_de_caractere("é") == 0xE9
    assert wi.keysym_de_caractere("ç") == 0xE7
    assert wi.keysym_de_caractere("1") == 0x31
    assert wi.keysym_de_caractere("@") == 0x40 and wi.keysym_de_caractere("€") == 0x20AC and wi.keysym_de_caractere("œ") == 0x13BD
    assert wi.keysym_de_caractere("\n") == 0xFF0D
    assert wi.keysym_de("ctrl") == 0xFFE3 and wi.keysym_de("F5") == 0xFFC2 and wi.keysym_de("altgr") == 0xFE03
    assert wi.keysym_de("inconnue") is None and wi.keysym_de("") is None


def test_une_seule_session_pour_plusieurs_frappes(bus):
    c, ok = clavier()
    assert ok and c.etat == "actif"
    assert c.taper("é1@") == (True, "")
    assert c.combinaison("ctrl", "a")[0] and c.touche("enter")[0]
    assert bus.appels.count("CreateSession") == 1 and bus.appels.count("Start") == 1
    assert bus.notifs[:6] == [(0xE9, 1), (0xE9, 0), (0x31, 1), (0x31, 0), (0x40, 1), (0x40, 0)]
    assert bus.notifs[6:10] == [(0xFFE3, 1), (0x61, 1), (0x61, 0), (0xFFE3, 0)]
    c.arreter()
    assert bus.closed


def test_combinaison_relache_tout_meme_en_cas_d_erreur(bus):
    c, _ = clavier()
    bus.echec_notif_apres = 2              # échoue sur la 3e notification (le « c » de Ctrl+Shift+c)
    ok, msg = c.combinaison("ctrl", "shift", "c")
    assert not ok and "PAS" in msg
    assert (0xFFE3, 0) in bus.notifs and (0xFFE1, 0) in bus.notifs     # Ctrl et Shift relâchés
    assert attend(lambda: c.etat == "ferme")


def test_jeton_ecrit_en_0600_et_relu_sans_fuite(bus, caplog, capsys):
    c, _ = clavier()
    f = wi._fichier_jeton()
    assert json.loads(f.read_text())["restore_token"] == JETON
    assert stat.S_IMODE(os.stat(f).st_mode) == 0o600
    c.arreter()
    assert bus.jetons_recus == [None]
    c2, ok = clavier()
    assert ok and bus.jetons_recus[-1] == JETON
    ok, msg = c2.taper("x")
    out = capsys.readouterr()
    assert JETON not in msg + out.out + out.err + caplog.text
    c2.arreter()


def test_jeton_rejete_un_seul_nouvel_essai_sans_jeton(bus):
    wi._ecrire_jeton("VIEUX")
    bus.start_codes = [2, 0]
    c, ok = clavier()
    assert ok and bus.jetons_recus == ["VIEUX", None]
    assert bus.appels.count("Start") == 2
    c.arreter()


def test_un_jeton_n_est_pas_une_session(bus):
    wi._ecrire_jeton("JETON")
    bus.start_code = 1                      # le portail refuse malgré le jeton
    c, ok = clavier()
    assert not ok and c.etat == "refuse"
    assert c.taper("a") == (False, wi.ETATS["refuse"]) and bus.notifs == []


def test_refus_pas_de_redemande_en_boucle(bus):
    bus.start_code = 1
    c, ok = clavier()
    assert not ok and c.etat == "refuse"
    n = bus.appels.count("CreateSession")
    assert c.demarrer() is False and c.demarrer() is False
    assert bus.appels.count("CreateSession") == n


def test_clavier_non_accorde(bus):
    bus.devices = 2                         # pointeur seulement
    c, ok = clavier()
    assert not ok and c.etat == "refuse"


def test_app_id_et_bus_indisponible(bus, monkeypatch):
    bus.register_ok = False
    c, ok = clavier()
    assert not ok and c.etat == "sans_app"
    bus.register_ok = True

    def boom(bus="SESSION"):
        raise OSError
    sys.modules["jeepney.io.blocking"].open_dbus_connection = boom
    c2, ok = clavier()
    assert not ok and c2.etat == "indisponible" and "indisponible" in c2.taper("a")[1]


def test_session_fermee_jamais_de_succes_annonce(bus):
    c, _ = clavier()
    assert c.taper("a")[0]
    bus.push(Msg("Closed", ({},), "/sess/9"))
    assert attend(lambda: not c._vivant())
    ok, msg = c.taper("b")
    assert not ok and "PAS" in msg
    assert (0x62, 1) not in bus.notifs


def test_portail_disparait(bus):
    c, _ = clavier()
    bus.push(Msg("NameOwnerChanged", ("org.freedesktop.portal.Desktop", ":1.3", "")))
    assert attend(lambda: not c._vivant())
    assert c.touche("enter")[0] is False


def test_reouverture_apres_perte_au_prochain_appel(bus):
    c = wi.ClavierWayland()
    c.demarrer(attente=5)
    bus.push(Msg("Closed", ({},), "/sess/9"))
    attend(lambda: not c._vivant())
    assert c.taper("a")[0] is False
    assert c.demarrer(attente=5) and c.taper("a")[0]     # nouvelle session, jeton restauré
    assert bus.jetons_recus[-1] == JETON
    c.arreter()


def test_inf_sup_par_touche_physique_sur_disposition_fr(bus, monkeypatch):
    c, _ = clavier()
    monkeypatch.setattr(wi, "_disposition_fr", lambda: True)
    assert c.taper("<>")[0]
    assert bus.notifs == [("code", 86, 1), ("code", 86, 0),
                          (0xFFE1, 1), ("code", 86, 1), ("code", 86, 0), (0xFFE1, 0)]
    bus.notifs.clear()
    monkeypatch.setattr(wi, "_disposition_fr", lambda: False)
    c.taper("<")
    assert bus.notifs == [(0x3C, 1), (0x3C, 0)]
    c.arreter()


def test_disposition_fr_lecture_gsettings(monkeypatch):
    import subprocess
    sortie = {"sources": "[('xkb', 'fr+latin9')]", "current": "uint32 0"}
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: types.SimpleNamespace(stdout=sortie[cmd[-1]]))
    assert wi._disposition_fr() is True
    sortie["sources"] = "[('xkb', 'us')]"
    assert wi._disposition_fr() is False

    def boom(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr(subprocess, "run", boom)
    assert wi._disposition_fr() is False


def test_keycode_avec_maj_et_relache(bus):
    c, _ = clavier()
    assert c.keycode(86, maj=True) == (True, "")
    assert bus.notifs == [(0xFFE1, 1), ("code", 86, 1), ("code", 86, 0), (0xFFE1, 0)]
    assert c.keycode(0)[0] is False and c.keycode("x")[0] is False
    c.arreter()


def test_touche_inconnue_et_texte_vide(bus):
    c, _ = clavier()
    assert c.touche("zzz")[0] is False and c.taper("")[0] is False and c.combinaison()[0] is False
    assert bus.notifs == []
    c.arreter()


def test_windows_ou_sans_wayland_inactif(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert not wi.actif()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("WAYLAND_DISPLAY")
    assert not wi.actif()
