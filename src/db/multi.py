"""
Cémantix Solver — Persistance des Salons Multijoueurs (multi_rooms)
===================================================================
Gère la persistance relationnelle, les mises à jour atomiques et le cycle de vie
des parties 1v1 multijoueurs (Même Mot ou Mots Choisis).
"""
import os
import hmac
import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Optional

from .connection import db

SECRET_KEY = os.getenv("SECRET_KEY", "cemantix_default_hmac_secret_key").encode("utf-8")


def hash_player_key(raw_key: str) -> str:
    """Calcule le hash HMAC-SHA256 d'une clé joueur pour stockage sécurisé (SEC-05b)."""
    if not raw_key:
        return ""
    # Si la clé est déjà un hash hexadécimal HMAC (64 caractères hex préfixés par 'hmac:'), on la conserve
    if raw_key.startswith("hmac:"):
        return raw_key
    k_norm = raw_key.strip().upper().encode("utf-8")
    sig = hmac.new(SECRET_KEY, k_norm, hashlib.sha256).hexdigest()
    return f"hmac:{sig}"


def verify_player_key(raw_key: str, stored_hash_or_key: str) -> bool:
    """Vérifie si une clé fournie correspond au hash HMAC stocké ou à l'ancienne clé en clair."""
    if not raw_key or not stored_hash_or_key:
        return False
    # Vérification rétrocompatible : ancienne clé en clair ou hash HMAC
    if stored_hash_or_key.startswith("hmac:"):
        expected = hash_player_key(raw_key)
        return hmac.compare_digest(expected, stored_hash_or_key)
    # Rétrocompatibilité avec les anciennes clés en clair existantes
    return hmac.compare_digest(raw_key.strip().upper(), stored_hash_or_key.strip().upper())


def save_room(
    room_id: str,
    mode: str,
    difficulty: str,
    state: str,
    player1_key: str,
    player2_key: str,
    current_turn: str,
    winner: Optional[str],
    p1_data: dict,
    p2_data: dict,
    created_at: Optional[Any] = None,
    updated_at: Optional[Any] = None,
) -> bool:
    """Enregistre ou met à jour de manière atomique un salon multijoueur."""
    now_iso = datetime.now(timezone.utc).isoformat()
    c_at = created_at or now_iso
    u_at = updated_at or now_iso

    query = """
    INSERT INTO multi_rooms (
        room_id, mode, difficulty, state, player1_key, player2_key,
        current_turn, winner, p1_data, p2_data, created_at, updated_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (room_id) DO UPDATE SET
        mode = EXCLUDED.mode,
        difficulty = EXCLUDED.difficulty,
        state = EXCLUDED.state,
        player1_key = EXCLUDED.player1_key,
        player2_key = EXCLUDED.player2_key,
        current_turn = EXCLUDED.current_turn,
        winner = EXCLUDED.winner,
        p1_data = EXCLUDED.p1_data,
        p2_data = EXCLUDED.p2_data,
        updated_at = EXCLUDED.updated_at;
    """
    params = (
        room_id.strip().upper(),
        mode,
        difficulty,
        state,
        player1_key,
        player2_key,
        current_turn,
        winner,
        p1_data,
        p2_data,
        c_at,
        u_at,
    )
    db.execute(query, params)
    return True


def get_room(room_id: str) -> Optional[dict]:
    """Récupère un salon multijoueur par son code (ex: DUEL-XXXX)."""
    if not room_id:
        return None
    query = "SELECT * FROM multi_rooms WHERE room_id = %s;"
    return db.fetch_one(query, (room_id.strip().upper(),))


def delete_room(room_id: str) -> bool:
    """Supprime un salon multijoueur."""
    if not room_id:
        return False
    query = "DELETE FROM multi_rooms WHERE room_id = %s;"
    return db.execute(query, (room_id.strip().upper(),)) > 0


def cleanup_old_rooms(max_age_seconds: float = 7 * 86400.0) -> int:
    """Supprime les salons inactifs depuis plus de max_age_seconds (défaut : 7 jours)."""
    now = time.time()
    cutoff_dt = datetime.fromtimestamp(now - max_age_seconds, tz=timezone.utc).isoformat()
    query = "DELETE FROM multi_rooms WHERE updated_at < %s;"
    return db.execute(query, (cutoff_dt,))


def save_multiplayer_session(session) -> bool:
    """Persiste une instance de MultiplayerSession directement en base relationnelle."""
    p1_data = {
        "name": session.p1_name,
        "target": session.target_for_p1,
        "guesses": session.p1_guesses,
        "hints_used": session.p1_hints_used,
        "turn_no": session.turn_no,
    }
    p2_data = {
        "name": session.p2_name,
        "target": session.target_for_p2,
        "guesses": session.p2_guesses,
        "hints_used": session.p2_hints_used,
        "p2_joined": session.p2_joined,
    }

    c_at = datetime.fromtimestamp(session.created_at, tz=timezone.utc).isoformat() if session.created_at else None
    u_at = datetime.fromtimestamp(session.last_activity, tz=timezone.utc).isoformat() if session.last_activity else None

    return save_room(
        room_id=session.room_id,
        mode=session.mode,
        difficulty=session.difficulty,
        state=session.state,
        player1_key=hash_player_key(session.key_p1),
        player2_key=hash_player_key(session.key_p2),
        current_turn=session.current_turn,
        winner=session.winner,
        p1_data=p1_data,
        p2_data=p2_data,
        created_at=c_at,
        updated_at=u_at,
    )


def load_multiplayer_session(room_id: str, store) -> Optional[Any]:
    """Charge et reconstruit une MultiplayerSession depuis la base de données."""
    row = get_room(room_id)
    if not row:
        return None

    from ..game.multi import MultiplayerSession

    p1_data = row.get("p1_data") or {}
    p2_data = row.get("p2_data") or {}

    # Conversion timestamps
    c_raw = row.get("created_at")
    u_raw = row.get("updated_at")

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

    created_at = _parse_ts(c_raw)
    last_activity = _parse_ts(u_raw)

    session = MultiplayerSession(
        room_id=row["room_id"],
        mode=row.get("mode", "same_word"),
        difficulty=row.get("difficulty", "moyen"),
        store=store,
        key_p1=row.get("player1_key"),
        key_p2=row.get("player2_key"),
        target_for_p1=p1_data.get("target"),
        target_for_p2=p2_data.get("target"),
        p1_name=p1_data.get("name", "Joueur 1"),
        p2_name=p2_data.get("name", "Joueur 2"),
        current_turn=row.get("current_turn", "p1"),
        turn_no=p1_data.get("turn_no", 0),
        winner=row.get("winner"),
        is_finished=(row.get("state") == "finished" or bool(row.get("winner"))),
        p1_guesses=p1_data.get("guesses", {}),
        p2_guesses=p2_data.get("guesses", {}),
        p1_hints_used=p1_data.get("hints_used", []),
        p2_hints_used=p2_data.get("hints_used", []),
        p2_joined=bool(p2_data.get("p2_joined", False)),
        state=row.get("state"),
        created_at=created_at,
        last_activity=last_activity,
    )
    return session
