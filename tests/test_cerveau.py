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


class TestBugsDejaCorriges(unittest.TestCase):
    """Un test par bug signalé : il ne doit plus jamais revenir."""

    def test_prenom_vide_ou_unknown_pas_enregistre(self):
        # Bug du 31/10 : la personne passe la question, « unknown » était enregistré comme prénom.
        from plugins._cerveau_commun import valeur_vide
        for v in ("", "  ", "unknown", "Unknown", "inconnu", "N/A", None):
            self.assertTrue(valeur_vide(v), f"{v!r} devrait être ignoré")
        self.assertFalse(valeur_vide("Frédéric"))

    def test_prenom_first_name_apparait_dans_la_page_moi(self):
        # Bug du 30/10 : Gemini range le prénom sous « first_name » au lieu de « name ».
        import tempfile
        import plugins._cerveau_commun as cc
        with tempfile.TemporaryDirectory() as tmp:
            ancien = cc.WIKI
            cc.WIKI = Path(tmp)
            try:
                cc.page_moi({"identity": {"first_name": {"value": "Cyril"}}})
                texte = (Path(tmp) / "entites" / "moi.md").read_text(encoding="utf-8")
            finally:
                cc.WIKI = ancien
        self.assertIn("**Prénom** : Cyril", texte)

    def test_compteur_processeur_demarre_mesure(self):
        # Bug du 31/10 : le compteur CPU affichait 0 % car la 1re mesure de psutil n'était pas amorcée.
        source = (RACINE / "core" / "iron_hud.py").read_text(encoding="utf-8")
        init = source.split("class _Donnees:")[1].split("def maj(self)")[0]
        self.assertIn("psutil.cpu_percent(None)", init)


class TestMeteoVille(unittest.TestCase):
    """Bug d'Abdel (31/10) : la ville apprise par Jarvis n'était pas utilisée, la météo restait sur Paris."""

    def setUp(self):
        try:
            import core.iron_hud as hud
        except Exception as e:      # PyQt6 absent : test ignoré
            self.skipTest(f"iron_hud non importable : {e}")
        import json
        import tempfile
        self.hud = hud
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.sauve = (hud.INTERFACE, hud.MEMOIRE, hud.GEO_CACHE, hud._geocoder)
        hud.INTERFACE, hud.MEMOIRE, hud.GEO_CACHE = t / "interface.json", t / "long_term.json", t / "geo.json"
        self.json = json

    def tearDown(self):
        h = self.hud
        h.INTERFACE, h.MEMOIRE, h.GEO_CACHE, h._geocoder = self.sauve
        self.tmp.cleanup()

    def _memoire(self, ville):
        self.hud.MEMOIRE.write_text(self.json.dumps({"identity": {"city": {"value": ville}}}), encoding="utf-8")

    def test_ville_apprise_utilisee(self):
        self._memoire("Lille")
        self.hud._geocoder = lambda v: {"ville": v, "lat": 50.63, "lon": 3.06}
        self.assertEqual(self.hud._lieu()["ville"], "Lille")

    def test_sans_ville_on_garde_paris(self):
        self.assertEqual(self.hud._lieu()["ville"], "Paris")

    def test_geocodage_en_panne_retombe_sur_paris(self):
        self._memoire("Lille")
        self.hud._geocoder = lambda v: None
        self.assertEqual(self.hud._lieu()["ville"], "Paris")

    def test_reglage_manuel_prioritaire(self):
        self._memoire("Lille")
        self.hud.INTERFACE.write_text(self.json.dumps({"ville": "Nice", "latitude": 43.7, "longitude": 7.26}),
                                      encoding="utf-8")
        self.hud._geocoder = lambda v: {"ville": v, "lat": 50.63, "lon": 3.06}
        self.assertEqual(self.hud._lieu()["ville"], "Nice")


if __name__ == "__main__":
    unittest.main()
