"""Tests de rétrocompatibilité et d'étanchéité pour la modularisation SEO (M4).

Valide :
1. L'identité stricte des objets ré-exportés (`assertIs`).
2. La préservation de toutes les cibles de monkeypatching historiques (`src.services.seo.*`).
3. La compatibilité de tous les styles d'import historiques.
"""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import _context  # noqa: F401

from src.services import (
    ensure_seo_published as services_ensure_seo,
    publish_seo_pages as services_publish_seo,
    seo,
    seo_agents,
    seo_archives,
    seo_hubs,
    seo_sitemap,
    seo_templates,
)


class TestSeoBackwardCompatibility(unittest.TestCase):
    """Vérification de la rétrocompatibilité d'import et d'identité."""

    def test_reexported_symbols_object_identity(self):
        """Vérifie que les symboles ré-exportés par seo.py sont strictement identiques."""
        # seo_templates
        self.assertIs(seo.WEB_ROOT, seo_templates.WEB_ROOT)
        self.assertIs(seo.SITE_ORIGIN, seo_templates.SITE_ORIGIN)
        self.assertIs(seo.ARCHIVES_PAGE_SIZE, seo_templates.ARCHIVES_PAGE_SIZE)
        self.assertIs(seo.parse_puzzle_date, seo_templates.parse_puzzle_date)
        self.assertIs(seo.format_date_fr, seo_templates.format_date_fr)
        self.assertIs(seo.format_clue_words_list, seo_templates.format_clue_words_list)
        self.assertIs(seo.archive_title, seo_templates.archive_title)
        self.assertIs(seo.archive_url, seo_templates.archive_url)
        self.assertIs(seo.render_page, seo_templates.render_page)
        self.assertIs(seo._clue_rows, seo_templates._clue_rows)

        # seo_archives
        self.assertIs(seo.build_archive_page, seo_archives.build_archive_page)
        self.assertIs(seo.build_archives_index_page, seo_archives.build_archives_index_page)

        # seo_hubs
        self.assertIs(seo.build_mot_du_jour_page, seo_hubs.build_mot_du_jour_page)
        self.assertIs(seo.build_methode_page, seo_hubs.build_methode_page)

        # seo_sitemap
        self.assertIs(seo.build_sitemap, seo_sitemap.build_sitemap)
        self.assertIs(seo._write_file, seo_sitemap._write_file)

        # seo_agents
        self.assertIs(seo.build_ard_manifest, seo_agents.build_ard_manifest)
        self.assertIs(seo.build_agent_card, seo_agents.build_agent_card)
        self.assertIs(seo.refresh_agent_docs, seo_agents.refresh_agent_docs)
        self.assertIs(seo.publish_ard_manifests, seo_agents.publish_ard_manifests)

        # src.services __init__
        self.assertIs(services_ensure_seo, seo.ensure_seo_published)
        self.assertIs(services_publish_seo, seo.publish_seo_pages)

    def test_all_declaration_covers_all_exports(self):
        """Vérifie que chaque symbole déclaré dans __all__ existe sur le module."""
        for sym in seo.__all__:
            self.assertTrue(
                hasattr(seo, sym),
                f"Le symbole {sym} déclaré dans seo.__all__ est absent du module seo",
            )

    def test_monkeypatch_publish_seo_pages_affects_ensure_seo_published(self):
        """Vérifie que le monkeypatching de seo.publish_seo_pages est bien intercepté."""
        fake_result = {"archives": 999, "sitemap": True}
        with mock.patch("src.services.seo.publish_seo_pages", return_value=fake_result) as mock_pub:
            with mock.patch("src.services.daemon.load_history", return_value=[]):
                res = seo.ensure_seo_published()
                self.assertEqual(res, fake_result)
                mock_pub.assert_called_once()

    def test_monkeypatch_ensure_seo_published_affects_callers(self):
        """Vérifie le contrat de patch utilisé dans test_seo_startup.py."""
        with mock.patch("src.services.seo.ensure_seo_published") as mock_ensure:
            from src.services.seo import ensure_seo_published
            ensure_seo_published()
            mock_ensure.assert_called_once()

    def test_deterministic_parity_between_direct_and_reexported_calls(self):
        """Vérifie la parité bit à bit entre appel direct au sous-module et via seo.py."""
        entry = {
            "date": "2026-10-30",
            "puzzle": 1703,
            "word": "lumiere",
            "win": True,
            "tries": 7,
            "duration_seconds": 32.4,
            "top_guesses": [{"word": "clarté", "score": 45.2, "permille": 920}],
        }
        dt = datetime(2026, 10, 30, 0, 5, 0, tzinfo=timezone.utc)

        # Archives
        html_direct = seo_archives.build_archive_page(entry, None, None)
        html_reexported = seo.build_archive_page(entry, None, None)
        self.assertEqual(html_direct, html_reexported)

        # Index
        idx_direct = seo_archives.build_archives_index_page([entry], 1, 1)
        idx_reexported = seo.build_archives_index_page([entry], 1, 1)
        self.assertEqual(idx_direct, idx_reexported)

        # Hubs
        mot_direct = seo_hubs.build_mot_du_jour_page(entry, [entry])
        mot_reexported = seo.build_mot_du_jour_page(entry, [entry])
        self.assertEqual(mot_direct, mot_reexported)

        methode_direct = seo_hubs.build_methode_page()
        methode_reexported = seo.build_methode_page()
        self.assertEqual(methode_direct, methode_reexported)

        # Sitemap
        sitemap_direct = seo_sitemap.build_sitemap([entry], dt)
        sitemap_reexported = seo.build_sitemap([entry], dt)
        self.assertEqual(sitemap_direct, sitemap_reexported)

        # Agents
        ard_direct = seo_agents.build_ard_manifest()
        ard_reexported = seo.build_ard_manifest()
        self.assertEqual(ard_direct, ard_reexported)

        card_direct = seo_agents.build_agent_card()
        card_reexported = seo.build_agent_card()
        self.assertEqual(card_direct, card_reexported)


if __name__ == "__main__":
    unittest.main(verbosity=2)
