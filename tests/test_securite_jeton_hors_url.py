"""Le jeton de session ne doit plus voyager dans une URL (revue de sécurité).

Avant : `/ws?token=...`, `/ws/phone-audio?token=...` et `/uploads/{fichier}?token=...`
mettaient le jeton dans la query string -- donc potentiellement dans les journaux
d'accès, l'historique du navigateur ou un en-tête Referer.

Maintenant :
  - les deux WebSockets exigent le jeton comme PREMIER message envoyé après la
    connexion (`{"type": "auth", "token": "..."}`), jamais dans l'URL ;
  - le téléchargement de fichier s'authentifie par l'en-tête Authorization,
    comme les autres routes -- un `?token=` dans l'URL ne fonctionne plus.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402
from dashboard.server import DashboardServer  # noqa: E402


class JetonHorsURL(unittest.TestCase):
    def setUp(self):
        self.serveur = DashboardServer()
        self.client = TestClient(self.serveur.app)
        cle = self.serveur.new_key()
        self.token = self.client.post("/login", json={"pin": cle}).json()["token"]

    # ── /ws ──────────────────────────────────────────────────────────────
    def test_ws_accepte_avec_bon_jeton_en_premier_message(self):
        with self.client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "token": self.token})
            # Pas de fermeture immédiate : on peut encore échanger.
            ws.send_json({"type": "command", "text": ""})  # texte vide -> ignoré, pas d'erreur

    def test_ws_refuse_un_mauvais_jeton(self):
        with self.client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "token": "ce-jeton-n-existe-pas"})
            with self.assertRaises(Exception):
                ws.receive_json()  # la connexion doit être fermée (code 4001)

    def test_ws_refuse_si_le_premier_message_n_est_pas_une_auth(self):
        with self.client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "command", "text": "coucou"})
            with self.assertRaises(Exception):
                ws.receive_json()

    def test_ws_ignore_un_ancien_jeton_dans_l_url(self):
        # L'ancienne méthode (query string) ne doit plus servir à s'authentifier :
        # sans message d'auth envoyé, la connexion doit se fermer.
        with self.client.websocket_connect(f"/ws?token={self.token}") as ws:
            with self.assertRaises(Exception):
                ws.receive_json()

    # ── /ws/phone-audio ──────────────────────────────────────────────────
    def test_phone_audio_accepte_avec_bon_jeton_en_premier_message(self):
        with self.client.websocket_connect("/ws/phone-audio") as ws:
            ws.send_json({"type": "auth", "token": self.token})
            ws.send_bytes(b"\x00\x00")  # un petit fragment audio, ne doit rien lever

    def test_phone_audio_refuse_un_mauvais_jeton(self):
        with self.client.websocket_connect("/ws/phone-audio") as ws:
            ws.send_json({"type": "auth", "token": "faux"})
            with self.assertRaises(Exception):
                ws.receive_bytes()

    # ── /uploads/{filename} ──────────────────────────────────────────────
    def test_telechargement_avec_en_tete_autorisation(self):
        fichier = self.serveur._uploads_dir / "test_jeton_hors_url.txt"
        self.serveur._uploads_dir.mkdir(parents=True, exist_ok=True)
        fichier.write_text("contenu")
        try:
            reponse = self.client.get(
                "/uploads/test_jeton_hors_url.txt",
                headers={"Authorization": f"Bearer {self.token}"},
            )
            self.assertEqual(reponse.status_code, 200)
            self.assertEqual(reponse.text, "contenu")
        finally:
            fichier.unlink(missing_ok=True)

    def test_telechargement_refuse_sans_authentification(self):
        fichier = self.serveur._uploads_dir / "test_jeton_hors_url.txt"
        self.serveur._uploads_dir.mkdir(parents=True, exist_ok=True)
        fichier.write_text("contenu")
        try:
            reponse = self.client.get("/uploads/test_jeton_hors_url.txt")
            self.assertEqual(reponse.status_code, 401)
        finally:
            fichier.unlink(missing_ok=True)

    def test_l_ancien_token_dans_l_url_ne_fonctionne_plus(self):
        fichier = self.serveur._uploads_dir / "test_jeton_hors_url.txt"
        self.serveur._uploads_dir.mkdir(parents=True, exist_ok=True)
        fichier.write_text("contenu")
        try:
            reponse = self.client.get(f"/uploads/test_jeton_hors_url.txt?token={self.token}")
            self.assertEqual(reponse.status_code, 401)
        finally:
            fichier.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
