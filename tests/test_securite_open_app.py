"""Sécurité de « ouvre telle application » (revue du 2026-11-12).

Le nom de l'application vient de Gemini, donc potentiellement d'un texte lu par Jarvis (page web, mail, PDF) qui
contiendrait des instructions cachées. Il ne doit JAMAIS être passé tel quel à un interpréteur de commandes :
avant, `start {nom}` était lancé avec shell=True, et « x:&calc » exécutait aussi calc.
"""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from actions import open_app  # noqa: E402


def faux_pyautogui():
    """Évite d'appuyer sur de vraies touches pendant les tests."""
    return types.SimpleNamespace(PAUSE=0, press=mock.Mock(), write=mock.Mock(), hotkey=mock.Mock())


class OuvrirUneApplicationSansShell(unittest.TestCase):
    def lancer(self, nom, which=None):
        popen, startfile, pag = mock.Mock(), mock.Mock(), faux_pyautogui()
        with mock.patch.object(open_app.subprocess, "Popen", popen), \
                mock.patch.object(open_app.shutil, "which", return_value=which), \
                mock.patch.object(os, "startfile", startfile, create=True), \
                mock.patch.dict(sys.modules, {"pyautogui": pag}), \
                mock.patch.object(open_app.time, "sleep"):
            open_app._launch_windows(nom)
        return popen, startfile

    def test_aucune_commande_ne_passe_par_le_shell(self):
        for nom in ("x:&calc.exe", "http://a.b & del /q *", "ms-settings:|whoami", "app:^&cmd", "a:%COMSPEC%"):
            popen, startfile = self.lancer(nom)
            for appel in popen.call_args_list:
                self.assertFalse(appel.kwargs.get("shell"), f"{nom!r} lancé avec shell=True")
            startfile.assert_not_called()

    def test_un_programme_trouve_est_lance_sans_shell(self):
        popen, _ = self.lancer("notepad.exe", which=r"C:\Windows\notepad.exe")
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], [r"C:\Windows\notepad.exe"])
        self.assertFalse(popen.call_args.kwargs.get("shell"))

    def test_un_nom_avec_caracteres_speciaux_ne_lance_pas_le_programme_trouve(self):
        popen, _ = self.lancer("calc.exe & whoami", which=r"C:\Windows\calc.exe")
        popen.assert_not_called()

    def test_un_lien_normal_s_ouvre_toujours(self):
        for nom in ("ms-settings:", "ms-settings:network-wifi", "spotify:", "https://exemple.fr/a?b=1&c=2"):
            popen, startfile = self.lancer(nom)
            startfile.assert_called_once_with(nom)
            popen.assert_not_called()

    def test_les_liens_dangereux_sont_refuses(self):
        for nom in ("file:///C:/Windows/System32/cmd.exe", "ms-msdt:/id PCWDiagnostic", "search-ms:query=x",
                    "javascript:alert(1)", "vbscript:x"):
            popen, startfile = self.lancer(nom)
            startfile.assert_not_called()
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
