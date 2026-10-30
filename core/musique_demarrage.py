"""
Musique d'ouverture de Jarvis (demande de l'utilisateur, 2026-10-28 : « quand on ouvre Jarvis, une
musique qui se lance, comme dans le film »).

Jarvis joue le premier fichier .mp3 ou .wav qu'il trouve dans assets/musique-demarrage/,
pendant quelques secondes, puis la baisse doucement jusqu'au silence. Le fichier, c'est l'utilisateur
qui le dépose (Jarvis ne télécharge aucune musique). S'il n'y a pas de fichier, rien ne se passe.

Réglages dans memory/interface.json :
    "musique_demarrage": true/false   (allumer ou couper la musique)
    "musique_duree": 25               (secondes avant la fin en fondu)
    "musique_volume": 40              (0 à 100)
"""
from __future__ import annotations

import ctypes
import json
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DOSSIER = BASE / "assets" / "musique-demarrage"
INTERFACE = BASE / "memory" / "interface.json"


def _reglages() -> dict:
    try:
        return json.loads(INTERFACE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mci(cmd: str) -> int:
    return ctypes.windll.winmm.mciSendStringW(cmd, None, 0, None)


def _jouer(fichier: Path, duree: float, volume: int) -> None:
    alias = "jarvis_ouverture"
    type_ = "mpegvideo" if fichier.suffix.lower() == ".mp3" else "waveaudio"
    if _mci(f'open "{fichier}" type {type_} alias {alias}') != 0:
        print(f"[Musique] impossible d'ouvrir {fichier.name}")
        return
    try:
        vol = max(0, min(1000, volume * 10))
        _mci(f"setaudio {alias} volume to {vol}")
        _mci(f"play {alias}")
        print(f"[Musique] ouverture : {fichier.name}")
        time.sleep(max(1.0, duree))
        for i in range(30, -1, -1):          # fondu de 3 secondes
            _mci(f"setaudio {alias} volume to {vol * i // 30}")
            time.sleep(0.1)
    finally:
        _mci(f"stop {alias}")
        _mci(f"close {alias}")


def lancer() -> None:
    """À appeler une fois au démarrage : ne bloque jamais Jarvis."""
    r = _reglages()
    if not r.get("musique_demarrage", True):
        return
    try:
        fichiers = sorted(f for f in DOSSIER.iterdir() if f.suffix.lower() in (".mp3", ".wav"))
    except Exception:
        return
    if not fichiers:
        return
    duree = float(r.get("musique_duree", 25))
    volume = int(r.get("musique_volume", 40))
    threading.Thread(target=_jouer, args=(fichiers[0], duree, volume), daemon=True).start()
