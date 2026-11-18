"""Ouverture de la galaxie hors Windows : Chrome en mode application, suivi du processus."""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from galaxie import server  # noqa: E402


class OuvertureHorsWindows(unittest.TestCase):
    def setUp(self):
        server.FENETRE = None

    def test_chrome_est_lance_en_mode_application(self):
        with mock.patch.object(server, "chrome_posix", return_value="/usr/bin/google-chrome"), \
                mock.patch.object(server.subprocess, "Popen") as popen:
            self.assertTrue(server.ouvrir_fenetre_posix())
        commande = popen.call_args[0][0]
        self.assertEqual(commande[0], "/usr/bin/google-chrome")
        self.assertIn(f"--app={server.ADRESSE}", commande)
        self.assertTrue(any(a.startswith("--user-data-dir=") for a in commande))
        self.assertNotIn("creationflags", popen.call_args[1])

    def test_sans_chrome_le_navigateur_par_defaut_s_ouvre(self):
        with mock.patch.object(server, "chrome_posix", return_value=None), \
                mock.patch.object(server.webbrowser, "open") as ouvrir:
            self.assertFalse(server.ouvrir_fenetre_posix())
        ouvrir.assert_called_once_with(server.ADRESSE)

    def test_chrome_qui_repart_tout_de_suite_n_eteint_pas_jarvis(self):
        server.FENETRE = mock.Mock()
        self.assertFalse(server.attendre_fenetre_posix())

    def test_fermer_ne_touche_pas_un_processus_deja_termine(self):
        server.FENETRE = mock.Mock(poll=mock.Mock(return_value=0))
        server.fermer_fenetre_posix()
        server.FENETRE.terminate.assert_not_called()

    def test_ouvrir_fenetre_sous_windows_garde_le_chemin_existant(self):
        with mock.patch.object(server.sys, "platform", "win32"), \
                mock.patch.object(server, "ouvrir_fenetre_posix") as posix, \
                mock.patch.object(server.CHROME.__class__, "exists", return_value=False), \
                mock.patch.object(server.webbrowser, "open"):
            self.assertFalse(server.ouvrir_fenetre())
        posix.assert_not_called()


class DrapeauxDeProcessus(unittest.TestCase):
    def test_creationflags_ne_sont_jamais_non_nuls_hors_windows(self):
        from plugins import cerveau_galaxie, cerveau_hologramme, cerveau_tableau
        attendu = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for module in (cerveau_galaxie, cerveau_hologramme, cerveau_tableau):
            self.assertEqual(module.CREATE_NO_WINDOW, attendu)
        if sys.platform != "win32":
            subprocess.run([sys.executable, "-c", "pass"], creationflags=attendu)


if __name__ == "__main__":
    unittest.main()
