"""
Cémantix Solver — Contrôleur des Routes Système & Mot du Jour
=============================================================
Endpoints :
- GET  /api/health, /api/healthcheck : Statut de santé et sessions actives
- GET  /api/daily, /api/dashboard    : Données du tableau de bord Caddy & trajectoire
- POST /api/daily/reveal             : Révélation explicite du mot du jour

Le mot secret n'est **jamais** présent dans une réponse GET : il ne transite que par
`POST /api/daily/reveal`, une route volontairement exclue du cache et du crawl. Les
mots de la trajectoire et les indices qui révéleraient la cible sont masqués côté
serveur, jamais par le seul effet du CSS.
"""
from typing import Optional

from ...game import GameManager

MASK = "••••••••"


def _scrub_secret(data: dict) -> dict:
    """Retire toute trace du mot secret des données du tableau de bord.

    Le masquage s'applique au champ `word` mais aussi à la trajectoire et aux
    indices (`top_guesses`) : sans cela, la solution restait lisible dans un
    tableau annexe alors que le champ principal était vidé.
    """
    current = data.get("current")
    if not current:
        data["is_revealed"] = False
        return data

    secret = str(current.get("word") or "").strip().lower()
    current["word"] = None
    data["is_revealed"] = False

    if not secret:
        return data

    for key in ("trajectory", "top_guesses", "history"):
        steps = current.get(key)
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict) and str(step.get("word", "")).strip().lower() == secret:
                step["word"] = MASK

    # L'historique complet expose aussi le mot du jour (même entrée, clé "word").
    history = data.get("history")
    if isinstance(history, list):
        today = current.get("date")
        for entry in history:
            if (
                isinstance(entry, dict)
                and entry.get("date") == today
                and str(entry.get("word", "")).strip().lower() == secret
            ):
                entry["word"] = None
                entry["word_hidden"] = True

    return data


import hashlib
import time
import threading

# Cache mémoire pour /api/daily et /api/dashboard (PERF-01)
_CACHE_LOCK = threading.Lock()
_CACHE_DATA: Optional[dict] = None
_CACHE_ETAG: Optional[str] = None
_CACHE_TIMESTAMP: float = 0.0
_CACHE_TTL: float = 15.0  # 15 secondes


def invalidate_system_cache() -> None:
    """Invalide immédiatement le cache du tableau de bord (ex: après résolution)."""
    global _CACHE_DATA, _CACHE_ETAG, _CACHE_TIMESTAMP
    with _CACHE_LOCK:
        _CACHE_DATA = None
        _CACHE_ETAG = None
        _CACHE_TIMESTAMP = 0.0


def handle_system_get(
    manager: Optional[GameManager],
    path: str,
    query: str = "",
    if_none_match: Optional[str] = None,
) -> tuple[dict, int, Optional[str]]:
    """Traite les requêtes de santé et de consultation du tableau de bord.

    Renvoie (data, status_code, etag).
    """
    global _CACHE_DATA, _CACHE_ETAG, _CACHE_TIMESTAMP

    if path in ("/api/health", "/api/healthcheck"):
        count = len(manager.sessions) if manager else 0
        return {"status": "ok", "active_sessions": count}, 200, None

    if path in ("/api/daily", "/api/dashboard"):
        now = time.time()
        with _CACHE_LOCK:
            if _CACHE_DATA is not None and (now - _CACHE_TIMESTAMP) < _CACHE_TTL:
                data = _CACHE_DATA
                etag = _CACHE_ETAG
            else:
                try:
                    from ...services import build_web_data
                    raw_data = build_web_data()
                    data = _scrub_secret(raw_data)
                    # Calcul de l'ETag basé sur le contenu masqué
                    raw_bytes = str(sorted(data.items())).encode("utf-8")
                    etag = f'"{hashlib.md5(raw_bytes).hexdigest()}"'
                    _CACHE_DATA = data
                    _CACHE_ETAG = etag
                    _CACHE_TIMESTAMP = now
                except Exception as e:
                    from ...config import log
                    log(f"Erreur chargement données dashboard: {e}", level="ERROR")
                    return {"error": "Erreur interne lors du chargement des données"}, 500, None

        if if_none_match and if_none_match.strip() == etag:
            return {}, 304, etag

        return data, 200, etag

    return {"error": "Route introuvable"}, 404, None


def handle_system_post(manager: Optional[GameManager], path: str, data: dict) -> tuple[dict, int]:
    """Révèle le mot du jour sur demande explicite de l'utilisateur.

    Volontairement en POST : un simple crawl, un prefetch de lien ou un `curl`
    ne peuvent pas récupérer la solution par accident.
    """
    if path != "/api/daily/reveal":
        return {"error": "Route introuvable"}, 404

    try:
        from ...services import build_web_data
        payload = build_web_data(mask_words=False)
    except Exception as e:
        from ...config import log
        log(f"Erreur chargement données reveal: {e}", level="ERROR")
        return {"error": "Erreur interne lors du chargement des données"}, 500

    current = payload.get("current") or {}
    word = str(current.get("word") or "").strip()
    if not word:
        # Le mot du jour n'est pas encore résolu : ce n'est pas une erreur de
        # routage. Réponse 200 avec word=None pour que le client affiche l'état
        # « pas encore résolu » au lieu d'un 404 brut (et de son toast générique).
        return {
            "word": None,
            "puzzle": current.get("puzzle"),
            "date": current.get("date"),
            "is_revealed": False,
            "pending": True,
            "message": "Le mot du jour n'a pas encore été résolu.",
        }, 200

    return {
        "word": word,
        "puzzle": current.get("puzzle"),
        "date": current.get("date"),
        "is_revealed": True,
    }, 200

