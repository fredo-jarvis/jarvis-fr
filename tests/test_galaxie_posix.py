"""Ouverture de la galaxie hors Windows : Chrome en mode application, suivi du processus."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from galaxie import server  # noqa: E402


class OuvertureHorsWindows(unittest.TestCase):
    def setUp(self):
        server.FENETRE = None
        server.FENETRE_ISOLEE = False

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
                mock.patch.object(server, "firefox_posix", return_value=None), \
                mock.patch.object(server.webbrowser, "open") as ouvrir:
            self.assertFalse(server.ouvrir_fenetre_posix())
        ouvrir.assert_called_once_with(server.ADRESSE)
        self.assertIsNone(server.FENETRE)

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


class FirefoxIsole(unittest.TestCase):
    def setUp(self):
        server.FENETRE = None
        server.FENETRE_ISOLEE = False

    def _ouvrir(self, vivant=True):
        lance = mock.Mock(pid=4242, returncode=None if vivant else 1)
        lance.poll.return_value = None if vivant else 1
        with mock.patch.object(server, "chrome_posix", return_value=None), \
                mock.patch.object(server, "firefox_posix", return_value="/usr/bin/firefox"), \
                mock.patch.object(server, "profil_firefox", return_value=Path(tempfile.mkdtemp())), \
                mock.patch.object(server.time, "sleep"), \
                mock.patch.object(server.subprocess, "Popen", return_value=lance) as popen, \
                mock.patch.object(server.webbrowser, "open") as ouvrir:
            ok = server.ouvrir_fenetre_posix()
        return ok, popen, ouvrir, lance

    def test_firefox_est_lance_isole_avec_profil_dedie(self):
        ok, popen, ouvrir, lance = self._ouvrir()
        self.assertTrue(ok)
        commande = popen.call_args[0][0]
        self.assertIn("--no-remote", commande)
        self.assertIn("--profile", commande)
        self.assertEqual(commande[-1], server.ADRESSE)
        self.assertTrue(popen.call_args[1]["start_new_session"])
        self.assertIs(server.FENETRE, lance)
        self.assertTrue(server.FENETRE_ISOLEE)
        ouvrir.assert_not_called()

    def test_firefox_qui_s_arrete_tout_de_suite_retombe_sur_le_navigateur_par_defaut(self):
        ok, _popen, ouvrir, _lance = self._ouvrir(vivant=False)
        self.assertFalse(ok)
        self.assertIsNone(server.FENETRE)
        ouvrir.assert_called_once_with(server.ADRESSE)

    def test_fermeture_ne_vise_que_le_groupe_de_jarvis(self):
        server.FENETRE, server.FENETRE_ISOLEE = mock.Mock(pid=4242), True
        server.FENETRE.poll.return_value = None
        with mock.patch.object(server.os, "getpgid", return_value=4242), \
                mock.patch.object(server.os, "getpgrp", return_value=1), \
                mock.patch.object(server.os, "killpg") as killpg:
            server.fermer_fenetre_posix()
        killpg.assert_called_once_with(4242, server.signal.SIGTERM)
        server.FENETRE.terminate.assert_not_called()

    def test_fermeture_force_apres_delai_dans_le_meme_groupe(self):
        f = mock.Mock(pid=4242)
        f.poll.return_value = None
        f.wait.side_effect = subprocess.TimeoutExpired("firefox", 2.5)
        server.FENETRE, server.FENETRE_ISOLEE = f, True
        with mock.patch.object(server.os, "getpgid", return_value=4242), \
                mock.patch.object(server.os, "getpgrp", return_value=1), \
                mock.patch.object(server.os, "killpg") as killpg:
            server.fermer_fenetre_posix()
        self.assertEqual([c.args for c in killpg.call_args_list],
                         [(4242, server.signal.SIGTERM), (4242, server.signal.SIGKILL)])

    def test_groupe_qui_n_est_pas_le_notre_jamais_tue_en_bloc(self):
        f = mock.Mock(pid=4242)
        f.poll.return_value = None
        server.FENETRE, server.FENETRE_ISOLEE = f, True
        for groupe in (1, 777):            # groupe de Jarvis lui-même, ou groupe partagé avec d'autres processus
            f.reset_mock()
            f.poll.return_value = None
            with mock.patch.object(server.os, "getpgid", return_value=groupe), \
                    mock.patch.object(server.os, "getpgrp", return_value=1), \
                    mock.patch.object(server.os, "killpg") as killpg:
                server.fermer_fenetre_posix()
            killpg.assert_not_called()
            f.terminate.assert_called_once()

    def test_fermeture_chrome_inchangee(self):
        f = mock.Mock()
        f.poll.return_value = None
        server.FENETRE, server.FENETRE_ISOLEE = f, False
        with mock.patch.object(server.os, "killpg") as killpg:
            server.fermer_fenetre_posix()
        f.terminate.assert_called_once()
        killpg.assert_not_called()

    def test_attendre_sans_fenetre_suivie_n_eteint_pas_jarvis(self):
        self.assertFalse(server.attendre_fenetre_posix())

    def test_profil_dans_snap_ou_etat_jamais_le_profil_habituel(self):
        with mock.patch.object(Path, "resolve", return_value=Path("/snap/firefox/current/firefox")):
            self.assertIn("snap/firefox/common/jarvis-fr-galaxie", str(server.profil_firefox("/usr/bin/firefox")))
        with mock.patch.object(Path, "resolve", return_value=Path("/usr/lib/firefox/firefox")):
            self.assertIn("jarvis-fr/firefox-galaxie", str(server.profil_firefox("/usr/bin/firefox")))


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
