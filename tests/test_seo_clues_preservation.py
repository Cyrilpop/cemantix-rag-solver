"""
Tests de préservation et d'extraction robuste des indices pour le mot du jour (M7).
"""
import json
import unittest

import _context  # noqa: F401 — environnement de test isolé

from src.db.daily import _row_to_entry, save_daily_puzzle, save_daily_hints
from src.services.seo_templates import extract_clue_guesses, format_clue_words_list, _clue_rows
from src.services.seo_hubs import build_mot_du_jour_page


class TestSeoCluesPreservation(unittest.TestCase):
    def test_row_to_entry_deserializes_json_strings(self):
        """Vérifie que les chaînes JSON issues de SQLite sont correctement désérialisées."""
        row = {
            "date": "2026-10-31",
            "puzzle_id": 1704,
            "secret_word": "apparence",
            "tries_count": 9,
            "attempts_count": 9,
            "source": "rag",
            "win": 1,
            "duration_seconds": 12.3,
            "top_guesses": json.dumps([
                {"word": "apparence", "score": 100.0, "permille": 1000},
                {"word": "nudité", "score": 40.73, "permille": 918},
                {"word": "corps", "score": 37.12, "permille": 771},
            ]),
            "trajectory": json.dumps([
                {"word": "maison", "score": -6.76},
                {"word": "apparence", "score": 100.0},
            ]),
            "is_revealed": 0,
            "solved_at": "2026-10-31T00:00:00",
        }
        entry = _row_to_entry(row)
        self.assertIsInstance(entry["top_guesses"], list)
        self.assertEqual(len(entry["top_guesses"]), 3)
        self.assertEqual(entry["top_guesses"][1]["word"], "nudité")
        self.assertIsInstance(entry["trajectory"], list)
        self.assertEqual(len(entry["trajectory"]), 2)

    def test_extract_clue_guesses_filters_secret_word_and_masks(self):
        """Vérifie que le mot secret et les masques ne figurent jamais dans les indices."""
        entry = {
            "date": "2026-10-31",
            "puzzle": 1704,
            "word": "apparence",
            "top_guesses": [
                {"word": "apparence", "score": 100.0, "permille": 1000},
                {"word": "nudité", "score": 40.73, "permille": 918},
                {"word": "••••••••", "score": 99.9, "permille": 999},
                {"word": "corps", "score": 37.12, "permille": 771},
            ],
        }
        clues = extract_clue_guesses(entry)
        words = [c["word"] for c in clues]
        self.assertNotIn("apparence", words)
        self.assertNotIn("••••••••", words)
        self.assertIn("nudité", words)
        self.assertIn("corps", words)

    def test_extract_clue_guesses_fallback_to_trajectory(self):
        """Vérifie le repli sur trajectory si top_guesses est absent."""
        entry = {
            "date": "2026-10-31",
            "puzzle": 1704,
            "word": "apparence",
            "top_guesses": [],
            "trajectory": [
                {"word": "soleil", "score": 15.0, "permille": 300},
                {"word": "corps", "score": 37.12, "permille": 771},
                {"word": "apparence", "score": 100.0, "permille": 1000},
            ],
        }
        clues = extract_clue_guesses(entry)
        words = [c["word"] for c in clues]
        self.assertEqual(words, ["corps", "soleil"])

    def test_format_clue_words_list_various_inputs(self):
        """Vérifie le formatage et l'anti-spoiler pour divers formats d'entrée."""
        guesses_dict = [
            {"word": "secret", "score": 100.0, "permille": 1000},
            {"word": "proche", "score": 42.0, "permille": 900},
            {"word": "ami", "score": 35.0, "permille": 800},
        ]
        res = format_clue_words_list(guesses_dict, limit=10, secret_word="secret")
        self.assertEqual(res, "proche, ami")

        # Liste de strings
        res_str = format_clue_words_list(["secret", "proche", "ami"], limit=10, secret_word="secret")
        self.assertEqual(res_str, "proche, ami")

    def test_build_mot_du_jour_page_preserves_clues(self):
        """Vérifie que la page mot-du-jour contient bien les indices dans le HTML et les metas."""
        entry = {
            "date": "2026-10-31",
            "puzzle": 1704,
            "word": "apparence",
            "win": True,
            "tries": 9,
            "duration_seconds": 12.3,
            "top_guesses": [
                {"word": "apparence", "score": 100.0, "permille": 1000},
                {"word": "nudité", "score": 40.73, "permille": 918},
                {"word": "corps", "score": 37.12, "permille": 771},
                {"word": "érotiser", "score": 34.11, "permille": 493},
            ],
        }
        html = build_mot_du_jour_page(entry, [entry])
        # Table des indices
        self.assertIn("🌡️ Les 3 indices du mot du jour", html)
        self.assertIn("Nudité", html)
        self.assertIn("Corps", html)
        self.assertIn("Érotiser", html)
        # Pas de spoiler dans les indices
        self.assertNotIn("Apparence", html.split('<details class="reveal">')[0])
        # Meta description avec les mots indices
        self.assertIn("nudité, corps, érotiser", html)


if __name__ == "__main__":
    unittest.main()

