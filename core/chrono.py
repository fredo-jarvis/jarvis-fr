r"""
Chronomètre de Jarvis (07/11/2026, Jarvis Claude) : sert à trouver pourquoi Jarvis « lague » ou ne répond plus.

Une petite tâche mesure toutes les 50 ms si la boucle principale de Jarvis (celle qui gère la voix et la
connexion à Gemini) a pris du retard. Si elle est bloquée plus de SEUIL_MS, une ligne datée est écrite
dans jarvis.log. Toutes les 10 minutes, une ligne « Jarvis OK » datée sert de repère dans le journal.
Ne modifie rien d'autre : il écrit seulement dans le journal.
"""
import asyncio
import time
from datetime import datetime

SEUIL_MS = 400          # au-delà, on écrit « bloqué » dans le journal
PAS_S = 0.05
REPERE_S = 600


def ligne_blocage(retard_ms: float, quand: datetime | None = None) -> str:
    quand = quand or datetime.now()
    return f"[Chrono] {quand:%H:%M:%S} Jarvis bloqué {retard_ms:.0f} ms (la voix et la connexion attendent)"


def ligne_repere(pire_ms: float, quand: datetime | None = None) -> str:
    quand = quand or datetime.now()
    return f"[Chrono] {quand:%d/%m %H:%M:%S} Jarvis OK · pire retard des 10 dernières minutes : {pire_ms:.0f} ms"


async def surveiller(ecrire=print, seuil_ms: float = SEUIL_MS, pas_s: float = PAS_S, repere_s: float = REPERE_S, tours: int | None = None):
    pire, dernier_repere, n = 0.0, time.monotonic(), 0
    ecrire(ligne_repere(0))
    while tours is None or n < tours:
        n += 1
        avant = time.monotonic()
        await asyncio.sleep(pas_s)
        retard_ms = (time.monotonic() - avant - pas_s) * 1000
        pire = max(pire, retard_ms)
        if retard_ms > seuil_ms:
            ecrire(ligne_blocage(retard_ms))
        if time.monotonic() - dernier_repere > repere_s:
            ecrire(ligne_repere(pire))
            pire, dernier_repere = 0.0, time.monotonic()
