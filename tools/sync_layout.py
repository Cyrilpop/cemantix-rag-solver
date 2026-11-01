"""Outil CLI de synchronisation du layout (Header & Nav-tabs) sur les pages statiques.

Usage :
    python tools/sync_layout.py
"""
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.services.layout_sync import sync_all_pages


def main():
    print("🔄 Synchronisation du layout (Header & Nav-tabs)...")
    res = sync_all_pages()
    for page, ok in res.items():
        status = "✔" if ok else "✖ (introuvable)"
        print(f"  {status} {page}")
    print("✨ Synchronisation terminée avec succès.")


if __name__ == "__main__":
    main()

