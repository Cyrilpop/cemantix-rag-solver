"""Socle de tests de la couche d'accès aux données.

Lancement :  python -m unittest discover -s tests -v
Aucune dépendance extérieure : les tests utilisent le repli SQLite en mémoire,
ils tournent donc aussi bien hors conteneur qu'en CI.
"""
import threading
import unittest

import _context  # noqa: F401  — force le repli SQLite avant tout import de src

from src.db import connection  # noqa: E402
from src.db.connection import DatabaseManager  # noqa: E402

INSERT_PUZZLE = (
    "INSERT INTO daily_puzzles (date, puzzle_id, secret_word, tries_count,"
    " attempts_count, top_guesses, trajectory) VALUES (%s, %s, %s, %s, %s, %s, %s)"
)


class BaseDonneesTestCase(unittest.TestCase):
    """Base commune : un gestionnaire neuf et isolé par test."""

    def setUp(self):
        self.db = DatabaseManager()
        self.db.init_db()
        # La base est partagée par la suite : on repart toujours de zéro.
        self.db.execute("DELETE FROM daily_puzzles;")

    def tearDown(self):
        self.db.reset()


class TestPoolDeConnexions(BaseDonneesTestCase):
    """PERF-06 : le nombre de connexions ne doit pas croître avec les requêtes."""

    def test_reutilise_une_connexion_par_thread(self):
        """Un thread qui fait plusieurs appels n'ouvre qu'une connexion."""
        for _ in range(10):
            self.db.fetch_one("SELECT 1 AS x")
        self.assertEqual(self.db.pool_stats()["opened_total"], 1)

    def test_connexions_des_threads_morts_sont_recuperees(self):
        """Une connexion dont l'emprunteur est mort retourne au pool."""

        def emprunter_et_mourir():
            self.db.get_connection()  # emprunt conserve, jamais rendu

        # init_db() a pu retenir une connexion pour ce thread : on repart de zero.
        self.db.release_connection()
        self.assertEqual(self.db.pool_stats()["in_use"], 0)

        thread = threading.Thread(target=emprunter_et_mourir)
        thread.start()
        thread.join()

        self.assertEqual(self.db.pool_stats()["in_use"], 1)
        self.db.fetch_one("SELECT 1 AS x")  # declenche la recuperation

        stats = self.db.pool_stats()
        self.assertEqual(stats["in_use"], 0)
        self.assertEqual(
            stats["opened_total"],
            1,
            "la connexion du thread mort aurait du etre reutilisee, pas reouverte",
        )

    def test_release_connection_redonne_au_pool(self):
        """Le rendu volontaire est immédiat, sans attendre la mort du thread."""
        self.db.get_connection()
        self.assertEqual(self.db.pool_stats()["in_use"], 1)
        self.db.release_connection()
        stats = self.db.pool_stats()
        self.assertEqual(stats["in_use"], 0)
        self.assertEqual(stats["idle"], 1)

    def test_une_operation_rend_sa_connexion(self):
        """Un appel court ne retient pas la connexion : c'est ce qui évite la file d'attente."""
        self.db.fetch_one("SELECT 1 AS x")
        stats = self.db.pool_stats()
        self.assertEqual(stats["in_use"], 0)
        self.assertEqual(stats["idle"], 1)

    def test_erreur_explicite_quand_le_pool_est_sature(self):
        """Pool plein et emprunteur vivant : une erreur claire, pas une saturation."""
        original_max, original_timeout = (
            connection.DB_POOL_MAX,
            connection.DB_POOL_TIMEOUT,
        )
        connection.DB_POOL_MAX, connection.DB_POOL_TIMEOUT = 1, 0.3
        try:
            # init_db() a emprunte une connexion pour ce thread : sans la rendre,
            # c'est lui qui sature le pool et le test ne prouverait plus rien.
            self.db.release_connection()
            relache = threading.Event()
            occupe = threading.Event()

            def retenteur():
                # Emprunt conserve volontairement : l'emprunteur reste vivant, donc
                # la récupération des threads morts ne peut pas masquer la saturation.
                self.db.get_connection()
                occupe.set()
                relache.wait(10)

            thread = threading.Thread(target=retenteur)
            thread.start()
            self.assertTrue(occupe.wait(5), "le thread n'a pas emprunte la connexion")
            try:
                self.assertRaises(RuntimeError, self.db.fetch_one, "SELECT 1 AS x")
            finally:
                relache.set()
                thread.join(timeout=10)
        finally:
            connection.DB_POOL_MAX, connection.DB_POOL_TIMEOUT = original_max, original_timeout

    def test_le_plafond_n_est_pas_depasse(self):
        """250 threads courts ne doivent pas ouvrir 250 connexions."""
        erreurs = []

        def travail():
            try:
                self.db.fetch_one("SELECT 1 AS x")
            except Exception as exc:  # noqa: BLE001
                erreurs.append(exc)

        for _ in range(5):
            threads = [threading.Thread(target=travail) for _ in range(50)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(erreurs, [], f"erreurs remontees : {erreurs[:3]}")
        self.assertLessEqual(
            self.db.pool_stats()["opened_total"], connection.DB_POOL_MAX
        )


class TestRequetes(BaseDonneesTestCase):
    """Non-régression : le pool ne doit rien casser aux opérations SQL."""

    def test_insertion_et_lecture(self):
        self.db.execute(
            INSERT_PUZZLE,
            ("2026-01-01", 42, "maison", 5, 7, [{"word": "clef"}], [{"step": 1}]),
        )
        row = self.db.fetch_one(
            "SELECT * FROM daily_puzzles WHERE date = %s", ("2026-01-01",)
        )
        self.assertEqual(row["secret_word"], "maison")
        self.assertEqual(row["puzzle_id"], 42)
        self.assertEqual(row["top_guesses"], [{"word": "clef"}])  # JSON redecode

    def test_lecture_depuis_un_autre_thread(self):
        self.db.execute(
            INSERT_PUZZLE, ("2026-01-02", 43, "foret", 3, 3, [], [])
        )
        resultat = {}

        def lire():
            resultat.update(
                self.db.fetch_one(
                    "SELECT secret_word FROM daily_puzzles WHERE date = %s",
                    ("2026-01-02",),
                )
            )

        thread = threading.Thread(target=lire)
        thread.start()
        thread.join(timeout=10)
        self.assertEqual(resultat.get("secret_word"), "foret")

    def test_rollback_en_cas_dechec(self):
        """Un échec ne laisse ni ligne fantôme, ni connexion dans un état douteux."""
        with self.assertRaises(ValueError):
            with self.db.transaction() as conn:
                conn.execute(
                    "INSERT INTO daily_puzzles (date, puzzle_id, secret_word,"
                    " tries_count, attempts_count, top_guesses, trajectory)"
                    " VALUES ('2026-01-03', 44, 'echec', 1, 1, '[]', '[]')"
                )
                raise ValueError("erreur forcee")
        row = self.db.fetch_one(
            "SELECT secret_word FROM daily_puzzles WHERE date = %s", ("2026-01-03",)
        )
        self.assertIsNone(row)

    def test_une_operation_ne_ferme_pas_la_connexion(self):
        """Le rendu au pool ne doit jamais fermer une connexion réutilisable."""
        for _ in range(3):
            self.db.fetch_all("SELECT * FROM daily_puzzles")
        self.assertEqual(self.db.pool_stats()["opened_total"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
