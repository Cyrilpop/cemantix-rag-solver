"""
Tests unitaires pour l'indexation instantanée (Google Indexing API, IndexNow)
et les données structurées Schema.org avancées (HowTo).
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
RACINE = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import _context  # noqa: F401

from src.services.seo_google import (
    notify_daily_urls_to_google,
    notify_google_indexing,
    reset_token_cache,
)
from src.services.seo_hubs import build_methode_page
from src.services.seo_indexnow import (
    get_indexnow_key,
    submit_indexnow_urls,
)


class TestGoogleIndexingApi(unittest.TestCase):
    def setUp(self):
        reset_token_cache()

    def test_notify_missing_credentials(self):
        res = notify_google_indexing("https://site.fr/", credentials={"client_id": ""})
        self.assertFalse(res["success"])
        self.assertEqual(res["status_code"], 0)

    @mock.patch("src.services.seo_google.get_access_token", return_value="ya29.indexing-token")
    @mock.patch("requests.post")
    def test_notify_success(self, mock_post, mock_token):
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        creds = {"client_id": "cid", "refresh_token": "rt"}
        res = notify_google_indexing(
            "https://cemantix.cyril-randon.fr/mot-du-jour/",
            credentials=creds,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["status_code"], 200)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://indexing.googleapis.com/v3/urlNotifications:publish")
        self.assertEqual(kwargs["json"]["url"], "https://cemantix.cyril-randon.fr/mot-du-jour/")
        self.assertEqual(kwargs["json"]["type"], "URL_UPDATED")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer ya29.indexing-token")

    @mock.patch("src.services.seo_google.notify_google_indexing")
    def test_notify_daily_urls(self, mock_notify):
        mock_notify.return_value = {"success": True}
        entries = [{"date": "2026-11-05"}]
        results = notify_daily_urls_to_google(entries, site_origin="https://cemantix.cyril-randon.fr")
        self.assertEqual(len(results), 3)
        self.assertIn("https://cemantix.cyril-randon.fr/", results)
        self.assertIn("https://cemantix.cyril-randon.fr/mot-du-jour/", results)
        self.assertIn("https://cemantix.cyril-randon.fr/puzzles/2026-11-05/", results)


class TestIndexNow(unittest.TestCase):
    def test_get_indexnow_key_generation_and_file_creation(self):
        with tempfile.TemporaryDirectory() as tmp_web:
            root = Path(tmp_web)
            key = get_indexnow_key(web_root=root)
            self.assertTrue(bool(key))
            self.assertEqual(len(key), 32)
            # Vérifier l'existence des fichiers dans le webroot
            self.assertTrue((root / "indexnow-key.txt").is_file())
            self.assertTrue((root / f"{key}.txt").is_file())
            self.assertEqual((root / f"{key}.txt").read_text(encoding="utf-8"), key)

    @mock.patch("requests.post")
    def test_submit_indexnow_urls_success(self, mock_post):
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        with tempfile.TemporaryDirectory() as tmp_web:
            root = Path(tmp_web)
            urls = ["https://cemantix.cyril-randon.fr/", "https://cemantix.cyril-randon.fr/mot-du-jour/"]
            res = submit_indexnow_urls(urls, host="cemantix.cyril-randon.fr", key="testkey123", web_root=root)
            self.assertTrue(res["success"])
            self.assertEqual(res["status_code"], 200)
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertEqual(kwargs["json"]["host"], "cemantix.cyril-randon.fr")
            self.assertEqual(kwargs["json"]["key"], "testkey123")
            self.assertEqual(kwargs["json"]["urlList"], urls)


class TestSchemaOrgHowTo(unittest.TestCase):
    def test_build_methode_page_contains_howto_schema(self):
        html = build_methode_page()
        self.assertIn('"HowTo"', html)
        self.assertIn('"HowToStep"', html)
        self.assertIn("Méthode pour trouver le mot du jour Cémantix", html)


class TestPublishSeoIntegration(unittest.TestCase):
    @mock.patch("src.services.seo_google.submit_sitemap_to_google")
    @mock.patch("src.services.seo_google.notify_daily_urls_to_google")
    @mock.patch("src.services.seo_indexnow.submit_indexnow_urls")
    def test_publish_seo_triggers_all_instant_notifications(self, mock_indexnow, mock_google_idx, mock_sitemap):
        from datetime import datetime
        from src.services.seo import publish_seo_pages

        mock_sitemap.return_value = {"success": True}
        mock_google_idx.return_value = {"https://site/": {"success": True}}
        mock_indexnow.return_value = {"success": True}

        history = [
            {"date": "2026-11-05", "puzzle": 1709, "win": True, "target": "soleil", "guesses": ["pomme", "soleil"]}
        ]
        with tempfile.TemporaryDirectory() as tmp_web:
            tmp_root = Path(tmp_web)
            (tmp_root / "index.html").write_text(
                "<!-- SEO-PRERENDER:DEBUT --> <!-- SEO-PRERENDER:FIN -->",
                encoding="utf-8"
            )
            report = publish_seo_pages(history=history, generated_at=datetime(2026, 11, 5), web_root=tmp_root)
            self.assertTrue(report.get("google_sitemap"))
            self.assertTrue(report.get("indexnow"))
            mock_google_idx.assert_called_once()
            mock_indexnow.assert_called_once()


if __name__ == "__main__":
    unittest.main()
