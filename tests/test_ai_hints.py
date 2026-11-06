"""
Suite de tests unitaires pour le module IA Gemini et les indices (M12).
Couvre :
- Le sélecteur de modèle et configurations
- L'ingénierie des prompts et le Leak-Guard
- Le client HTTP REST Gemini (avec simulation mock)
- La persistance SQL (SQLite de repli) et fonctions CRUD
- L'orchestration idempotente et le backfill
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import _context  # noqa: F401 — isole sur SQLite temporaire

from src.ai import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    GeminiClient,
    SYSTEM_PROMPT,
    build_user_prompt,
    check_leak_guard,
    generate_hints,
    get_model_endpoint,
    get_model_info,
    parse_gemini_hints_response,
)
from src.db.connection import db
from src.db.daily import (
    get_daily_ai_hints,
    has_daily_ai_hints,
    save_daily_ai_hints,
    save_daily_puzzle,
)
from src.services.ai_hints import (
    backfill_ai_hints,
    generate_ai_hints_cli,
    generate_and_store_ai_hints,
)


SAMPLE_VALID_RESPONSE = {
    "secret_word": "boussole",
    "hints": [
        {
            "level": 1,
            "weight": 0.33,
            "word": "navigation",
            "phrase": "Ce concept renvoie aux grandes expéditions maritimes et à l'art ancestral de ne jamais perdre son chemin."
        },
        {
            "level": 2,
            "weight": 0.66,
            "word": "orientation",
            "phrase": "Cet instrument pratique s'utilise en pleine nature pour repérer immédiatement les quatre points cardinaux."
        },
        {
            "level": 3,
            "weight": 1.00,
            "word": "aimant",
            "phrase": "Son cadran circulaire renferme une fine aiguille métallique attirée sans cesse vers le pôle nord terrestre."
        }
    ]
}


class TestModelSelector(unittest.TestCase):
    """Vérifie la centralisation des paramètres du modèle."""

    def test_default_constants(self):
        self.assertEqual(DEFAULT_MODEL, "gemini-3.8-flash")
        self.assertEqual(DEFAULT_TEMPERATURE, 0.3)
        self.assertEqual(DEFAULT_TIMEOUT_SECONDS, 10.0)

    def test_model_endpoint(self):
        endpoint = get_model_endpoint("gemini-3.8-flash")
        self.assertIn("v1beta/models/gemini-3.8-flash:generateContent", endpoint)
        # Gestion du préfixe models/
        endpoint_prefixed = get_model_endpoint("models/gemini-3.8-flash")
        self.assertEqual(endpoint, endpoint_prefixed)

    def test_get_model_info(self):
        info = get_model_info()
        self.assertIn("model", info)
        self.assertEqual(info["temperature"], 0.3)
        self.assertEqual(info["timeout"], 10.0)


class TestPromptsAndLeakGuard(unittest.TestCase):
    """Vérifie les prompts, le parsing et le filtre Leak-Guard."""

    def test_system_prompt_rules(self):
        self.assertIn("Maître du Jeu officiel de Cémantix", SYSTEM_PROMPT)
        self.assertIn("INTERDICTION ABSOLUE", SYSTEM_PROMPT)
        self.assertIn("weight = 0.33", SYSTEM_PROMPT)
        self.assertIn("weight = 0.66", SYSTEM_PROMPT)
        self.assertIn("weight = 1.00", SYSTEM_PROMPT)

    def test_build_user_prompt(self):
        prompt = build_user_prompt("boussole")
        self.assertIn('MOT_SECRET : "boussole"', prompt)
        self.assertIn('"secret_word": "boussole"', prompt)

    def test_parse_valid_json(self):
        raw = json.dumps(SAMPLE_VALID_RESPONSE)
        hints = parse_gemini_hints_response(raw, secret_word="boussole")
        self.assertEqual(len(hints), 3)
        self.assertEqual(hints[0]["hint_level"], 1)
        self.assertEqual(hints[0]["hint_word"], "navigation")
        self.assertEqual(hints[1]["hint_level"], 2)
        self.assertEqual(hints[2]["hint_level"], 3)
        self.assertEqual(hints[2]["weight"], 1.0)

    def test_parse_markdown_wrapped_json(self):
        raw = f"```json\n{json.dumps(SAMPLE_VALID_RESPONSE)}\n```"
        hints = parse_gemini_hints_response(raw, secret_word="boussole")
        self.assertEqual(len(hints), 3)

    def test_parse_invalid_json(self):
        with self.assertRaises(ValueError):
            parse_gemini_hints_response("texte non json", secret_word="boussole")

    def test_parse_incomplete_hints_count(self):
        data = {
            "secret_word": "test",
            "hints": [
                {"level": 1, "weight": 0.33, "word": "a", "phrase": "p1"},
                {"level": 2, "weight": 0.66, "word": "b", "phrase": "p2"},
            ]
        }
        with self.assertRaises(ValueError):
            parse_gemini_hints_response(json.dumps(data), secret_word="test")

    def test_leak_guard_direct_word_match(self):
        self.assertTrue(check_leak_guard("boussole", "boussole", "Une phrase anodine"))
        self.assertTrue(check_leak_guard("boussole", "boussoles", "Une phrase anodine"))

    def test_leak_guard_stem_match_in_word(self):
        # Racine de "boussole" -> "bouss"
        self.assertTrue(check_leak_guard("boussole", "boussolier", "Une phrase anodine"))

    def test_leak_guard_in_phrase(self):
        self.assertTrue(check_leak_guard("boussole", "nord", "Cette boussole indique le nord."))
        self.assertTrue(check_leak_guard("boussole", "nord", "Ces boussoles sont indispensables."))

    def test_leak_guard_rejection_in_parser(self):
        leaked_response = {
            "secret_word": "boussole",
            "hints": [
                {"level": 1, "weight": 0.33, "word": "navigation", "phrase": "Un domaine large"},
                {"level": 2, "weight": 0.66, "word": "boussole", "phrase": "Une fuite directe ici"},
                {"level": 3, "weight": 1.00, "word": "aimant", "phrase": "Une phrase d'orientation"},
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            parse_gemini_hints_response(json.dumps(leaked_response), secret_word="boussole")
        self.assertIn("Leak-Guard", str(ctx.exception))


class TestGeminiClient(unittest.TestCase):
    """Vérifie le client Gemini avec simulation HTTP via requests."""

    def test_is_configured(self):
        c1 = GeminiClient(api_key="AIzaSyDummyKey")
        self.assertTrue(c1.is_configured())
        c2 = GeminiClient(api_key="")
        self.assertFalse(c2.is_configured())

    @mock.patch("requests.post")
    def test_generate_hints_success(self, mock_post):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": json.dumps(SAMPLE_VALID_RESPONSE)}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        client = GeminiClient(api_key="dummy_key", model="gemini-3.8-flash")
        hints = client.generate_hints("boussole")

        self.assertIsNotNone(hints)
        self.assertEqual(len(hints), 3)
        self.assertEqual(hints[0]["model"], "gemini-3.8-flash")
        mock_post.assert_called_once()

    @mock.patch("requests.post")
    def test_generate_hints_http_error(self, mock_post):
        mock_response = mock.MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Quota exceeded"
        mock_post.return_value = mock_response

        client = GeminiClient(api_key="dummy_key")
        hints = client.generate_hints("boussole")
        self.assertIsNone(hints)

    @mock.patch("requests.post")
    def test_generate_hints_network_timeout(self, mock_post):
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        client = GeminiClient(api_key="dummy_key")
        hints = client.generate_hints("boussole")
        self.assertIsNone(hints)

    def test_generate_hints_unconfigured(self):
        client = GeminiClient(api_key="")
        hints = client.generate_hints("boussole")
        self.assertIsNone(hints)


class TestSQLPersistence(unittest.TestCase):
    """Vérifie le stockage relationnel SQLite de repli pour daily_puzzle_ai_hints."""

    def setUp(self):
        db.init_db()
        db.execute("DELETE FROM daily_puzzle_ai_hints;")
        db.execute("DELETE FROM daily_puzzles;")

    def tearDown(self):
        db.execute("DELETE FROM daily_puzzle_ai_hints;")
        db.execute("DELETE FROM daily_puzzles;")

    def test_save_and_get_ai_hints(self):
        puzzle_date = "2026-11-06"
        save_daily_puzzle({
            "date": puzzle_date,
            "puzzle": 123,
            "word": "boussole",
            "tries": 42,
            "attempts": 42,
            "win": True,
        })

        hints_to_save = [
            {"hint_level": 1, "weight": 0.33, "hint_word": "navigation", "hint_phrase": "P1", "model": "gemini-3.8-flash", "is_revealed": False},
            {"hint_level": 2, "weight": 0.66, "hint_word": "orientation", "hint_phrase": "P2", "model": "gemini-3.8-flash", "is_revealed": False},
            {"hint_level": 3, "weight": 1.00, "hint_word": "aimant", "hint_phrase": "P3", "model": "gemini-3.8-flash", "is_revealed": True},
        ]

        inserted = save_daily_ai_hints(puzzle_date, hints_to_save)
        self.assertEqual(inserted, 3)

        # Récupération complète
        loaded = get_daily_ai_hints(puzzle_date, revealed_only=False)
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0]["hint_level"], 1)
        self.assertEqual(loaded[0]["hint_word"], "navigation")
        self.assertEqual(loaded[1]["hint_level"], 2)
        self.assertEqual(loaded[2]["hint_level"], 3)
        self.assertEqual(loaded[2]["hint_phrase"], "P3")

        # Filtrage revealed_only
        revealed = get_daily_ai_hints(puzzle_date, revealed_only=True)
        self.assertEqual(len(revealed), 1)
        self.assertEqual(revealed[0]["hint_level"], 3)

    def test_idempotent_upsert(self):
        puzzle_date = "2026-11-06"
        save_daily_puzzle({
            "date": puzzle_date,
            "puzzle": 123,
            "word": "boussole",
            "tries": 42,
            "attempts": 42,
            "win": True,
        })

        hints_v1 = [
            {"hint_level": 1, "weight": 0.33, "hint_word": "ancien_mot", "hint_phrase": "ancienne phrase"},
        ]
        save_daily_ai_hints(puzzle_date, hints_v1)

        hints_v2 = [
            {"hint_level": 1, "weight": 0.35, "hint_word": "nouveau_mot", "hint_phrase": "nouvelle phrase"},
        ]
        save_daily_ai_hints(puzzle_date, hints_v2)

        loaded = get_daily_ai_hints(puzzle_date)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["hint_word"], "nouveau_mot")
        self.assertEqual(loaded[0]["hint_phrase"], "nouvelle phrase")

    def test_has_daily_ai_hints(self):
        puzzle_date = "2026-11-06"
        save_daily_puzzle({
            "date": puzzle_date,
            "puzzle": 123,
            "word": "boussole",
            "tries": 10,
            "attempts": 10,
            "win": True,
        })
        self.assertFalse(has_daily_ai_hints(puzzle_date))

        # Moins de 3 indices -> incomplet
        save_daily_ai_hints(puzzle_date, [
            {"hint_level": 1, "weight": 0.33, "hint_word": "w1", "hint_phrase": "p1"},
            {"hint_level": 2, "weight": 0.66, "hint_word": "w2", "hint_phrase": "p2"},
        ])
        self.assertFalse(has_daily_ai_hints(puzzle_date))

        # 3 indices complets -> True
        save_daily_ai_hints(puzzle_date, [
            {"hint_level": 3, "weight": 1.00, "hint_word": "w3", "hint_phrase": "p3"},
        ])
        self.assertTrue(has_daily_ai_hints(puzzle_date))


class TestOrchestrationService(unittest.TestCase):
    """Vérifie les fonctions d'orchestration de src.services.ai_hints."""

    def setUp(self):
        db.init_db()
        db.execute("DELETE FROM daily_puzzle_ai_hints;")
        db.execute("DELETE FROM daily_puzzles;")

    def tearDown(self):
        db.execute("DELETE FROM daily_puzzle_ai_hints;")
        db.execute("DELETE FROM daily_puzzles;")

    def test_generate_and_store_idempotence(self):
        puzzle_date = "2026-11-06"
        save_daily_puzzle({
            "date": puzzle_date,
            "puzzle": 100,
            "word": "boussole",
            "tries": 10,
            "attempts": 10,
            "win": True,
        })

        mock_client = mock.MagicMock(spec=GeminiClient)
        mock_client.is_configured.return_value = True
        mock_client.request_hints.return_value = [
            {"hint_level": 1, "weight": 0.33, "hint_word": "navigation", "hint_phrase": "p1", "model": "gemini-3.8-flash"},
            {"hint_level": 2, "weight": 0.66, "hint_word": "orientation", "hint_phrase": "p2", "model": "gemini-3.8-flash"},
            {"hint_level": 3, "weight": 1.00, "hint_word": "aimant", "hint_phrase": "p3", "model": "gemini-3.8-flash"},
        ]

        # Premier appel : effectue l'appel API et enregistre
        res1 = generate_and_store_ai_hints(puzzle_date, "boussole", force=False, client=mock_client)
        self.assertEqual(len(res1), 3)
        self.assertEqual(mock_client.request_hints.call_count, 1)

        # Deuxième appel sans force pour le MÊME mot de la MÊME date : réutilise la BDD sans appeler l'API Gemini
        res2 = generate_and_store_ai_hints(puzzle_date, "boussole", force=False, client=mock_client)
        self.assertEqual(len(res2), 3)
        self.assertEqual(mock_client.request_hints.call_count, 1)

        # Troisième appel avec force=True : ré-exécute l'appel API
        res3 = generate_and_store_ai_hints(puzzle_date, "boussole", force=True, client=mock_client)
        self.assertEqual(len(res3), 3)
        self.assertEqual(mock_client.request_hints.call_count, 2)

    def test_backfill_ai_hints(self):
        for i in range(1, 4):
            save_daily_puzzle({
                "date": f"2026-11-0{i}",
                "puzzle": i,
                "word": f"mot{i}",
                "tries": 10,
                "attempts": 10,
                "win": True,
            })

        with mock.patch("src.services.ai_hints.GeminiClient") as MockClientClass:
            mock_inst = MockClientClass.return_value
            mock_inst.is_configured.return_value = True
            mock_inst.request_hints.return_value = [
                {"hint_level": 1, "weight": 0.33, "hint_word": "w1", "hint_phrase": "p1", "model": "gemini-3.8-flash"},
                {"hint_level": 2, "weight": 0.66, "hint_word": "w2", "hint_phrase": "p2", "model": "gemini-3.8-flash"},
                {"hint_level": 3, "weight": 1.00, "hint_word": "w3", "hint_phrase": "p3", "model": "gemini-3.8-flash"},
            ]

            count = backfill_ai_hints()
            self.assertEqual(count, 3)

            # Un second backfill sans force ne doit rien réinsérer
            count_repeat = backfill_ai_hints(force=False)
            self.assertEqual(count_repeat, 0)

    def test_generate_ai_hints_cli(self):
        save_daily_puzzle({
            "date": "2026-11-06",
            "puzzle": 456,
            "word": "boussole",
            "tries": 5,
            "attempts": 5,
            "win": True,
        })
        with mock.patch("src.services.ai_hints.generate_and_store_ai_hints") as mock_gen:
            mock_gen.return_value = [
                {"hint_level": 1, "weight": 0.33, "hint_word": "navigation", "hint_phrase": "phrase 1"},
                {"hint_level": 2, "weight": 0.66, "hint_word": "orientation", "hint_phrase": "phrase 2"},
                {"hint_level": 3, "weight": 1.00, "hint_word": "aimant", "hint_phrase": "phrase 3"},
            ]
            # Exécution sans lever d'exception
            generate_ai_hints_cli(target_date="2026-11-06", force=True)
            mock_gen.assert_called_once_with("2026-11-06", "boussole", force=True)


if __name__ == "__main__":
    unittest.main()

