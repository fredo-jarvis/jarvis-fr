import sys

from core import cerveau_local as c


class _Proc:
    def __init__(self, rc=0):
        self.rc = rc
    def wait(self):
        return self.rc
    def poll(self):
        return self.rc


def _voix(monkeypatch, exe="/usr/bin/spd-say"):
    monkeypatch.setattr(c.shutil, "which", lambda n: exe)
    return c.VoixSpd()


def test_spd_say_parle_en_francais_et_attend(monkeypatch):
    appels = []
    monkeypatch.setattr(c.subprocess, "Popen", lambda cmd, **k: appels.append(cmd) or _Proc(0))
    v = _voix(monkeypatch)
    assert v.dire("  -bonjour   Jérôme ") is True
    assert appels == [["/usr/bin/spd-say", "-l", "fr", "-w", "--", "-bonjour Jérôme"]]


def test_spd_say_absent_ne_plante_pas(monkeypatch):
    v = _voix(monkeypatch, exe=None)
    assert v.dire("bonjour") is False
    v.couper()


def test_spd_say_muet_ne_lance_rien(monkeypatch):
    monkeypatch.setattr(c.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(c.shutil, "which", lambda n: "/usr/bin/spd-say")
    assert c.VoixSpd(muet=True).dire("bonjour") is True


def test_repli_linux_sans_piper_donne_spd_say(monkeypatch):
    monkeypatch.setattr(c, "ouvrir_studio", lambda: False)
    monkeypatch.setattr(c, "studio_repond", lambda *a, **k: False)
    monkeypatch.setattr(c, "VoixPiper", lambda **k: (_ for _ in ()).throw(FileNotFoundError("voix")))
    monkeypatch.setattr(c.shutil, "which", lambda n: "/usr/bin/spd-say")
    monkeypatch.setattr(sys, "platform", "linux")
    assert isinstance(c.nouvelle_voix(), c.VoixSpd)


def test_repli_windows_reste_hortense(monkeypatch):
    monkeypatch.setattr(c, "ouvrir_studio", lambda: False)
    monkeypatch.setattr(c, "VoixPiper", lambda **k: (_ for _ in ()).throw(FileNotFoundError("voix")))
    monkeypatch.setattr(sys, "platform", "win32")
    assert isinstance(c.nouvelle_voix(), c.VoixLocale)
