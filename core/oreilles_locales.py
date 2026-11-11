r"""
Oreilles locales de Jarvis (Whisper sur le PC) : ajoutées le 04/11/2026.

Le micro est découpé en phrases ici, puis Whisper écrit ce qui a été dit. Rien ne sort du PC.
Avec des haut-parleurs, le micro est ignoré tant que Jarvis parle (il s'entendrait lui-même),
on lui coupe la parole avec Échap.
"""
import re
from pathlib import Path

import numpy as np

TAUX = 16000
MODELE = "small"             # environ 480 Mo, bon français, assez rapide sur le processeur
SILENCE_S = 0.7              # fin de phrase après ce silence
AVANT_S = 0.3                # on garde ce qu'il y a juste avant, pour ne pas couper le premier mot
MIN_PAROLE_S = 0.35          # en dessous : un bruit, pas une phrase
MAX_PHRASE_S = 20.0
PART_DU_PIC = 0.25           # la voix retombe sous ce quart de son maximum : c'est un silence, même si le fond est bruyant
SEUIL_MIN = 0.004            # plancher de volume : certains casques captent très bas (silence à 0,00001)
MULTIPLE_BRUIT = 3.0         # une voix est au moins 3 fois plus forte que le bruit de la pièce

# Sur du bruit, Whisper invente souvent ces phrases, apprises dans les sous-titres de vidéos.
_INVENTIONS = ("sous-titr", "sous titr", "amara.org", "merci d'avoir regard", "abonnez-vous", "à bientôt pour une prochaine")


# Ces mots aident Whisper à ne pas se tromper sur le vocabulaire de l'utilisateur.
VOCABULAIRE = ("Conversation avec Jarvis, l'assistant vocal. J'ai des mails ? Lis mes mails, mon agenda, mes rendez-vous, "
               "mes notes, le cerveau local, le cerveau en ligne, Gmail, la météo.")
# Vu dans le journal : Whisper écrit « mailles » pour « mails ». On ne touche pas à « cotte de mailles ».
_CORRECTIONS = ((r"(?i)(?<!cotte de )\bmailles\b", "mails"), (r"(?i)(?<!cotte de )\bmaille\b", "mail"),
                (r"(?i)^pas sur (le|ton|mon) cerveau", r"passe sur \1 cerveau"))


class Decoupeur:
    """Reçoit le micro bloc par bloc et rend une phrase entière quand elle est finie, sinon None."""

    def __init__(self, taux: int = TAUX):
        self.taux = taux
        self.bruit = SEUIL_MIN / MULTIPLE_BRUIT
        self.avant, self.phrase = [], []
        self.en_cours = False
        self.silence = self.parole = self.pic = 0.0

    def seuil(self) -> float:
        return max(SEUIL_MIN, self.bruit * MULTIPLE_BRUIT)

    def _vider(self) -> None:
        self.phrase, self.avant = [], []
        self.en_cours = False
        self.silence = self.parole = self.pic = 0.0

    def ajouter(self, bloc: np.ndarray):
        bloc = np.asarray(bloc, dtype=np.float32).reshape(-1)
        duree = len(bloc) / self.taux
        volume = float(np.sqrt(np.mean(bloc * bloc))) if len(bloc) else 0.0
        fort = volume >= self.seuil()
        # Le bruit de la pièce : il descend tout de suite, et monte lentement. Une voix a des creux, un ventilateur non.
        self.bruit = volume if volume < self.bruit else self.bruit + (volume - self.bruit) * 0.01
        if not self.en_cours:
            if not fort:
                self.avant.append(bloc)
                while sum(len(b) for b in self.avant) > AVANT_S * self.taux:
                    self.avant.pop(0)
                return None
            self.en_cours = True
            self.phrase = list(self.avant)
        self.phrase.append(bloc)
        self.pic = max(self.pic, volume)
        if fort and volume >= self.pic * PART_DU_PIC:
            self.parole += duree
            self.silence = 0.0
        else:
            self.silence += duree
        total = sum(len(b) for b in self.phrase) / self.taux
        if self.silence < SILENCE_S and total < MAX_PHRASE_S:
            return None
        finie, parole = self.phrase, self.parole
        self._vider()
        return np.concatenate(finie) if parole >= MIN_PAROLE_S else None


def nettoyer(texte: str, nom_obligatoire: bool = False) -> str:
    """Rend la commande à traiter, ou "" s'il n'y a rien à faire (bruit, invention de Whisper, nom absent)."""
    texte = " ".join((texte or "").split()).strip()
    for motif, juste in _CORRECTIONS:
        texte = re.sub(motif, juste, texte)
    bas = texte.lower()
    if len(re.sub(r"\W", "", bas)) < 2 or any(x in bas for x in _INVENTIONS):
        return ""
    m = re.match(r"^(?:h[eé]\s+|hey\s+|ok\s+|dis\s+)?jarvis\b[\s,.:!?-]*", texte, re.IGNORECASE)
    if m:
        return texte[m.end():].strip()
    return "" if nom_obligatoire else texte


def remonter(audio: np.ndarray) -> np.ndarray:
    """Met le son à un volume normal pour Whisper : un micro qui capte bas ne doit pas gêner la compréhension."""
    audio = np.asarray(audio, dtype=np.float32)
    pic = float(np.abs(audio).max()) if len(audio) else 0.0
    return audio * (.5 / pic) if pic > 1e-6 else audio


class Oreilles:
    """Whisper chargé une seule fois. On n'importe faster_whisper qu'au besoin : Jarvis démarre sans lui."""

    def __init__(self, modele: str = MODELE):
        self.nom = modele
        self.modele = None

    def charger(self) -> None:
        if self.modele is None:
            from faster_whisper import WhisperModel
            dossier = Path(__file__).resolve().parent.parent / "modeles" / "whisper"
            self.modele = WhisperModel(self.nom, device="cpu", compute_type="int8", download_root=str(dossier))

    def transcrire(self, audio: np.ndarray) -> str:
        self.charger()
        morceaux, _info = self.modele.transcribe(remonter(audio), language="fr", beam_size=3,
                                                 vad_filter=True, condition_on_previous_text=False,
                                                 initial_prompt=VOCABULAIRE)
        return " ".join(m.text.strip() for m in morceaux if m.no_speech_prob < 0.7).strip()
