r"""Petits tests sans installation (unittest de Python).
Lancer depuis le dossier de Jarvis :  .venv\Scripts\python.exe -m unittest discover tests
"""
import ast
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


class TestCerveau(unittest.TestCase):
    def test_fiche_courte_si_elle_existe(self):
        from plugins._cerveau_commun import FICHE
        if not FICHE.exists():
            self.skipTest("pas encore de cerveau installé")
        self.assertLess(len(FICHE.read_text(encoding="utf-8")), 4500,
                        "la fiche doit rester sous 4 500 caractères")

    def test_recherche_sans_erreur(self):
        from plugins._cerveau_commun import chercher
        self.assertIsInstance(chercher("projet"), list)

    def test_main_lit_la_fiche_au_bon_endroit(self):
        source = (RACINE / "main.py").read_text(encoding="utf-8")
        self.assertIn("from plugins._cerveau_commun import FICHE", source)


class TestPlugins(unittest.TestCase):
    def test_tous_les_plugins_sont_bien_formes(self):
        for f in (RACINE / "plugins").glob("*.py"):
            if f.name.startswith("_"):
                continue
            arbre = ast.parse(f.read_text(encoding="utf-8"))
            noms = {n.targets[0].id for n in arbre.body if isinstance(n, ast.Assign)
                    and isinstance(n.targets[0], ast.Name)}
            fonctions = {n.name for n in arbre.body if isinstance(n, ast.FunctionDef)}
            self.assertIn("PLUGIN", noms, f"{f.name} : PLUGIN manquant")
            self.assertIn("run", fonctions, f"{f.name} : fonction run manquante")


class TestNavigateur(unittest.TestCase):
    def test_edge_reconnu_par_son_nom_exact(self):
        from actions.browser_control import _PROCESSUS
        self.assertEqual(_PROCESSUS["edge"], "msedge.exe")   # pas msedgewebview2.exe


if __name__ == "__main__":
    unittest.main()
