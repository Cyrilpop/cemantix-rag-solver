#!/usr/bin/env python3
"""
Cémantix Solver — Script de Migration JSON vers PostgreSQL
===========================================================
Charge l'historique complet consigné dans cemantix_data/daily_history.json
directement dans la table relationnelle PostgreSQL daily_puzzles.

Usage :
  python scripts/migrate_json_to_pg.py
  python scripts/migrate_json_to_pg.py /chemin/vers/daily_history.json
"""
import json
import sys
from pathlib import Path

# Ajout de la racine du projet au PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATA_DIR, log
from src.db import init_db, save_daily_puzzle, get_db_type


def migrate_history(json_path: Path = None) -> int:
    """Migre les entrées de l'historique JSON vers PostgreSQL."""
    if json_path is None:
        json_path = DATA_DIR / "daily_history.json"

    if not json_path.exists():
        log(f"⚠️  Fichier historique introuvable : {json_path}")
        return 0

    log(f"📂  Lecture de {json_path}...")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log(f"❌  Erreur lors de la lecture du JSON : {e}")
        return 1

    if not isinstance(data, list):
        log("❌  Format invalide : une liste d'entrées JSON était attendue.")
        return 1

    log(f"🚀  Initialisation du schéma de base ({get_db_type()})...")
    init_db()

    total = len(data)
    success = 0
    errors = 0

    log(f"📦  Migration de {total} puzzles quotidiens vers la base de données...")
    for entry in data:
        try:
            if not isinstance(entry, dict):
                continue
            save_daily_puzzle(entry)
            success += 1
        except Exception as e:
            errors += 1
            log(f"⚠️  Erreur sur l'entrée {entry.get('date', '?')} : {e}")

    log("=" * 60)
    log(f"✓   Migration achevée : {success}/{total} entrées insérées/mises à jour ({errors} erreur(s)).")
    log("=" * 60)
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    filepath = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(migrate_history(filepath))
