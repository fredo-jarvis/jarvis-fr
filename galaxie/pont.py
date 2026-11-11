r"""
Le pont entre la page de la galaxie et le vrai Jarvis (ajouté le 04/11/2026).

Il écoute ce que Jarvis écrit dans sa fenêtre (journal, état, confirmations) pour le montrer dans la page,
et il transmet les demandes de la page à Jarvis. Une confirmation ne peut venir que d'un clic dans la page.
"""
import threading
from collections import deque

class Pont:
    def __init__(self, jarvis, ui, nom_modele, confirm, holo=None):
        self.jarvis, self.ui, self.nom_modele, self.confirm = jarvis, ui, nom_modele, confirm
        self.holo = holo
        self.journal = deque(maxlen=200)
        self.numero = 0
        self.etat = "THINKING"
        self.confirmation = None
        self.verrou = threading.Lock()
        self.verrou_voix = threading.Lock()
        self._brancher()

    def _brancher(self):
        ui = self.ui
        log, etat, montrer, cacher = ui.write_log, ui.set_state, ui.show_confirm, ui.hide_confirm

        def write_log(texte):
            self.noter(str(texte))
            log(texte)

        def set_state(valeur):
            self.etat = str(valeur)
            etat(valeur)

        def show_confirm(titre, detail):
            self.confirmation = {"titre": str(titre)[:120], "detail": str(detail)[:300]}
            montrer(titre, detail)

        def hide_confirm():
            self.confirmation = None
            cacher()

        ui.write_log, ui.set_state, ui.show_confirm, ui.hide_confirm = write_log, set_state, show_confirm, hide_confirm

    def noter(self, texte: str):
        with self.verrou:
            self.numero += 1
            self.journal.append({"n": self.numero, "texte": texte[:2000]})

    def photo(self, depuis: int = 0) -> dict:
        with self.verrou:
            lignes = [l for l in self.journal if l["n"] > depuis]
            numero = self.numero
        j = self.jarvis
        cerveau = getattr(j, "_cerveau", "cloud")
        if cerveau == "local":
            connexion = "LOCAL"
        elif getattr(j, "session", None) is not None:
            connexion = "EN LIGNE"
        else:
            connexion = "CONNEXION"
        return {"branche": True, "etat": self.etat, "cerveau": cerveau, "connexion": connexion,
                "modele": str(self.nom_modele()).split("/")[-1].replace("-preview", "").replace("-live", ""), "lignes": lignes, "numero": numero,
                "confirmation": self.confirmation if self.confirm.pending_title() else None,
                "muet": bool(getattr(self.ui, "muted", False))}

    def commande(self, texte: str):
        texte = (texte or "").strip()
        if not texte:
            raise ValueError("Écris d'abord quelque chose.")
        self.jarvis._on_text_command(texte[:2000])

    def voix_tele(self, pcm: bytes) -> str:
        """Une phrase dite au micro de la télé (16 kHz, mono) : elle suit le même chemin qu'une demande tapée, et la réponse sort de la télé."""
        import numpy as np
        from core import oreilles_locales, sortie_tele
        pcm = pcm[:len(pcm) // 2 * 2]
        if len(pcm) < oreilles_locales.TAUX // 2:
            raise ValueError("Je n'ai rien entendu.")
        with self.verrou_voix:
            if self.jarvis._oreilles_locales is None:
                self.jarvis._oreilles_locales = oreilles_locales.Oreilles()
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
            texte = self.jarvis._oreilles_locales.transcrire(audio)
        phrase = oreilles_locales.nettoyer(texte, False)
        print(f"[Télé] micro : {len(audio) / oreilles_locales.TAUX:.1f} s, pic {float(np.abs(audio).max()):.3f}, écrit : {phrase[:60]!r}")
        if not phrase:
            raise ValueError("Je n'ai rien compris. Réessaie, un peu plus fort.")
        sortie_tele.SORTIE.demander()
        self.commande(phrase)
        return phrase

    def son_tele(self):
        from core import sortie_tele
        return sortie_tele.SORTIE.lire()

    def changer_cerveau(self, voulu: str) -> str:
        if voulu not in ("local", "cloud"):
            raise ValueError("Cerveau inconnu.")
        message = self.jarvis.changer_cerveau(voulu)
        self.noter("SYS: " + message)
        return message

    def confirmer(self, accepte: bool):
        self.confirmation = None
        self.confirm.resolve(bool(accepte))

    def muet(self, voulu: bool):
        """Coupe ou remet le micro (le bouton MICRO de la page, comme la touche F4)."""
        self.ui.set_muted(bool(voulu))
        self.noter("SYS: Microphone " + ("coupé." if voulu else "actif."))

    def couper(self):
        boucle = getattr(self.jarvis, "_loop", None)
        if boucle:
            boucle.call_soon_threadsafe(self.jarvis.interrupt)

    def hologramme(self):
        if self.holo:
            self.holo()
