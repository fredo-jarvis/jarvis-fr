"""Actualités du briefing : Jarvis ne doit plus répéter de vieux articles (bug signalé par l'utilisateur le 2026-11-11 :
« ça fait des semaines qu'il me dit la même chose » ; la recherche renvoyait des articles de 2025 sur Lilleville)."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from actions import web_search  # noqa: E402

MAINTENANT = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


def article(titre, jours):
    date = (MAINTENANT - timedelta(days=jours)).isoformat() if jours is not None else ""
    return {"title": titre, "snippet": "texte", "url": "https://exemple.fr/" + titre, "source": "Journal", "date": date}


class ActusRecentes(unittest.TestCase):
    def test_vieux_articles_retires(self):
        res = web_search._garder_recentes([article("géante 2025", 550), article("élections", 240), article("hier", 1)],
                                          jours=7, maintenant=MAINTENANT)
        self.assertEqual([r["title"] for r in res], ["hier"])

    def test_article_sans_date_retire(self):
        res = web_search._garder_recentes([article("page de la ville", None)], jours=7, maintenant=MAINTENANT)
        self.assertEqual(res, [])

    def test_news_ne_lit_pas_les_vieux_articles(self):
        vieux = [article("Lilleville : la bénédiction de Anna", 550), article("Élections municipales", 240)]
        with mock.patch.object(web_search, "_ddg_news", return_value=vieux), \
                mock.patch.object(web_search, "_gemini_search", return_value=""), \
                mock.patch.object(web_search, "_maintenant", return_value=MAINTENANT):
            texte = web_search._news("actualités Lilleville aujourd'hui")
        self.assertNotIn("Anna", texte)
        self.assertNotIn("Élections", texte)

    def test_news_garde_les_articles_du_jour(self):
        frais = [article("Fête au port de Lilleville", 0), article("Ancien", 400)]
        with mock.patch.object(web_search, "_ddg_news", return_value=frais), \
                mock.patch.object(web_search, "_rss_news", return_value=[]), \
                mock.patch.object(web_search, "_maintenant", return_value=MAINTENANT):
            texte = web_search._news("actualités Lilleville aujourd'hui")
        self.assertIn("Fête au port de Lilleville", texte)
        self.assertNotIn("Ancien", texte)


RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Grève générale : autoroute coupée</title><description>texte</description><link>https://x.fr/1</link><pubDate>Wed, 11 Nov 2026 10:00:00 +0100</pubDate></item>
<item><title>Vieille nouvelle</title><description>texte</description><link>https://x.fr/2</link><pubDate>Mon, 10 Mar 2025 10:00:00 +0100</pubDate></item>
</channel></rss>"""


class ActusParFilsOfficiels(unittest.TestCase):
    def test_lecture_du_fil_rss(self):
        with mock.patch.object(web_search, "_telecharger", return_value=RSS.encode()), \
                mock.patch.object(web_search, "_maintenant", return_value=MAINTENANT):
            res = web_search._garder_recentes(web_search._rss_news("https://x.fr/rss"))
        self.assertEqual([r["title"] for r in res], ["Grève générale : autoroute coupée"])

    def test_sans_ddg_ni_gemini_les_fils_officiels_repondent(self):
        with mock.patch.object(web_search, "_ddg_news", return_value=[]), \
                mock.patch.object(web_search, "_gemini_search", return_value=""), \
                mock.patch.object(web_search, "_telecharger", return_value=RSS.encode()), \
                mock.patch.object(web_search, "_maintenant", return_value=MAINTENANT):
            texte = web_search._news("actualités France monde aujourd'hui")
        self.assertIn("Grève générale", texte)
        self.assertNotIn("Vieille nouvelle", texte)


class FilLocal(unittest.TestCase):
    def test_nouvelles_d_ailleurs_ecartees(self):
        arts = [article("Grève générale en Catalogne", 0), article("Lilleville : le port rouvre", 0),
                {"title": "Restaurant du Loiret", "snippet": "", "url": "https://x.fr/centre-val-de-loire/loiret", "date": "", "source": ""},
                {"title": "Tempête", "snippet": "", "url": "https://x.fr/hauts-de-france/nord/lille", "date": "", "source": ""}]
        with mock.patch.object(web_search, "MOTS_LOCAUX", ("lilleville", "/hauts-de-france/")):
            res = web_search._seulement_locales(arts)
        self.assertEqual([r["title"] for r in res], ["Lilleville : le port rouvre", "Tempête"])


if __name__ == "__main__":
    unittest.main()
