"""Demandes de l'utilisateur du 2026-11-11 :
1. « Je voudrais créer un bouton mute de mon micro dans mon Jarvis » (Jarvis lui répondait quand il parlait à quelqu'un d'autre) ;
2. « Je voudrais plus que ça soit l'utilisateur OS, tu me mets Jarvis OS : je vais le rendre public, tout le monde doit voir Jarvis OS »."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


def lire(*chemin) -> str:
    return (RACINE.joinpath(*chemin)).read_text(encoding="utf-8")


class FauxUI:
    muted = False

    def __init__(self):
        self.journal = []

    def write_log(self, t):
        self.journal.append(t)

    def set_state(self, e):
        pass

    def show_confirm(self, t, d):
        pass

    def hide_confirm(self):
        pass

    def set_muted(self, v):
        self.muted = bool(v)


class FauxConfirm:
    def pending_title(self):
        return ""

    def resolve(self, oui):
        pass


class FauxJarvis:
    _cerveau, session, _loop = "cloud", None, None


class TestMicro(unittest.TestCase):
    def setUp(self):
        from galaxie.pont import Pont
        self.ui = FauxUI()
        self.p = Pont(FauxJarvis(), self.ui, lambda: "models/gemini-x", FauxConfirm())

    def test_la_photo_dit_si_le_micro_est_coupe(self):
        self.assertIs(self.p.photo()["muet"], False)
        self.p.muet(True)
        self.assertIs(self.p.photo()["muet"], True)

    def test_le_bouton_coupe_et_remet_le_micro(self):
        self.p.muet(True)
        self.assertTrue(self.ui.muted)
        self.p.muet(False)
        self.assertFalse(self.ui.muted)

    def test_le_serveur_a_la_route(self):
        serveur = lire("galaxie", "server.py")
        self.assertIn('"/api/jarvis/muet"', serveur)
        self.assertIn("PONT.muet(", serveur)

    def test_les_deux_pages_ont_le_bouton(self):
        for page in ("index.html", "tableau.html"):
            html = lire("galaxie", page)
            self.assertIn('id="micro"', html, page)
            self.assertIn("/api/jarvis/muet", html, page)

    def test_la_fenetre_coupe_le_micro_sans_toucher_qt_depuis_un_autre_fil(self):
        ui = lire("ui.py")
        self.assertIn("_mute_sig", ui)
        self.assertIn("def set_muted", ui)


class TestNomPublic(unittest.TestCase):
    def test_le_tableau_s_appelle_jarvis_os(self):
        html = lire("galaxie", "tableau.html")
        self.assertIn("<title>Jarvis OS</title>", html)
        self.assertIn("JARVIS OS", html)

    def test_ton_nom_n_est_plus_dans_ce_que_le_public_voit(self):
        interdits = ["FRE" + "DO", "Fre" + "do", "Grave" + "lines"]   # ni prénom ni ville personnelle
        for page in ("index.html", "tableau.html"):
            html = lire("galaxie", page)
            for mot in interdits:
                self.assertNotIn(mot, html, f"{mot} dans {page}")


class TestSortieDuFocus(unittest.TestCase):
    """l'utilisateur (2026-11-11) : en mode FOCUS tous les boutons disparaissaient, il ne pouvait plus revenir."""

    def test_un_bouton_pour_sortir_du_focus_reste_visible(self):
        html = lire("galaxie", "index.html")
        self.assertIn('id="sortir-focus"', html)
        # il ne doit pas être dans les parties cachées par le mode focus
        debut = html.rindex("<", 0, html.index('id="sortir-focus"'))
        balise = html[debut:html.index(">", debut) + 1]   # seulement la balise du bouton
        self.assertNotIn("cachable", balise)
        self.assertIn("body.focus #sortir-focus", html)
        self.assertIn('$("sortir-focus").onclick', html)


if __name__ == "__main__":
    unittest.main()
