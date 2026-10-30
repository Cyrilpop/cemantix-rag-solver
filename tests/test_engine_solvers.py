"""Tests déterministes de non-régression pour le Solveur Cémantix (Phase A).

Vérifie de manière strictement reproductible :
- La table météo officielle (weather_for_score)
- Les propriétés mathématiques de la régression Ridge (estimate_secret)
- L'algorithme de reranking multicritère (rerank)
- Le fonctionnement autonome du solveur (Solver / CemantixSolver) en mode RAG pur
- L'agent de duel IA (RagDuelPlayer)
- Zéro appel réseau, zéro inférence LLM, zéro dépendance binaire externe.
"""
import sys
from pathlib import Path
_tests_dir = str(Path(__file__).resolve().parent)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)
import _context  # noqa: F401
import unittest
import numpy as np
from types import SimpleNamespace

from src.engine.solvers import (
    weather_for_score,
    estimate_secret,
    rerank,
    Solver,
    CemantixSolver,
    RagDuelPlayer,
)
from src.engine.clients import MockClient


class SyntheticVocabStore:
    """Doublure légère et déterministe en mémoire pour VocabStore.

    Fournit un ensemble fini de lemmes avec vecteurs de dimension D connue,
    sans nécessiter le modèle de 500 Mo frWac ni ChromaDB.
    """
    def __init__(self, words_vecs: dict[str, np.ndarray]):
        self.words = list(words_vecs.keys())
        self.index = {w: i for i, w in enumerate(self.words)}
        raw_vecs = np.array([words_vecs[w] for w in self.words], dtype=np.float32)
        # Normalisation unitaire stricte (cosinus = produit scalaire)
        norms = np.linalg.norm(raw_vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.vecs = raw_vecs / norms
        self.valid_lemmas = set(self.words)
        self.accent_map = {}
        self.clean_french_words = list(self.words)
        self.col = None  # Mode NumPy pur

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
        # Normalise la requête si nécessaire
        q_norm = np.linalg.norm(query)
        q = query / q_norm if q_norm > 0 else query
        sims = self.vecs @ q
        k_val = min(k, len(self.words))
        top_idx = np.argpartition(sims, -k_val)[-k_val:]
        top_sorted = top_idx[np.argsort(sims[top_idx])[::-1]]
        return [self.words[i] for i in top_sorted]


class TestWeatherForScore(unittest.TestCase):
    """Contrôle de conformité de l'échelle météo officielle Cémantix."""

    def test_p1000_is_win(self):
        icon, label = weather_for_score(1.0, 1000)
        self.assertEqual(icon, "🥳")
        self.assertEqual(label, "GAGNÉ")

    def test_permille_thresholds(self):
        # Permille >= 999
        icon, label = weather_for_score(0.65, 999)
        self.assertEqual(icon, "😱")
        self.assertEqual(label, "BRÛL.")

        # Permille 990-998
        icon, label = weather_for_score(0.55, 990)
        self.assertEqual(icon, "🔥")
        self.assertEqual(label, "CHAUD")

        # Permille 900-989
        icon, label = weather_for_score(0.40, 900)
        self.assertEqual(icon, "🥵")
        self.assertEqual(label, "CHAUD")

        # Permille 1-899
        icon, label = weather_for_score(0.25, 1)
        self.assertEqual(icon, "😎")
        self.assertEqual(label, "TIÈDE")

    def test_similarity_score_thresholds_without_permille(self):
        # s >= 0.15 sans permille
        icon, label = weather_for_score(0.18, None)
        self.assertEqual(icon, "🥶")
        self.assertEqual(label, "FRAIS")

        # 0.0 <= s < 0.15 sans permille
        icon, label = weather_for_score(0.05, None)
        self.assertEqual(icon, "🥶")
        self.assertEqual(label, "FROID")

        # s < 0.0 sans permille
        icon, label = weather_for_score(-0.02, None)
        self.assertEqual(icon, "🧊")
        self.assertEqual(label, "GLAC.")


class TestEstimateSecretMath(unittest.TestCase):
    """Validation mathématique de la régression Ridge : estimate_secret."""

    def test_output_is_normalized_unit_vector(self):
        rng = np.random.default_rng(42)
        dim = 20
        n_guesses = 5
        G = rng.standard_normal((n_guesses, dim))
        G /= np.linalg.norm(G, axis=1, keepdims=True)
        s = rng.uniform(-0.1, 0.8, n_guesses)

        q_est = estimate_secret(G, s, lam=0.1)
        self.assertEqual(q_est.shape, (dim,))
        self.assertAlmostEqual(float(np.linalg.norm(q_est)), 1.0, places=6)

    def test_exact_recovery_noiseless_direction(self):
        """Si les scores sont générés exactement par une direction q*,
        estimate_secret avec faible pénalité Ridge doit s'aligner sur q*."""
        dim = 15
        n_guesses = 30
        rng = np.random.default_rng(1234)

        # Direction secrète cible
        q_star = rng.standard_normal(dim)
        q_star /= np.linalg.norm(q_star)

        # Matrice d'essais variés
        G = rng.standard_normal((n_guesses, dim))
        G /= np.linalg.norm(G, axis=1, keepdims=True)

        # Scores cosinus réels parfaits
        s = G @ q_star

        # Estimation Ridge avec faible régularisation (presque OLS)
        q_est = estimate_secret(G, s, lam=1e-5)

        alignment = float(q_est @ q_star)
        self.assertGreater(alignment, 0.999, f"Alignement insuffisant : {alignment}")

    def test_numerical_stability_with_collinear_or_rank_deficient_matrix(self):
        """Vérifie la robustesse numérique face à des lignes dupliquées ou colinéaires."""
        dim = 10
        # Deux lignes strictement identiques
        v = np.array([1.0] + [0.0] * (dim - 1), dtype=np.float64)
        G = np.vstack([v, v, v])
        s = np.array([0.5, 0.5, 0.5], dtype=np.float64)

        # Ne doit pas lever de SingularMatrixError grâce au terme lam * I
        q_est = estimate_secret(G, s, lam=0.1)
        self.assertFalse(np.isnan(q_est).any())
        self.assertAlmostEqual(float(np.linalg.norm(q_est)), 1.0, places=6)


class TestRerankAlgorithm(unittest.TestCase):
    """Validation de l'algorithme de reranking multicritère."""

    def setUp(self):
        # Création d'un espace vectoriel de test 3D simple
        self.words_vecs = {
            "soleil": np.array([1.0, 0.0, 0.0]),
            "chaleur": np.array([0.9, 0.1, 0.0]),
            "lumiere": np.array([0.8, 0.2, 0.0]),
            "glace": np.array([-0.9, 0.0, 0.1]),
            "neige": np.array([-0.8, -0.1, 0.1]),
        }
        self.store = SyntheticVocabStore(self.words_vecs)

    def test_empty_candidates_returns_empty_list(self):
        G = np.array([[1.0, 0.0, 0.0]])
        s = np.array([0.5])
        q_est = np.array([1.0, 0.0, 0.0])
        res = rerank(self.store, [], G, s, q_est)
        self.assertEqual(res, [])

    def test_rerank_orders_candidates_by_composite_score(self):
        # Essai déjà joué : "soleil" avec score élevé 0.9
        G = np.array([self.store.vec("soleil")])
        s = np.array([0.9])
        q_est = self.store.vec("soleil")

        candidates = ["chaleur", "glace", "lumiere"]
        reranked = rerank(self.store, candidates, G, s, q_est)

        self.assertEqual(len(reranked), 3)
        # Chaque élément est un tuple (mot, temp_est, err)
        for cand, temp, err in reranked:
            self.assertIsInstance(cand, str)
            self.assertIsInstance(temp, float)
            self.assertIsInstance(err, float)

        # "lumiere" et "chaleur" doivent être bien mieux classés que "glace"
        top_words = [r[0] for r in reranked]
        self.assertIn(top_words[0], ("chaleur", "lumiere"))
        self.assertIn(top_words[1], ("chaleur", "lumiere"))
        self.assertEqual(top_words[-1], "glace")


class TestSolverAutonomous(unittest.TestCase):
    """Validation du solveur en mode simulation déterministe (rag_only=True)."""

    def setUp(self):
        # Dictionnaire synthétique avec lemmes de base et graines
        rng = np.random.default_rng(999)
        dim = 8
        words = [
            "science", "musique", "histoire", "philosophie",
            "soleil", "lumiere", "rayon", "etoile", "planete", "espace",
            "pomme", "poire", "arbre", "fruit"
        ]
        words_vecs = {w: rng.standard_normal(dim) for w in words}
        # Force "soleil" et "rayon" à être proches
        words_vecs["rayon"] = words_vecs["soleil"] * 0.95 + rng.standard_normal(dim) * 0.05
        words_vecs["lumiere"] = words_vecs["soleil"] * 0.90 + rng.standard_normal(dim) * 0.10

        self.store = SyntheticVocabStore(words_vecs)
        self.secret = "soleil"
        self.mock_game = MockClient(self.store, secret=self.secret)

    def test_solver_play_word_and_trajectory(self):
        args = SimpleNamespace(
            mock=True,
            secret=self.secret,
            delay=0.0,
            verbose=False,
            rag_only=True,
            max_tries=20,
            rag_words=3,
        )
        solver = Solver(args=args, store=self.store, game=self.mock_game)
        self.assertEqual(len(solver.guesses), 0)
        self.assertEqual(len(solver.tried), 0)

        # Joue un premier mot
        is_win = solver.play_word("pomme", "seed")
        self.assertFalse(is_win)
        self.assertEqual(len(solver.guesses), 1)
        self.assertIn("pomme", solver.tried)
        self.assertEqual(len(solver.trajectory), 1)

        # Jouer le même mot doit être ignoré
        is_dup = solver.play_word("pomme", "seed")
        self.assertFalse(is_dup)
        self.assertEqual(len(solver.guesses), 1)

        # Jouer le mot secret doit renvoyer True (victoire)
        is_win_secret = solver.play_word("soleil", "rag")
        self.assertTrue(is_win_secret)
        self.assertEqual(solver.win_source, "rag")

    def test_solver_ranked_order(self):
        args = SimpleNamespace(
            mock=True, secret=self.secret, delay=0.0, verbose=False,
            rag_only=True, max_tries=10, rag_words=3
        )
        solver = Solver(args=args, store=self.store, game=self.mock_game)
        solver.play_word("pomme", "seed")
        solver.play_word("lumiere", "seed")

        ranked = solver.ranked()
        self.assertEqual(len(ranked), 2)
        # "lumiere" est beaucoup plus proche de "soleil" que "pomme"
        self.assertEqual(ranked[0][0], "lumiere")
        self.assertGreater(ranked[0][1], ranked[1][1])

    def test_solver_win_dictionary_structure(self):
        args = SimpleNamespace(
            mock=True, secret=self.secret, delay=0.0, verbose=False,
            rag_only=True, max_tries=10, rag_words=3
        )
        solver = Solver(args=args, store=self.store, game=self.mock_game)
        solver.play_word("soleil", "rag")
        res = solver.win("soleil", elapsed=1.23)

        self.assertTrue(res["win"])
        self.assertEqual(res["word"], "soleil")
        self.assertEqual(res["source"], "rag")
        self.assertEqual(res["tries"], 1)
        self.assertEqual(res["attempts"], 1)
        self.assertEqual(res["time"], 1.23)
        self.assertIsInstance(res["top_guesses"], list)
        self.assertIsInstance(res["trajectory"], list)

    def test_cemantix_solver_alias(self):
        self.assertIs(CemantixSolver, Solver)

    def test_solver_retrieve_method(self):
        args = SimpleNamespace(
            mock=True, secret=self.secret, delay=0.0, verbose=False,
            rag_only=True, max_tries=10, rag_words=3, retrieve=5
        )
        solver = Solver(args=args, store=self.store, game=self.mock_game)
        solver.play_word("pomme", "seed")
        solver.play_word("rayon", "seed")

        cands = solver.retrieve(solver.ranked(), verbose=False)
        self.assertIsInstance(cands, list)
        self.assertGreater(len(cands), 0)
        top_cand, top_temp, top_err = cands[0]
        self.assertIn(top_cand, self.store)
        self.assertIsInstance(top_temp, float)
        self.assertIsInstance(top_err, float)

    def test_solver_full_run_rag_only_solves_puzzle(self):
        """Simulation déterministe complète d'une résolution autonome sans LLM."""
        args = SimpleNamespace(
            mock=True, secret="soleil", delay=0.0, verbose=False,
            rag_only=True, max_tries=15, rag_words=3, retrieve=5,
            seeds=None, seeds_file=None, static_seeds=False, seed_count=3
        )
        solver = Solver(args=args, store=self.store, game=self.mock_game)
        # On force les graines initiales
        res = solver.run(forced_seeds=["pomme", "arbre"])

        self.assertTrue(res["win"], "Le solveur en mode RAG pur doit converger vers le secret.")
        self.assertEqual(res["word"], "soleil")
        self.assertIn(res["source"], ("seed", "rag"))
        self.assertLessEqual(res["tries"], 15)

    def test_solver_run_exceeds_max_tries_returns_failure(self):
        """Cas où le solveur s'arrête si max_tries est atteint."""
        args = SimpleNamespace(
            mock=True, secret="soleil", delay=0.0, verbose=False,
            rag_only=True, max_tries=1, rag_words=1, retrieve=5,
            seeds=None, seeds_file=None, static_seeds=False, seed_count=1
        )
        solver = Solver(args=args, store=self.store, game=self.mock_game)
        res = solver.run(forced_seeds=["pomme"])

        self.assertFalse(res["win"])
        self.assertEqual(res["word"], "soleil")
        self.assertEqual(res["tries"], 1)

    def test_generate_optimal_seeds_fps(self):
        args = SimpleNamespace(
            mock=True, secret="soleil", delay=0.0, verbose=False,
            rag_only=True, max_tries=10, rag_words=3, retrieve=5,
            seeds=None, seeds_file=None, static_seeds=False, seed_count=3
        )
        solver = Solver(args=args, store=self.store, game=self.mock_game)
        seeds = solver.generate_optimal_seeds(count=3, randomize_anchor=False)
        self.assertIsInstance(seeds, list)
        self.assertGreater(len(seeds), 0)
        for s in seeds:
            self.assertIn(s, self.store)

    def test_get_seeds_precedence(self):
        args = SimpleNamespace(
            mock=True, secret="soleil", delay=0.0, verbose=False,
            rag_only=True, max_tries=10, rag_words=3, retrieve=5,
            seeds="pomme,poire", seeds_file=None, static_seeds=False, seed_count=2
        )
        solver = Solver(args=args, store=self.store, game=self.mock_game)
        # 1. forced_seeds est prioritaire
        self.assertEqual(solver.get_seeds(forced_seeds=["arbre"]), ["arbre"])
        # 2. args.seeds est utilisé si non forcé
        self.assertEqual(solver.get_seeds(), ["pomme", "poire"])


class TestRagDuelPlayer(unittest.TestCase):
    """Validation du joueur IA de duel tour par tour."""

    def setUp(self):
        rng = np.random.default_rng(777)
        dim = 8
        words = [
            "science", "musique", "histoire", "philosophie",
            "soleil", "lumiere", "rayon", "etoile", "planete", "espace",
            "pomme", "poire", "arbre", "fruit"
        ]
        words_vecs = {w: rng.standard_normal(dim) for w in words}
        self.store = SyntheticVocabStore(words_vecs)
        self.mock_game = MockClient(self.store, secret="soleil")

    def test_initialization_with_different_difficulties(self):
        player_facile = RagDuelPlayer(self.store, self.mock_game, difficulty="facile")
        self.assertEqual(player_facile.difficulty, "facile")
        self.assertEqual(player_facile.min_seeds, 6)

        player_expert = RagDuelPlayer(self.store, self.mock_game, difficulty="expert")
        self.assertEqual(player_expert.difficulty, "expert")
        self.assertEqual(player_expert.min_seeds, 2)

        player_unknown = RagDuelPlayer(self.store, self.mock_game, difficulty="inconnu")
        self.assertEqual(player_unknown.difficulty, "moyen")
        self.assertEqual(player_unknown.min_seeds, 4)

    def test_play_turn_uses_seed_then_ridge(self):
        player = RagDuelPlayer(self.store, self.mock_game, difficulty="expert")
        # Injection de graines connues dans le mock player
        player.seeds = ["musique", "histoire", "science"]

        # Tour 1 : doit jouer une graine
        turn1 = player.play_turn(1)
        self.assertIsNotNone(turn1)
        word, score, permille, icon, label = turn1
        self.assertIn(word, self.store)
        self.assertIn(word, player.tried)
        self.assertIsInstance(score, float)
        self.assertIsInstance(icon, str)
        self.assertIsInstance(label, str)


if __name__ == "__main__":
    unittest.main()
