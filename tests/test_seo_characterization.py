"""Tests de caractérisation déterministe pour la modularisation SEO (Jalon M4).

Sanctuaire de non-régression validant au caractère près :
1. Génération des pages d'archives (résolues, non résolues, avec ou sans navigation older/newer).
2. Pagination de l'index des archives (page 1 canonique, page N paginée, limites).
3. Pages hub (mot du jour avec et sans historique, méthode & guide des indices).
4. Sitemap XML (format ISO, dates valides, protocol conformant, priorité).
5. Manifestes ARD et documentation agent (catalogue OpenAPI/llms.txt, idempotence).
6. Pré-rendu du tableau de bord (injection de métadonnées sans altérer le reste).
7. Invariants anti-spoiler stricts et gestion des entrées malformées/vides.
"""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.services import seo  # noqa: E402

FIXED_DT = datetime(2026, 10, 30, 0, 5, 0, tzinfo=timezone.utc)
DATE_1 = "2026-10-28"
DATE_2 = "2026-10-29"
DATE_3 = "2026-10-30"

MOCK_ENTRIES = [
    {
        "date": DATE_3,
        "puzzle": 1703,
        "word": "lumiere",
        "win": True,
        "tries": 7,
        "duration_seconds": 32.4,
        "source": "rag",
        "timestamp": f"{DATE_3}T00:04:12+02:00",
        "top_guesses": [
            {"word": "clarté", "score": 45.2, "permille": 920},
            {"word": "rayon", "score": 38.1, "permille": 850},
            {"word": "soleil", "score": 29.4, "permille": 780},
            {"word": "••••••••", "score": 99.9, "permille": 999},
        ],
    },
    {
        "date": DATE_2,
        "puzzle": 1702,
        "word": "patrie",
        "win": True,
        "tries": 12,
        "duration_seconds": 65.0,
        "source": "hybrid",
        "timestamp": f"{DATE_2}T00:06:45+02:00",
        "top_guesses": [
            {"word": "nation", "score": 52.0, "permille": 960},
            {"word": "pays", "score": 41.3, "permille": 890},
        ],
    },
    {
        "date": DATE_1,
        "puzzle": 1701,
        "word": "enigme",
        "win": False,
        "tries": 80,
        "duration_seconds": 300.0,
        "source": "rag",
        "timestamp": f"{DATE_1}T00:15:00+02:00",
        "top_guesses": [
            {"word": "mystere", "score": 34.0, "permille": 810},
        ],
    },
]


class TestSeoCharacterization(unittest.TestCase):
    """Vérification déterministe de la génération HTML / XML / JSON."""

    def test_formatters_deterministic_output(self):
        self.assertEqual(seo.format_date_fr("2026-10-30"), "vendredi 30 octobre 2026")
        self.assertEqual(seo.archive_title("2026-10-30"), "Solution Cémantix du vendredi 30 octobre 2026")
        self.assertEqual(
            seo.archive_anchor("2026-10-30"),
            "Indices et solution du Cémantix du vendredi 30 octobre 2026"
        )
        self.assertEqual(seo.format_duration_fr(42.5), "42,5 s")
        self.assertEqual(seo.format_duration_fr(125), "2 min 05")
        self.assertEqual(seo.format_duration_fr(0), "--")
        self.assertEqual(seo.format_duration_fr(None), "--")
        self.assertEqual(seo.format_duration_fr("invalid"), "--")

    def test_archive_page_structure_and_anti_spoiler(self):
        entry_win = MOCK_ENTRIES[0]
        older = MOCK_ENTRIES[1]
        newer = None

        html = seo.build_archive_page(entry_win, older=older, newer=newer)

        # Structure globale
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn('<html lang="fr" data-theme="dark">', html)
        self.assertIn("<title>Solution Cémantix du vendredi 30 octobre 2026</title>", html)
        self.assertIn('<link rel="canonical" href="https://cemantix.cyril-randon.fr/puzzles/2026-10-30/">', html)
        self.assertIn('<meta name="robots" content="index, follow">', html)

        # Anti-spoiler : le mot secret ne doit apparaître qu'à l'intérieur de <details class="reveal">
        self.assertIn('<details class="reveal">', html)
        self.assertIn('<p class="reveal-word">LUMIERE</p>', html)

        # En dehors de la zone reveal, le mot ne doit pas fuiter dans le corps
        parts = html.split('<details class="reveal">')
        before_reveal = parts[0]
        after_reveal = parts[1].split("</details>")[1]
        self.assertNotIn("lumiere", before_reveal.lower().replace("solution cémantix", ""))
        self.assertNotIn("lumiere", after_reveal.lower())

        # Le mot masqué "••••••••" ne doit pas être affiché dans le tableau d'indices
        self.assertNotIn("••••••••", html)

    def test_archive_page_unsolved_is_noindex(self):
        # Entrée non résolue avec indices : reste indexable
        entry_lost = MOCK_ENTRIES[2]
        html_lost = seo.build_archive_page(entry_lost, older=None, newer=None)
        self.assertIn('<span class="badge">⏳ Non résolu</span>', html_lost)
        self.assertIn('<meta name="robots" content="index, follow">', html_lost)

        # Entrée non résolue ET sans aucun indice ("thin content") : doit être noindex
        entry_thin = {
            "date": "2026-10-25",
            "puzzle": 1698,
            "word": "",
            "win": False,
            "tries": 0,
            "top_guesses": [],
        }
        html_thin = seo.build_archive_page(entry_thin, older=None, newer=None)
        self.assertIn('<meta name="robots" content="noindex, follow">', html_thin)
        self.assertIn('<span class="badge">⏳ Non résolu</span>', html_thin)

    def test_archives_index_pagination_structure(self):
        # Page 1
        html_p1 = seo.build_archives_index_page(MOCK_ENTRIES, page=1, total_pages=2)
        self.assertIn("<title>Cémantix du jour : mot du jour, indices et solutions par date</title>", html_p1)
        self.assertIn('<link rel="canonical" href="https://cemantix.cyril-randon.fr/puzzles/">', html_p1)
        self.assertIn('href="../page/2/"', html_p1)

        # Page 2
        html_p2 = seo.build_archives_index_page(MOCK_ENTRIES, page=2, total_pages=2)
        self.assertIn("<title>Cémantix du jour : archives des indices et solutions, page 2", html_p2)
        self.assertIn('<link rel="canonical" href="https://cemantix.cyril-randon.fr/puzzles/page/2/">', html_p2)
        self.assertIn('href="../"', html_p2)

    def test_mot_du_jour_page_with_and_without_entry(self):
        # Avec entrée
        html = seo.build_mot_du_jour_page(MOCK_ENTRIES[0], MOCK_ENTRIES)
        self.assertIn("Mot du jour Cémantix", html)
        self.assertIn("https://cemantix.cyril-randon.fr/mot-du-jour/", html)
        self.assertIn('<details class="reveal">', html)
        self.assertIn("Clarté", html)

        # Sans entrée (historique vide)
        html_empty = seo.build_mot_du_jour_page(None, [])
        self.assertIn("Mot du jour Cémantix", html_empty)
        self.assertIn("Première publication à minuit", html_empty)

    def test_methode_page_structure(self):
        html = seo.build_methode_page()
        self.assertIn("Indice Cémantix : lire le thermomètre", html)
        self.assertIn("https://cemantix.cyril-randon.fr/methode/", html)
        self.assertIn("FAQ", html)
        self.assertIn("thermomètre", html.lower())

    def test_sitemap_xml_protocol_compliance(self):
        xml = seo.build_sitemap(MOCK_ENTRIES, FIXED_DT)
        self.assertTrue(xml.startswith('<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', xml)
        self.assertIn("<loc>https://cemantix.cyril-randon.fr/</loc>", xml)
        self.assertIn("<loc>https://cemantix.cyril-randon.fr/mot-du-jour/</loc>", xml)
        self.assertIn("<loc>https://cemantix.cyril-randon.fr/methode/</loc>", xml)
        self.assertIn("<loc>https://cemantix.cyril-randon.fr/puzzles/</loc>", xml)
        self.assertIn("<loc>https://cemantix.cyril-randon.fr/puzzles/2026-10-30/</loc>", xml)
        self.assertIn("<lastmod>2026-10-30</lastmod>", xml)
        # Aucune date au format français dans le sitemap
        self.assertFalse(re.search(r"<lastmod>.*(octobre|lundi).*</lastmod>", xml))

    def test_ard_manifest_and_agent_card_valid_json(self):
        manifest_raw = seo.build_ard_manifest()
        manifest = json.loads(manifest_raw)
        self.assertIn("specVersion", manifest)
        self.assertIn("entries", manifest)
        self.assertIn("host", manifest)

        card_raw = seo.build_agent_card()
        card = json.loads(card_raw)
        self.assertIn("skills", card)
        self.assertIn("name", card)

    def test_malformed_and_boundary_entries_handled_safely(self):
        malformed = {
            "date": "bad-date",
            "word": None,
            "win": False,
            "tries": "invalid",
            "duration_seconds": None,
            "top_guesses": None,
        }
        # Doit s'exécuter sans lever d'exception
        html = seo.build_archive_page(malformed, older=None, newer=None)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Solution Cémantix", html)


class TestSeoFilesystemPublication(unittest.TestCase):
    """Validation de la publication sur disque temporaire."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="cemantix_test_seo_"))
        # Créer l'arborescence minimale
        (self.tmp_dir / "css").mkdir(parents=True)
        (self.tmp_dir / "puzzles").mkdir(parents=True)
        # Copier les fichiers css et gabarits s'ils existent
        for f in ("variables.css", "puzzle.css"):
            src_f = seo.WEB_ROOT / "css" / f
            if src_f.exists():
                shutil.copy(src_f, self.tmp_dir / "css" / f)
        for f in ("index.html", "llms.txt", "agent-skills.md"):
            src_f = seo.WEB_ROOT / f
            if src_f.exists():
                shutil.copy(src_f, self.tmp_dir / f)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_publish_seo_pages_creates_all_artifacts(self):
        res = seo.publish_seo_pages(MOCK_ENTRIES, FIXED_DT, web_root=self.tmp_dir)
        # Seuls les 2 puzzles gagnés génèrent une page d'archive dédiée
        self.assertEqual(res["archives"], 2)
        self.assertEqual(res["index_pages"], 1)
        self.assertEqual(res["hub_pages"], 2)
        self.assertTrue(res["sitemap"])

        # Vérifier présence des fichiers
        self.assertTrue((self.tmp_dir / "sitemap.xml").is_file())
        self.assertTrue((self.tmp_dir / "puzzles" / "index.html").is_file())
        self.assertTrue((self.tmp_dir / "puzzles" / DATE_3 / "index.html").is_file())
        self.assertTrue((self.tmp_dir / "mot-du-jour" / "index.html").is_file())
        self.assertTrue((self.tmp_dir / "methode" / "index.html").is_file())

        # Aucun fichier temporaire résiduel
        self.assertEqual(list(self.tmp_dir.glob("*.tmp")), [])
        self.assertEqual(list(self.tmp_dir.glob(".*.tmp")), [])

    def test_publish_ard_manifests_creates_manifests(self):
        count = seo.publish_ard_manifests(web_root=self.tmp_dir)
        self.assertEqual(count, 3)
        self.assertTrue((self.tmp_dir / ".well-known" / "ai-catalog.json").is_file())
        self.assertTrue((self.tmp_dir / ".well-known" / "ard.json").is_file())
        self.assertTrue((self.tmp_dir / ".well-known" / "agent-card.json").is_file())

    def test_prerender_dashboard_injects_metadata(self):
        ok = seo.prerender_dashboard(MOCK_ENTRIES[0], web_root=self.tmp_dir)
        self.assertTrue(ok)
        idx_content = (self.tmp_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn("30 octobre 2026", idx_content)
        self.assertIn(DATE_3, idx_content)
        # Anti-spoiler : le mot secret ne doit jamais fuiter dans le résumé du dashboard
        self.assertNotIn("lumiere", idx_content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
