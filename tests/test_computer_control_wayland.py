import types

import pytest

from actions import computer_control as cc
from core import wayland_input as wi


class FauxClavier:
    def __init__(self, ok=True, msg=""):
        self.ok, self.msg, self.appels = ok, msg, []

    def _rep(self, nom, *a):
        self.appels.append((nom, *a))
        return self.ok, self.msg

    def taper(self, t, i=0.0): return self._rep("taper", t)
    def touche(self, k): return self._rep("touche", k)
    def combinaison(self, *k): return self._rep("combinaison", *k)


@pytest.fixture
def wayland(monkeypatch):
    faux = FauxClavier()
    monkeypatch.setattr(wi, "actif", lambda: True)
    monkeypatch.setattr(wi, "garantir", lambda: faux)
    monkeypatch.setattr(cc.time, "sleep", lambda s: None)
    monkeypatch.setattr(cc, "pyautogui", types.SimpleNamespace(
        typewrite=lambda *a, **k: pytest.fail("pyautogui utilisé sous Wayland"),
        hotkey=lambda *a, **k: pytest.fail("pyautogui utilisé sous Wayland"),
        press=lambda *a, **k: pytest.fail("pyautogui utilisé sous Wayland")), raising=False)
    return faux


def test_frappes_passent_par_le_portail(wayland):
    assert cc._type("é1").startswith("Typed")
    assert cc._hotkey("ctrl", "s") == "Hotkey: ctrl+s"
    assert cc._press("enter") == "Pressed: enter"
    assert cc._clear_field() == "Field cleared"
    assert cc._smart_type("bonjour").startswith("Smart-typed")
    assert ("combinaison", "ctrl", "a") in wayland.appels and ("taper", "bonjour") in wayland.appels


def test_echec_jamais_annonce_comme_reussite(wayland):
    wayland.ok, wayland.msg = False, "Clavier Wayland : la session a été perdue"
    for res in (cc._type("a"), cc._hotkey("ctrl", "c"), cc._press("tab"), cc._clear_field(),
                cc._smart_type("x")):
        assert res == "Clavier Wayland : la session a été perdue"


def test_sans_autorisation_message_explicite_et_rien_ne_plante(monkeypatch):
    monkeypatch.setattr(wi, "actif", lambda: True)
    c = wi.ClavierWayland()
    c.etat = "refuse"
    monkeypatch.setattr(wi, "garantir", lambda: c)
    assert cc._press("enter") == wi.ETATS["refuse"]
    assert cc._type("a") == wi.ETATS["refuse"]


def test_hors_wayland_pyautogui_inchange(monkeypatch):
    monkeypatch.setattr(wi, "actif", lambda: False)
    appels = []
    faux = types.SimpleNamespace(hotkey=lambda *k: appels.append(("hotkey", k)),
                                 press=lambda k: appels.append(("press", k)),
                                 typewrite=lambda t, interval=0: appels.append(("type", t)))
    monkeypatch.setattr(cc, "pyautogui", faux, raising=False)
    monkeypatch.setattr(cc, "_require_pyautogui", lambda: None)
    monkeypatch.setattr(cc.time, "sleep", lambda s: None)
    cc._hotkey("ctrl", "c"); cc._press("enter"); cc._type("ab")
    assert appels == [("hotkey", ("ctrl", "c")), ("press", "enter"), ("type", "ab")]


def test_souris_indisponible_sous_wayland_sans_faux_succes(wayland):
    for res in (cc._click(10, 20), cc._click(), cc._scroll("down", 3), cc._move(5, 5), cc._drag(1, 1, 2, 2)):
        assert "indisponible sous Wayland" in res and "aucune action effectuée" in res
    assert not any(a[0] in ("taper", "touche") for a in wayland.appels)


def test_focus_fenetre_indisponible_sous_wayland(wayland, monkeypatch):
    monkeypatch.setattr(cc, "_get_os", lambda: "linux")
    monkeypatch.setattr(cc.subprocess, "run", lambda *a, **k: pytest.fail("wmctrl/xdotool appelé"))
    assert "indisponible sous Wayland" in cc._focus_window("Calculatrice")


def test_souris_inchangee_hors_wayland(monkeypatch):
    monkeypatch.setattr(wi, "actif", lambda: False)
    appels = []
    faux = types.SimpleNamespace(click=lambda *a, **k: appels.append(("click", a)),
                                 moveTo=lambda *a, **k: appels.append(("move", a)))
    monkeypatch.setattr(cc, "pyautogui", faux, raising=False)
    monkeypatch.setattr(cc, "_require_pyautogui", lambda: None)
    assert cc._click(3, 4).startswith("Clicked (3, 4)")
    assert cc._move(1, 2) == "Mouse → (1, 2)"
    assert appels == [("click", (3, 4)), ("move", (1, 2))]
