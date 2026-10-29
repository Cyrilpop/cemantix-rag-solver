"""Tests de validation de la configuration au démarrage (QUAL-04).

Lancement :  python -m unittest discover -s tests -v
"""
import os
import unittest
from unittest import mock

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src import config  # noqa: E402

CLE = {
    "DB_HOST": "cemantix_db",
    "DB_NAME": "cemantix",
    "DB_USER": "cemantix_user",
    "DB_PASS": "un-mot-de-passe-reel",
}


class TestValidationConfig(unittest.TestCase):
    def test_mode_sqlite_n_est_pas_bloquant(self):
        """Sans DB_HOST, on est en repli SQLite : rien à exiger."""
        avec = dict(CLE)
        avec["DB_HOST"] = ""
        with mock.patch.dict(os.environ, avec, clear=False):
            self.assertEqual(config.validate_runtime_config(), [])

    def test_le_mot_de_passe_exemple_est_refuse(self):
        avec = dict(CLE, DB_PASS=config.DB_PASS_PLACEHOLDER)
        with mock.patch.dict(os.environ, avec, clear=False):
            problemes = config.validate_runtime_config()
        self.assertEqual(len(problemes), 1)
        self.assertIn("valeur d'exemple", problemes[0])

    def test_mot_de_passe_vide_refuse_quand_postgres_configre(self):
        avec = dict(CLE, DB_PASS="")
        with mock.patch.dict(os.environ, avec, clear=False):
            problemes = config.validate_runtime_config()
        self.assertEqual(len(problemes), 1)
        self.assertIn("DB_PASS", problemes[0])

    def test_db_name_et_db_user_sont_requis(self):
        avec = dict(CLE)
        avec.pop("DB_NAME")
        avec["DB_USER"] = ""
        with mock.patch.dict(os.environ, avec, clear=False):
            problemes = config.validate_runtime_config()
        self.assertEqual(len(problemes), 2)

    def test_configuration_complete_acceptee(self):
        with mock.patch.dict(os.environ, CLE, clear=False):
            self.assertEqual(config.validate_runtime_config(), [])

    def test_enforce_leve_systemexit(self):
        avec = dict(CLE, DB_PASS=config.DB_PASS_PLACEHOLDER)
        with mock.patch.dict(os.environ, avec, clear=False):
            with self.assertRaises(SystemExit) as ref:
                config.enforce_runtime_config()
        self.assertIn("Configuration refusée", str(ref.exception))

    def test_enforce_ne_rien_dire_sur_une_config_valide(self):
        with mock.patch.dict(os.environ, CLE, clear=False):
            self.assertIsNone(config.enforce_runtime_config())


if __name__ == "__main__":
    unittest.main(verbosity=2)
