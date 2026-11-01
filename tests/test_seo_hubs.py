"""Tests des pages hub « mot du jour » et « méthode / indices » (SEO-17 à SEO-21).

Lancement :  python -m unittest discover -s tests -v

Ces deux pages existent parce que la tendance Google Cémantix est sans appel :
« mot du jour » apparaît dans 5 des 10 requêtes en hausse, « indice » occupe les
deux premières et « synonyme » est en hausse — aucune page du site ne les ciblait.
Elles sont rendues côté serveur : un crawler (comme un visiteur sans JavaScript)
doit y lire le résumé, les indices, la méthode et la FAQ.
"""
import json
import re
import unittest
from datetime import datetime

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.services.seo import (  # noqa: E402
    METHODE_DIRNAME,
    MOT_DU_JOUR_DIRNAME,
    SITE_ORIGIN,
    build_methode_page,
    build_mot_du_jour_page,
    build_sitemap,
)

DATE_ISO = "2026-10-26"
ENTREE = {
    "date": DATE_ISO,
    "puzzle": 1700,
    "word": "maison",
    "win": True,
    "tries": 9,
    "duration_seconds": 41.7,
    "source": "rag",
    "timestamp": f"{DATE_ISO}T00:05:00+02:00",
    "top_guesses": [
        {"word": "cabane", "score": 31.2, "permille": 812},
        {"word": "abri", "score": 24.8, "permille": 764},
        {"word": "••••••••", "score": 99.9, "permille": 999},
    ],
}


def _texte_visible(html: str) -> str:
    """Corps `<main>` sans balises ni CSS : ce que le crawler lit réellement."""
    corps = re.search(r"<main>(.*?)</main>", html, re.S).group(1)
    return re.sub(r"<[^>]+>", " ", corps)


def _graphes(html: str):
    bloc = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    return json.loads(bloc)["@graph"]


class TestPageMotDuJour(unittest.TestCase):
    def setUp(self):
        self.html = build_mot_du_jour_page(ENTREE, [ENTREE])

    def test_le_titre_porte_le_cluster_mot_du_jour_et_la_date_francaise(self):
        attendu = "Indice Cémantix du jour (lundi 26 octobre 2026) : indices, synonymes et mot du jour"
        self.assertIn(f"<title>{attendu}</title>", self.html)
        self.assertIn(f"<h1>{attendu}</h1>", self.html)

    def test_canonical_et_fil_dariane(self):
        self.assertIn(f'<link rel="canonical" href="{SITE_ORIGIN}/mot-du-jour/">', self.html)
        self.assertIn("<span>Mot du jour</span>", self.html)

    def test_les_indices_sont_dans_le_html_sans_javascript(self):
        texte = _texte_visible(self.html)
        self.assertIn("Cabane", texte)
        self.assertIn("812 ‰", texte)
        self.assertNotIn("<script", self.html.split("<body>")[1])

    def test_le_mot_masque_n_est_jamais_publie_comme_indice(self):
        # Le solveur masque le mot trouvé par •••••••• dans la trajectoire : ce leurre
        # ne doit jamais être présenté comme un indice au chercheur.
        self.assertNotIn("••••••••", _texte_visible(self.html))

    def test_la_solution_reste_derriere_un_details(self):
        corps = self.html.split("<body>")[1]
        self.assertRegex(corps, r'(?s)<details class="reveal">.*MAISON.*</details>')
        # Le mot n'apparaît qu'une fois : jamais dans le titre, la description ou le JSON-LD.
        self.assertEqual(self.html.count("MAISON"), 1)

    def test_faq_visible_et_structee(self):
        graphes = _graphes(self.html)
        types = {g["@type"] for g in graphes}
        self.assertEqual({"Article", "BreadcrumbList", "FAQPage"}, types)
        faq = next(g for g in graphes if g["@type"] == "FAQPage")
        questions = [q["name"] for q in faq["mainEntity"]]
        self.assertTrue(any("mot du jour" in q.lower() for q in questions))
        self.assertTrue(any("synonyme" in q.lower() for q in questions))
        for question in questions:
            self.assertIn(question, self.html, "la FAQ structurée doit aussi exister en clair")

    def test_la_page_maille_vers_la_methode_et_les_archives(self):
        self.assertIn('href="../methode/"', self.html)
        self.assertIn('href="../puzzles/"', self.html)

    def test_historique_vide_produit_quand_meme_une_page_indexable(self):
        html = build_mot_du_jour_page(None, [])
        self.assertIn(
            "<title>Indice Cémantix du jour : indices, synonymes et mot du jour</title>", html
        )
        self.assertIn('content="index, follow"', html)
        self.assertNotIn("🌡️", html)

class TestPageMethode(unittest.TestCase):
    def setUp(self):
        self.html = build_methode_page()
        self.texte = _texte_visible(self.html)

    def test_le_titre_ouvre_sur_le_mot_indice(self):
        self.assertIn(
            "<title>Indice Cémantix : lire le thermomètre, les scores et les synonymes</title>",
            self.html,
        )
        self.assertTrue(self.html.split("<h1>")[1].startswith("Indice Cémantix"))

    def test_le_contenu_couvre_indice_synonyme_et_pour_mille(self):
        bas = self.texte.lower()
        self.assertGreaterEqual(bas.count("indice"), 8)
        self.assertGreaterEqual(bas.count("synonyme"), 5)
        self.assertIn("pour mille", bas)
        self.assertIn("1000 ‰", self.texte)

    def test_la_page_fait_un_contenu_suffisant(self):
        # Une page « thin content » ne classe pas une requête informationnelle :
        # 700 mots est le plancher retenu pour ce guide.
        self.assertGreaterEqual(len(re.findall(r"[\wà-ÿ'’-]+", self.texte)), 700)

    def test_howto_et_faq_structures_et_lisibles(self):
        graphes = _graphes(self.html)
        self.assertEqual({"HowTo", "BreadcrumbList", "FAQPage"}, {g["@type"] for g in graphes})
        etapes = next(g for g in graphes if g["@type"] == "HowTo")["step"]
        self.assertEqual([e["position"] for e in etapes], [1, 2, 3, 4, 5])
        for etape in etapes:
            self.assertIn(etape["name"], self.texte, "une étape JSON-LD doit être lisible")

    def test_la_page_maille_vers_le_mot_du_jour_et_les_archives(self):
        for href in ('href="../mot-du-jour/"', 'href="../puzzles/"', 'href="../play/"'):
            self.assertIn(href, self.html)


class TestHubsDansLeSitemap(unittest.TestCase):
    def setUp(self):
        self.sitemap = build_sitemap([ENTREE], datetime(2026, 10, 26, 0, 5))

    def test_les_deux_hubs_sont_declares(self):
        self.assertIn(f"<loc>{SITE_ORIGIN}/mot-du-jour/</loc>", self.sitemap)
        self.assertIn(f"<loc>{SITE_ORIGIN}/methode/</loc>", self.sitemap)

    def test_le_mot_du_jour_est_prioritaire_et_quotidien(self):
        bloc = next(b for b in self.sitemap.split("<url>")[1:] if "mot-du-jour" in b)
        self.assertIn("<changefreq>daily</changefreq>", bloc)
        self.assertIn("<priority>0.95</priority>", bloc)
        self.assertIn("<lastmod>2026-10-26</lastmod>", bloc)

    def test_repertoires_generees_hors_suivi_git(self):
        ignore = (_context.RACINE / ".gitignore").read_text(encoding="utf-8")
        for nom in (MOT_DU_JOUR_DIRNAME, METHODE_DIRNAME):
            self.assertIn(f"volumes/web/{nom}/", ignore)


class TestLibellesDesPagesApplicatives(unittest.TestCase):
    """Lot 1 : un `<h1>` descriptif par page, la marque ne servant plus de titre."""

    PAGES = ("index.html", "play/index.html", "battle/index.html", "multi/index.html")

    def setUp(self):
        self.pages = {
            p: (_context.RACINE / "volumes" / "web" / p).read_text(encoding="utf-8")
            for p in self.PAGES
        }

    def _h1(self, html):
        return re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)

    def test_une_seule_h1_par_page(self):
        for nom, html in self.pages.items():
            self.assertEqual(len(self._h1(html)), 1, nom)

    def test_les_h1_sont_uniques_et_descriptives(self):
        titres = [self._h1(html)[0] for html in self.pages.values()]
        self.assertEqual(len(set(titres)), len(titres), f"H1 dupliquées : {titres}")
        for titre in titres:
            self.assertNotEqual(titre.strip(), "Cémantix Solver")
            self.assertIn("émantix", titre)

    def test_la_marque_reste_visible_hors_h1(self):
        for nom, html in self.pages.items():
            self.assertIn('<span class="brand-title">Cémantix Solver</span>', html, nom)

    def test_chaque_page_maille_vers_les_hubs(self):
        for nom, html in self.pages.items():
            self.assertIn("mot-du-jour/", html, nom)
            self.assertIn("methode/", html, nom)

    def test_le_css_critique_inline_connait_les_nouvelles_classes(self):
        # Le CSS critique est régénéré par tools/build_css_bundles.py : s'il n'a pas été
        # reconstruit, le titre de page s'affiche en h1 brut et casse la mise en page.
        for nom, html in self.pages.items():
            critique = re.search(r'<style id="critical-css"[^>]*>(.*?)</style>', html, re.S).group(1)
            self.assertIn(".brand-text .brand-title", critique, nom)
            self.assertIn(".page-heading", critique, nom)

    def test_la_faq_de_l_acueil_couvre_la_tendance(self):
        html = self.pages["index.html"]
        faq = next(g for g in _graphes(html) if g["@type"] == "FAQPage")
        questions = " ".join(q["name"].lower() for q in faq["mainEntity"])
        self.assertGreaterEqual(len(faq["mainEntity"]), 8)
        for mot in ("mot du jour", "indice", "synonyme"):
            self.assertIn(mot, questions)


if __name__ == "__main__":
    unittest.main(verbosity=2)

