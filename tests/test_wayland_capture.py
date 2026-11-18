import os
import sys

import pytest
from PIL import Image

from core import wayland_capture as wc


def test_actif_selon_session(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert wc.actif()
    monkeypatch.delenv("WAYLAND_DISPLAY")
    assert not wc.actif()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert not wc.actif()


def test_capturer_renvoie_image_et_supprime_le_fichier(monkeypatch, tmp_path):
    p = tmp_path / "shot.png"
    Image.new("RGBA", (20, 10), (1, 2, 3, 255)).save(p)
    monkeypatch.setattr(wc, "_demander", lambda delai=0: str(p))
    im = wc.capturer()
    assert im.size == (20, 10) and im.mode == "RGB"
    assert not os.path.exists(p)


@pytest.mark.parametrize("etat", ["refuse", "annule", "delai", "indisponible"])
def test_erreurs_explicites(monkeypatch, etat):
    def boom(delai=0):
        raise wc.CaptureErreur(etat)
    monkeypatch.setattr(wc, "_demander", boom)
    with pytest.raises(wc.CaptureErreur) as e:
        wc.capturer()
    assert e.value.etat == etat and str(e.value)


def test_fichier_illisible(monkeypatch, tmp_path):
    p = tmp_path / "x.png"
    p.write_text("pas une image")
    monkeypatch.setattr(wc, "_demander", lambda delai=0: str(p))
    with pytest.raises(wc.CaptureErreur) as e:
        wc.capturer()
    assert e.value.etat == "erreur"


def test_montre_ou_cliquer_message_explicite(monkeypatch):
    from plugins import montre_ou_cliquer as mc
    monkeypatch.setattr(wc, "actif", lambda: True)

    def boom(delai=0):
        raise wc.CaptureErreur("refuse")
    monkeypatch.setattr(wc, "capturer", boom)
    assert mc._grab_screenshot() is None
    assert "refusée" in mc._derniere_erreur_capture
