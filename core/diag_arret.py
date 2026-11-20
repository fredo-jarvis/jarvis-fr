"""Diagnostic des arrêts de Jarvis : pourquoi le processus s'est-il terminé ?

Deux journaux, hors du dépôt (dossier d'état de l'utilisateur, ou JARVIS_LOG_DIR) :
  arrets.log       une ligne JSON par arrêt volontaire (os._exit, fin normale, SIGTERM/SIGHUP reçus)
  plantage-*.log   faulthandler : pile de tous les threads si le processus plante (segfault, abort…)

Limites assumées : faulthandler ne voit PAS os._exit, SIGKILL ni une terminaison par le système (OOM killer…).
Un os._exit passe par tracer_arret(), les autres terminaisons externes ne laissent aucune trace ici.
On n'écrit jamais de clé, de conversation ni de donnée personnelle : seulement des motifs, des noms de
fonctions, des PID et l'état technique (cerveau actif, état de la fenêtre Chrome).
"""
import atexit
import faulthandler
import json
import os
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

MAX_TAILLE = 200_000        # octets avant rotation de arrets.log
GARDER_ARRETS = 3           # arrets.log.1 … .3
GARDER_PLANTAGES = 10       # derniers fichiers plantage-*.log conservés

_fh = None                  # descripteur gardé ouvert toute la vie du processus (sinon faulthandler écrit dans le vide)
_demarre = 0.0
_etat = None


def dossier() -> Path:
    base = os.environ.get("JARVIS_LOG_DIR")
    if base:
        return Path(base)
    if sys.platform == "win32":
        racine = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        racine = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return racine / "jarvis-fr" / "logs"


def fournir_etat(fonction) -> None:
    """fonction() rend un petit dict technique (cerveau actif, connexion…). Appelée seulement au moment de l'arrêt."""
    global _etat
    _etat = fonction


def _tourner(chemin: Path) -> None:
    try:
        if chemin.exists() and chemin.stat().st_size > MAX_TAILLE:
            for i in range(GARDER_ARRETS, 0, -1):
                src = chemin if i == 1 else chemin.with_name(f"{chemin.name}.{i - 1}")
                if src.exists():
                    os.replace(src, chemin.with_name(f"{chemin.name}.{i}"))
    except OSError:
        pass


def _nettoyer_plantages(d: Path, courant: Path) -> None:
    """Un fichier vide = un processus qui s'est arrêté sans planter : inutile de le garder."""
    try:
        anciens = sorted((p for p in d.glob("plantage-*.log") if p != courant), key=lambda p: p.name)
        for p in anciens:
            if p.stat().st_size == 0:
                p.unlink()
        restants = sorted((p for p in d.glob("plantage-*.log") if p != courant), key=lambda p: p.name)
        for p in restants[:max(0, len(restants) - (GARDER_PLANTAGES - 1))]:
            p.unlink()
    except OSError:
        pass


def demarrer() -> bool:
    """À appeler le plus tôt possible. Ne lève jamais : un diagnostic ne doit pas empêcher Jarvis de démarrer."""
    global _fh, _demarre
    if _fh is not None:
        return True
    try:
        d = dossier()
        d.mkdir(parents=True, exist_ok=True)
        courant = d / f"plantage-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.log"
        _nettoyer_plantages(d, courant)
        _fh = open(courant, "w", encoding="utf-8")
        faulthandler.enable(file=_fh, all_threads=True)
        _demarre = time.time()
        atexit.register(_fin_normale)
        _installer_signaux()
        return True
    except Exception as e:                  # disque plein, dossier en lecture seule…
        print(f"[Diag] arrêts non journalisés : {type(e).__name__}", file=sys.stderr)
        return False


def _appelants(profondeur: int = 6) -> list[str]:
    """fichier:ligne fonction, sans aucun argument ni valeur."""
    pile = traceback.extract_stack()[:-2]          # sans tracer_arret et _appelants
    return [f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in pile[-profondeur:]]


def _chrome() -> dict:
    try:
        from galaxie import server
        f = getattr(server, "FENETRE", None)
        if f is None:
            return {"suivi": False}
        etat = f.poll()
        return {"suivi": True, "pid": f.pid, "etat": "en cours" if etat is None else f"terminé (code {etat})"}
    except Exception:
        return {"suivi": False}


def tracer_arret(motif: str, **plus) -> None:
    """Écrit la ligne d'arrêt et la force sur disque. Appelée juste avant os._exit : aucune exception ne doit sortir."""
    try:
        info = {"heure": time.strftime("%Y-%m-%d %H:%M:%S"), "motif": motif, "pid": os.getpid(),
                "duree_s": round(time.time() - _demarre, 1) if _demarre else None,
                "fil": threading.current_thread().name, "appelants": _appelants(),
                "chrome": _chrome()}
        try:
            if _etat is not None:
                info["jarvis"] = _etat()
        except Exception:
            info["jarvis"] = "indisponible"
        info.update(plus)
        d = dossier()
        d.mkdir(parents=True, exist_ok=True)
        chemin = d / "arrets.log"
        _tourner(chemin)
        with open(chemin, "a", encoding="utf-8") as f:
            f.write(json.dumps(info, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass


def _fin_normale() -> None:
    """atexit : fin du programme sans os._exit (fenêtre Qt fermée, retour de main). Ne passe pas par os._exit."""
    tracer_arret("fin_normale")


def _installer_signaux() -> None:
    """SIGTERM/SIGHUP : on trace puis on rend le signal à son comportement par défaut, donc même effet qu'avant.
    Seulement dans le fil principal, et seulement si Python reprend la main (boucle Qt)."""
    if sys.platform == "win32" or threading.current_thread() is not threading.main_thread():
        return
    for nom in ("SIGTERM", "SIGHUP"):
        sig = getattr(signal, nom, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _recu)
        except (ValueError, OSError):
            pass


def _recu(signum, _frame) -> None:
    tracer_arret("signal_recu", signal=signal.Signals(signum).name)
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)
