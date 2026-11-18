import types

import pytest

from actions import computer_settings as cs
from core import wayland_input as wi


class Faux:
    def __init__(self, ok=True, msg=""):
        self.ok, self.msg, self.appels = ok, msg, []

    def combinaison(self, *k):
        self.appels.append(k)
        return self.ok, self.msg


@pytest.fixture
def wl(monkeypatch):
    faux = Faux()
    monkeypatch.setattr(cs, "_OS", "Linux")
    monkeypatch.setattr(wi, "actif", lambda: True)
    monkeypatch.setattr(wi, "garantir", lambda: faux)
    monkeypatch.setattr(cs.subprocess, "run", lambda *a, **k: pytest.fail("wmctrl appelé sous Wayland"))
    monkeypatch.setattr(cs, "pyautogui", types.SimpleNamespace(
        hotkey=lambda *a, **k: pytest.fail("pyautogui utilisé")), raising=False)
    return faux


@pytest.mark.parametrize("fonction,combo", [(cs.snap_left, ("super", "left")),
                                            (cs.snap_right, ("super", "right")),
                                            (cs.maximize_window, ("super", "up"))])
def test_placement_via_remotedesktop_non_verifie(wl, fonction, combo):
    msg = fonction()
    assert wl.appels == [combo]
    assert "résultat non vérifié" in msg and "fenêtre active" in msg and "focus" in msg
    assert "Done" not in msg


def test_placement_indisponible_si_session_refusee_ou_perdue(wl):
    wl.ok, wl.msg = False, "session perdue, frappe NON envoyée"
    msg = cs.snap_left()
    assert msg.startswith("snap_left indisponible sous Wayland") and "NON envoyée" in msg
    assert "non vérifié" not in msg


def test_dispatch_renvoie_le_message_et_pas_done(wl, monkeypatch):
    monkeypatch.setattr(cs, "_PYAUTOGUI", True)
    monkeypatch.setitem(cs.ACTION_MAP, "snap_left", cs.snap_left)
    res = cs.computer_settings({"action": "snap_left"})
    assert "résultat non vérifié" in res and not res.startswith("Done")
    wl.ok, wl.msg = False, "autorisation refusée"
    assert "indisponible" in cs.computer_settings({"action": "snap_left"})


def test_windows_inchange(monkeypatch):
    monkeypatch.setattr(cs, "_OS", "Windows")
    monkeypatch.setattr(wi, "actif", lambda: pytest.fail("Wayland consulté sous Windows"))
    appels = []
    monkeypatch.setattr(cs, "pyautogui", types.SimpleNamespace(hotkey=lambda *k: appels.append(k)), raising=False)
    assert cs.snap_left() is None and cs.snap_right() is None and cs.maximize_window() is None
    assert appels == [("win", "left"), ("win", "right"), ("win", "up")]


def test_x11_garde_wmctrl(monkeypatch):
    monkeypatch.setattr(cs, "_OS", "Linux")
    monkeypatch.setattr(wi, "actif", lambda: False)
    appels = []
    monkeypatch.setattr(cs.subprocess, "run", lambda c, **k: appels.append(c))
    cs.snap_left()
    assert appels and appels[0][0] == "wmctrl"
