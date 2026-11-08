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
import threading
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..config import log
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
# (`DB_PASS`) ; à défaut des deux, un sel persistant sur disque (ip_salt.key)
# pour que les quotas survivent aux redémarrages de conteneurs.
def _get_persistent_salt() -> bytes:
    """Récupère ou génère un sel persistant sur disque (DATA_DIR / 'ip_salt.key')."""
    try:
        from ..config import DATA_DIR
        salt_file = DATA_DIR / "ip_salt.key"
        if salt_file.exists():
            content = salt_file.read_bytes().strip()
            if content:
                return content
        new_salt = secrets.token_bytes(16)
        try:
            salt_file.parent.mkdir(parents=True, exist_ok=True)
            salt_file.write_bytes(new_salt)
        except Exception:
            pass
        return new_salt
    except Exception:
        return secrets.token_bytes(16)


_SALT_ENV = os.getenv("CHALLENGE_IP_SALT") or os.getenv("DB_PASS") or ""
_PERSISTENT_SALT = _SALT_ENV.encode("utf-8") if _SALT_ENV else _get_persistent_salt()


def ip_hash(ip_anonymized: str) -> str:
    """HMAC-SHA256 salé de l'IP déjà anonymisée en /24 (empreinte non réversible)."""
    return hmac.new(_PERSISTENT_SALT, ("cemantix-challenge|" + ip_anonymized).encode("utf-8"),
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
        "player_name": row.get("player_name"),
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
                     max_tries: int = CHALLENGE_MAX_TRIES,
                     player_name: Optional[str] = None) -> str:
    """Empile un défi validé. Retourne son identifiant aléatoire 128 bits (SEC-22)."""
    challenge_id = secrets.token_hex(16)
    p_name = str(player_name).strip()[:64] if player_name else None
    try:
        db.execute(
            """
            INSERT INTO bot_challenges (id, secret_word, ip_hash, status, max_tries, created_at, player_name)
            VALUES (%s, %s, %s, 'queued', %s, %s, %s);
            """,
            (challenge_id, secret_word, ip_hash_value, int(max_tries), _utcnow(), p_name),
        )
    except Exception:
        db.execute(
            """
            INSERT INTO bot_challenges (id, secret_word, ip_hash, status, max_tries, created_at)
            VALUES (%s, %s, %s, 'queued', %s, %s);
            """,
            (challenge_id, secret_word, ip_hash_value, int(max_tries), _utcnow()),
        )
    return challenge_id


def get_challenge(challenge_id: str, include_trajectory: bool = True) -> Optional[dict]:
    """Relit un défi par son identifiant (None si inconnu ou purgé).

    Par défaut `include_trajectory=True` charge la trajectoire complète (utile au SSE/replay).
    Si `include_trajectory=False`, la colonne JSONB volumineuse est omise pour les contrôles d'existence.
    """
    try:
        if include_trajectory:
            query = """
            SELECT id, secret_word, ip_hash, status, max_tries, tries_count,
                   duration_seconds, trajectory, error, heartbeat_at, started_at,
                   finished_at, created_at, player_name
            FROM bot_challenges
            WHERE id = %s;
            """
        else:
            query = """
            SELECT id, secret_word, ip_hash, status, max_tries, tries_count,
                   duration_seconds, error, heartbeat_at, started_at,
                   finished_at, created_at, player_name
            FROM bot_challenges
            WHERE id = %s;
            """
        row = db.fetch_one(query, (str(challenge_id),))
    except Exception:
        if include_trajectory:
            query = """
            SELECT id, secret_word, ip_hash, status, max_tries, tries_count,
                   duration_seconds, trajectory, error, heartbeat_at, started_at,
                   finished_at, created_at
            FROM bot_challenges
            WHERE id = %s;
            """
        else:
            query = """
            SELECT id, secret_word, ip_hash, status, max_tries, tries_count,
                   duration_seconds, error, heartbeat_at, started_at,
                   finished_at, created_at
            FROM bot_challenges
            WHERE id = %s;
            """
        row = db.fetch_one(query, (str(challenge_id),))
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


# --------------------------------------------------------------------------- #
# Traçage pérenne & KPIs analytiques des défis (M8, DEFI-02 / SEC-27)
# --------------------------------------------------------------------------- #
def anonymize_player_token(ip_hash_value: str) -> str:
    """Dérive un identifiant visiteur pseudonymisé et stable (ex: 'joueur_a1b2c3d4')."""
    token = hashlib.sha256(f"player_token|{ip_hash_value}".encode("utf-8")).hexdigest()[:10]
    return f"joueur_{token}"


def format_player_display(player_anon_id: str) -> str:
    """Formate un identifiant pseudonymisé pour l'affichage (ex: 'Visiteur #a1b2' ou pseudo réel)."""
    raw = str(player_anon_id or "").strip()
    if not raw:
        return "Visiteur #0000"
    if raw.startswith("joueur_"):
        token = raw.replace("joueur_", "")[:4]
        return f"Visiteur #{token}"
    return raw


def upgrade_player_challenges(legacy_anon_id: str, new_player_name: str) -> int:
    """Met à niveau les défis historiques rattachés au token IP vers le pseudonyme du joueur."""
    if not legacy_anon_id or not new_player_name:
        return 0
    cleaned = str(new_player_name).strip()[:32]
    if not cleaned or cleaned.startswith("joueur_") or cleaned.startswith("Visiteur #"):
        return 0
    query = """
    UPDATE bot_challenge_stats
    SET player_anon_id = %s
    WHERE player_anon_id = %s;
    """
    try:
        return db.execute(query, (cleaned, legacy_anon_id))
    except Exception:
        return 0


def record_challenge_stat(
    challenge_id: str,
    secret_word: str,
    ip_hash_value: str,
    outcome: str,
    tries_count: int,
    duration_seconds: Optional[float] = None,
    created_at: Optional[datetime] = None,
    player_name: Optional[str] = None,
) -> bool:
    """Enregistre un défi terminé dans les statistiques. Idempotent via ON CONFLICT DO NOTHING."""
    if player_name and str(player_name).strip():
        player_anon_id = str(player_name).strip()[:32]
    else:
        player_anon_id = anonymize_player_token(ip_hash_value)
    # Mapping outcome : 'solved' -> 'won', 'lost' -> 'lost', 'error' -> 'error'
    norm_outcome = "won" if outcome == "solved" else outcome
    created_val = created_at or _utcnow()

    query = """
    INSERT INTO bot_challenge_stats (
        challenge_id, secret_word, player_anon_id, outcome,
        tries_count, duration_seconds, created_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (challenge_id) DO NOTHING;
    """
    db.execute(
        query,
        (
            str(challenge_id),
            str(secret_word),
            str(player_anon_id),
            str(norm_outcome),
            int(tries_count),
            float(duration_seconds) if duration_seconds is not None else None,
            created_val,
        ),
    )
    return True


def save_challenge_guesses(challenge_id: str, guesses: list[dict]) -> int:
    """Enregistre les coups du chemin en base relationnelle avec ON CONFLICT DO NOTHING."""
    if not guesses:
        return 0
    query = """
    INSERT INTO bot_challenge_guesses (
        challenge_id, step_num, word, score, permille, weather, is_record, source
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (challenge_id, step_num) DO NOTHING;
    """
    inserted = 0
    with db.transaction() as conn:
        with closing(conn.cursor()) as cur:
            for idx, g in enumerate(guesses, start=1):
                step_num = g.get("step") if g.get("step") is not None else (g.get("step_num") if g.get("step_num") is not None else idx)
                q, p = db._format_query(query, (
                    str(challenge_id),
                    int(step_num),
                    str(g.get("word") or ""),
                    float(g.get("score") or 0.0),
                    int(g["permille"]) if g.get("permille") is not None else None,
                    str(g.get("weather") or "")[:8] or None,
                    bool(g.get("is_record", False)),
                    str(g.get("source") or "rag")[:16],
                ), db._determine_engine())
                cur.execute(q, p)
                inserted += 1
    return inserted


def get_challenge_guesses(challenge_id: str) -> list[dict]:
    """Relit le cheminement complet ordonné pour un défi donné."""
    query = """
    SELECT step_num, word, score, permille, weather, is_record, source
    FROM bot_challenge_guesses
    WHERE challenge_id = %s
    ORDER BY step_num ASC;
    """
    return db.fetch_all(query, (str(challenge_id),))


def get_challenge_stat(challenge_id: str) -> Optional[dict]:
    """Relit la ligne de statistique d'un défi par son identifiant."""
    query = """
    SELECT challenge_id, secret_word, player_anon_id, outcome, tries_count,
           duration_seconds, created_at
    FROM bot_challenge_stats
    WHERE challenge_id = %s;
    """
    return db.fetch_one(query, (str(challenge_id),))


def get_player_stats(player_ip_hash: Optional[str], player_name: Optional[str] = None) -> dict:
    """Bilan pseudonymisé d'un visiteur (M9) : le seul bloc non mis en cache."""
    cleaned_name = str(player_name).strip()[:32] if player_name else None
    if not player_ip_hash and not cleaned_name:
        return {"identified": False, "display_name": None, "total_played": 0,
                "player_wins": 0, "player_losses": 0, "player_win_rate_pct": 0.0}
    player_anon_id = anonymize_player_token(player_ip_hash) if player_ip_hash else None

    conds = []
    params = []
    if player_anon_id:
        conds.append("player_anon_id = %s")
        params.append(player_anon_id)
    if cleaned_name and cleaned_name != player_anon_id:
        conds.append("player_anon_id = %s")
        params.append(cleaned_name)

    where_sql = " OR ".join(conds)
    row = db.fetch_one(
        f"""
        SELECT
            COUNT(*) AS total_played,
            SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) AS player_wins,
            SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) AS player_losses
        FROM bot_challenge_stats
        WHERE {where_sql};
        """,
        tuple(params),
    ) or {}
    total = int(row.get("total_played") or 0)
    wins = int(row.get("player_wins") or 0)
    losses = int(row.get("player_losses") or 0)
    disp = cleaned_name or (format_player_display(player_anon_id) if player_anon_id else "Visiteur #0000")
    return {
        "identified": True,
        "display_name": disp,
        "total_played": total,
        "player_wins": wins,
        "player_losses": losses,
        "player_win_rate_pct": round((wins / total) * 100, 1) if total > 0 else 0.0,
    }


# --------------------------------------------------------------------------- #
# M9 — Synchronisation legacy, KPIs et Wall of Fame (WOF-01..06)
# --------------------------------------------------------------------------- #
_legacy_sync_done = False
_legacy_sync_lock = threading.Lock()


def reset_legacy_sync() -> None:
    """Réinitialise l'indicateur de synchronisation legacy (tests uniquement)."""
    global _legacy_sync_done
    with _legacy_sync_lock:
        _legacy_sync_done = False


def sync_legacy_challenges_to_stats(limit: int = 200, force: bool = False) -> int:
    """Rétro-remplit bot_challenge_stats et bot_challenge_guesses depuis bot_challenges
    pour tous les défis antérieurs non encore enregistrés dans les stats.
    Idempotent et exécuté une seule fois au démarrage (sauf si force=True).
    """
    global _legacy_sync_done
    if not force and _legacy_sync_done:
        return 0

    with _legacy_sync_lock:
        if not force and _legacy_sync_done:
            return 0
        try:
            try:
                rows = db.fetch_all(
                    """
                    SELECT id, secret_word, ip_hash, status, tries_count, duration_seconds, trajectory, created_at, player_name
                    FROM bot_challenges
                    WHERE status IN ('solved', 'won', 'lost')
                      AND id NOT IN (SELECT challenge_id FROM bot_challenge_stats)
                    ORDER BY created_at ASC
                    LIMIT %s;
                    """,
                    (int(limit),),
                )
            except Exception:
                rows = db.fetch_all(
                    """
                    SELECT id, secret_word, ip_hash, status, tries_count, duration_seconds, trajectory, created_at
                    FROM bot_challenges
                    WHERE status IN ('solved', 'won', 'lost')
                      AND id NOT IN (SELECT challenge_id FROM bot_challenge_stats)
                    ORDER BY created_at ASC
                    LIMIT %s;
                    """,
                    (int(limit),),
                )
        except Exception as exc:
            log(f"⚠️  [DÉFI] Erreur lecture défis historiques : {exc}", level="WARNING")
            return 0

        if not rows:
            _legacy_sync_done = True
            return 0

        count = 0
        for r in rows:
            try:
                cid = str(r["id"])
                word = str(r["secret_word"])
                status = str(r["status"])
                outcome = "won" if status in ("solved", "won") else status
                tries = int(r.get("tries_count") or 0)
                dur = float(r.get("duration_seconds")) if r.get("duration_seconds") is not None else None
                created = r.get("created_at")
                created_dt = None
                if isinstance(created, datetime):
                    created_dt = created
                elif isinstance(created, str) and created:
                    try:
                        clean_date = created.replace(" ", "T")
                        created_dt = datetime.fromisoformat(clean_date)
                    except Exception as err:
                        log(f"⚠️  [DÉFI] Format date invalide pour legacy {cid}: {err}", level="DEBUG")

                record_challenge_stat(
                    challenge_id=cid,
                    secret_word=word,
                    ip_hash_value=str(r.get("ip_hash") or ""),
                    outcome=outcome,
                    tries_count=tries,
                    duration_seconds=dur,
                    created_at=created_dt,
                    player_name=r.get("player_name"),
                )

                traj = r.get("trajectory")
                if isinstance(traj, str) and traj:
                    try:
                        traj = json.loads(traj)
                    except Exception:
                        traj = []
                if isinstance(traj, list) and traj:
                    save_challenge_guesses(cid, traj)
                count += 1
            except Exception as exc:
                log(f"⚠️  [DÉFI] Erreur sync défi legacy {r.get('id')}: {exc}", level="WARNING")

        _legacy_sync_done = True
        if count > 0:
            log(f"🔄  [DÉFI] {count} défi(s) historique(s) synchronisé(s) dans bot_challenge_stats.")
        return count


def get_wall_of_fame(limit: int = 12) -> list[dict]:
    """Derniers mots invaincus (`outcome = 'lost'`), du plus récent au plus ancien (M9)."""
    rows = db.fetch_all(
        """
        SELECT challenge_id, secret_word, player_anon_id, outcome, tries_count,
               duration_seconds, created_at
        FROM bot_challenge_stats
        WHERE outcome = 'lost'
        ORDER BY created_at DESC
        LIMIT %s;
        """,
        (int(limit),),
    )
    result = []
    for r in rows:
        created = r.get("created_at")
        date_str = created.isoformat() if isinstance(created, datetime) else str(created or "")
        dur = r.get("duration_seconds")
        result.append({
            "challenge_id": str(r["challenge_id"]),
            "secret_word": str(r["secret_word"]),
            "player": format_player_display(r["player_anon_id"]),
            "outcome": str(r.get("outcome") or "lost"),
            "tries_count": int(r["tries_count"]),
            "duration_seconds": round(float(dur), 1) if dur is not None else None,
            "date": date_str,
        })
    return result


def get_recent_challenges(limit: int = 20) -> list[dict]:
    """Derniers défis joués (victoires ET défaites), du plus récent au plus ancien."""
    rows = db.fetch_all(
        """
        SELECT challenge_id, secret_word, player_anon_id, outcome, tries_count,
               duration_seconds, created_at
        FROM bot_challenge_stats
        ORDER BY created_at DESC
        LIMIT %s;
        """,
        (int(limit),),
    )
    result = []
    for r in rows:
        created = r.get("created_at")
        date_str = created.isoformat() if isinstance(created, datetime) else str(created or "")
        dur = r.get("duration_seconds")
        result.append({
            "challenge_id": str(r["challenge_id"]),
            "secret_word": str(r["secret_word"]),
            "player": format_player_display(r["player_anon_id"]),
            "outcome": str(r.get("outcome") or "won"),
            "tries_count": int(r["tries_count"]),
            "duration_seconds": round(float(dur), 1) if dur is not None else None,
            "date": date_str,
        })
    return result


def get_challenge_kpis(player_ip_hash: Optional[str] = None, player_name: Optional[str] = None) -> dict:
    """Retourne la synthèse des KPIs globaux et les stats de la session courante."""
    sync_legacy_challenges_to_stats()
    row_counts = db.fetch_one(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) AS bot_wins,
            SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) AS bot_losses
        FROM bot_challenge_stats;
        """
    ) or {}
    total_challenges = int(row_counts.get("total") or 0)
    bot_wins = int(row_counts.get("bot_wins") or 0)
    bot_losses = int(row_counts.get("bot_losses") or 0)

    total_completed = bot_wins + bot_losses
    bot_win_rate_pct = round((bot_wins / total_completed) * 100, 1) if total_completed > 0 else 0.0
    player_win_rate_pct = round((bot_losses / total_completed) * 100, 1) if total_completed > 0 else 0.0

    row_tries = db.fetch_one(
        """
        SELECT
            AVG(tries_count) AS avg_tries,
            MIN(tries_count) AS min_tries,
            MAX(tries_count) AS max_tries
        FROM bot_challenge_stats
        WHERE outcome = 'won';
        """
    ) or {}
    if row_tries.get("avg_tries") is None and total_challenges > 0:
        row_tries = db.fetch_one(
            """
            SELECT
                AVG(tries_count) AS avg_tries,
                MIN(tries_count) AS min_tries,
                MAX(tries_count) AS max_tries
            FROM bot_challenge_stats;
            """
        ) or {}

    avg_tries = round(float(row_tries.get("avg_tries")), 1) if row_tries.get("avg_tries") is not None else 0.0
    min_tries = int(row_tries.get("min_tries")) if row_tries.get("min_tries") is not None else 0
    max_tries = int(row_tries.get("max_tries")) if row_tries.get("max_tries") is not None else 0

    rows_top = db.fetch_all(
        """
        SELECT
            secret_word AS word,
            COUNT(*) AS count,
            SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) AS bot_wins
        FROM bot_challenge_stats
        GROUP BY secret_word
        ORDER BY count DESC, bot_wins DESC
        LIMIT 5;
        """
    )
    top_words = [
        {
            "word": str(r["word"]),
            "count": int(r["count"]),
            "bot_wins": int(r.get("bot_wins") or 0),
        }
        for r in rows_top
    ]

    rows_tough = db.fetch_all(
        """
        SELECT
            secret_word AS word,
            tries_count AS tries,
            created_at AS date
        FROM bot_challenge_stats
        WHERE outcome = 'lost'
        ORDER BY created_at DESC
        LIMIT 5;
        """
    )
    tough_words = [
        {
            "word": str(r["word"]),
            "tries": int(r["tries"]),
            "date": str(r["date"])[:10],
        }
        for r in rows_tough
    ]

    rows_recent = db.fetch_all(
        """
        SELECT
            player_anon_id,
            secret_word AS word,
            outcome,
            tries_count AS tries,
            duration_seconds,
            created_at AS date
        FROM bot_challenge_stats
        ORDER BY created_at DESC
        LIMIT 10;
        """
    )
    recent_activity = []
    for r in rows_recent:
        created_raw = r.get("date")
        if isinstance(created_raw, datetime):
            date_str = created_raw.isoformat()
        else:
            date_str = str(created_raw or "")
        dur = r.get("duration_seconds")
        recent_activity.append({
            "player": format_player_display(r["player_anon_id"]),
            "word": str(r["word"]),
            "outcome": str(r["outcome"]),
            "tries": int(r["tries"]),
            "duration_seconds": round(float(dur), 1) if dur is not None else None,
            "date": date_str,
        })

    if player_ip_hash or player_name:
        player_data = get_player_stats(player_ip_hash, player_name)
    else:
        player_data = {
            "identified": False,
            "display_name": None,
            "total_played": 0,
            "player_wins": 0,
            "player_losses": 0,
            "player_win_rate_pct": 0.0,
        }

    return {
        "status": "ok",
        "global": {
            "total_challenges": total_challenges,
            "bot_wins": bot_wins,
            "bot_losses": bot_losses,
            "bot_win_rate_pct": bot_win_rate_pct,
            "player_win_rate_pct": player_win_rate_pct,
            "avg_tries": avg_tries,
            "min_tries": min_tries,
            "max_tries": max_tries,
            "top_words": top_words,
            "tough_words": tough_words,
            "recent_activity": recent_activity,
        },
        "player": player_data,
    }


