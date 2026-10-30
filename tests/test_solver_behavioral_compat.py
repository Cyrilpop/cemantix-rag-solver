"""Tests de durcissement de la compatibilité comportementale pour le Solveur (M2.1).

Vérifie l'impact réel et indirect du monkeypatching de :
- `solvers.estimate_secret`
- `solvers.rerank`
- `solvers.ask_llm`
- `solvers.weather_for_score`
sur l'exécution de `Solver` et `RagDuelPlayer`.

Valide également la stricte équivalence déterministe des trajectoires de jeu
entre les versions M1 et M2 sous fixtures synthétiques contrôlées.
"""
import sys
from pathlib import Path
_tests_dir = str(Path(__file__).resolve().parent)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)
import _context  # noqa: F401
import unittest
from unittest import mock
from types import SimpleNamespace
import numpy as np

import src.engine.solvers as solvers
import src.engine.ranking as ranking
from src.engine.clients import MockClient


class SyntheticVocabStore:
    def __init__(self, words_vecs: dict[str, np.ndarray]):
        self.words = list(words_vecs.keys())
        self.index = {w: i for i, w in enumerate(self.words)}
        raw_vecs = np.array([words_vecs[w] for w in self.words], dtype=np.float32)
        norms = np.linalg.norm(raw_vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.vecs = raw_vecs / norms
        self.valid_lemmas = set(self.words)
        self.accent_map = {}
        self.clean_french_words = list(self.words)
        self.col = None

    def normalize(self, word: str) -> str:
        return word.strip().lower()

    def is_valid_french(self, word: str) -> bool:
        return word.strip().lower() in self.index

    def has_word(self, word: str) -> bool:
        return word.strip().lower() in self.index

    def __contains__(self, word: str) -> bool:
        return word.strip().lower() in self.index

    def vec(self, word: str) -> np.ndarray:
        return self.vecs[self.index[word.strip().lower()]]

    def knn(self, query: np.ndarray, k: int) -> list[str]:
        q_norm = np.linalg.norm(query)
        q = query / q_norm if q_norm > 0 else query
        sims = self.vecs @ q
        k_val = min(k, len(self.words))
        top_idx = np.argpartition(sims, -k_val)[-k_val:]
        top_sorted = top_idx[np.argsort(sims[top_idx])[::-1]]
        return [self.words[i] for i in top_sorted]


def _build_test_store():
    rng = np.random.default_rng(42)
    dim = 8
    words = [
        "science", "musique", "histoire", "philosophie",
        "soleil", "lumiere", "rayon", "etoile", "planete", "espace",
        "pomme", "poire", "arbre", "fruit"
    ]
    words_vecs = {w: rng.standard_normal(dim) for w in words}
    words_vecs["lumiere"] = words_vecs["soleil"] * 0.95 + rng.standard_normal(dim) * 0.05
    words_vecs["rayon"] = words_vecs["soleil"] * 0.90 + rng.standard_normal(dim) * 0.10
    return SyntheticVocabStore(words_vecs)


class TestSolverBehavioralPatching(unittest.TestCase):
    """Vérifie que patcher solvers.* affecte bien l'exécution interne de Solver."""

    def setUp(self):
        self.store = _build_test_store()
        self.mock_game = MockClient(self.store, secret="soleil")

    def test_patch_estimate_secret_affects_solver_retrieve(self):
        args = SimpleNamespace(
            mock=True, secret="soleil", delay=0.0, verbose=False,
            rag_only=True, max_tries=10, rag_words=3, retrieve=5
        )
        solver = solvers.Solver(args=args, store=self.store, game=self.mock_game)
        solver.play_word("pomme", "seed")
        solver.play_word("arbre", "seed")

        sentinel_vector = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        with mock.patch("src.engine.solvers.estimate_secret", return_value=sentinel_vector) as mock_est:
            solver.retrieve(solver.ranked(), verbose=False)
            mock_est.assert_called_once()

    def test_patch_rerank_affects_solver_retrieve(self):
        args = SimpleNamespace(
            mock=True, secret="soleil", delay=0.0, verbose=False,
            rag_only=True, max_tries=10, rag_words=3, retrieve=5
        )
        solver = solvers.Solver(args=args, store=self.store, game=self.mock_game)
        solver.play_word("pomme", "seed")
        solver.play_word("arbre", "seed")

        sentinel_result = [("etoile", 95.0, 0.001)]
        with mock.patch("src.engine.solvers.rerank", return_value=sentinel_result) as mock_rr:
            result = solver.retrieve(solver.ranked(), verbose=False)
            mock_rr.assert_called_once()
            self.assertEqual(result, sentinel_result)

    def test_patch_ask_llm_affects_solver_run(self):
        args = SimpleNamespace(
            mock=True, secret="soleil", delay=0.0, verbose=False,
            rag_only=False, max_tries=5, rag_words=1, llm_words=2, retrieve=5,
            seeds=None, seeds_file=None, static_seeds=False, seed_count=2
        )
        solver = solvers.Solver(args=args, store=self.store, game=self.mock_game)

        with mock.patch("src.engine.solvers.ask_llm", return_value=["soleil"]) as mock_llm:
            res = solver.run(forced_seeds=["pomme", "arbre"])
            mock_llm.assert_called()
            self.assertTrue(res["win"])
            self.assertEqual(res["word"], "soleil")
            self.assertEqual(res["source"], "llm")


class TestRagDuelPlayerBehavioralPatching(unittest.TestCase):
    """Vérifie que patcher solvers.* affecte également l'exécution de RagDuelPlayer."""

    def setUp(self):
        self.store = _build_test_store()
        self.mock_game = MockClient(self.store, secret="soleil")

    def test_patch_solvers_estimate_secret_on_rag_duel_player(self):
        player = solvers.RagDuelPlayer(self.store, self.mock_game, difficulty="expert")
        player.seeds = ["musique", "histoire"]
        player.guesses["musique"] = (0.05, 5, 1, "😎", "TIÈDE")
        player.guesses["histoire"] = (0.08, 8, 2, "😎", "TIÈDE")
        player.seed_idx = 2

        sentinel_vector = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        with mock.patch("src.engine.solvers.estimate_secret", return_value=sentinel_vector) as mock_est:
            player.play_turn(3)
            self.assertTrue(mock_est.called)

    def test_patch_solvers_rerank_on_rag_duel_player(self):
        player = solvers.RagDuelPlayer(self.store, self.mock_game, difficulty="expert")
        player.seeds = ["musique", "histoire"]
        player.guesses["musique"] = (0.05, 5, 1, "😎", "TIÈDE")
        player.guesses["histoire"] = (0.08, 8, 2, "😎", "TIÈDE")
        player.seed_idx = 2

        sentinel_rerank = [("soleil", 99.0, 0.0001)]
        with mock.patch("src.engine.solvers.rerank", return_value=sentinel_rerank) as mock_rr:
            word, score, perm, icon, label = player.play_turn(3)
            self.assertTrue(mock_rr.called)
            self.assertEqual(word, "soleil")

    def test_patch_solvers_weather_for_score_on_rag_duel_player(self):
        player = solvers.RagDuelPlayer(self.store, self.mock_game, difficulty="expert")
        player.seeds = ["musique"]

        with mock.patch("src.engine.solvers.weather_for_score", return_value=("🛸", "COSMIC")) as mock_w:
            word, score, perm, icon, label = player.play_turn(1)
            self.assertTrue(mock_w.called)
            self.assertEqual(icon, "🛸")
            self.assertEqual(label, "COSMIC")


class TestDeterministicEquivalenceM1M2(unittest.TestCase):
    """Validation de la stricte équivalence numérique et algorithmique entre M1 et M2."""

    def test_solver_deterministic_trajectory_exact_match(self):
        """La trajectoire de résolution RAG pure doit être 100% reproductible."""
        store = _build_test_store()
        mock_game = MockClient(store, secret="soleil")
        args = SimpleNamespace(
            mock=True, secret="soleil", delay=0.0, verbose=False,
            rag_only=True, max_tries=10, rag_words=3, retrieve=5,
            seeds=None, seeds_file=None, static_seeds=False, seed_count=2
        )
        solver = solvers.Solver(args=args, store=store, game=mock_game)
        res = solver.run(forced_seeds=["pomme", "arbre"])

        self.assertTrue(res["win"])
        self.assertEqual(res["word"], "soleil")
        self.assertEqual(res["tries"], 4)
        trajectory_words = [t["word"] for t in res["trajectory"]]
        self.assertEqual(trajectory_words, ["pomme", "arbre", "philosophie", "soleil"])

    def test_ridge_and_rerank_pure_functions_numerical_identity(self):
        """Les calculs de ranking.py et solvers.* produisent des résultats binaires identiques."""
        store = _build_test_store()
        G = np.array([store.vec("pomme"), store.vec("arbre")])
        s = np.array([0.1, 0.2], dtype=np.float32)

        q1 = solvers.estimate_secret(G, s, lam=0.1)
        q2 = ranking.estimate_secret(G, s, lam=0.1)
        np.testing.assert_array_equal(q1, q2)

        cands = ["soleil", "lumiere", "rayon"]
        rr1 = solvers.rerank(store, cands, G, s, q1)
        rr2 = ranking.rerank(store, cands, G, s, q2)
        self.assertEqual(rr1, rr2)


if __name__ == "__main__":
    unittest.main()
