#!/usr/bin/env python3
"""
tools/bump_version.py — Générateur de version automatique PR (0.{pr}.{secondes:06d})
==================================================================================
Calcule la version basée sur :
  - Le numéro de la Pull Request associée à la branche courante (via `gh pr view`)
  - Le nombre de secondes écoulées depuis l'ouverture de la PR, formaté sur 6 chiffres (000000 - 999999).
Génère volumes/web/version.json pour affichage dynamique dans le footer à la place de la dernière synchro.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent / "volumes" / "web" / "version.json"


def compute_version() -> dict:
    try:
        res = subprocess.run(
            ["gh", "pr", "view", "--json", "number,createdAt"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout)
        pr_number = int(data.get("number", 0))
        created_at_raw = data.get("createdAt", "")
        # Format ISO GitHub UTC: 2026-11-10T22:16:52Z
        created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
    except Exception as e:
        # Repli si pas de PR ouverte pour la branche (ex: dev local avant PR)
        pr_number = 0
        created_at = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    seconds = max(0, int((now - created_at).total_seconds()))
    # Règle : 6 chiffres fixes complétés par des zéros
    version_str = f"0.{pr_number}.{seconds:06d}"

    payload = {
        "version": version_str,
        "pr": pr_number,
        "seconds": seconds,
        "updated_at": now.isoformat(),
    }
    return payload


def main():
    payload = compute_version()
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"📦 Version générée : v{payload['version']} (PR #{payload['pr']}, +{payload['seconds']}s)")


if __name__ == "__main__":
    main()
