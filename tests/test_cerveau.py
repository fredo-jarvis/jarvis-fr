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


class TestChangerEcran(unittest.TestCase):
    """Bug de Jibis Lucius (01/11) : avec trois écrans, impossible de déplacer Jarvis."""

    def test_ecran_suivant_fait_le_tour(self):
        try:
            from ui import _ecran_suivant
        except Exception as e:
            self.skipTest(f"ui non importable : {e}")
        self.assertEqual(_ecran_suivant(["A", "B", "C"], "A"), "B")
        self.assertEqual(_ecran_suivant(["A", "B", "C"], "B"), "C")
        self.assertEqual(_ecran_suivant(["A", "B", "C"], "C"), "A")      # on refait le tour
        self.assertEqual(_ecran_suivant(["A", "B"], "inconnu"), "A")
        self.assertIsNone(_ecran_suivant(["A"], "A"))                    # un seul écran : rien à faire
        self.assertIsNone(_ecran_suivant([], None))

    def test_plugin_repond_selon_le_nombre_d_ecrans(self):
        from plugins.changer_ecran import run

        class Un:
            def changer_ecran(self):
                return False

        class Trois:
            def changer_ecran(self):
                return True

        self.assertIn("seul écran", run({}, Un()))
        self.assertIn("écran suivant", run({}, Trois()))
        self.assertIn("pas", run({}, None))

    def test_raccourcis_valables_meme_sans_le_focus(self):
        source = (RACINE / "ui.py").read_text(encoding="utf-8")
        self.assertIn('QKeySequence("F3")', source)
        self.assertIn("ApplicationShortcut", source)


class TestFenetreDeplacable(unittest.TestCase):
    """Demande de Fredo (01/11) : pouvoir mettre Jarvis en fenêtre et le déplacer à la souris."""

    def test_rectangle_de_la_fenetre(self):
        try:
            from ui import _rect_fenetre
        except Exception as e:
            self.skipTest(f"ui non importable : {e}")
        self.assertEqual(_rect_fenetre(0, 0, 1920, 1080), (192, 108, 1536, 864))
        x, y, w, h = _rect_fenetre(1920, 0, 2560, 1440)      # écran de droite
        self.assertGreaterEqual(x, 1920)
        self.assertEqual((w, h), (2048, 1152))

    def test_on_peut_attraper_la_fenetre_a_la_souris(self):
        source = (RACINE / "ui.py").read_text(encoding="utf-8")
        self.assertIn("startSystemMove", source)


class TestFichierDepose(unittest.TestCase):
    """Bug d'un client (01/11) : « le fichier que je t'ai envoyé » -> « je n'ai pas de souvenir »."""

    def test_questions_sur_un_fichier(self):
        from core.fichier_depose import parle_d_un_fichier
        for q in ("le fichier que je t'ai envoyé sur les agences", "Allied agences pdf", "mon document",
                  "la pièce jointe", "le fichier déposé"):
            self.assertTrue(parle_d_un_fichier(q), q)
        for q in ("mon prénom", "la ville où j'habite", ""):
            self.assertFalse(parle_d_un_fichier(q), q)

    def test_indice_donne_seulement_si_un_fichier_est_depose(self):
        from core.fichier_depose import indice_fichier
        chemin = "C:/x/07-Alliade-Agences.pdf"
        self.assertIn("file_processor", indice_fichier("le fichier envoyé", chemin))
        self.assertIn("07-Alliade-Agences.pdf", indice_fichier("le fichier envoyé", chemin))
        self.assertEqual(indice_fichier("le fichier envoyé", None), "")
        self.assertEqual(indice_fichier("mon prénom", "C:/x/a.pdf"), "")

    def test_main_et_prompt_utilisent_le_fichier_depose(self):
        self.assertIn("indice_fichier", (RACINE / "main.py").read_text(encoding="utf-8"))
        self.assertIn("[UPLOADED FILES]", (RACINE / "core" / "prompt.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
