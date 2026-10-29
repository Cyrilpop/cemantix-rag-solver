"""Tests du battement du démon (QUAL-10 et QUAL-14).

Lancement :  python -m unittest discover -s tests -v
"""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.services import daemon  # noqa: E402


class TestHeartbeat(unittest.TestCase):
    """Le chemin est patché sur le module, pas via l'environnement.

    `HEARTBEAT_FILE` est résolu à l'import : si un autre module de la suite a
    déjà importé `src` (c'est le cas de test_db_pool), la variable d'environnement
    posée ici arrive trop tard et le test écrirait à l'emplacement réel.
    """

    def setUp(self):
        self.path = Path(tempfile.mkdtemp(prefix="cemantix_hb_")) / "daemon_heartbeat.json"
        self._orig_path = daemon.HEARTBEAT_FILE
        self._orig_interval = daemon.HEARTBEAT_INTERVAL_SECONDS
        daemon.HEARTBEAT_FILE = self.path
        daemon.HEARTBEAT_INTERVAL_SECONDS = 0.05
        daemon.stop_heartbeat_monitor()

    def tearDown(self):
        daemon.stop_heartbeat_monitor()
        daemon.HEARTBEAT_FILE = self._orig_path
        daemon.HEARTBEAT_INTERVAL_SECONDS = self._orig_interval

    def _read(self) -> dict:
        with open(self.path, encoding="utf-8") as handle:
            return json.load(handle)

    def test_update_heartbeat_ecrit_le_fichier(self):
        daemon.update_heartbeat("sleeping", {"next_run": "2026-10-28 00:00"})
        data = self._read()
        self.assertEqual(data["status"], "sleeping")
        self.assertEqual(data["next_run"], "2026-10-28 00:00")
        self.assertEqual(data["pid"], os.getpid())

    def test_le_fichier_ne_termine_jamais_en_tmp(self):
        """L'écriture est atomique : pas de fichier partiel visible."""
        daemon.update_heartbeat("solving")
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_le_monitor_rafrachit_pendant_une_phase_longue(self):
        """QUAL-10 : le battement doit vieillir même si le thread principal bloque.

        Sans ce comportement, une indexation ou un appel LLM de plusieurs minutes
        faisait passer le conteneur `unhealthy` alors qu'il travaillait.
        """
        daemon.update_heartbeat("solving", {"etape": "indexation"})
        daemon.start_heartbeat_monitor()
        premier = self._read()["updated_at"]

        deadline = time.monotonic() + 2.0
        second = self._read()
        while second["updated_at"] <= premier and time.monotonic() < deadline:
            time.sleep(0.05)  # le thread principal ne fait RIEN pendant ce temps
            second = self._read()

        self.assertGreater(second["updated_at"], premier)
        self.assertEqual(second["status"], "solving")
        self.assertEqual(second["etape"], "indexation")

    def test_le_monitor_conserve_le_dernier_etat_demande(self):
        daemon.update_heartbeat("sleeping")
        daemon.start_heartbeat_monitor()
        daemon.update_heartbeat("solving")
        time.sleep(0.2)
        self.assertEqual(self._read()["status"], "solving")

    def test_start_est_idempotent(self):
        daemon.start_heartbeat_monitor()
        premier = daemon._heartbeat_thread
        daemon.start_heartbeat_monitor()
        self.assertIs(premier, daemon._heartbeat_thread)

    def test_stop_arrete_le_rafraichissement(self):
        daemon.update_heartbeat("sleeping")
        daemon.start_heartbeat_monitor()
        daemon.stop_heartbeat_monitor()
        time.sleep(0.2)
        avant = self._read()["updated_at"]
        time.sleep(0.2)
        self.assertEqual(self._read()["updated_at"], avant)

    def test_le_chemin_par_defaut_n_est_pas_dans_tmp(self):
        """QUAL-14 : /tmp est propre a chaque conteneur, le web ne le voit jamais."""
        import inspect

        source = inspect.getsource(daemon)
        self.assertNotIn("tempfile.gettempdir()", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
