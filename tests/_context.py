"""Contexte partagé par la suite de tests.

À importer **avant** tout module de `src` :

    import _context  # noqa: F401

Pourquoi c'est nécessaire : `src.db.connection` expose un singleton dont le moteur
(PostgreSQL ou SQLite) et le chemin du fichier sont résolus au moment de l'import.
Chaque fichier de test qui posait sa propre variable d'environnement ne pouvait
plus influencer ce singleton déjà créé, et les classes de tests se retrouvaient
à partager la même base — d'où des collisions de clés uniques selon l'ordre
d'exécution.

Ce module fixe donc une fois pour toutes une base SQLite jetable, partagée par
toute la suite. Les tests qui écrivent dans une table nettoient cette table dans
leur `setUp`, pour ne pas dépendre de l'ordre d'exécution.
"""
import os
import sys
import tempfile
from pathlib import Path

# Aucun DB_HOST : on force le repli SQLite, la suite n'a besoin de rien d'autre.
os.environ.pop("DATABASE_URL", None)
for _var in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASS"):
    os.environ.pop(_var, None)

TMP_DIR = Path(tempfile.mkdtemp(prefix="cemantix_tests_"))
os.environ["SQLITE_PATH"] = str(TMP_DIR / "suite.sqlite3")

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))
