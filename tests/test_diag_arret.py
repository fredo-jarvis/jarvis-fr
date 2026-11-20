import ast
import json
import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import diag_arret as d

RACINE = Path(__file__).resolve().parent.parent
MOTIFS = {"extinction_vocale_gemini", "filet_30s_extinction_vocale", "extinction_locale",
          "filet_30s_outil_shutdown", "outil_shutdown_jarvis", "fenetre_chrome_fermee", "fenetre_galaxie_fermee"}


@pytest.fixture
def logs(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(d, "_etat", None)
    return tmp_path


def _lignes(dossier):
    f = dossier / "arrets.log"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def test_chaque_appel_de_eteindre_tout_porte_un_motif_connu():
    arbre = ast.parse((RACINE / "main.py").read_text(encoding="utf-8"))
    vus = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call):
            nom = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            if nom == "_eteindre_tout":
                assert n.args and isinstance(n.args[0], ast.Constant), f"ligne {n.lineno} sans motif"
                vus.add(n.args[0].value)
            if nom == "Timer" and any(getattr(a, "id", "") == "_eteindre_tout" for a in n.args):
                kw = [k for k in n.keywords if k.arg == "args"]
                assert kw, f"ligne {n.lineno} : Timer sans motif"
                vus.add(kw[0].value.elts[0].value)
    assert vus == MOTIFS


def test_trace_contient_motif_pid_chrome_et_etat_sans_donnee_perso(logs, monkeypatch):
    from galaxie import server
    monkeypatch.setattr(server, "FENETRE", SimpleNamespace(pid=4242, poll=lambda: None))
    d.fournir_etat(lambda: {"cerveau": "local", "connecte": False})
    d.tracer_arret("extinction_locale")
    (l,) = _lignes(logs)
    assert l["motif"] == "extinction_locale" and l["pid"] == os.getpid()
    assert l["chrome"] == {"suivi": True, "pid": 4242, "etat": "en cours"}
    assert l["jarvis"] == {"cerveau": "local", "connecte": False}
    assert any("test_trace" in a for a in l["appelants"])
    assert set(l) <= {"heure", "motif", "pid", "duree_s", "fil", "appelants", "chrome", "jarvis"}


def test_chrome_termine_et_chrome_non_suivi(logs, monkeypatch):
    from galaxie import server
    monkeypatch.setattr(server, "FENETRE", SimpleNamespace(pid=1, poll=lambda: 0))
    assert d._chrome()["etat"] == "terminé (code 0)"
    monkeypatch.setattr(server, "FENETRE", None)
    assert d._chrome() == {"suivi": False}


def test_etat_qui_plante_ne_bloque_pas_la_trace(logs):
    d.fournir_etat(lambda: 1 / 0)
    d.tracer_arret("x")
    assert _lignes(logs)[0]["jarvis"] == "indisponible"


def test_rotation_de_arrets_log(logs, monkeypatch):
    monkeypatch.setattr(d, "MAX_TAILLE", 300)
    for i in range(12):
        d.tracer_arret(f"m{i}")
    noms = sorted(p.name for p in logs.iterdir())
    assert noms == ["arrets.log", "arrets.log.1", "arrets.log.2", "arrets.log.3"]


def test_nettoyage_des_plantages(logs, monkeypatch):
    for i in range(14):
        (logs / f"plantage-20260101-0000{i:02d}-{i}.log").write_text("x" if i % 5 else "")
    courant = logs / "plantage-99999999-000000-1.log"
    d._nettoyer_plantages(logs, courant)
    restants = list(logs.glob("plantage-*.log"))
    assert len(restants) <= d.GARDER_PLANTAGES - 1
    assert all(p.stat().st_size > 0 for p in restants)


def test_windows_n_installe_pas_de_gestionnaire_de_signal(monkeypatch):
    appels = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(signal, "signal", lambda *a: appels.append(a))
    d._installer_signaux()
    assert appels == []


def test_dossier_hors_depot(monkeypatch):
    monkeypatch.delenv("JARVIS_LOG_DIR", raising=False)
    assert RACINE not in d.dossier().parents


def _enfant(logs, code):
    script = "from core import diag_arret as d\nd.demarrer()\n" + textwrap.dedent(code)
    return subprocess.run([sys.executable, "-c", script], cwd=RACINE, env={**os.environ, "JARVIS_LOG_DIR": str(logs)},
                          capture_output=True, text=True, timeout=30)


def test_plantage_natif_ecrit_la_pile(logs):
    r = _enfant(logs, "import faulthandler; faulthandler._sigsegv()")
    assert r.returncode != 0
    contenu = "".join(p.read_text() for p in logs.glob("plantage-*.log"))
    assert "Segmentation fault" in contenu


def test_fin_normale_tracee(logs):
    _enfant(logs, "pass")
    assert [l["motif"] for l in _lignes(logs)] == ["fin_normale"]


@pytest.mark.skipif(sys.platform == "win32", reason="signaux POSIX")
def test_sigterm_trace_puis_meme_effet_qu_avant(logs):
    p = subprocess.Popen([sys.executable, "-c", "from core import diag_arret as d\nd.demarrer()\nimport time\nprint('pret',flush=True)\n"
                          "while True: time.sleep(0.05)"], cwd=RACINE, env={**os.environ, "JARVIS_LOG_DIR": str(logs)},
                         stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "pret"
    p.send_signal(signal.SIGTERM)
    assert p.wait(timeout=15) == -signal.SIGTERM
    (l,) = _lignes(logs)
    assert l["motif"] == "signal_recu" and l["signal"] == "SIGTERM"


@pytest.mark.skipif(sys.platform == "win32", reason="signaux POSIX")
def test_sigkill_n_est_pas_trace(logs):
    p = subprocess.Popen([sys.executable, "-c", "from core import diag_arret as d\nd.demarrer()\nimport time\nprint('pret',flush=True)\n"
                          "time.sleep(60)"], cwd=RACINE, env={**os.environ, "JARVIS_LOG_DIR": str(logs)}, stdout=subprocess.PIPE, text=True)
    p.stdout.readline()
    p.kill(); p.wait(timeout=15)
    assert _lignes(logs) == []


def test_eteindre_tout_trace_avant_os_exit(logs, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import main
    ordre = []
    monkeypatch.setattr(os, "_exit", lambda c: ordre.append(("exit", c, bool(_lignes(logs)))))
    main._eteindre_tout("outil_shutdown_jarvis")
    assert ordre == [("exit", 0, True)]
    assert _lignes(logs)[0]["motif"] == "outil_shutdown_jarvis"


def test_ecriture_audio_serialisee_avec_arret(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import threading, time, main
    if sys.platform == "win32":
        pytest.skip("verrou PortAudio : Linux seulement")
    ev = []

    class S:
        def write(self, d):
            ev.append("w+"); time.sleep(0.2); ev.append("w-")
    t = threading.Thread(target=main._ecrire_pa, args=(S(), b""))
    t.start(); time.sleep(0.05)
    with main._PA_VERROU:
        ev.append("stop")
    t.join()
    assert ev == ["w+", "w-", "stop"]
