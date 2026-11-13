#!/usr/bin/env python3
"""
tools/bump_version.py — Générateur de version automatique PR (0.{pr}.{secondes:06d})
==================================================================================
Calcule la version basée sur :
  1. Le numéro de la Pull Request associée à la branche courante (`gh pr view`)
  2. À défaut, la dernière Pull Request du dépôt (`gh pr list --state all --limit 1`)
  3. À défaut (hors-ligne), la version existante dans volumes/web/version.json
  - Le nombre de secondes écoulées depuis l'ouverture de la PR, formaté sur 6 chiffres (000000 - 999999).
Génère volumes/web/version.json pour affichage dynamique dans le footer à la place de la dernière synchro.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

VERSION_FILE = Path(__file__).resolve().parent.parent / "volumes" / "web" / "version.json"


def _parse_pr_entry(data: object) -> Optional[Tuple[int, datetime]]:
    """Extrait (pr_number, created_at) depuis une réponse JSON de GitHub CLI."""
    if not isinstance(data, dict):
        return None
    pr_number = int(data.get("number") or 0)
    created_at_raw = str(data.get("createdAt") or "").strip()
    if pr_number <= 0 or not created_at_raw:
        return None
    created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
    return pr_number, created_at


def _fetch_pr_info() -> Optional[Tuple[int, datetime]]:
    """Tente de récupérer la PR de la branche courante, sinon la dernière PR du dépôt."""
    # Étape 1 : PR associée à la branche courante
    try:
        res = subprocess.run(
            ["gh", "pr", "view", "--json", "number,createdAt"],
            capture_output=True,
            text=True,
            check=True,
        )
        parsed = _parse_pr_entry(json.loads(res.stdout))
        if parsed:
            return parsed
    except Exception:
        pass

    # Étape 2 : Repli sur la dernière PR du dépôt (ex: nouveau push avant gh pr create, ou sur main)
    try:
        res = subprocess.run(
            ["gh", "pr", "list", "--state", "all", "--limit", "1", "--json", "number,createdAt"],
            capture_output=True,
            text=True,
            check=True,
        )
        items = json.loads(res.stdout)
        if isinstance(items, list) and items:
            parsed = _parse_pr_entry(items[0])
            if parsed:
                return parsed
    except Exception:
        pass

    return None


def _read_existing_version(now: datetime) -> Tuple[int, int]:
    """Repli hors-ligne : conserve le numéro de PR et met à jour les secondes depuis version.json."""
    if VERSION_FILE.is_file():
        try:
            existing = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
            pr_number = int(existing.get("pr") or 0)
            seconds = int(existing.get("seconds") or 0)
            updated_raw = str(existing.get("updated_at") or "").strip()
            if updated_raw:
                prev_updated = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
                seconds = max(0, seconds + int((now - prev_updated).total_seconds()))
            return pr_number, max(0, seconds)
        except Exception:
            pass
    return 0, 0


def compute_version() -> dict:
    """Calcule le payload de version pour volumes/web/version.json."""
    now = datetime.now(timezone.utc)
    pr_info = _fetch_pr_info()
    if pr_info is not None:
        pr_number, created_at = pr_info
        seconds = max(0, int((now - created_at).total_seconds()))
    else:
        pr_number, seconds = _read_existing_version(now)

    # Règle : 6 chiffres fixes complétés par des zéros
    version_str = f"0.{pr_number}.{seconds:06d}"

    return {
        "version": version_str,
        "pr": pr_number,
        "seconds": seconds,
        "updated_at": now.isoformat(),
    }


def main():
    payload = compute_version()
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(VERSION_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"📦 Version générée : v{payload['version']} (PR #{payload['pr']}, +{payload['seconds']}s)")


if __name__ == "__main__":
    main()
