"""Limite des essais de connexion de la télécommande (revue de sécurité du 2026-11-12).

Au bout de `maxi` mauvais essais en `fenetre` secondes, l'appareil (son adresse sur le réseau) est bloqué pendant
`blocage` secondes, même s'il donne ensuite la bonne clé. Un essai réussi remet son compteur à zéro.
"""
import time


class LimiteEssais:
    def __init__(self, maxi: int = 5, fenetre: float = 300.0, blocage: float = 300.0):
        self.maxi, self.fenetre, self.blocage = maxi, fenetre, blocage
        self._echecs: dict[str, list[float]] = {}
        self._bloque_jusqu_a: dict[str, float] = {}

    def bloque(self, appareil: str, maintenant: float | None = None) -> bool:
        maintenant = time.time() if maintenant is None else maintenant
        fin = self._bloque_jusqu_a.get(appareil)
        if fin is None:
            return False
        if maintenant >= fin:
            del self._bloque_jusqu_a[appareil]
            self._echecs.pop(appareil, None)
            return False
        return True

    def echec(self, appareil: str, maintenant: float | None = None) -> None:
        maintenant = time.time() if maintenant is None else maintenant
        recents = [t for t in self._echecs.get(appareil, []) if maintenant - t < self.fenetre]
        recents.append(maintenant)
        self._echecs[appareil] = recents
        if len(recents) >= self.maxi:
            self._bloque_jusqu_a[appareil] = maintenant + self.blocage
        self._nettoyer(maintenant)

    def reussite(self, appareil: str) -> None:
        self._echecs.pop(appareil, None)
        self._bloque_jusqu_a.pop(appareil, None)

    def _nettoyer(self, maintenant: float) -> None:
        """Garde la mémoire petite : oublie les appareils sans échec récent et sans blocage."""
        if len(self._echecs) < 200:
            return
        for appareil in [a for a, ts in self._echecs.items()
                         if a not in self._bloque_jusqu_a and all(maintenant - t >= self.fenetre for t in ts)]:
            del self._echecs[appareil]
