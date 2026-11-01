#!/usr/bin/env python3
"""
Cémantix Solver — Script de Rattrapage des Indices Quotidiens (M6)
==================================================================
Parcourt tous les puzzles de la table daily_puzzles et calcule les indices
par palier thermique (800, 900, 950, 990) via le RAG vectoriel local.
Le traitement est strictement idempotent : tout puzzle possédant déjà des
indices dans daily_puzzle_hints est ignoré.

Usage :
  python scripts/backfill_daily_hints.py
"""
import sys
from pathlib import Path

# Ajout de la racine du projet au PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.hints import backfill_puzzle_hints


def main():
    count = backfill_puzzle_hints()
    print(f"Rattrapage terminé : {count} puzzle(s) mis à jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

