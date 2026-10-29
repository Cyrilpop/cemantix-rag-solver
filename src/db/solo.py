"""
Cémantix Solver — Persistance des Sessions Solo / Défi Libre (solo_sessions)
=============================================================================
Gère la persistance relationnelle et la reprise des parties individuelles (Solo).
"""
import time
from datetime import datetime, timezone
from typing import Any, Optional

from .connection import db


def save_solo_session_record(
    game_id: str,
    puzzle_id: str,
    difficulty: str,
    mode: str,
    secret_word: str,
    state: dict,
    created_at: Optional[Any] = None,
    updated_at: Optional[Any] = None,
) -> bool:
    """Enregistre ou met à jour une session solo en base de données."""
    now_iso = datetime.now(timezone.utc).isoformat()
    c_at = created_at or now_iso
    u_at = updated_at or now_iso

    query = """
    INSERT INTO solo_sessions (
        game_id, puzzle_id, difficulty, mode, secret_word, state, created_at, updated_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (game_id) DO UPDATE SET
        puzzle_id = EXCLUDED.puzzle_id,
        difficulty = EXCLUDED.difficulty,
        mode = EXCLUDED.mode,
        secret_word = EXCLUDED.secret_word,
        state = EXCLUDED.state,
        updated_at = EXCLUDED.updated_at;
    """
    params = (
        game_id,
        puzzle_id,
        difficulty,
        mode,
        secret_word,
        state,
        c_at,
        u_at,
    )
    db.execute(query, params)
    return True


def get_solo_session(game_id: str) -> Optional[dict]:
    """Récupère une session solo par son identifiant unique."""
    if not game_id:
        return None
    query = "SELECT * FROM solo_sessions WHERE game_id = %s;"
    return db.fetch_one(query, (game_id,))


def delete_solo_session(game_id: str) -> bool:
    """Supprime une session solo."""
    if not game_id:
        return False
    query = "DELETE FROM solo_sessions WHERE game_id = %s;"
    return db.execute(query, (game_id,)) > 0


def cleanup_old_solo(max_age_seconds: float = 86400.0) -> int:
    """Supprime les sessions inactives depuis plus de max_age_seconds (défaut : 24 heures)."""
    now = time.time()
    cutoff_dt = datetime.fromtimestamp(now - max_age_seconds, tz=timezone.utc).isoformat()
    query = "DELETE FROM solo_sessions WHERE updated_at < %s;"
    return db.execute(query, (cutoff_dt,))


def save_game_session(session) -> bool:
    """Sauvegarde directement une instance de GameSession en base de données."""
    state = {
        "guesses": session.guesses,
        "hints": session.hints,
        "is_won": session.is_won,
        "is_given_up": getattr(session, "is_given_up", False),
    }
    c_at = datetime.fromtimestamp(session.created_at, tz=timezone.utc).isoformat() if session.created_at else None
    u_at = datetime.fromtimestamp(session.last_activity, tz=timezone.utc).isoformat() if session.last_activity else None

    return save_solo_session_record(
        game_id=session.game_id,
        puzzle_id=session.puzzle_id,
        difficulty=session.difficulty,
        mode=session.mode,
        secret_word=session.secret,
        state=state,
        created_at=c_at,
        updated_at=u_at,
    )


def load_game_session(game_id: str, store) -> Optional[Any]:
    """Charge et reconstruit une GameSession depuis la base de données."""
    row = get_solo_session(game_id)
    if not row:
        return None

    from ..game.solo import GameSession

    state = row.get("state") or {}
    secret = row["secret_word"]
    if secret not in store:
        return None

    def _parse_ts(val):
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, datetime):
            return val.timestamp()
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val).timestamp()
            except Exception:
                return time.time()
        return time.time()

    created_at = _parse_ts(row.get("created_at"))
    last_activity = _parse_ts(row.get("updated_at"))

    session = GameSession(
        game_id=row["game_id"],
        mode=row.get("mode", "daily"),
        difficulty=row.get("difficulty", "moyen"),
        puzzle_id=row.get("puzzle_id", "--"),
        secret=secret,
        store=store,
    )
    session.created_at = created_at
    session.last_activity = last_activity
    session.is_won = bool(state.get("is_won", False))
    session.is_given_up = bool(state.get("is_given_up", False))
    session.guesses = state.get("guesses", {})
    session.hints = state.get("hints", [])
    return session
