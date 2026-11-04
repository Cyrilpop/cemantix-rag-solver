"""Outil CLI de synchronisation du layout (Header & Nav-tabs) sur les pages statiques.

Injecte au passage le bloc Google Tag Manager placeholder dans chaque vue
(l'ID réel, lu depuis GOOGLE_TAG_MANAGER_ID dans .env, n'est substitué qu'au
rendu HTTP — il ne fuit jamais dans git).

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
    print("🔄 Synchronisation du layout (Header & Nav-tabs + bloc GTM)...")
    res = sync_all_pages()
    for page, ok in res.items():
        status = "✔" if ok else "✖ (introuvable)"
        print(f"  {status} {page}")
    try:
        from src.services.gtm import gtm_id_from_env
        if gtm_id_from_env():
            print("  ✔ GOOGLE_TAG_MANAGER_ID détecté dans l'environnement : "
                  "l'ID réel sera injecté au rendu HTTP.")
        else:
            print("  ⚠ GOOGLE_TAG_MANAGER_ID absent de l'environnement (.env) : "
                  "le placeholder sera servi tel quel (aucun suivi actif).")
    except Exception as exc:  # pragma: no cover - diagnostic only
        print(f"  ⚠ Contrôle GTM indisponible : {exc}")
    print("✨ Synchronisation terminée avec succès.")


if __name__ == "__main__":
    main()

