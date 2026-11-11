r"""
La voix de Jarvis sur la télé du salon (ajouté le 05/11/2026, demande d'un utilisateur).

Quand tu parles depuis le bouton de la télé, la réponse sort de la télé. Si la télé ne lit plus le son
(page fermée, télé éteinte), le PC reprend tout seul au bout de quelques secondes.
"""
import threading
import time
from collections import deque


class SortieTele:
    ATTENTE_LECTEUR = 5.0       # la télé demande du son en continu : au-delà, elle n'écoute plus
    DUREE = 60.0                # temps laissé à Jarvis pour répondre, prolongé par chaque morceau de voix
    MAX_OCTETS = 8_000_000      # environ 2 min 45 de voix
    MAX_ENVOI = 96_000          # 2 s de voix par envoi : moins de requêtes, donc moins de trous dans le son

    def __init__(self, horloge=time.monotonic):
        self._horloge = horloge
        self._file: deque[tuple[int, bytes]] = deque()
        self._taille = 0
        self._lecteur = None
        self._route = None
        self._cond = threading.Condition()

    def demander(self) -> None:
        """L'utilisateur vient de parler depuis la télé : la prochaine réponse sort là-bas."""
        with self._cond:
            self._route = self._horloge()

    def actif(self) -> bool:
        with self._cond:
            maintenant = self._horloge()
            return (self._route is not None and self._lecteur is not None
                    and maintenant - self._route < self.DUREE
                    and maintenant - self._lecteur < self.ATTENTE_LECTEUR)

    def envoyer(self, pcm: bytes, taux: int) -> None:
        with self._cond:
            self._file.append((int(taux), bytes(pcm)))
            self._taille += len(pcm)
            while self._taille > self.MAX_OCTETS:
                self._taille -= len(self._file.popleft()[1])
            if self._route is not None:
                self._route = self._horloge()
            self._cond.notify_all()

    def lire(self, attente: float = 1.0):
        """Le prochain morceau (taux, octets), ou None s'il n'y a rien à lire."""
        with self._cond:
            self._lecteur = self._horloge()
            if not self._file and attente > 0:
                self._cond.wait(attente)
            self._lecteur = self._horloge()
            if not self._file:
                return None
            taux, son = self._file.popleft()
            morceaux = [son]
            total = len(son)
            while self._file and self._file[0][0] == taux and total + len(self._file[0][1]) <= self.MAX_ENVOI:
                suite = self._file.popleft()[1]
                morceaux.append(suite)
                total += len(suite)
            self._taille -= total
            return taux, b"".join(morceaux)

    def vider(self) -> None:
        """Couper la parole : plus de son en attente, et la voix revient au PC."""
        with self._cond:
            self._file.clear()
            self._taille = 0
            self._route = None

    def octets(self) -> int:
        with self._cond:
            return self._taille


SORTIE = SortieTele()
