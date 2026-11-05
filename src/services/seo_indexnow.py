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
