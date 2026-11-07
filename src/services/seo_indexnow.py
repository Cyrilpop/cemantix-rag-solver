"""
Cémantix Solver — Protocole IndexNow Multi-Moteurs (seo_indexnow)
================================================================
Notifie instantanément Microsoft Bing, Yahoo, Yandex, Naver et Seznam
dès qu'une page ou une archive quotidienne est générée ou mise à jour.
Protocole standard : https://www.indexnow.org/
"""
import os
from pathlib import Path
import secrets
from typing import Any, Dict, List, Optional
import urllib.parse

try:
    import requests
except ImportError:
    requests = None  # type: ignore

try:
    from ..config import log
except ImportError:
    import datetime

    def log(msg: str):  # type: ignore
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {msg}")

from .seo_templates import SITE_ORIGIN, WEB_ROOT

INDEXNOW_API_ENDPOINT = "https://api.indexnow.org/indexnow"


def get_indexnow_key(web_root: Optional[Path] = None) -> str:
    """Récupère ou génère automatiquement la clé secrète IndexNow exposée publiquement."""
    root = web_root or WEB_ROOT
    key = os.getenv("INDEXNOW_KEY", "").strip()

    key_file = root / "indexnow-key.txt"
    if not key:
        if key_file.is_file():
            try:
                key = key_file.read_text(encoding="utf-8").strip()
            except Exception:
                key = ""

    if not key:
        # Génération d'une clé aléatoire pérenne de 32 caractères hexadécimaux
        key = secrets.token_hex(16)
        try:
            root.mkdir(parents=True, exist_ok=True)
            key_file.write_text(key, encoding="utf-8")
        except Exception as exc:
            log(f"⚠️  [INDEXNOW] Impossible d'écrire {key_file} : {exc}")

    # Garantit que le fichier de vérification correspondant à la clé existe bien dans le webroot
    public_file = root / f"{key}.txt"
    if not public_file.is_file():
        try:
            root.mkdir(parents=True, exist_ok=True)
            public_file.write_text(key, encoding="utf-8")
        except Exception as exc:
            log(f"⚠️  [INDEXNOW] Impossible d'exposer {public_file} : {exc}")

    return key


def submit_indexnow_urls(
    urls: List[str],
    host: Optional[str] = None,
    key: Optional[str] = None,
    web_root: Optional[Path] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Transmet la liste des URLs mises à jour à l'API IndexNow."""
    if not urls:
        return {"success": False, "status_code": 0, "message": "Aucune URL à soumettre."}

    if not requests:
        return {"success": False, "status_code": 0, "message": "Module requests indisponible."}

    # Garde-fou anti-quota en test : neutralise tout appel réseau réel
    if os.getenv("SKIP_SEO_PUSH") == "1" and not hasattr(requests.post, "assert_called"):
        return {
            "success": True,
            "status_code": 200,
            "skipped": True,
            "message": "Soumission IndexNow neutralisée (mode test anti-quota).",
        }

    active_host = host or urllib.parse.urlparse(SITE_ORIGIN).netloc or "cemantix.cyril-randon.fr"
    active_key = key or get_indexnow_key(web_root=web_root)

    key_location = f"https://{active_host}/{active_key}.txt"

    payload = {
        "host": active_host,
        "key": active_key,
        "keyLocation": key_location,
        "urlList": urls,
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}

    try:
        resp = requests.post(INDEXNOW_API_ENDPOINT, json=payload, headers=headers, timeout=timeout)
        # 200 OK ou 202 Accepted
        if resp.status_code in (200, 202):
            log(
                f"⚡ [INDEXNOW] {len(urls)} URL(s) transmise(s) avec succès à IndexNow (Bing/Yahoo)"
            )
            return {
                "success": True,
                "status_code": resp.status_code,
                "message": "URLs acceptées par IndexNow.",
            }
        log(
            f"ℹ️  [INDEXNOW] Réponse IndexNow (HTTP {resp.status_code}) : {resp.text}"
        )
        return {
            "success": False,
            "status_code": resp.status_code,
            "message": resp.text,
        }
    except Exception as exc:
        log(f"⚠️  [INDEXNOW] Exception lors de la soumission IndexNow : {exc}")
        return {
            "success": False,
            "status_code": -1,
            "message": str(exc),
        }


def notify_daily_urls_to_indexnow(
    entries: List[Dict[str, Any]],
    site_origin: Optional[str] = None,
    web_root: Optional[Path] = None,
    force: bool = False,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Notifie les URLs chaudes du jour à IndexNow (Bing / Yahoo / etc.).

    Vérifie au préalable si le puzzle du jour a déjà été notifié à IndexNow
    afin de prévenir les erreurs HTTP 429 (TooManyRequests) lors des redémarrages
    successifs du conteneur.
    Le paramètre `force=True` contourne cette protection.
    """
    newest_date = str(entries[0].get("date")) if entries else ""

    # Protection quota / anti-429 : vérifier si déjà notifié
    if newest_date and not force:
        try:
            from ..db import is_daily_puzzle_indexnow_indexed
            if is_daily_puzzle_indexnow_indexed(newest_date):
                log(
                    f"ℹ️  [INDEXNOW] Puzzle du {newest_date} déjà notifié à IndexNow "
                    "(quota et anti-429 préservés). Utilisez force=True pour forcer."
                )
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "already_indexed",
                    "date": newest_date,
                }
        except Exception as check_exc:
            log(f"⚠️  [INDEXNOW] Impossible de vérifier l'état d'indexation IndexNow ({check_exc})")

    origin = (site_origin or SITE_ORIGIN).rstrip("/")
    hot_urls = [
        f"{origin}/",
        f"{origin}/mot-du-jour/",
    ]
    if newest_date:
        hot_urls.append(f"{origin}/puzzles/{newest_date}/")

    res = submit_indexnow_urls(
        urls=hot_urls,
        web_root=web_root,
        timeout=timeout,
    )

    # Si succès (200 ou 202), marquer en base
    if newest_date and res.get("success"):
        try:
            from ..db import mark_daily_puzzle_indexnow_indexed
            mark_daily_puzzle_indexnow_indexed(newest_date)
        except Exception as mark_exc:
            log(f"⚠️  [INDEXNOW] Erreur marquage d'indexation IndexNow en base : {mark_exc}")

    return res
