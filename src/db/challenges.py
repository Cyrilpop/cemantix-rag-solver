"""
Cémantix Solver — Persistance des Défis au Bot (bot_challenges, DEFI-02)
========================================================================
File de tâches tri-partite de l'évolution « Défier le bot » :

- le conteneur web (`cemantix_web`) **enqueue** : `create_challenge()` ;
- le conteneur worker (`cemantix_worker`) **résout** : `claim_next_challenge()`,
  `append_trajectory()`, `finish_challenge()` ;
- l'API relit l'état pour le polling et le SSE : `get_challenge()`.

Aucune donnée personnelle : `ip_hash` est un HMAC-SHA256 salé de l'IP anonymisée
/24 (SEC-21). Les requêtes sont 100 % paramétrées, sur PostgreSQL comme sur le
repli SQLite (même convention que `src/db/daily.py`).
"""
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from .connection import db

# --------------------------------------------------------------------------- #
# Bornes et secrets (défauts du plan 2026-10-06-defier-le-bot, §6)
# --------------------------------------------------------------------------- #
CHALLENGE_ENABLED = os.getenv("CHALLENGE_ENABLED", "1").strip().lower() not in ("0", "false", "non")
CHALLENGE_MAX_TRIES = int(os.getenv("CHALLENGE_MAX_TRIES", "100"))
CHALLENGE_TIMEOUT = float(os.getenv("CHALLENGE_TIMEOUT", "900"))
CHALLENGE_MAX_QUEUE = int(os.getenv("CHALLENGE_MAX_QUEUE", "20"))
CHALLENGE_RETENTION_DAYS = int(os.getenv("CHALLENGE_RETENTION_DAYS", "30"))
CHALLENGE_QUOTA_PER_HOUR = int(os.getenv("CHALLENGE_QUOTA_PER_HOUR", "10"))

# Sel du HMAC d'IP (SEC-21) : secret d'exploitation, jamais le mot de passe
# admin, jamais versionné. À défaut d'un sel dédié (`CHALLENGE_IP_SALT`), on
# dérive du secret d'exploitation déjà partagé entre le web et le worker
# (`DB_PASS`) ; à défaut des deux, un sel aléatoire par processus : le quota
# reste valable pendant la vie du processus mais ne survit pas au redémarrage.
_SALT_ENV = os.getenv("CHALLENGE_IP_SALT") or os.getenv("DB_PASS") or ""
_RANDOM_SALT = secrets.token_bytes(16)


def ip_hash(ip_anonymized: str) -> str:
    """HMAC-SHA256 salé de l'IP déjà anonymisée en /24 (empreinte non réversible)."""
    sel = _SALT_ENV.encode("utf-8") if _SALT_ENV else _RANDOM_SALT
    return hmac.new(sel, ("cemantix-challenge|" + ip_anonymized).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_challenge(row: Optional[dict]) -> Optional[dict]:
    """Normalise une ligne `bot_challenges` (Decimal → float, trajectoire → liste)."""
    if not row:
        return None
    trajectory = row.get("trajectory")
    if isinstance(trajectory, str):
        try:
            trajectory = json.loads(trajectory)
        except Exception:
            trajectory = []
    duration = row.get("duration_seconds")
    return {
        "id": row["id"],
        "status": row["status"],
        "tries_count": int(row.get("tries_count") or 0),
        "max_tries": int(row.get("max_tries") or CHALLENGE_MAX_TRIES),
        "duration_seconds": float(duration) if duration is not None else None,
        "trajectory": trajectory if isinstance(trajectory, list) else [],
        "error": row.get("error"),
        "created_at": str(row.get("created_at") or ""),
        "started_at": str(row.get("started_at") or ""),
        "finished_at": str(row.get("finished_at") or ""),
        # Jamais exposé aux clients avant le statut terminal : réservé au worker
        # et à la construction de l'événement final (SEC-26).
        "secret_word": row.get("secret_word"),
        "ip_hash": row.get("ip_hash"),
    }


# --------------------------------------------------------------------------- #
# File de tâches (DEFI-01..03)
# --------------------------------------------------------------------------- #
def create_challenge(secret_word: str, ip_hash_value: str,
                     max_tries: int = CHALLENGE_MAX_TRIES) -> str:
    """Empile un défi validé. Retourne son identifiant aléatoire 128 bits (SEC-22)."""
    challenge_id = secrets.token_hex(16)
    db.execute(
        """
        INSERT INTO bot_challenges (id, secret_word, ip_hash, status, max_tries, created_at)
        VALUES (%s, %s, %s, 'queued', %s, %s);
        """,
        (challenge_id, secret_word, ip_hash_value, int(max_tries), _utcnow()),
    )
    return challenge_id


def get_challenge(challenge_id: str) -> Optional[dict]:
    """Relit un défi par son identifiant (None si inconnu ou purgé)."""
    row = db.fetch_one("SELECT * FROM bot_challenges WHERE id = %s;", (str(challenge_id),))
    return _row_to_challenge(row)


def claim_next_challenge() -> Optional[dict]:
    """Réserve le défi « queued » le plus ancien, de façon atomique (DEFI-09).

    L'`UPDATE` conditionné sur `status='queued'` garantit qu'un second claim
    concurrent ne peut pas voler la même ligne : il obtient `rowcount = 0` et
    passe à la suivante.
    """
    for _ in range(8):
        row = db.fetch_one(
            "SELECT id FROM bot_challenges WHERE status = 'queued' ORDER BY created_at LIMIT 1;"
        )
        if not row:
            return None
        now = _utcnow()
        claimed = db.execute(
            """
            UPDATE bot_challenges
            SET status = 'running', started_at = %s, heartbeat_at = %s
            WHERE id = %s AND status = 'queued';
            """,
            (now, now, row["id"]),
        )
        if claimed:
            return get_challenge(row["id"])
    return None


def append_trajectory(challenge_id: str, steps: list, tries_count: int) -> int:
    """Publie la trajectoire incrémentale et rafraîchit le battement (DEFI-11)."""
    return db.execute(
        """
        UPDATE bot_challenges
        SET trajectory = %s, tries_count = %s, heartbeat_at = %s
        WHERE id = %s AND status = 'running';
        """,
        (list(steps), int(tries_count), _utcnow(), challenge_id),
    )


def heartbeat(challenge_id: str) -> int:
    """Rafraîchit seul la preuve de vie, sans réécrire la trajectoire."""
    return db.execute(
        "UPDATE bot_challenges SET heartbeat_at = %s WHERE id = %s AND status = 'running';",
        (_utcnow(), challenge_id),
    )


def release_challenge(challenge_id: str) -> int:
    """Rend une tâche `running` à la file sans la marquer orpheline.

    Cas légitime : le worker ne peut pas démarrer la résolution (index vectoriel
    en cours de reconstruction) — la tâche attend le prochain réveil, intacte.
    """
    return db.execute(
        """
        UPDATE bot_challenges
        SET status = 'queued', started_at = NULL, heartbeat_at = NULL
        WHERE id = %s AND status = 'running';
        """,
        (challenge_id,),
    )


def finish_challenge(challenge_id: str, status: str, tries_count: int,
                     duration_seconds: float, error: Optional[str] = None) -> int:
    """Clôture un défi : `solved`, `lost` ou `error` (DEFI-03, DEFI-12)."""
    if status not in ("solved", "lost", "error"):
        raise ValueError(f"Statut terminal invalide : {status}")
    return db.execute(
        """
        UPDATE bot_challenges
        SET status = %s, tries_count = %s, duration_seconds = %s, error = %s,
            finished_at = %s, heartbeat_at = %s
        WHERE id = %s AND status = 'running';
        """,
        (status, int(tries_count), round(float(duration_seconds), 2),
         (error or "")[:200] or None, _utcnow(), _utcnow(), challenge_id),
    )


def count_recent_for_ip(ip_hash_value: str, window_seconds: float) -> int:
    """Nombre de défis créés par cette empreinte sur la fenêtre glissante (SEC-20)."""
    cutoff = _utcnow() - timedelta(seconds=window_seconds)
    row = db.fetch_one(
        "SELECT COUNT(*) AS n FROM bot_challenges WHERE ip_hash = %s AND created_at > %s;",
        (ip_hash_value, cutoff),
    )
    return int((row or {}).get("n") or 0)


def oldest_recent_for_ip(ip_hash_value: str, window_seconds: float):
    """Création du défi le plus ancien de la fenêtre : base du `retry_after`."""
    cutoff = _utcnow() - timedelta(seconds=window_seconds)
    row = db.fetch_one(
        """
        SELECT created_at FROM bot_challenges
        WHERE ip_hash = %s AND created_at > %s
        ORDER BY created_at LIMIT 1;
        """,
        (ip_hash_value, cutoff),
    )
    return (row or {}).get("created_at")


def queue_position(challenge_id: str) -> int:
    """Rang d'attente d'un défi (0 = le prochain pris en charge).

    La comparaison se fait en base sur `created_at` du défi lui-même : pas de
    va-et-vient de formats de date entre les moteurs.
    """
    row = db.fetch_one(
        """
        SELECT COUNT(*) AS n FROM bot_challenges
        WHERE status = 'queued'
          AND created_at < (SELECT created_at FROM bot_challenges WHERE id = %s);
        """,
        (challenge_id,),
    )
    return int((row or {}).get("n") or 0)


def count_queued() -> int:
    """Profondeur d'attente actuelle, pour le plafond de file (SEC-24)."""
    row = db.fetch_one("SELECT COUNT(*) AS n FROM bot_challenges WHERE status = 'queued';")
    return int((row or {}).get("n") or 0)


def requeue_stale_running(max_age_seconds: float = CHALLENGE_TIMEOUT) -> int:
    """Recycle les défis `running` sans battement (worker mort, DEFI-03).

    Premier orphelinat : la tâche repart en `queued` (marqueur dans `error`).
    Second orphelinat : la tâche est déclarée `error` — on ne rejoue pas à l'infini.
    """
    cutoff = _utcnow() - timedelta(seconds=max_age_seconds)
    stale = db.fetch_all(
        "SELECT id, error FROM bot_challenges WHERE status = 'running' AND heartbeat_at < %s;",
        (cutoff,),
    )
    recycled = 0
    for row in stale:
        if row.get("error"):
            db.execute(
                """
                UPDATE bot_challenges
                SET status = 'error', error = %s, finished_at = %s
                WHERE id = %s AND status = 'running';
                """,
                ("worker perdu une seconde fois", _utcnow(), row["id"]),
            )
        else:
            recycled += db.execute(
                """
                UPDATE bot_challenges
                SET status = 'queued', error = %s, started_at = NULL
                WHERE id = %s AND status = 'running';
                """,
                ("rejoué : worker interrompu", row["id"]),
            )
    return recycled


def purge_older_than(days: int = CHALLENGE_RETENTION_DAYS) -> int:
    """Efface les défis plus vieux que `days` jours (SEC-27, purge RGPD)."""
    cutoff = _utcnow() - timedelta(days=int(days))
    return db.execute("DELETE FROM bot_challenges WHERE created_at < %s;", (cutoff,))


# --------------------------------------------------------------------------- #
# Whitelist d'exemption de quota (DEFI-18, SEC-20)
# --------------------------------------------------------------------------- #
def is_ip_whitelisted(ip_address: str) -> bool:
    """Le client (IP exacte, non anonymisée) est-il exempté de quota ?"""
    row = db.fetch_one(
        "SELECT ip_address FROM bot_challenge_whitelist WHERE ip_address = %s;",
        (str(ip_address),),
    )
    return row is not None


def get_whitelist() -> list:
    """Liste des exemptions, avec description et date d'ajout."""
    rows = db.fetch_all(
        "SELECT ip_address, description, created_at FROM bot_challenge_whitelist ORDER BY created_at;"
    )
    return [
        {"ip_address": r["ip_address"], "description": r.get("description") or "",
         "created_at": str(r.get("created_at") or "")}
        for r in rows
    ]


def add_whitelist_ip(ip_address: str, description: str = "") -> bool:
    """Ajoute (ou met à jour la description d')une IP exemptée."""
    db.execute(
        """
        INSERT INTO bot_challenge_whitelist (ip_address, description, created_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (ip_address) DO UPDATE SET description = EXCLUDED.description;
        """,
        (str(ip_address), (description or "")[:100], _utcnow()),
    )
    return True


def remove_whitelist_ip(ip_address: str) -> bool:
    """Retire une exemption ; retourne False si l'IP n'y figurait pas."""
    return bool(db.execute(
        "DELETE FROM bot_challenge_whitelist WHERE ip_address = %s;",
        (str(ip_address),),
    ))

