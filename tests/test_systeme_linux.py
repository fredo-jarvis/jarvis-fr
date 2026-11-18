import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux seulement")

from core import apps_linux


def _desktop(dossier, fichier, **champs):
    corps = "[Desktop Entry]\nType=Application\n" + "".join(f"{k}={v}\n" for k, v in champs.items())
    (dossier / fichier).write_text(corps, encoding="utf-8")


@pytest.fixture
def xdg(tmp_path, monkeypatch):
    d = tmp_path / "applications"
    d.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path))
    monkeypatch.setattr(apps_linux, "_dossiers", lambda: [d])
    return d


def test_lister_ignore_les_entrees_cachees(xdg):
    _desktop(xdg, "org.gnome.Calculator.desktop", Name="Calculator", Exec="gnome-calculator")
    _desktop(xdg, "cache.desktop", Name="Caché", Exec="x", NoDisplay="true")
    _desktop(xdg, "lien.desktop", Name="Lien", Type="Link")
    assert [a["id"] for a in apps_linux.lister()] == ["org.gnome.Calculator"]


def test_trouver_par_nom_id_commande_et_nom_francais(xdg):
    _desktop(xdg, "org.gnome.Calculator.desktop", Name="Calculator", **{"Name[fr]": "Calculatrice"}, Exec="gnome-calculator %U")
    for q in ("Calculator", "calculatrice", "org.gnome.Calculator", "gnome-calculator", "Calculator"):
        assert apps_linux.trouver(q)["id"] == "org.gnome.Calculator"
    assert apps_linux.trouver("inconnu") is None


def test_nom_generique_ambigu_refuse(xdg):
    _desktop(xdg, "a.desktop", Name="A", GenericName="Navigateur", Exec="a")
    _desktop(xdg, "b.desktop", Name="B", GenericName="Navigateur", Exec="b")
    _desktop(xdg, "c.desktop", Name="C", GenericName="Éditeur", Exec="c")
    assert apps_linux.trouver("navigateur") is None
    assert apps_linux.trouver("editeur")["id"] == "c"


def test_lancer_desktop_succes_si_toujours_vivant_et_echec_si_code_non_nul(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/gio")

    def popen(code):
        def _p(*a, **k):
            def wait(timeout):
                if code is None:
                    raise subprocess.TimeoutExpired("gio", timeout)
                return code
            return SimpleNamespace(wait=wait)
        return _p
    monkeypatch.setattr(subprocess, "Popen", popen(None))
    assert apps_linux.lancer_desktop("x.desktop") is True
    monkeypatch.setattr(subprocess, "Popen", popen(1))
    assert apps_linux.lancer_desktop("x.desktop") is False


def test_index_linux_contient_noms_et_chemin_desktop(xdg):
    import index_pc
    _desktop(xdg, "org.gnome.Calculator.desktop", Name="Calculator", **{"Name[fr]": "Calculatrice"}, Exec="gnome-calculator")
    apps, seen = [], set()
    index_pc.collect_apps_linux(apps, seen)
    assert {a["name"] for a in apps} == {"Calculator", "Calculatrice"}
    assert all(a["path"].endswith("org.gnome.Calculator.desktop") for a in apps)


def test_open_anything_ouvre_via_apps_linux(monkeypatch):
    from actions import open_anything
    vus = []
    monkeypatch.setattr(apps_linux, "ouvrir", lambda p: vus.append(p))
    open_anything._open("/x/y.desktop")
    assert vus == ["/x/y.desktop"]


def test_open_app_nom_inconnu_n_appelle_pas_xdg_open(xdg, monkeypatch):
    from actions import open_app
    appels = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: appels.append(a) or SimpleNamespace(returncode=1))
    monkeypatch.setattr(open_app, "_lancer_commande", lambda c: False)
    assert open_app._launch_linux("nom-qui-nexiste-pas") is False
    assert not any("xdg-open" in a[0] for a in appels)


def test_open_app_equivalent_francais(xdg, monkeypatch):
    from actions import open_app
    _desktop(xdg, "org.gnome.Calculator.desktop", Name="Calculator", Exec="gnome-calculator")
    monkeypatch.setattr(open_app, "_lancer_commande", lambda c: False)
    lances = []
    monkeypatch.setattr(apps_linux, "lancer_desktop", lambda p: lances.append(p) or True)
    monkeypatch.setattr(open_app.time, "sleep", lambda s: None)
    assert open_app._launch_linux("calculatrice") is True
    assert lances[0].endswith("org.gnome.Calculator.desktop")


@pytest.mark.parametrize("wpctl", [True, False])
def test_volume_linux_commandes(monkeypatch, wpctl):
    from actions import computer_settings as cs
    cmds = []
    monkeypatch.setattr(cs.shutil, "which", lambda n: "/usr/bin/wpctl" if wpctl else None)
    sortie = "Volume: 0.42 [MUTED]\n" if wpctl else "Volume: front-left: 1 / 42% / -22 dB\n"
    monkeypatch.setattr(cs.subprocess, "run", lambda c, **k: cmds.append(c) or SimpleNamespace(stdout=sortie, returncode=0))
    cs._linux_volume("up"); cs._linux_volume("down"); cs._linux_volume("mute"); cs._linux_volume("set", 30)
    assert cs._linux_volume("get") == 42
    outil = "wpctl" if wpctl else "pactl"
    assert all(c[0] == outil for c in cmds)
    if wpctl:
        assert cmds[0] == ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "10%+"]
        assert cmds[3][-1] == "30%" and "-l" in cmds[3]
