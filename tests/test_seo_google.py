"""
Tests unitaires pour la soumission du sitemap à Google Search Console (seo_google).
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
    exchange_code_for_tokens,
    generate_auth_url,
    get_access_token,
    get_google_credentials,
    parse_dotenv,
    reset_token_cache,
    submit_sitemap_to_google,
)


class TestGoogleCredentials(unittest.TestCase):
    def setUp(self):
        reset_token_cache()

    def test_parse_dotenv(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as tf:
            tf.write("# Commentaire\n")
            tf.write("GOOGLE_CLIENT_ID=\"client-id-123\"\n")
            tf.write("GOOGLE_CLIENT_SECRET='secret-456'\n")
            tf.write("GOOGLE_REDIRECT_URIS=[\"https://cemantix.cyril-randon.fr\"]\n")
            tf.write("CLE_VIDE=\n")
            temp_path = Path(tf.name)

        try:
            parsed = parse_dotenv(temp_path)
            self.assertEqual(parsed.get("GOOGLE_CLIENT_ID"), "client-id-123")
            self.assertEqual(parsed.get("GOOGLE_CLIENT_SECRET"), "secret-456")
            self.assertEqual(parsed.get("GOOGLE_REDIRECT_URIS"), '["https://cemantix.cyril-randon.fr"]')
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_get_google_credentials_from_env_with_typo_fallback(self):
        fake_env = {
            "GOOGLE_CLIENT_ID": "client-abc",
            "GOOGLE_CLIENT_SECRET": "secret-xyz",
            "GOOGLE_REFRESH_TOKEN": "refresh-123",
            "GOOGLE_PROJECT_ID": "proj-99",
            "GOOGLE_REDIRECT_URIS": "https://custom.domaine.fr",
        }
        with mock.patch.dict(os.environ, fake_env, clear=True):
            creds = get_google_credentials()
            self.assertEqual(creds["client_id"], "client-abc")
            # Tolérance sur la clé avec faute de frappe
            self.assertEqual(creds["client_secret"], "secret-xyz")
            self.assertEqual(creds["refresh_token"], "refresh-123")
            self.assertEqual(creds["project_id"], "proj-99")
            self.assertEqual(creds["redirect_uri"], "https://custom.domaine.fr")

    def test_generate_auth_url(self):
        creds = {
            "client_id": "test-client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "redirect_uri": "https://cemantix.cyril-randon.fr",
        }
        url = generate_auth_url(creds)
        self.assertIn("https://accounts.google.com/o/oauth2/auth?", url)
        self.assertIn("client_id=test-client-id", url)
        self.assertIn("response_type=code", url)
        self.assertIn("scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fwebmasters", url)
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)


class TestGoogleTokenExchange(unittest.TestCase):
    def setUp(self):
        reset_token_cache()

    @mock.patch("requests.post")
    def test_exchange_code_success(self, mock_post):
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "ya29.test-access",
            "refresh_token": "1//test-refresh",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_resp

        creds = {"client_id": "cid", "client_secret": "sec", "redirect_uri": "https://site.fr"}
        res = exchange_code_for_tokens("mon-code-auth", creds)
        self.assertEqual(res.get("access_token"), "ya29.test-access")
        self.assertEqual(res.get("refresh_token"), "1//test-refresh")

    @mock.patch("requests.post")
    def test_get_access_token_refresh_and_caching(self, mock_post):
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "ya29.cached-token",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_resp

        creds = {"client_id": "cid", "client_secret": "sec", "refresh_token": "refr-123"}
        token1 = get_access_token(creds)
        self.assertEqual(token1, "ya29.cached-token")
        self.assertEqual(mock_post.call_count, 1)

        # Deuxième appel immédiat : doit réutiliser le cache sans nouvel appel HTTP
        token2 = get_access_token(creds)
        self.assertEqual(token2, "ya29.cached-token")
        self.assertEqual(mock_post.call_count, 1)


class TestGoogleSitemapSubmission(unittest.TestCase):
    def setUp(self):
        reset_token_cache()

    def test_submit_without_client_id(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            res = submit_sitemap_to_google(credentials={"client_id": ""})
            self.assertFalse(res["success"])
            self.assertEqual(res["status_code"], 0)
            self.assertIn("GOOGLE_CLIENT_ID absent", res["message"])

    def test_submit_without_refresh_token(self):
        creds = {"client_id": "test-cid", "refresh_token": ""}
        res = submit_sitemap_to_google(credentials=creds)
        self.assertFalse(res["success"])
        self.assertIn("GOOGLE_REFRESH_TOKEN absent", res["message"])
        self.assertIn("auth_url", res)

    @mock.patch("src.services.seo_google.get_access_token", return_value="ya29.valid-token")
    @mock.patch("requests.put")
    def test_submit_success_204(self, mock_put, mock_token):
        mock_resp = mock.Mock()
        mock_resp.status_code = 204
        mock_put.return_value = mock_resp

        creds = {"client_id": "cid", "refresh_token": "rtoken"}
        res = submit_sitemap_to_google(
            site_url="https://cemantix.cyril-randon.fr",
            sitemap_url="https://cemantix.cyril-randon.fr/sitemap.xml",
            credentials=creds,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["status_code"], 204)
        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args
        self.assertIn("Authorization", kwargs["headers"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer ya29.valid-token")
        # Vérifier l'encodage de l'URL cible
        self.assertIn("webmasters/v3/sites/https%3A%2F%2Fcemantix.cyril-randon.fr%2F/sitemaps/", args[0])

    @mock.patch("src.services.seo_google.get_access_token", return_value="ya29.valid-token")
    @mock.patch("requests.put")
    def test_submit_api_error_403(self, mock_put, mock_token):
        mock_resp = mock.Mock()
        mock_resp.status_code = 403
        mock_resp.text = "User does not have permission on site"
        mock_put.return_value = mock_resp

        creds = {"client_id": "cid", "refresh_token": "rtoken"}
        res = submit_sitemap_to_google(credentials=creds)
        self.assertFalse(res["success"])
        self.assertEqual(res["status_code"], 403)
        self.assertIn("User does not have permission", res["message"])


class TestSeoPublishIntegration(unittest.TestCase):
    @mock.patch("src.services.seo_google.submit_sitemap_to_google")
    def test_publish_seo_pages_triggers_google_submission(self, mock_submit):
        mock_submit.return_value = {"success": True, "status_code": 204}
        from datetime import datetime
        from src.services.seo import publish_seo_pages

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
            mock_submit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
