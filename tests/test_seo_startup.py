"""Tests de la génération automatique de sitemap.xml au démarrage des conteneurs.

Lancement :  python -m unittest discover -s tests -v
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.api import server as api_server  # noqa: E402
from src.services import seo, web  # noqa: E402


class _DummyStore:
    """Doublure légère de VocabStore pour tester start_api_server sans charger frWac."""

    words: list[str] = ["maison"]
    word_to_idx: dict[str, int] = {"maison": 0}


class TestSitemapAuDemarrage(unittest.TestCase):
    def setUp(self):
        self.web_root = Path(tempfile.mkdtemp(prefix="cemantix_seo_"))
        for nom in ("index.html", "llms.txt", "agent-skills.md"):
            shutil.copy(seo.WEB_ROOT / nom, self.web_root / nom)

    def tearDown(self):
        shutil.rmtree(self.web_root, ignore_errors=True)

    def test_ensure_seo_published_recree_sitemap_apres_suppression(self):
        sitemap = self.web_root / "sitemap.xml"
        self.assertFalse(sitemap.exists())

        historique = [
            {"date": "2026-10-29", "win": True, "puzzle": 1702, "word": "patrie", "tries": 11},
        ]
        with mock.patch("src.services.daemon.load_history", return_value=historique):
            res = seo.ensure_seo_published(web_root=self.web_root)

        self.assertIsNotNone(res)
        self.assertTrue(res["sitemap"])
        self.assertTrue(sitemap.is_file())
        contenu = sitemap.read_text(encoding="utf-8")
        self.assertIn("<urlset", contenu)
        self.assertIn("/puzzles/2026-10-29/", contenu)
        # Aucun fichier temporaire résiduel ne doit subsister après l'écriture atomique
        self.assertEqual(list(self.web_root.glob("*.tmp")), [])
        self.assertEqual(list(self.web_root.glob(".*.tmp")), [])

    def test_ensure_seo_published_genere_sitemap_meme_sans_historique(self):
        sitemap = self.web_root / "sitemap.xml"
        with mock.patch("src.services.daemon.load_history", return_value=[]):
            res = seo.ensure_seo_published(web_root=self.web_root)

        self.assertIsNotNone(res)
        self.assertTrue(sitemap.is_file())
        contenu = sitemap.read_text(encoding="utf-8")
        for route in ("/", "/puzzles/", "/play/", "/battle/", "/multi/"):
            self.assertIn(f"{seo.SITE_ORIGIN}{route}", contenu)

    def test_export_web_data_publie_sitemap_meme_si_data_json_echoue(self):
        data_dir = Path(tempfile.mkdtemp(prefix="cemantix_data_ro_"))
        try:
            historique = [{"date": "2026-10-29", "win": True, "puzzle": 1702}]
            with (
                mock.patch.object(seo, "WEB_ROOT", self.web_root),
                mock.patch("builtins.open", side_effect=PermissionError("data.json verrouillé")),
            ):
                with self.assertRaises(PermissionError):
                    web.export_web_data(
                        target_dir=data_dir,
                        history=historique,
                        heartbeat_path=None,
                        publish_seo=True,
                    )

            # Même en cas de PermissionError sur data.json, sitemap.xml est bien régénéré
            self.assertTrue((self.web_root / "sitemap.xml").is_file())
        finally:
            shutil.rmtree(data_dir, ignore_errors=True)

    def test_start_api_server_declenche_ensure_seo_published_en_mode_persistant(self):
        with (
            mock.patch.object(api_server, "GameManager"),
            mock.patch("src.services.seo.ensure_seo_published") as mock_seo,
        ):
            srv = api_server.start_api_server(
                _DummyStore(), host="127.0.0.1", port=0, persist=True
            )
            srv.server_close()
            mock_seo.assert_called_once_with()

    def test_start_api_server_n_ecrit_pas_en_mode_memoire_test(self):
        with (
            mock.patch.object(api_server, "GameManager"),
            mock.patch("src.services.seo.ensure_seo_published") as mock_seo,
        ):
            srv = api_server.start_api_server(
                _DummyStore(), host="127.0.0.1", port=0, persist=False
            )
            srv.server_close()
            mock_seo.assert_not_called()

    def test_ensure_seo_published_recree_et_corrige_les_manifestes_ard(self):
        well_known = self.web_root / ".well-known"
        well_known.mkdir(parents=True, exist_ok=True)
        # Simule un ai-catalog.json obsolète avec "host" sous forme de chaîne (ancien bug)
        (well_known / "ai-catalog.json").write_text(
            '{"specVersion": "1.0", "host": "cemantix.cyril-randon.fr", "entries": []}',
            encoding="utf-8",
        )

        with mock.patch("src.services.daemon.load_history", return_value=[]):
            res = seo.ensure_seo_published(web_root=self.web_root)

        self.assertIsNotNone(res)
        self.assertEqual(res["ard_manifests"], 3)
        for nom in ("ai-catalog.json", "ard.json", "agent-card.json"):
            self.assertTrue((well_known / nom).is_file(), nom)

        catalog = json.loads((well_known / "ai-catalog.json").read_text(encoding="utf-8"))
        ard = json.loads((well_known / "ard.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog, ard)
        self.assertIsInstance(catalog["host"], dict)
        self.assertEqual(catalog["host"]["displayName"], "Cémantix Solver")
        self.assertEqual(catalog["specVersion"], "1.0")
        self.assertGreaterEqual(len(catalog["entries"]), 2)

    def test_ensure_seo_published_survit_a_une_erreur_load_history(self):
        with mock.patch("src.services.daemon.load_history", side_effect=RuntimeError("DB indisponible")):
            res = seo.ensure_seo_published(web_root=self.web_root)

        self.assertIsNotNone(res)
        self.assertTrue((self.web_root / "sitemap.xml").is_file())
        self.assertTrue((self.web_root / ".well-known" / "ai-catalog.json").is_file())
        self.assertTrue((self.web_root / ".well-known" / "ard.json").is_file())

    def test_manifestes_ard_versionnes_synchronises_avec_generateur(self):
        real_wk = seo.WEB_ROOT / ".well-known"
        self.assertEqual(
            (real_wk / "ai-catalog.json").read_text(encoding="utf-8"),
            seo.build_ard_manifest(seo.SITE_ORIGIN),
        )
        self.assertEqual(
            (real_wk / "ard.json").read_text(encoding="utf-8"),
            seo.build_ard_manifest(seo.SITE_ORIGIN),
        )
        self.assertEqual(
            (real_wk / "agent-card.json").read_text(encoding="utf-8"),
            seo.build_agent_card(seo.SITE_ORIGIN),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
