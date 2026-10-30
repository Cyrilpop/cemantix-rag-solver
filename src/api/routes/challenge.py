"""
Cémantix Solver — Routes « Défier le bot » (src.api.routes.challenge)
=====================================================================
Évolution 2026-10-06-defier-le-bot. Le conteneur web ne fait **aucun calcul** :
il valide, compte, et empile une ligne en base. C'est le worker qui résout.

- `POST /api/challenge`             — empile un défi validé (DEFI-04)
- `GET  /api/challenge/<id>`        — état borné pour le polling (DEFI-05)
- `GET  /api/challenge/<id>/stream` — coups en direct via SSE (DEFI-06)

Interdit structurel : ce module n'importe ni le moteur de résolution ni les
services du worker — uniquement la couche de données (DEFI-04).
"""
import json
import os
import re
import threading
import time
import unicodedata
from typing import Optional

from ...config import log
from ...db import (
    CHALLENGE_ENABLED,
    CHALLENGE_MAX_QUEUE,
    CHALLENGE_MAX_TRIES,
    CHALLENGE_QUOTA_PER_HOUR,
    count_queued,
    count_recent_for_ip,
    create_challenge,
    get_challenge,
    ip_hash,
    is_ip_whitelisted,
    oldest_recent_for_ip,
)
from ..ratelimit import RateLimiter

# --------------------------------------------------------------------------- #
# Bornes (plan §3 et §6)
# --------------------------------------------------------------------------- #
WORD_RE = re.compile(r"^[a-zà-ÿ][a-zà-ÿ-]{2,23}$")
CHALLENGE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
QUOTA_WINDOW_SECONDS = 3600.0
SSE_MAX_STREAMS = int(os.getenv("SSE_MAX_STREAMS", "16"))
SSE_MAX_DURATION_SECONDS = float(os.getenv("SSE_STREAM_MAX_DURATION", "900"))
SSE_POLL_SECONDS = 0.5
TERMINAL_STATUSES = ("solved", "lost", "error")

# DEFI-07 : anti-rafale mémoire, devant la lecture SQL. 6 créneaux, refill 10/min.
_challenge_limiter = RateLimiter(default_capacity=6.0, refill_per_second=10.0 / 60.0,
                                 burst_capacity=6.0)

# SEC-23 : plafond global de flux SSE simultanés — chaque flux retient un thread.
_sse_slots = threading.BoundedSemaphore(max(1, SSE_MAX_STREAMS))


# --------------------------------------------------------------------------- #
# Validation du mot (DEFI-08)
# --------------------------------------------------------------------------- #
def validate_word(raw, store) -> Optional[str]:
    """Mot normalisé si acceptable, sinon None. Message unique côté appelant :
    aucune distinction renvoyée entre « forme invalide » et « hors lexique »,
    pour ne pas offrir d'oracle lexikaliste."""
    if not isinstance(raw, str):
        return None
    word = unicodedata.normalize("NFC", raw.strip().lower())
    if not WORD_RE.match(word):
        return None
    if store is None:
        return None
    try:
        canonical = store.normalize(word)
        if canonical != word or not store.is_valid_french(word):
            return None
    except Exception:
        # Un store indisponible ne doit jamais transformer la validation en 500.
        return None
    return word


def _quota_restant(hashed_ip: str, whitelisted: bool):
    """Défis restants sur la fenêtre (DEFI-04), ou "unlimited" si exempté."""
    if whitelisted:
        return "unlimited"
    used = count_recent_for_ip(hashed_ip, QUOTA_WINDOW_SECONDS)
    return max(0, CHALLENGE_QUOTA_PER_HOUR - used)


def _retry_after_seconds(hashed_ip: str) -> float:
    """Temps d'attente avant libération d'un créneau : expiration du plus ancien."""
    oldest = oldest_recent_for_ip(hashed_ip, QUOTA_WINDOW_SECONDS)
    try:
        from datetime import datetime, timezone
        if isinstance(oldest, str):
            oldest = datetime.fromisoformat(oldest)
        if oldest is not None:
            if oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
            wait = QUOTA_WINDOW_SECONDS - (datetime.now(timezone.utc) - oldest).total_seconds()
            return max(5.0, round(wait, 1))
    except Exception:
        pass
    return QUOTA_WINDOW_SECONDS


# --------------------------------------------------------------------------- #
# POST /api/challenge (DEFI-04, SEC-20, SEC-24)
# --------------------------------------------------------------------------- #
def handle_challenge_post(manager, path: str, data: dict, client_ip: str,
                          anonymized_ip: str) -> tuple[dict, int]:
    """Valide → exemptés → anti-rafale → quota base → file bornée → enqueue."""
    if not CHALLENGE_ENABLED:
        return {"error": "Le bot est momentanément indisponible. Réessayez plus tard."}, 503

    word = validate_word((data or {}).get("word"), getattr(manager, "store", None))
    if not word:
        return {"error": "Mot non reconnu."}, 400

    whitelisted = is_ip_whitelisted(client_ip)
    hashed = ip_hash(anonymized_ip)

    if not whitelisted:
        allowed, retry = _challenge_limiter.allow(anonymized_ip)
        if not allowed:
            return {"error": "Trop de tentatives d'affilée.",
                    "retry_after": round(retry, 1)}, 429
        used = count_recent_for_ip(hashed, QUOTA_WINDOW_SECONDS)
        if used >= CHALLENGE_QUOTA_PER_HOUR:
            return {"error": "Quota de défis atteint : 10 par heure.",
                    "retry_after": _retry_after_seconds(hashed)}, 429
        if count_queued() >= CHALLENGE_MAX_QUEUE:
            return {"error": "Le bot est déjà occupé, la file d'attente est pleine.",
                    "retry_after": 30}, 429

    challenge_id = create_challenge(word, hashed, max_tries=CHALLENGE_MAX_TRIES)
    log(f"⚔️  [DÉFI] Défi empilé ({'exempté de quota' if whitelisted else 'quota standard'})")
    return {"id": challenge_id, "status": "queued",
            "quota_restant": _quota_restant(hashed, whitelisted)}, 201


# --------------------------------------------------------------------------- #
# GET /api/challenge/<id> (DEFI-05, SEC-22, SEC-26)
# --------------------------------------------------------------------------- #
def _public_view(challenge: dict) -> dict:
    """Vue publique : jamais le mot avant le statut terminal ; au terminal,
    seulement si le bot a gagné (le mot est alors déjà dans la trajectoire)."""
    view = {
        "status": challenge["status"],
        "tries_count": challenge["tries_count"],
        "steps": len(challenge["trajectory"]),
    }
    if challenge["status"] in TERMINAL_STATUSES:
        view["duration_seconds"] = challenge["duration_seconds"]
        if challenge["status"] == "solved":
            view["word"] = challenge["secret_word"]
        elif challenge["status"] == "error":
            view["error"] = "Le bot n'a pas pu mener ce défi au bout."
    return view


def _parse_challenge_id(path: str) -> tuple[Optional[str], bool]:
    """Extrait `(id, est_un_flux)` de `/api/challenge/<id>[/stream]`.

    Retourne `(None, …)` pour un identifiant malformé — traité comme inconnu
    (même 404 générique, pas d'oracle).
    """
    sub = path[len("/api/challenge"):].strip("/")
    parts = [p for p in sub.split("/") if p]
    if not parts:
        return None, False
    is_stream = len(parts) > 1 and parts[1] == "stream"
    candidate = parts[0]
    if not CHALLENGE_ID_RE.match(candidate):
        return None, False
    return candidate, is_stream


def handle_challenge_get(manager, path: str) -> tuple[dict, int]:
    """État borné pour le polling : compte de coups, pas la trajectoire."""
    challenge_id, _ = _parse_challenge_id(path)
    if not challenge_id:
        return {"error": "Défi introuvable."}, 404
    challenge = get_challenge(challenge_id)
    if not challenge:
        return {"error": "Défi introuvable."}, 404
    return _public_view(challenge), 200


# --------------------------------------------------------------------------- #
# GET /api/challenge/<id>/stream — SSE (DEFI-06, SEC-23, SEC-26)
# --------------------------------------------------------------------------- #
def handle_challenge_stream(path: str, send_json, send_sse) -> None:
    """Flux SSE des coups, plafonné en durée et en connexions simultanées."""
    challenge_id, _ = _parse_challenge_id(path)
    if not challenge_id or not get_challenge(challenge_id):
        send_json({"error": "Défi introuvable."}, 404)
        return

    if not _sse_slots.acquire(blocking=False):
        send_json({"error": "Trop de suivis en direct, réessayez dans quelques secondes.",
                   "retry_after": 5}, 503)
        return

    def _produce(emit):
        sent = 0
        deadline = time.time() + SSE_MAX_DURATION_SECONDS
        try:
            while time.time() < deadline:
                challenge = get_challenge(challenge_id)
                if not challenge:
                    emit(json.dumps({"event": "gone"}))
                    return
                steps = challenge["trajectory"]
                for step in steps[sent:]:
                    emit(json.dumps({"event": "step", "step": step}, ensure_ascii=False))
                    sent += 1
                if challenge["status"] in TERMINAL_STATUSES:
                    final = {"event": "done", "status": challenge["status"],
                             "tries_count": challenge["tries_count"],
                             "duration_seconds": challenge["duration_seconds"]}
                    if challenge["status"] == "solved":
                        final["word"] = challenge["secret_word"]
                    elif challenge["status"] == "error":
                        final["error"] = "Le bot n'a pas pu mener ce défi au bout."
                    emit(json.dumps(final, ensure_ascii=False))
                    return
                time.sleep(SSE_POLL_SECONDS)
            emit(json.dumps({"event": "timeout"}))
        finally:
            _sse_slots.release()

    send_sse(_produce)

