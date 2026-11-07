"""Point d'entrée direct pour la suite de tests Cémantix : python -m tests."""
import os
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
RACINE = TESTS_DIR.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import _context  # noqa: F401
from runner import CemantixTestRunner


def main() -> None:
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TESTS_DIR), pattern="test_*.py")
    runner = CemantixTestRunner()
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()

