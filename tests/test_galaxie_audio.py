import json
from types import SimpleNamespace

from galaxie import pont as pont_mod


def _pont(monkeypatch, tmp_path):
    import memory.config_manager as cm
    from core import audio_devices
    store = {"input_device": "", "output_device": ""}
    monkeypatch.setattr(cm, "get_input_device", lambda: store["input_device"])
    monkeypatch.setattr(cm, "get_output_device", lambda: store["output_device"])
    monkeypatch.setattr(cm, "save_input_device", lambda n: store.__setitem__("input_device", n))
    monkeypatch.setattr(cm, "save_output_device", lambda n: store.__setitem__("output_device", n))
    monkeypatch.setattr(audio_devices, "list_devices",
                        lambda kind, refresh=False: ["Micro A"] if kind == "input" else ["Sortie A"])
    appels = []
    jarvis = SimpleNamespace(_on_audio_device_change=lambda: appels.append(1))
    p = pont_mod.Pont(jarvis, SimpleNamespace(write_log=None, set_state=None, show_confirm=None, hide_confirm=None), lambda: "m", SimpleNamespace(pending_title=lambda: None))
    return p, store, appels


def test_choix_enregistre_et_reconnecte_une_fois(monkeypatch, tmp_path):
    p, store, appels = _pont(monkeypatch, tmp_path)
    p.choisir_peripheriques("Micro A", "Sortie A")
    assert store == {"input_device": "Micro A", "output_device": "Sortie A"}
    p.choisir_peripheriques("Micro A", "Sortie A")
    assert appels == [1]


def test_peripherique_inconnu_refuse(monkeypatch, tmp_path):
    p, store, appels = _pont(monkeypatch, tmp_path)
    try:
        p.choisir_peripheriques("Inconnu", "")
    except ValueError:
        pass
    else:
        raise AssertionError
    assert appels == [] and store["input_device"] == ""
