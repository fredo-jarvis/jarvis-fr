"""Sécurité de la télécommande du téléphone (revue du 2026-11-12).

Avant : la page de connexion acceptait un nombre illimité d'essais de clé. La clé à usage unique ne dure que dix
minutes, mais rien n'empêchait un appareil du même réseau d'en essayer des milliers. Maintenant : au bout de
5 mauvais essais, l'appareil est bloqué 5 minutes, même s'il donne ensuite la bonne clé.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dashboard.limite_essais import LimiteEssais  # noqa: E402


class LimiteEssaisSeule(unittest.TestCase):
    def test_bloque_apres_cinq_echecs(self):
        lim = LimiteEssais(maxi=5, fenetre=300, blocage=300)
        for _ in range(4):
            lim.echec("1.2.3.4", maintenant=100)
        self.assertFalse(lim.bloque("1.2.3.4", maintenant=101))
        lim.echec("1.2.3.4", maintenant=102)
        self.assertTrue(lim.bloque("1.2.3.4", maintenant=103))

    def test_debloque_apres_le_delai(self):
        lim = LimiteEssais(maxi=5, fenetre=300, blocage=300)
        for _ in range(5):
            lim.echec("1.2.3.4", maintenant=100)
        self.assertTrue(lim.bloque("1.2.3.4", maintenant=399))
        self.assertFalse(lim.bloque("1.2.3.4", maintenant=401))

    def test_les_appareils_sont_independants(self):
        lim = LimiteEssais(maxi=5, fenetre=300, blocage=300)
        for _ in range(5):
            lim.echec("1.2.3.4", maintenant=100)
        self.assertFalse(lim.bloque("5.6.7.8", maintenant=101))

    def test_les_vieux_echecs_ne_comptent_plus(self):
        lim = LimiteEssais(maxi=5, fenetre=300, blocage=300)
        for _ in range(4):
            lim.echec("1.2.3.4", maintenant=100)
        lim.echec("1.2.3.4", maintenant=1000)          # les 4 premiers ont plus de 300 s
        self.assertFalse(lim.bloque("1.2.3.4", maintenant=1001))

    def test_une_reussite_remet_a_zero(self):
        lim = LimiteEssais(maxi=5, fenetre=300, blocage=300)
        for _ in range(4):
            lim.echec("1.2.3.4", maintenant=100)
        lim.reussite("1.2.3.4")
        lim.echec("1.2.3.4", maintenant=101)
        self.assertFalse(lim.bloque("1.2.3.4", maintenant=102))


class TelecommandeBranchee(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from dashboard.server import DashboardServer
        self.serveur = DashboardServer()
        self.client = TestClient(self.serveur.app)

    def test_apres_cinq_mauvaises_cles_meme_la_bonne_est_refusee(self):
        bonne = self.serveur.new_key()
        for i in range(5):
            self.assertEqual(self.client.post("/login", json={"pin": f"ZZZZZ{i}"}).status_code, 401)
        self.assertEqual(self.client.post("/login", json={"pin": bonne}).status_code, 429)

    def test_le_lien_du_qr_code_est_limite_aussi(self):
        bonne = self.serveur.new_key()
        for i in range(5):
            self.client.get(f"/auto-login?key=ZZZZZ{i}")
        reponse = self.client.get(f"/auto-login?key={bonne}", follow_redirects=False)
        self.assertEqual(reponse.status_code, 429)

    def test_la_bonne_cle_fonctionne_sans_essais_rates(self):
        bonne = self.serveur.new_key()
        self.assertEqual(self.client.post("/login", json={"pin": bonne}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
