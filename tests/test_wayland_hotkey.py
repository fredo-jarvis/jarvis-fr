import sys
import threading
import time
import types

import pytest

from core import hotkey, wayland_shortcuts as ws

CHEMIN = "/org/freedesktop/portal/desktop"


class Msg:
    def __init__(self, membre, corps, chemin=None, erreur=False):
        self.header = types.SimpleNamespace(
            fields={3: membre, 1: chemin},
            message_type=types.SimpleNamespace(name="error" if erreur else "method_return"))
        self.body = corps


class FauxBus:
    """Bus D-Bus factice : répond aux appels du portail et rejoue des signaux scénarisés."""

    def __init__(self, register_ok=True, bind_code=0):
        self.register_ok, self.bind_code = register_ok, bind_code
        self.unique_name = ":1.5"
        self.events = []
        self.cv = threading.Condition()
        self.closed = False
        self.appels = []

    def push(self, m):
        with self.cv:
            self.events.append(m)
            self.cv.notify_all()

    def send_and_get_reply(self, appel, timeout=None):
        methode, corps = appel
        self.appels.append(methode)
        if methode == "Register":
            return Msg("", (), erreur=not self.register_ok)
        jeton = corps[0]["handle_token"][1] if methode == "CreateSession" else corps[3]["handle_token"][1]
        chemin = f"{CHEMIN}/request/1_5/{jeton}"
        if methode == "CreateSession":
            self.push(Msg("Response", (0, {"session_handle": ("s", "/sess/1")}), chemin))
        else:
            res = {"shortcuts": ("a", [(ws._ID, {"trigger_description": ("s", "Ctrl+Espace")})])}
            self.push(Msg("Response", (self.bind_code, res if self.bind_code == 0 else {}), chemin))
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
                self.cv.wait(min(reste, 0.05))
            return self.events.pop(0)

    def close(self):
        self.closed = True


@pytest.fixture
def bus(monkeypatch):
    b = FauxBus()
    jeepney = types.ModuleType("jeepney")
    jeepney.DBusAddress = lambda *a, **k: None
    jeepney.message_bus = None
    jeepney.new_method_call = lambda adresse, m, sig, corps: (m, corps)

    class Regle:
        def __init__(self, **k): pass
        def add_arg_condition(self, *a): pass
    jeepney.MatchRule = Regle
    io = types.ModuleType("jeepney.io")
    blocking = types.ModuleType("jeepney.io.blocking")
    blocking.Proxy = lambda *a: types.SimpleNamespace(AddMatch=lambda r: None)
    blocking.open_dbus_connection = lambda bus="SESSION": b
    monkeypatch.setitem(sys.modules, "jeepney", jeepney)
    monkeypatch.setitem(sys.modules, "jeepney.io", io)
    monkeypatch.setitem(sys.modules, "jeepney.io.blocking", blocking)
    monkeypatch.setattr(ws, "_PAS", 0.02)
    return b


def lance(bus):
    evts = []
    r = ws.RaccourciGlobal(evts.append, ("ctrl", "space"))
    return r, evts, r.demarrer(attente=5)


def attend(cond, delai=2):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_activations_repetees_sans_rester_bloque(bus):
    r, evts, ok = lance(bus)
    assert ok and r.etat == "actif" and r.trigger_obtenu == "Ctrl+Espace"
    for _ in range(3):
        bus.push(Msg("Activated", ("/sess/1", ws._ID, 1, {})))
        bus.push(Msg("Deactivated", ("/sess/1", ws._ID, 2, {})))
    assert attend(lambda: evts.count(True) == 3 and evts.count(False) >= 3)
    pairs = [e for e in evts]
    assert pairs[-1] is False
    r.arreter()
    assert evts[-1] is False and bus.closed
    assert bus.appels.count("CreateSession") == 1      # une seule session


def test_signal_d_un_autre_raccourci_ignore(bus):
    r, evts, ok = lance(bus)
    bus.push(Msg("Activated", ("/sess/1", "autre", 1, {})))
    time.sleep(0.2)
    assert True not in evts
    r.arreter()


def test_refus_gnome(bus):
    bus.bind_code = 1
    r, evts, ok = lance(bus)
    assert not ok and r.etat == "refuse" and "fenêtre" in ws.ETATS[r.etat]
    assert evts[-1] is False and attend(lambda: bus.closed)


def test_app_id_introuvable(bus):
    bus.register_ok = False
    r, evts, ok = lance(bus)
    assert not ok and r.etat == "sans_app"


def test_portail_disparait_en_cours_d_ecoute(bus):
    r, evts, ok = lance(bus)
    bus.push(Msg("Activated", ("/sess/1", ws._ID, 1, {})))
    assert attend(lambda: True in evts)
    bus.push(Msg("NameOwnerChanged", ("org.freedesktop.portal.Desktop", ":1.9", "")))
    assert attend(lambda: r.etat == "ferme")
    assert evts[-1] is False            # plus de mode écoute bloqué
    r.arreter()


def test_session_fermee(bus):
    r, evts, ok = lance(bus)
    bus.push(Msg("Activated", ("/sess/1", ws._ID, 1, {})))
    assert attend(lambda: True in evts)
    bus.push(Msg("Closed", ({},)))
    assert attend(lambda: r.etat == "ferme") and evts[-1] is False


def test_bus_indisponible(monkeypatch, bus):
    def boom(bus="SESSION"):
        raise OSError("pas de bus")
    sys.modules["jeepney.io.blocking"].open_dbus_connection = boom
    r, evts, ok = lance(bus)
    assert not ok and r.etat == "indisponible"


def test_trigger_et_chord():
    assert ws.trigger(("ctrl", "space")) == "CTRL+space"
    assert ws.trigger(("ctrl", "f9")) == "CTRL+F9"
    assert hotkey.chord_from_text("Ctrl+F9") == ("ctrl", "f9")
    assert hotkey.chord_from_text("n'importe quoi") == hotkey.DEFAULT_CHORD
    assert hotkey.chord_from_text(None) == hotkey.DEFAULT_CHORD


class FauxRaccourci:
    resultat = True

    def __init__(self, cb, chord):
        self.etat = "actif" if self.resultat else "refuse"

    def demarrer(self, attente=0):
        return self.resultat

    def arreter(self):
        pass


def test_pushtotalk_portail_puis_repli_fenetre(monkeypatch):
    monkeypatch.setattr(hotkey, "_OS", "Linux")
    monkeypatch.setattr(ws, "actif", lambda: True)
    monkeypatch.setattr(ws, "RaccourciGlobal", FauxRaccourci)
    p = hotkey.PushToTalk(lambda h: None)
    FauxRaccourci.resultat = True
    assert p.start() == "global"
    FauxRaccourci.resultat = False
    assert p.start() == "window" and "refusé" in p.etat_portail
    p.set_held(True)                       # le raccourci Qt de fenêtre reste utilisable
    assert p.held
    p.stop()


def test_windows_n_utilise_pas_le_portail(monkeypatch):
    monkeypatch.setattr(hotkey, "_OS", "Windows")
    monkeypatch.setattr(hotkey.PushToTalk, "_can_poll", lambda self: False)
    monkeypatch.setattr(ws, "actif", lambda: True)
    p = hotkey.PushToTalk(lambda h: None)
    assert p.start() == "window" and p._portail is None
