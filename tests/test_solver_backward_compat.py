"""Tests de caractérisation et de compatibilité ascendante pour la modularisation du Solveur (M2).

Valide :
- Les ré-exports rétrocompatibles depuis `src.engine.solvers`
- Les ré-exports depuis `src.engine` et `src`
- L'identité stricte des références d'objets (classes et fonctions)
- La possibilité de monkeypatcher les fonctions ré-exportées
- L'absence de cycles d'importation entre les sous-modules de `src.engine`.
"""
import sys
from pathlib import Path
_tests_dir = str(Path(__file__).resolve().parent)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)
import _context  # noqa: F401
import unittest
from unittest import mock
import numpy as np


class TestSolverBackwardCompatibility(unittest.TestCase):
    """Vérifie la préservation intégrale des contrats d'importation historiques."""

    def test_imports_from_src_engine_solvers(self):
        """Tous les symboles historiques doivent être importables depuis src.engine.solvers."""
        import src.engine.solvers as solvers_mod

        expected_symbols = [
            "weather_for_score",
            "estimate_secret",
            "rerank",
            "ask_llm",
            "Solver",
            "CemantixSolver",
            "RagDuelPlayer",
        ]
        for sym in expected_symbols:
            self.assertTrue(
                hasattr(solvers_mod, sym),
                f"Le symbole '{sym}' est absent de src.engine.solvers !"
            )

    def test_imports_from_src_engine_package(self):
        """Tous les symboles doivent être accessibles depuis src.engine."""
        import src.engine as engine_pkg

        expected_symbols = [
            "weather_for_score",
            "estimate_secret",
            "rerank",
            "ask_llm",
            "Solver",
            "CemantixSolver",
            "RagDuelPlayer",
        ]
        for sym in expected_symbols:
            self.assertTrue(
                hasattr(engine_pkg, sym),
                f"Le symbole '{sym}' est absent de src.engine !"
            )

    def test_imports_from_src_root_package(self):
        """Tous les symboles doivent être accessibles depuis la racine src."""
        import src as src_root

        expected_symbols = [
            "weather_for_score",
            "estimate_secret",
            "rerank",
            "ask_llm",
            "Solver",
            "CemantixSolver",
            "RagDuelPlayer",
        ]
        for sym in expected_symbols:
            self.assertTrue(
                hasattr(src_root, sym),
                f"Le symbole '{sym}' est absent de src !"
            )

    def test_monkeypatch_ask_llm_on_solvers_module(self):
        """Vérifie que monkeypatcher ask_llm sur src.engine.solvers intercepte bien l'appel."""
        import src.engine.solvers as solvers_mod

        fake_words = ["test_alpha", "test_beta"]
        with mock.patch.object(solvers_mod, "ask_llm", return_value=fake_words) as mocked_llm:
            res = solvers_mod.ask_llm([], [], [], 2)
            self.assertEqual(res, fake_words)
            mocked_llm.assert_called_once()

    def test_monkeypatch_estimate_secret_on_solvers_module(self):
        """Vérifie que monkeypatcher estimate_secret sur src.engine.solvers est effectif."""
        import src.engine.solvers as solvers_mod

        fake_vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        with mock.patch.object(solvers_mod, "estimate_secret", return_value=fake_vec) as mocked_est:
            res = solvers_mod.estimate_secret(np.eye(3), np.ones(3))
            np.testing.assert_array_equal(res, fake_vec)
            mocked_est.assert_called_once()

    def test_strict_object_identity_between_modules(self):
        """Les objets ré-exportés par solvers doivent être strictement identiques aux modules d'origine."""
        import src.engine.solvers as solvers_mod
        import src.engine.ranking as ranking_mod
        import src.engine.llm as llm_mod
        import src.engine.duel as duel_mod

        self.assertIs(solvers_mod.weather_for_score, ranking_mod.weather_for_score)
        self.assertIs(solvers_mod.estimate_secret, ranking_mod.estimate_secret)
        self.assertIs(solvers_mod.rerank, ranking_mod.rerank)
        self.assertIs(solvers_mod.ask_llm, llm_mod.ask_llm)
        self.assertIs(solvers_mod.RagDuelPlayer, duel_mod.RagDuelPlayer)

    def test_direct_modular_imports_without_circular_dependencies(self):
        """Chaque sous-module doit pouvoir être importé isolément sans cycle."""
        import importlib
        for mod_name in ("src.engine.ranking", "src.engine.llm", "src.engine.duel", "src.engine.solvers"):
            mod = importlib.import_module(mod_name)
            self.assertIsNotNone(mod)


if __name__ == "__main__":
    unittest.main()
