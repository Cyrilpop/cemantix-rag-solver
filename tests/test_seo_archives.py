"""Tests du référencement des pages d'archive (« Solution Cémantix du <date> »).

Lancement :  python -m unittest discover -s tests -v

Le quick-win SEO tient en un contrat en deux moitiés, tous deux verrouillés ici :

1. la date en **français long** (« lundi 26 octobre 2026 ») porte le `<title>`, le
   `<h1>`, les métadonnées Open Graph, le `headline` JSON-LD, le fil d'Ariane et les
   ancres de l'index des archives — c'est la requête tapée par un chercheur ;
2. l'URL et le `<lastmod>` du sitemap restent en **ISO `AAAA-MM-JJ`**, seul format
   accepté par le protocole sitemaps.org : une date française dans `sitemap.xml`
   ferait rejeter le fichier par les crawlers.
"""
import json
import re
import unittest
from datetime import datetime

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.services.seo import (  # noqa: E402
    ARCHIVE_TITLE_PREFIX,
    SITE_ORIGIN,
    archive_title,
    build_archive_page,
    build_archives_index_page,
    build_sitemap,
    format_date_fr,
)

DATE_ISO = "2026-10-26"
TITRE_ATTENDU = "Solution Cémantix du lundi 26 octobre 2026"
DATE_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _entry(date: str = DATE_ISO, **sur):
    """Entrée d'historique complète : une victoire, avec indices et trajectoire."""
    entry = {
        "date": date,
        "puzzle": 1700,
        "word": "maison",
        "win": True,
        "tries": 9,
        "duration_seconds": 41.7,
        "source": "rag",
        "timestamp": f"{date}T00:05:00+02:00",
        "top_guesses": [
            {"word": "cabane", "score": 31.2, "permille": 812},
            {"word": "abri", "score": 24.8, "permille": 764},
        ],
    }
    entry.update(sur)
    return entry


class TestTitreArchive(unittest.TestCase):
    def test_la_date_est_en_francais_long(self):
        self.assertEqual(archive_title(DATE_ISO), TITRE_ATTENDU)
        self.assertEqual(ARCHIVE_TITLE_PREFIX, "Solution Cémantix du")
        # Jour de semaine + quantième + mois + année : la requête du chercheur.
        self.assertEqual(format_date_fr(DATE_ISO), "lundi 26 octobre 2026")

    def test_le_titre_ne_contient_jamais_la_date_iso(self):
        self.assertFalse(DATE_ISO_RE.search(archive_title(DATE_ISO)))

    def test_le_titre_reste_court_pour_la_serp(self):
        # Google tronque au-delà de ~60 caractères : 40 ici, marge gardée.
        self.assertLessEqual(len(archive_title(DATE_ISO)), 60)

    def test_une_date_invalide_ne_sonne_pas_comme_une_date_valide(self):
        self.assertEqual(archive_title("2026-13-45"), f"{ARCHIVE_TITLE_PREFIX} 2026-13-45")
        self.assertEqual(archive_title(None), f"{ARCHIVE_TITLE_PREFIX} ")


class TestPageArchive(unittest.TestCase):
    def setUp(self):
        self.html = build_archive_page(_entry(), None, None)

    def _extrait(self, motif):
        match = re.search(motif, self.html, re.S)
        self.assertIsNotNone(match, f"Motif absent du HTML : {motif}")
        return match.group(1)

    def test_title_h1_et_open_graph_portent_le_titre(self):
        self.assertIn(f"<title>{TITRE_ATTENDU}</title>", self.html)
        self.assertIn(f"<h1>{TITRE_ATTENDU}</h1>", self.html)
        self.assertIn(f'property="og:title" content="{TITRE_ATTENDU}"', self.html)
        self.assertIn(f'name="twitter:title" content="{TITRE_ATTENDU}"', self.html)

    def test_la_description_cible_la_solution(self):
        description = self._extrait(r'<meta name="description" content="([^"]+)"')
        self.assertTrue(description.startswith(TITRE_ATTENDU), description)
        self.assertIn("le mot secret", description)
        self.assertIn("Puzzle #1700", description)
        # Google tronque la snippet au-delà de ~160 caractères : marge de sécurité.
        self.assertLessEqual(len(description), 175)

    def test_json_ld_headline_et_fil_dariane_en_francais(self):
        bloc = self._extrait(r'<script type="application/ld\+json">(.+?)</script>')
        donnees = json.loads(bloc)
        article = next(n for n in donnees["@graph"] if n["@type"] == "Article")
        fil = next(n for n in donnees["@graph"] if n["@type"] == "BreadcrumbList")
        self.assertEqual(article["headline"], TITRE_ATTENDU)
        self.assertEqual(article["datePublished"][:10], DATE_ISO)
        self.assertEqual(
            [e["name"] for e in fil["itemListElement"]],
            ["Accueil", "Archives", "lundi 26 octobre 2026"],
        )

    def test_le_fil_dariane_visible_est_aussi_date_en_francais(self):
        self.assertIn("<span>lundi 26 octobre 2026</span>", self.html)

    def test_l_url_canonical_reste_iso(self):
        self.assertIn(
            f'<link rel="canonical" href="{SITE_ORIGIN}/puzzles/{DATE_ISO}/">',
            self.html,
        )

    def test_l_archive_maille_vers_le_mot_du_jour_et_la_methode(self):
        # Le maillage interne descendant (archive → hub) fait circuler le PageRank
        # collecté par les pages datées vers les pages qui ciblent la tendance.
        self.assertIn('href="../../mot-du-jour/"', self.html)
        self.assertIn('href="../../methode/"', self.html)

    def test_une_archive_non_resolue_reste_noindex(self):
        html = build_archive_page(
            _entry(win=False, word="", tries=None, top_guesses=[]), None, None
        )
        self.assertIn('content="noindex, follow"', html)
        self.assertIn(f"<title>{TITRE_ATTENDU}</title>", html)


class TestIndexDesArchives(unittest.TestCase):
    def setUp(self):
        self.entrees = [_entry(), _entry(date="2026-10-25", puzzle=1699)]
        self.html = build_archives_index_page(self.entrees, 1, 1)

    def test_le_titre_de_l_index_vise_le_cluster_dominant(self):
        # La tendance Google place « mot du jour » sur 5 requêtes sur 10 et « indice »
        # sur les deux premières : l'index des archives doit porter ce cluster, le mot
        # « solution » restant la spécialité des pages datées (SEO-13).
        self.assertIn("<title>Cémantix du jour : mot du jour, indices et solutions", self.html)
        self.assertIn(
            "<h1>Archives Cémantix du jour : le mot du jour, ses indices et sa solution</h1>",
            self.html,
        )

    def test_chaque_ancre_porte_indices_et_solution_datés(self):
        # Le texte d'ancre est un critère de classement : il décrit la cible et reprend
        # les deux mots qui manquaient (indice, solution) à la simple date.
        self.assertIn(
            "<span>Indices et solution du Cémantix du lundi 26 octobre 2026</span>", self.html
        )
        self.assertIn(
            "<span>Indices et solution du Cémantix du dimanche 25 octobre 2026</span>", self.html
        )

    def test_l_index_maille_vers_les_pages_hub(self):
        self.assertIn('href="../mot-du-jour/"', self.html)
        self.assertIn('href="../methode/"', self.html)

    def test_la_page_2_est_titree_et_canonique(self):
        html = build_archives_index_page(self.entrees, 2, 2)
        self.assertIn(
            "<title>Cémantix du jour : archives des indices et solutions, page 2</title>", html
        )
        self.assertIn(f'{SITE_ORIGIN}/puzzles/page/2/"', html)


class TestSitemapGardeLeFormatIso(unittest.TestCase):
    def setUp(self):
        self.sitemap = build_sitemap(
            [_entry(), _entry(date="2026-10-25", puzzle=1699)],
            datetime(2026, 10, 26, 0, 5),
        )

    def test_url_et_lastmod_sont_en_iso(self):
        self.assertIn(f"<loc>{SITE_ORIGIN}/puzzles/{DATE_ISO}/</loc>", self.sitemap)
        self.assertIn("<lastmod>2026-10-26</lastmod>", self.sitemap)

    def test_aucune_date_francaise_ne_fuit_dans_le_sitemap(self):
        # sitemaps.org n'accepte que le format W3C/ISO : « octobre » rendrait le
        # fichier invalide et ferait perdre l'indexation de toutes les archives.
        self.assertNotIn("octobre", self.sitemap)
        self.assertNotIn(ARCHIVE_TITLE_PREFIX, self.sitemap)


if __name__ == "__main__":
    unittest.main(verbosity=2)
