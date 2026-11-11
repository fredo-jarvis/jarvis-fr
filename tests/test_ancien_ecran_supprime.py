"""Demande de l'utilisateur (2026-11-11) : « L'ancienne interface en bleu, je ne veux plus la voir. Elle doit être supprimée. »
La Galaxie et Jarvis OS restent ; le bouton HOLO (serveur à part, dossier holo) aussi."""
import os
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FICHIERS_SUPPRIMES = ("iron_hud.py", "decor_cercle.py", "panneaux_holo.py", "jarvis_vivant.py")


class AncienEcranSupprime(unittest.TestCase):
    def test_les_fichiers_de_l_ancien_ecran_n_existent_plus(self):
        for nom in FICHIERS_SUPPRIMES:
            self.assertFalse((RACINE / "core" / nom).exists(), nom)

    def test_plus_aucun_code_ne_les_appelle(self):
        for fichier in [RACINE / "ui.py", RACINE / "main.py", *sorted((RACINE / "core").glob("*.py")),
                        *sorted((RACINE / "plugins").glob("*.py")), *sorted((RACINE / "galaxie").glob("*.py"))]:
            texte = fichier.read_text(encoding="utf-8")
            for mot in ("iron_hud", "decor_cercle", "panneaux_holo", "jarvis_vivant"):
                self.assertNotIn(mot, texte, f"{mot} dans {fichier.name}")

    def test_la_fenetre_se_dessine_encore_pour_le_moteur(self):
        from PyQt6.QtGui import QGuiApplication, QImage, QPainter
        from PyQt6.QtWidgets import QApplication
        _app = QGuiApplication.instance() or QApplication([])
        import ui
        canvas = ui.HudCanvas("")
        canvas.resize(800, 450)
        canvas.minimal = True
        image = QImage(800, 450, QImage.Format.Format_ARGB32)
        p = QPainter(image)
        canvas.render(p)
        p.end()
        self.assertFalse(image.isNull())

    def test_le_bouton_holo_ne_depend_pas_de_l_ancien_ecran(self):
        plugin = (RACINE / "plugins" / "cerveau_hologramme.py").read_text(encoding="utf-8")
        self.assertIn("4890", plugin)
        self.assertTrue((RACINE / "plugins" / "cerveau_hologramme.py").exists())


if __name__ == "__main__":
    unittest.main()
