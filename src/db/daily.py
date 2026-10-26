"""
Cémantix Solver — Persistance des Puzzles Quotidiens (daily_puzzles)
====================================================================
Gère la persistance relationnelle et la consultation des résolutions
du mot du jour par le solveur RAG / Démon 24h/24.
"""
from datetime import datetime, timezone
from typing import Optional

from .connection import db


def _row_to_entry(row: dict) -> dict:
    """Harmonise le format de la ligne SQL avec le format historique attendu par web.py et daemon.py."""
    return {
        "date": str(row["date"]),
        "puzzle": row["puzzle_id"],
        "word": row["secret_word"],
        "tries": row["tries_count"],
        "attempts": row["attempts_count"],
        "source": row.get("source", "rag"),
        "win": bool(row.get("win", True)),
        "duration_seconds": float(row["duration_seconds"]) if row.get("duration_seconds") is not None else 0.0,
        "top_guesses": row.get("top_guesses") if isinstance(row.get("top_guesses"), list) else [],
        "trajectory": row.get("trajectory") if isinstance(row.get("trajectory"), list) else [],
        "is_revealed": bool(row.get("is_revealed", False)),
        "timestamp": str(row["solved_at"]) if row.get("solved_at") else "",
    }


def save_daily_puzzle(entry: dict) -> bool:
    """Enregistre ou met à jour la résolution quotidienne dans daily_puzzles."""
    date_val = str(entry.get("date", ""))
    puzzle_id = int(entry.get("puzzle") or entry.get("puzzle_id") or 0)
    secret_word = str(entry.get("word") or entry.get("secret_word") or "").strip().lower()
    tries_count = int(entry.get("tries") or entry.get("tries_count") or 0)
    attempts_count = int(entry.get("attempts") or entry.get("attempts_count") or tries_count)
    source = str(entry.get("source") or "rag")
    duration_seconds = float(entry.get("duration_seconds") or entry.get("time") or 0.0)
    win = bool(entry.get("win", True))
    top_guesses = entry.get("top_guesses") or []
    trajectory = entry.get("trajectory") or []
    is_revealed = bool(entry.get("is_revealed", False))
    solved_at = entry.get("timestamp") or entry.get("solved_at") or datetime.now(timezone.utc).isoformat()

    query = """
    INSERT INTO daily_puzzles (
        date, puzzle_id, secret_word, tries_count, attempts_count,
        source, duration_seconds, win, top_guesses, trajectory,
        is_revealed, solved_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (date) DO UPDATE SET
        puzzle_id = EXCLUDED.puzzle_id,
        secret_word = EXCLUDED.secret_word,
        tries_count = EXCLUDED.tries_count,
        attempts_count = EXCLUDED.attempts_count,
        source = EXCLUDED.source,
        duration_seconds = EXCLUDED.duration_seconds,
        win = EXCLUDED.win,
        top_guesses = EXCLUDED.top_guesses,
        trajectory = EXCLUDED.trajectory,
        is_revealed = EXCLUDED.is_revealed,
        solved_at = EXCLUDED.solved_at;
    """
    params = (
        date_val, puzzle_id, secret_word, tries_count, attempts_count,
        source, duration_seconds, win, top_guesses, trajectory,
        is_revealed, solved_at,
    )
    db.execute(query, params)
    return True


def get_daily_puzzle(date: str) -> Optional[dict]:
    """Récupère une résolution quotidienne par sa date (YYYY-MM-DD)."""
    query = "SELECT * FROM daily_puzzles WHERE date = %s;"
    row = db.fetch_one(query, (str(date),))
    if not row:
        return None
    return _row_to_entry(row)


def get_latest_daily_puzzle(winning_only: bool = True) -> Optional[dict]:
    """Récupère la plus récente résolution quotidienne enregistrée."""
    if winning_only:
        query = "SELECT * FROM daily_puzzles WHERE win = TRUE ORDER BY date DESC, puzzle_id DESC LIMIT 1;"
    else:
        query = "SELECT * FROM daily_puzzles ORDER BY date DESC, puzzle_id DESC LIMIT 1;"
    row = db.fetch_one(query)
    if not row:
        return None
    return _row_to_entry(row)



def get_all_daily_puzzles(limit: Optional[int] = None) -> list[dict]:
    """Récupère l'ensemble de l'historique des résolutions quotidiennes."""
    if limit and limit > 0:
        query = f"SELECT * FROM daily_puzzles ORDER BY date DESC, puzzle_id DESC LIMIT {int(limit)};"
    else:
        query = "SELECT * FROM daily_puzzles ORDER BY date DESC, puzzle_id DESC;"
    rows = db.fetch_all(query)
    return [_row_to_entry(r) for r in rows]
