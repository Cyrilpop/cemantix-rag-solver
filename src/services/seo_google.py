"""
Cémantix Solver — Soumission Sitemap à Google Search Console (seo_google)
========================================================================
Gère l'authentification OAuth 2.0 (renouvellement par refresh token) et
la soumission programmatique du fichier `sitemap.xml` auprès de l'API
Google Search Console v1 (`webmasters.sitemaps.submit`).
"""
import json
import os
from pathlib import Path
import time
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

from .seo_templates import SITE_ORIGIN

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Cache mémoire de l'access token
_TOKEN_CACHE: Dict[str, Any] = {"token": None, "expires_at": 0.0}


def parse_dotenv(dotenv_path: Optional[Path] = None) -> Dict[str, str]:
    """Parse un fichier .env simple sans dépendance tierce."""
    path = dotenv_path or (BASE_DIR / ".env")
    env_vars: Dict[str, str] = {}
    if not path.is_file():
        return env_vars

    try:
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Retirer les guillemets simples ou doubles
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                env_vars[key] = val
    except Exception as exc:
        log(f"⚠️  [SEO-GOOGLE] Erreur de lecture de {path} : {exc}")
    return env_vars


def get_google_credentials(dotenv_path: Optional[Path] = None) -> Dict[str, Any]:
    """Extrait les identifiants Google depuis l'environnement avec repli sur .env."""
    env_from_file = parse_dotenv(dotenv_path)

    def _get(key: str, default: str = "") -> str:
        return os.environ.get(key) or env_from_file.get(key, default)

    client_id = _get("GOOGLE_CLIENT_ID")
    # Tolérance sur la faute de frappe constatée dans le .env
    client_secret = (
        _get("GOOGLE_CLIENT_SECRET")
        or _get("GOOCLE_CLIEBNT_SECRET")
        or _get("GOOGLE_CLIENT_SECRET_TYPO")
    )
    refresh_token = _get("GOOGLE_REFRESH_TOKEN")
    project_id = _get("GOOGLE_PROJECT_ID")
    token_uri = _get("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")
    auth_uri = _get("GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth")

    redirect_raw = _get("GOOGLE_REDIRECT_URIS", f"{SITE_ORIGIN}")
    redirect_uri = SITE_ORIGIN
    if redirect_raw:
        try:
            parsed = json.loads(redirect_raw)
            if isinstance(parsed, list) and parsed:
                redirect_uri = str(parsed[0])
            elif isinstance(parsed, str):
                redirect_uri = parsed
        except Exception:
            redirect_uri = redirect_raw.strip("[]\"'")

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "project_id": project_id,
        "token_uri": token_uri,
        "auth_uri": auth_uri,
        "redirect_uri": redirect_uri,
    }


def generate_auth_url(
    credentials: Optional[Dict[str, Any]] = None,
    redirect_uri: Optional[str] = None,
    scope: str = "https://www.googleapis.com/auth/webmasters https://www.googleapis.com/auth/indexing",
) -> str:
    """Génère l'URL d'autorisation OAuth 2.0 pour Search Console et Indexing API."""
    creds = credentials or get_google_credentials()
    client_id = creds.get("client_id", "")
    auth_uri = creds.get("auth_uri", "https://accounts.google.com/o/oauth2/auth")
    redir = redirect_uri or creds.get("redirect_uri", SITE_ORIGIN)

    params = {
        "client_id": client_id,
        "redirect_uri": redir,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{auth_uri}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    code: str,
    credentials: Optional[Dict[str, Any]] = None,
    redirect_uri: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Échange un code d'autorisation OAuth contre access_token et refresh_token."""
    if not requests:
        return {"error": "Module requests indisponible."}

    creds = credentials or get_google_credentials()
    client_id = creds.get("client_id", "")
    client_secret = creds.get("client_secret", "")
    redir = redirect_uri or creds.get("redirect_uri", SITE_ORIGIN)
    token_uri = creds.get("token_uri", "https://oauth2.googleapis.com/token")

    if not client_id or not client_secret:
        return {"error": "Identifiants client_id ou client_secret manquants."}

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redir,
    }
    try:
        resp = requests.post(token_uri, data=payload, timeout=timeout)
        data = resp.json()
        if resp.status_code == 200:
            return data
        return {
            "error": f"Erreur Google (HTTP {resp.status_code}) : {data.get('error_description', resp.text)}"
        }
    except Exception as exc:
        return {"error": f"Exception lors de l'échange de token : {exc}"}


def get_access_token(
    credentials: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
    force_refresh: bool = False,
) -> Optional[str]:
    """Renvoie un jeton d'accès valide, renouvelé par refresh_token si nécessaire."""
    global _TOKEN_CACHE
    now = time.time()
    if (
        not force_refresh
        and _TOKEN_CACHE.get("token")
        and _TOKEN_CACHE.get("expires_at", 0) > now + 30
    ):
        return str(_TOKEN_CACHE["token"])

    if not requests:
        log("⚠️  [SEO-GOOGLE] Module requests non installé.")
        return None

    creds = credentials or get_google_credentials()
    client_id = creds.get("client_id", "")
    client_secret = creds.get("client_secret", "")
    refresh_token = creds.get("refresh_token", "")
    token_uri = creds.get("token_uri", "https://oauth2.googleapis.com/token")

    if not client_id or not client_secret or not refresh_token:
        return None

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        resp = requests.post(token_uri, data=payload, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            _TOKEN_CACHE["token"] = access_token
            _TOKEN_CACHE["expires_at"] = now + expires_in
            return str(access_token)
        log(
            f"⚠️  [SEO-GOOGLE] Renouvellement de token refusé (HTTP {resp.status_code}) : {resp.text}"
        )
        return None
    except Exception as exc:
        log(f"⚠️  [SEO-GOOGLE] Erreur de communication OAuth2 Google : {exc}")
        return None


def submit_sitemap_to_google(
    site_url: Optional[str] = None,
    sitemap_url: Optional[str] = None,
    credentials: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Soumet le sitemap à Google Search Console via l'API Webmasters / Search Console.

    Endpoint : PUT https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/sitemaps/{feedpath}
    """
    creds = credentials or get_google_credentials()
    client_id = creds.get("client_id", "")
    refresh_token = creds.get("refresh_token", "")

    if not client_id:
        log(
            "ℹ️  [SEO-GOOGLE] GOOGLE_CLIENT_ID absent du .env : soumission Search Console désactivée."
        )
        return {
            "success": False,
            "status_code": 0,
            "message": "GOOGLE_CLIENT_ID absent de la configuration.",
        }

    if not refresh_token:
        auth_url = generate_auth_url(creds)
        log(
            "ℹ️  [SEO-GOOGLE] GOOGLE_REFRESH_TOKEN absent. Pour autoriser Google Search Console, "
            f"visitez l'URL suivante et configurez le jeton :\n{auth_url}"
        )
        return {
            "success": False,
            "status_code": 0,
            "message": "GOOGLE_REFRESH_TOKEN absent.",
            "auth_url": auth_url,
        }

    token = get_access_token(creds, timeout=timeout)
    if not token:
        return {
            "success": False,
            "status_code": 0,
            "message": "Impossible d'obtenir un jeton d'accès Google.",
        }

    target_site = (site_url or SITE_ORIGIN).rstrip("/") + "/"
    target_sitemap = sitemap_url or f"{SITE_ORIGIN}/sitemap.xml"

    encoded_site = urllib.parse.quote(target_site, safe="")
    encoded_feed = urllib.parse.quote(target_sitemap, safe="")
    api_url = f"https://www.googleapis.com/webmasters/v3/sites/{encoded_site}/sitemaps/{encoded_feed}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Length": "0",
    }

    try:
        resp = requests.put(api_url, headers=headers, timeout=timeout)
        if resp.status_code in (200, 204):
            log(
                f"✅ [SEO-GOOGLE] Sitemap soumis avec succès à Google Search Console ({target_sitemap})"
            )
            return {
                "success": True,
                "status_code": resp.status_code,
                "message": "Sitemap soumis avec succès.",
            }
        log(
            f"⚠️  [SEO-GOOGLE] Échec de la soumission Google Search Console (HTTP {resp.status_code}) : {resp.text}"
        )
        return {
            "success": False,
            "status_code": resp.status_code,
            "message": resp.text,
        }
    except Exception as exc:
        log(f"⚠️  [SEO-GOOGLE] Exception réseau lors de la soumission du sitemap : {exc}")
        return {
            "success": False,
            "status_code": -1,
            "message": str(exc),
        }


def notify_google_indexing(
    url: str,
    notification_type: str = "URL_UPDATED",
    credentials: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Pousse une notification immédiate à l'API Google Indexing v3.

    Endpoint : POST https://indexing.googleapis.com/v3/urlNotifications:publish
    Types supportés : 'URL_UPDATED' (par défaut) ou 'URL_DELETED'.
    """
    creds = credentials or get_google_credentials()
    client_id = creds.get("client_id", "")
    refresh_token = creds.get("refresh_token", "")

    if not client_id or not refresh_token:
        return {
            "success": False,
            "status_code": 0,
            "message": "Identifiants Google ou GOOGLE_REFRESH_TOKEN manquants.",
        }

    token = get_access_token(creds, timeout=timeout)
    if not token:
        return {
            "success": False,
            "status_code": 0,
            "message": "Impossible d'obtenir un jeton d'accès Google.",
        }

    api_url = "https://indexing.googleapis.com/v3/urlNotifications:publish"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "url": url,
        "type": notification_type,
    }

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        if resp.status_code in (200, 202):
            log(f"⚡ [SEO-GOOGLE] Notification d'indexation acceptée par Google ({url})")
            return {
                "success": True,
                "status_code": resp.status_code,
                "message": "Notification d'indexation acceptée.",
            }
        log(
            f"ℹ️  [SEO-GOOGLE] Réponse Google Indexing API (HTTP {resp.status_code}) : {resp.text}"
        )
        return {
            "success": False,
            "status_code": resp.status_code,
            "message": resp.text,
        }
    except Exception as exc:
        log(f"⚠️  [SEO-GOOGLE] Exception Google Indexing API ({url}) : {exc}")
        return {
            "success": False,
            "status_code": -1,
            "message": str(exc),
        }


def notify_daily_urls_to_google(
    entries: list,
    site_origin: Optional[str] = None,
    credentials: Optional[Dict[str, Any]] = None,
    force: bool = False,
    urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Notifie les URLs chaudes du jour (accueil, mot-du-jour, archive récente, ou liste personnalisée).

    Vérifie au préalable si le puzzle du jour a déjà été indexé en base pour
    préserver le quota quotidien de l'API Google (200 URLs/jour).
    Le paramètre `force=True` contourne cette protection.
    """
    newest_date = str(entries[0].get("date")) if entries else ""

    # Protection quota : vérifier si déjà indexé
    if newest_date and not force:
        try:
            from ..db import is_daily_puzzle_indexed
            if is_daily_puzzle_indexed(newest_date):
                log(
                    f"ℹ️  [SEO-GOOGLE] Puzzle du {newest_date} déjà notifié à Google Indexing API "
                    "(quota quotidien préservé). Utilisez --force pour forcer."
                )
                return {
                    "skipped": True,
                    "reason": "already_indexed",
                    "date": newest_date,
                }
        except Exception as check_exc:
            log(f"⚠️  [SEO-GOOGLE] Impossible de vérifier l'état d'indexation ({check_exc})")

    origin = (site_origin or SITE_ORIGIN).rstrip("/")
    if urls is not None:
        urls_to_notify = list(dict.fromkeys(urls))
    else:
        urls_to_notify = [
            f"{origin}/",
            f"{origin}/mot-du-jour/",
        ]
        if newest_date:
            urls_to_notify.append(f"{origin}/puzzles/{newest_date}/")

    results = {}
    any_success = False
    for u in urls_to_notify:
        res = notify_google_indexing(u, credentials=credentials)
        results[u] = res
        if res.get("success"):
            any_success = True

    # Marquer comme indexé en base si au moins une notification a été acceptée
    if newest_date and any_success:
        try:
            from ..db import mark_daily_puzzle_indexed
            mark_daily_puzzle_indexed(newest_date)
        except Exception as mark_exc:
            log(f"⚠️  [SEO-GOOGLE] Erreur marquage d'indexation en base : {mark_exc}")

    return results


def reset_token_cache() -> None:
    """Réinitialise le cache mémoire du token (utile pour les tests unitaires)."""
    global _TOKEN_CACHE
    _TOKEN_CACHE = {"token": None, "expires_at": 0.0}

