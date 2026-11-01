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
        self.assertIn("fichiers_retenus", (RACINE / "main.py").read_text(encoding="utf-8"))
        self.assertIn("[UPLOADED FILES]", (RACINE / "core" / "prompt.txt").read_text(encoding="utf-8"))


def _pdf_avec_texte(chemin, texte):
    """Un vrai petit PDF avec du texte (écrit à la main, sans bibliothèque)."""
    flux = f"BT /F1 18 Tf 72 720 Td ({texte}) Tj ET".encode("latin-1")
    objets = [b"<< /Type /Catalog /Pages 2 0 R >>",
              b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
              b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
              b"/Resources << /Font << /F1 5 0 R >> >> >>",
              b"<< /Length %d >>\nstream\n" % len(flux) + flux + b"\nendstream",
              b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, positions = b"%PDF-1.4\n", []
    for i, o in enumerate(objets, 1):
        positions.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objets) + 1)
    for p in positions:
        out += b"%010d 00000 n \n" % p
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objets) + 1, xref)
    Path(chemin).write_bytes(out)


class TestLireTousLesFichiers(unittest.TestCase):
    """Un client dépose un PDF et Jarvis ne le lit pas (01/11) : il doit lire TOUS les types de fichiers."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.dossier = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _lire(self, nom):
        from core.lecteur_fichier import lire_texte
        return lire_texte(self.dossier / nom)

    def test_texte_utf8_et_ancien_encodage(self):
        (self.dossier / "a.txt").write_text("Rendez-vous à l'agence Allied, rue de l'Été", encoding="utf-8")
        (self.dossier / "b.txt").write_bytes("Café crème à 2 € (Windows)".encode("cp1252"))
        (self.dossier / "c.md").write_text("# Titre\nPhrase en *markdown*", encoding="utf-8")
        self.assertIn("rue de l'Été", self._lire("a.txt"))
        self.assertIn("Café crème", self._lire("b.txt"))
        self.assertIn("Phrase en", self._lire("c.md"))

    def test_csv_json_xml_code_et_extension_inconnue(self):
        (self.dossier / "t.csv").write_text("nom;prix\nPomme;2\n", encoding="utf-8")
        (self.dossier / "d.json").write_text('{"ville": "Lille"}', encoding="utf-8")
        (self.dossier / "x.xml").write_text("<a><b>bonjour</b></a>", encoding="utf-8")
        (self.dossier / "s.py").write_text("print('salut')", encoding="utf-8")
        (self.dossier / "note.zzz").write_text("un fichier bizarre mais lisible", encoding="utf-8")
        for nom, attendu in (("t.csv", "Pomme"), ("d.json", "Lille"), ("x.xml", "bonjour"),
                             ("s.py", "salut"), ("note.zzz", "bizarre")):
            self.assertIn(attendu, self._lire(nom), nom)

    def test_word_avec_tableau(self):
        from docx import Document
        doc = Document()
        doc.add_paragraph("Contrat de location")
        t = doc.add_table(rows=1, cols=2)
        t.rows[0].cells[0].text, t.rows[0].cells[1].text = "Loyer", "650 euros"
        doc.save(str(self.dossier / "contrat.docx"))
        texte = self._lire("contrat.docx")
        self.assertIn("Contrat de location", texte)
        self.assertIn("650 euros", texte)

    def test_powerpoint_et_excel(self):
        from pptx import Presentation
        from openpyxl import Workbook
        prs = Presentation()
        diapo = prs.slides.add_slide(prs.slide_layouts[1])
        diapo.shapes.title.text = "Bilan du trimestre"
        prs.save(str(self.dossier / "p.pptx"))
        wb = Workbook()
        wb.active.append(["produit", "quantité"])
        wb.active.append(["clous", 120])
        wb.save(str(self.dossier / "e.xlsx"))
        self.assertIn("Bilan du trimestre", self._lire("p.pptx"))
        self.assertIn("clous | 120", self._lire("e.xlsx"))

    def test_pdf_avec_texte(self):
        _pdf_avec_texte(self.dossier / "agences.pdf", "Alliade Agences Lille")
        self.assertIn("Alliade Agences Lille", self._lire("agences.pdf"))

    def test_pdf_scanne_envoye_en_images(self):
        # Un PDF qui n'est qu'une photo (scanné) : pas de texte, donc Jarvis envoie les pages en images.
        from PIL import Image
        from core.lecteur_fichier import construire_demande, lire_texte
        Image.new("RGB", (400, 300), "white").save(self.dossier / "scan.pdf")
        self.assertEqual(lire_texte(self.dossier / "scan.pdf"), "")
        demande = construire_demande(self.dossier / "scan.pdf", "que dit ce document ?")
        self.assertGreaterEqual(len(demande), 2)
        self.assertIn("que dit ce document", demande[0])

    def test_image_envoyee_a_gemini(self):
        from PIL import Image
        from core.lecteur_fichier import construire_demande
        Image.new("RGB", (200, 100), "blue").save(self.dossier / "photo.png")
        demande = construire_demande(self.dossier / "photo.png", "décris l'image")
        self.assertEqual(len(demande), 2)

    def test_la_question_est_transmise_avec_le_contenu(self):
        from core.lecteur_fichier import repondre
        _pdf_avec_texte(self.dossier / "agences.pdf", "Alliade Agences Lille")
        recu = {}

        def faux_gemini(contenu):
            recu["contenu"] = contenu
            return "L'agence est à Lille."

        rep = repondre(self.dossier / "agences.pdf", "Où est l'agence ?", appeler=faux_gemini)
        self.assertEqual(rep, "L'agence est à Lille.")
        self.assertIn("Alliade Agences Lille", recu["contenu"][0])
        self.assertIn("Où est l'agence ?", recu["contenu"][0])

    def test_fichier_illisible_ou_absent_message_clair(self):
        from core.lecteur_fichier import repondre
        (self.dossier / "vide.pdf").write_bytes(b"")
        (self.dossier / "binaire.bin").write_bytes(b"\x00\x01\x02" * 100)
        self.assertIn("n'arrive pas à lire", repondre(self.dossier / "binaire.bin", "?", appeler=lambda c: "x"))
        self.assertIn("ne trouve pas", repondre(self.dossier / "absent.txt", "?"))

    def test_images_converties_en_donnees_jpeg_pour_gemini(self):
        # Constaté avec le vrai Gemini : une image PIL brute est ignorée (« aucun fichier fourni »).
        from PIL import Image
        from core.lecteur_fichier import en_parts_gemini
        sortie = en_parts_gemini(["question", Image.new("RGB", (50, 50), "red")])
        self.assertEqual(sortie[0], "question")
        blob = sortie[1].inline_data
        self.assertEqual(blob.mime_type, "image/jpeg")
        self.assertTrue(bytes(blob.data).startswith(b"\xff\xd8"))

    def test_file_processor_passe_par_le_lecteur(self):
        source = (RACINE / "actions" / "file_processor.py").read_text(encoding="utf-8")
        self.assertIn("from core.lecteur_fichier import repondre", source)


class TestFichiersRetenus(unittest.TestCase):
    """Question de Fredo (01/11) : à chaque séance il fallait redonner le fichier à Jarvis."""

    def setUp(self):
        import tempfile
        import core.fichiers_retenus as fr
        self.fr = fr
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        self.ancienne_base, fr.BASE = fr.BASE, self.racine / "jarvis"

    def tearDown(self):
        self.fr.BASE = self.ancienne_base
        self.tmp.cleanup()

    def _fichier(self, nom, texte="contenu"):
        p = self.racine / nom
        p.write_text(texte, encoding="utf-8")
        return p

    def test_le_fichier_est_retrouve_a_la_seance_suivante(self):
        p = self._fichier("07-Alliade-Agences.txt")
        self.fr.retenir(p)
        # Une « nouvelle séance » ne garde rien en mémoire vive : tout se relit sur le disque.
        self.assertEqual(self.fr.retrouver("les agences Alliade"), str(p.resolve()))
        self.assertIn("07-Alliade-Agences.txt", self.fr.bloc_pour_prompt())
        self.assertIn("never ask", self.fr.bloc_pour_prompt())

    def test_fichier_efface_ou_deplace_on_utilise_la_copie(self):
        p = self._fichier("facture.txt", "Total 318 euros")
        self.fr.retenir(p)
        p.unlink()
        trouve = self.fr.retrouver("la facture")
        self.assertIsNotNone(trouve)
        self.assertEqual(Path(trouve).read_text(encoding="utf-8"), "Total 318 euros")

    def test_aucun_fichier_et_rien_qui_ressemble(self):
        self.assertIsNone(self.fr.retrouver("facture", dernier_si_rien=True))
        self.assertEqual(self.fr.bloc_pour_prompt(), "")
        self.fr.retenir(self._fichier("facture.txt"))
        self.assertIsNone(self.fr.retrouver("mon prénom"))
        self.assertIsNotNone(self.fr.retrouver("quel est le total", dernier_si_rien=True))

    def test_plus_recent_en_tete_et_limite(self):
        ancien_max, self.fr.MAX_FICHIERS = self.fr.MAX_FICHIERS, 2
        try:
            for nom in ("a1a.txt", "b2b.txt", "c3c.txt"):
                self.fr.retenir(self._fichier(nom))
        finally:
            self.fr.MAX_FICHIERS = ancien_max
        self.assertEqual([e["nom"] for e in self.fr.liste()], ["c3c.txt", "b2b.txt"])
        self.assertEqual(len(list((self.fr.BASE / "memory" / "fichiers").glob("*a1a.txt"))), 0)

    def test_redonner_le_meme_fichier_ne_fait_pas_de_doublon(self):
        p = self._fichier("note.txt")
        self.fr.retenir(p)
        self.fr.retenir(p)
        self.assertEqual(len(self.fr.liste()), 1)

    def test_indice_pour_recall_memory(self):
        self.fr.retenir(self._fichier("07-Alliade-Agences.txt"))
        self.assertIn("file_processor", self.fr.indice("Allied agences"))
        self.assertIn("07-Alliade-Agences.txt", self.fr.indice("le fichier que je t'ai envoyé"))
        self.assertEqual(self.fr.indice("mon prénom"), "")

    def test_file_processor_retrouve_sans_que_le_fichier_soit_depose(self):
        from actions import file_processor as fp
        import core.lecteur_fichier as lf
        self.fr.retenir(self._fichier("horaires.txt", "Ouvert de 9h à 18h"))
        recu, reel = {}, lf.repondre

        def faux(chemin, question="", appeler=None):
            recu["chemin"], recu["question"] = str(chemin), question
            return "ok"

        lf.repondre = faux
        try:
            self.assertEqual(fp.file_processor({"file_path": "horaires.txt", "instruction": "à quelle heure ?"}), "ok")
            self.assertTrue(recu["chemin"].endswith("horaires.txt"))
            self.assertEqual(recu["question"], "à quelle heure ?")
            self.assertEqual(fp.file_processor({"instruction": "à quelle heure ?"}), "ok")   # sans nom : le dernier
        finally:
            lf.repondre = reel


class TestActusDuBriefing(unittest.TestCase):
    """Demande de Fredo (01/11) : actualités locales au démarrage plutôt que celles du monde."""

    def test_requete_selon_le_reglage(self):
        from core.actus import GENERALE, requete_actus
        self.assertEqual(requete_actus("", "Gravelines"), GENERALE)
        self.assertEqual(requete_actus("monde", "Gravelines"), GENERALE)
        self.assertEqual(requete_actus(None, ""), GENERALE)
        self.assertEqual(requete_actus("locale", "Gravelines"), "actualités Gravelines aujourd'hui")
        self.assertEqual(requete_actus("Locale", "Lille"), "actualités Lille aujourd'hui")
        self.assertEqual(requete_actus("locale", ""), GENERALE)          # ville pas encore connue
        self.assertEqual(requete_actus("Dunkerque", "Lille"), "actualités Dunkerque aujourd'hui")

    def test_par_defaut_actus_locales_pour_tous_les_clients(self):
        # Les clients déjà installés n'ont pas la clé "actus" dans leur interface.json : sans réglage,
        # c'est la ville apprise (ou les actualités générales si Jarvis ne la connaît pas encore).
        import json
        import tempfile
        import core.actus as actus
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "memory").mkdir()
            ancienne_base, actus.BASE = actus.BASE, Path(tmp)
            try:
                (Path(tmp) / "memory" / "interface.json").write_text("{}", encoding="utf-8")
                self.assertEqual(actus.requete_du_briefing(), actus.GENERALE)        # ville pas connue
                (Path(tmp) / "memory" / "long_term.json").write_text(
                    json.dumps({"identity": {"city": {"value": "Lille"}}}), encoding="utf-8")
                self.assertEqual(actus.requete_du_briefing(), "actualités Lille aujourd'hui")
                (Path(tmp) / "memory" / "interface.json").write_text('{"actus": "monde"}', encoding="utf-8")
                self.assertEqual(actus.requete_du_briefing(), actus.GENERALE)        # le client choisit le monde
            finally:
                actus.BASE = ancienne_base

    def test_le_briefing_utilise_le_reglage_et_un_repli(self):
        source = (RACINE / "main.py").read_text(encoding="utf-8")
        self.assertIn("requete_du_briefing", source)
        self.assertIn("actualités générales à la place", source)


if __name__ == "__main__":
    unittest.main()
