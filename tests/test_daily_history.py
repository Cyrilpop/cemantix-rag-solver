"""Tests de la lecture de l'historique quotidien (PERF-04, SEC-14).

Lancement :  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

import _context  # noqa: F401  — force le repli SQLite avant tout import de src

from src.db import daily  # noqa: E402
from src.db.connection import db  # noqa: E402

INSERT = (
    "INSERT INTO daily_puzzles (date, puzzle_id, secret_word, tries_count,"
    " attempts_count, top_guesses, trajectory) VALUES (%s, %s, %s, %s, %s, %s, %s)"
)


class TestHistoriqueBorne(unittest.TestCase):
    def setUp(self):
        """Chaque test repart d'une table vide : l'ordre d'exécution n'a pas d'effet."""
        db.init_db()
        db.execute("DELETE FROM daily_puzzles;")
        for jour in range(1, 8):
            db.execute(
                INSERT,
                (
                    f"2026-01-{jour:02d}",
                    100 + jour,
                    f"mot{jour}",
                    jour,
                    jour,
                    [],
                    [{"step": 1}],
                ),
            )

    def test_limit_borne_le_nombre_de_lignes(self):
        lignes = daily.get_all_daily_puzzles(limit=3)
        self.assertEqual(len(lignes), 3)

    def test_le_tri_garde_les_plus_recents(self):
        lignes = daily.get_all_daily_puzzles(limit=2)
        self.assertEqual([l["date"] for l in lignes], ["2026-01-07", "2026-01-06"])

    def test_zero_charge_tout(self):
        self.assertEqual(len(daily.get_all_daily_puzzles(limit=0)), 7)

    def test_valeur_par_defaut_utilise_la_constante(self):
        # 7 lignes en base, borne par défaut bien supérieure : tout revient.
        self.assertGreater(daily.HISTORY_DEFAULT_LIMIT, 7)
        self.assertEqual(len(daily.get_all_daily_puzzles()), 7)

    def test_la_limite_n_est_pas_concatenee_dans_le_sql(self):
        """Le LIMIT est lié : une valeur invalide est rejetee, pas injectee."""
        with self.assertRaises(Exception):
            daily.get_all_daily_puzzles(limit="3; DROP TABLE daily_puzzles;")
        # La table est toujours la.
        self.assertEqual(len(daily.get_all_daily_puzzles(limit=0)), 7)

    def test_la_trajectory_revient_decodee(self):
        lignes = daily.get_all_daily_puzzles(limit=1)
        self.assertEqual(lignes[0]["trajectory"], [{"step": 1}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
