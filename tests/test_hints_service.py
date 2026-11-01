"""
Tests unitaires pour le service de génération et de rattrapage des indices (M6).
"""
import unittest
from unittest import mock
import numpy as np

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import _context  # noqa: F401 — isole sur SQLite temporaire

from src.db.connection import db
from src.db.daily import save_daily_puzzle, get_daily_hints
from src.services.hints import generate_hints_for_word, backfill_puzzle_hints, DEFAULT_TIER_TARGETS


class MockVocabStore:
    """Mock léger pour tester la génération d'indices de manière déterministe."""
    def __init__(self):
        # 10 mots de test avec des vecteurs 4D
        self.words = ["secret", "proche", "chaud", "tiede", "froid", "glace", "autre", "soleil", "lune", "etoile"]
        self.index = {w: i for i, w in enumerate(self.words)}
        # Vecteurs orthonormés / arbitraires normalisés
        rng = np.random.RandomState(42)
        raw_v = rng.randn(len(self.words), 10)
        self.vecs = raw_v / np.linalg.norm(raw_v, axis=1, keepdims=True)

    def normalize(self, word: str) -> str:
        return word.strip().lower()

    def __contains__(self, word: str) -> bool:
        return word in self.index

    def vec(self, word: str) -> np.ndarray:
        return self.vecs[self.index[word]]

    def is_valid_french(self, word: str) -> bool:
        return word in self.index


class TestHintsService(unittest.TestCase):
    def setUp(self):
        db.init_db()
        db.execute("DELETE FROM daily_puzzle_hints;")
        db.execute("DELETE FROM daily_puzzles;")
        self.store = MockVocabStore()

    def test_generate_hints_empty_or_unknown(self):
        self.assertEqual(generate_hints_for_word("", self.store), [])
        self.assertEqual(generate_hints_for_word("inconnu12345", self.store), [])

    def test_generate_hints_structure(self):
        hints = generate_hints_for_word("secret", self.store, tier_targets=[("800", 820), ("900", 900)])
        self.assertTrue(len(hints) > 0)
        for h in hints:
            self.assertIn(h["tier"], ["800", "900"])
            self.assertNotEqual(h["word"], "secret")
            self.assertFalse(h["is_revealed"])
            self.assertIsInstance(h["score"], float)

    def test_backfill_puzzle_hints_idempotency(self):
        # 1. Enregistrement d'un puzzle sans indices
        entry = {
            "date": "2026-11-01",
            "puzzle": 1800,
            "word": "secret",
            "tries": 10,
            "attempts": 10,
            "source": "rag",
        }
        self.assertTrue(save_daily_puzzle(entry))

        # 2. Premier passage du backfill -> 1 puzzle traité
        count1 = backfill_puzzle_hints(self.store)
        self.assertEqual(count1, 1)

        hints = get_daily_hints("2026-11-01", revealed_only=False)
        self.assertTrue(len(hints) > 0)

        # 3. Deuxième passage du backfill (idempotence) -> 0 puzzle traité
        count2 = backfill_puzzle_hints(self.store)
        self.assertEqual(count2, 0)

        # Les indices existants sont inchangés
        hints_after = get_daily_hints("2026-11-01", revealed_only=False)
        self.assertEqual(len(hints), len(hints_after))


if __name__ == "__main__":
    unittest.main()
