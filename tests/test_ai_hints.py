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
from src.engine.ranking import WordScorer
from src.services.ai_hints import (
    backfill_ai_hints,
    generate_ai_hints_cli,
    generate_and_store_ai_hints,
    generate_calibrated_ai_hints,
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
        self.assertEqual(DEFAULT_TIMEOUT_SECONDS, 30.0)

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
        self.assertEqual(info["timeout"], 30.0)


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
        with mock.patch("src.services.ai_hints.generate_and_store_ai_hints") as mock_gen, \
             mock.patch("src.services.ai_hints._print_hints_summary"):
            mock_gen.return_value = [
                {"hint_level": 1, "weight": 0.33, "hint_word": "navigation", "hint_phrase": "phrase 1"},
                {"hint_level": 2, "weight": 0.66, "hint_word": "orientation", "hint_phrase": "phrase 2"},
                {"hint_level": 3, "weight": 1.00, "hint_word": "aimant", "hint_phrase": "phrase 3"},
            ]
            # Exécution sans lever d'exception
            generate_ai_hints_cli(target_date="2026-11-06", force=True)
            mock_gen.assert_called_once_with("2026-11-06", "boussole", force=True)


class TestWordScorerAndCalibratedHints(unittest.TestCase):
    """Vérifie le calcul de score/permille et le calibrage sémantique des indices IA."""

    def setUp(self):
        import numpy as np

        class TinyMockStore:
            def __init__(self):
                self.words = ["secret", "w_tiede", "w_chaud", "w_brulant", "w_autre"]
                self.vec_map = {
                    "secret": np.array([1.0, 0.0, 0.0, 0.0]),
                    "w_tiede": np.array([0.4, 0.9165, 0.0, 0.0]),
                    "w_chaud": np.array([0.65, 0.7599, 0.0, 0.0]),
                    "w_brulant": np.array([0.95, 0.3122, 0.0, 0.0]),
                    "w_autre": np.array([0.1, 0.995, 0.0, 0.0]),
                }
                self.vecs = np.vstack([self.vec_map[w] for w in self.words])

            def normalize(self, w):
                return str(w or "").strip().lower()

            def __contains__(self, w):
                return self.normalize(w) in self.words

            def vec(self, w):
                return self.vec_map[self.normalize(w)]

        self.mock_store = TinyMockStore()

    def test_word_scorer_computation(self):
        ws = WordScorer("secret", self.mock_store)
        self.assertTrue(ws.is_valid)

        # Mot très proche
        score_b, permille_b = ws.score("w_brulant")
        self.assertAlmostEqual(score_b, 95.0, places=1)
        self.assertIsNotNone(permille_b)

        # Mot tiède
        score_t, permille_t = ws.score("w_tiede")
        self.assertAlmostEqual(score_t, 40.0, places=1)

        # Mot inconnu
        score_unk, permille_unk = ws.score("mot_inexistant")
        self.assertEqual(score_unk, 0.0)
        self.assertIsNone(permille_unk)

    def test_calibrated_hints_out_of_order_reorganization(self):
        """Si Gemini renvoie 3 indices aux bonnes températures mais désordonnés, réorganisation stricte."""
        client = mock.MagicMock(spec=GeminiClient)
        client.is_configured.return_value = True

        # Gemini renvoie : 1=brûlant, 2=tiède, 3=chaud
        client.generate_hints.return_value = [
            {"level": 1, "weight": 0.33, "word": "brulant", "phrase": "phrase brulante"},
            {"level": 2, "weight": 0.66, "word": "tiede", "phrase": "phrase tiede"},
            {"level": 3, "weight": 1.00, "word": "chaud", "phrase": "phrase chaude"},
        ]

        # Simuler les scores sémantiques cibles
        permille_map = {
            "tiede": (25.0, 420),
            "chaud": (45.0, 650),
            "brulant": (85.0, 950),
        }

        with mock.patch("src.services.ai_hints.WordScorer") as MockScorerClass:
            mock_scorer = MockScorerClass.return_value
            mock_scorer.score.side_effect = lambda w: permille_map.get(w, (0.0, None))

            hints = generate_calibrated_ai_hints("boussole", store=self.mock_store, client=client, max_calls=5)

            self.assertIsNotNone(hints)
            self.assertEqual(len(hints), 3)
            self.assertEqual(client.generate_hints.call_count, 1)

            # Vérifier l'ordre croissant et l'association mot + phrase intacte
            self.assertEqual(hints[0]["hint_level"], 1)
            self.assertEqual(hints[0]["word"], "tiede")
            self.assertEqual(hints[0]["phrase"], "phrase tiede")
            self.assertEqual(hints[0]["weight"], 0.33)
            self.assertEqual(hints[0]["permille"], 420)

            self.assertEqual(hints[1]["hint_level"], 2)
            self.assertEqual(hints[1]["word"], "chaud")
            self.assertEqual(hints[1]["phrase"], "phrase chaude")
            self.assertEqual(hints[1]["weight"], 0.66)
            self.assertEqual(hints[1]["permille"], 650)

            self.assertEqual(hints[2]["hint_level"], 3)
            self.assertEqual(hints[2]["word"], "brulant")
            self.assertEqual(hints[2]["phrase"], "phrase brulante")
            self.assertEqual(hints[2]["weight"], 1.00)
            self.assertEqual(hints[2]["permille"], 950)

            self.assertLess(hints[0]["permille"], hints[1]["permille"])
            self.assertLess(hints[1]["permille"], hints[2]["permille"])

    def test_calibrated_hints_retry_loop_with_feedback(self):
        """Si la tentative 1 est hors plages, relance avec feedback et réussit à la tentative 2."""
        client = mock.MagicMock(spec=GeminiClient)
        client.is_configured.return_value = True

        # Tentative 1 : mots hors plages (800, 810, 820)
        hints_attempt1 = [
            {"level": 1, "weight": 0.33, "word": "bad1", "phrase": "phrase bad1"},
            {"level": 2, "weight": 0.66, "word": "bad2", "phrase": "phrase bad2"},
            {"level": 3, "weight": 1.00, "word": "bad3", "phrase": "phrase bad3"},
        ]
        # Tentative 2 : mots conformes (400, 600, 930)
        hints_attempt2 = [
            {"level": 1, "weight": 0.33, "word": "good1", "phrase": "phrase good1"},
            {"level": 2, "weight": 0.66, "word": "good2", "phrase": "phrase good2"},
            {"level": 3, "weight": 1.00, "word": "good3", "phrase": "phrase good3"},
        ]
        client.generate_hints.side_effect = [hints_attempt1, hints_attempt2]

        permille_map = {
            "bad1": (50.0, 800),
            "bad2": (52.0, 810),
            "bad3": (54.0, 820),
            "good1": (20.0, 400),
            "good2": (40.0, 600),
            "good3": (80.0, 930),
        }

        with mock.patch("src.services.ai_hints.WordScorer") as MockScorerClass:
            mock_scorer = MockScorerClass.return_value
            mock_scorer.score.side_effect = lambda w: permille_map.get(w, (0.0, None))

            hints = generate_calibrated_ai_hints("boussole", store=self.mock_store, client=client, max_calls=5)

            self.assertIsNotNone(hints)
            self.assertEqual(client.generate_hints.call_count, 2)

            # Vérifier que le second appel a reçu un prompt avec feedback
            second_call_prompt = client.generate_hints.call_args_list[1].kwargs.get("user_prompt")
            self.assertIsNotNone(second_call_prompt)
            self.assertIn("ATTENTION", second_call_prompt)

            # Vérifier les indices finaux
            self.assertEqual(hints[0]["word"], "good1")
            self.assertEqual(hints[0]["phrase"], "phrase good1")
            self.assertEqual(hints[1]["word"], "good2")
            self.assertEqual(hints[1]["phrase"], "phrase good2")
            self.assertEqual(hints[2]["word"], "good3")
            self.assertEqual(hints[2]["phrase"], "phrase good3")

    def test_calibrated_hints_quota_guard_and_fallback(self):
        """Au-delà de 5 appels sans triplet parfait, sélection des 3 candidats les plus proches dans l'ordre."""
        client = mock.MagicMock(spec=GeminiClient)
        client.is_configured.return_value = True

        # Générer 5 retours avec des mots différents mais hors plages parfaites
        def fake_hints(secret_word, user_prompt=None):
            idx = client.generate_hints.call_count
            return [
                {"level": 1, "weight": 0.33, "word": f"w_a_{idx}", "phrase": f"phrase a {idx}"},
                {"level": 2, "weight": 0.66, "word": f"w_b_{idx}", "phrase": f"phrase b {idx}"},
                {"level": 3, "weight": 1.00, "word": f"w_c_{idx}", "phrase": f"phrase c {idx}"},
            ]
        client.generate_hints.side_effect = fake_hints

        # Attribution des scores
        def fake_score(w):
            if "w_a" in w:
                return (15.0, 250)
            if "w_b" in w:
                return (35.0, 480)
            if "w_c" in w:
                return (55.0, 820)
            return (0.0, None)

        with mock.patch("src.services.ai_hints.WordScorer") as MockScorerClass:
            mock_scorer = MockScorerClass.return_value
            mock_scorer.score.side_effect = fake_score

            hints = generate_calibrated_ai_hints("boussole", store=self.mock_store, client=client, max_calls=5)

            # Vérifier quota strict de 5 appels
            self.assertEqual(client.generate_hints.call_count, 5)

            # Vérifier présence de 3 indices dans l'ordre strictement croissant
            self.assertIsNotNone(hints)
            self.assertEqual(len(hints), 3)
            p1, p2, p3 = hints[0]["permille"], hints[1]["permille"], hints[2]["permille"]
            self.assertLess(p1, p2)
            self.assertLess(p2, p3)
            # Intégrité mot + phrase
            for h in hints:
                self.assertTrue(h["phrase"].startswith(f"phrase {h['word'].split('_')[1]}"))


if __name__ == "__main__":
    unittest.main()

