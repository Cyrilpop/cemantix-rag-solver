"""
Cémantix Solver — Persistance des Puzzles Quotidiens (daily_puzzles)
====================================================================
Gère la persistance relationnelle et la consultation des résolutions
du mot du jour par le solveur RAG / Démon 24h/24.
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional

from .connection import db

# Nombre de résolutions chargées par défaut (PERF-04). Le tableau de bord relit
# l'historique à chaque rafraîchissement : sans borne, le coût suit la croissance
# de la table, `trajectory` compris. 400 ≈ un an de puzzles quotidiens.
HISTORY_DEFAULT_LIMIT = int(os.getenv("HISTORY_LIMIT", "400"))


def _row_to_entry(row: dict) -> dict:
    """Harmonise le format de la ligne SQL avec le format historique attendu par web.py et daemon.py."""
    raw_guesses = row.get("top_guesses")
    if isinstance(raw_guesses, str):
        try:
            raw_guesses = json.loads(raw_guesses)
        except Exception:
            raw_guesses = []
    top_guesses = raw_guesses if isinstance(raw_guesses, list) else []

    raw_trajectory = row.get("trajectory")
    if isinstance(raw_trajectory, str):
        try:
            raw_trajectory = json.loads(raw_trajectory)
        except Exception:
            raw_trajectory = []
    trajectory = raw_trajectory if isinstance(raw_trajectory, list) else []

    return {
        "date": str(row["date"]),
        "puzzle": row["puzzle_id"],
        "word": row["secret_word"],
        "tries": row["tries_count"],
        "attempts": row["attempts_count"],
        "source": row.get("source", "rag"),
        "win": bool(row.get("win", True)),
        "duration_seconds": float(row["duration_seconds"]) if row.get("duration_seconds") is not None else 0.0,
        "top_guesses": top_guesses,
        "trajectory": trajectory,
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



def get_history_summary() -> Optional[dict]:
    """Calcule les métriques globales d'agrégation directement en SQL (PERF-04)."""
    query = """
    SELECT
        COUNT(*) FILTER (WHERE win = TRUE) as total_solved,
        COUNT(*) as total_count,
        ROUND(AVG(tries_count) FILTER (WHERE win = TRUE)::numeric, 1) as avg_tries,
        ROUND(AVG(duration_seconds) FILTER (WHERE win = TRUE AND duration_seconds > 0)::numeric, 2) as avg_duration,
        MIN(tries_count) FILTER (WHERE win = TRUE) as fastest_tries,
        MIN(duration_seconds) FILTER (WHERE win = TRUE AND duration_seconds > 0) as fastest_duration
    FROM daily_puzzles;
    """
    try:
        row = db.fetch_one(query)
        if not row or row.get("total_count", 0) == 0:
            return None
        total_solved = int(row.get("total_solved") or 0)
        total_count = int(row.get("total_count") or 0)
        win_rate = round((total_solved / total_count * 100), 1) if total_count > 0 else 100.0
        return {
            "total_solved": total_solved,
            "avg_tries": float(row.get("avg_tries") or 0.0),
            "avg_duration_seconds": float(row.get("avg_duration") or 0.0),
            "fastest_tries": int(row.get("fastest_tries") or 0),
            "fastest_duration_seconds": float(row.get("fastest_duration") or 0.0),
            "win_rate": win_rate,
        }
    except Exception:
        # Repli si la base est vide ou SQLite sans support FILTER
        return None


def get_all_daily_puzzles(
    limit: Optional[int] = None,
    include_trajectory: bool = True,
) -> list[dict]:
    """Récupère l'historique des résolutions quotidiennes, du plus récent au plus ancien.

    La limite par défaut (HISTORY_LIMIT, 400 résolutions) borne la charge.
    Par défaut, `include_trajectory=False` n'inclut pas la colonne JSONB lourde
    `trajectory` dans les listes globales pour économiser la mémoire et le réseau (PERF-04).
    """
    if limit is None:
        limit = HISTORY_DEFAULT_LIMIT

    is_sqlite = db.get_engine_type() == "sqlite"
    cols = "*" if include_trajectory else ("date, puzzle_id, secret_word, tries_count, attempts_count, source, duration_seconds, win, top_guesses, '[]' as trajectory, is_revealed, solved_at" if is_sqlite else "date, puzzle_id, secret_word, tries_count, attempts_count, source, duration_seconds, win, top_guesses, '[]'::jsonb as trajectory, is_revealed, solved_at")

    if limit and limit > 0:
        rows = db.fetch_all(
            f"SELECT {cols} FROM daily_puzzles ORDER BY date DESC, puzzle_id DESC LIMIT %s;",
            (int(limit),),
        )
    else:
        rows = db.fetch_all(
            f"SELECT {cols} FROM daily_puzzles ORDER BY date DESC, puzzle_id DESC;"
        )
    return [_row_to_entry(r) for r in rows]


def save_daily_hints(puzzle_date: str, hints: list[dict]) -> int:
    """Insère ou met à jour un lot d'indices."""
    query = """
    INSERT INTO daily_puzzle_hints (puzzle_date, tier, word, score, is_revealed)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (puzzle_date, word) DO UPDATE SET
        score = EXCLUDED.score,
        tier = EXCLUDED.tier,
        is_revealed = EXCLUDED.is_revealed;
    """
    inserted = 0
    with db.transaction() as conn:
        for hint in hints:
            q, p = db._format_query(query, (
                str(puzzle_date),
                str(hint["tier"]),
                str(hint["word"]),
                float(hint["score"]),
                bool(hint.get("is_revealed", False))
            ), db._determine_engine())
            conn.execute(q, p)
            inserted += 1
    return inserted


def get_daily_hints(puzzle_date: str, revealed_only: bool = True) -> list[dict]:
    """Récupère les indices d'un puzzle quotidien, triés par score décroissant."""
    if revealed_only:
        query = "SELECT * FROM daily_puzzle_hints WHERE puzzle_date = %s AND is_revealed = %s ORDER BY score DESC;"
        return db.fetch_all(query, (str(puzzle_date), True))
    query = "SELECT * FROM daily_puzzle_hints WHERE puzzle_date = %s ORDER BY score DESC;"
    return db.fetch_all(query, (str(puzzle_date),))


def reveal_daily_hint_tier(puzzle_date: str, tier: str) -> int:
    """Passe is_revealed à True pour un palier spécifique."""
    query = "UPDATE daily_puzzle_hints SET is_revealed = %s WHERE puzzle_date = %s AND tier = %s;"
    return db.execute(query, (True, str(puzzle_date), str(tier)))


def backfill_daily_puzzles_from_json(filepath: Optional[object] = None) -> int:
    """Rattrapage idempotent de daily_puzzles depuis l'historique JSON.

    Charge le fichier JSON (par défaut cemantix_data/daily_history.json)
    et insère tous les puzzles absents de la table daily_puzzles.
    Retourne le nombre de puzzles nouvellement insérés.
    """
    import json
    from pathlib import Path
    from ..config import DATA_DIR, log

    json_path = Path(str(filepath)) if filepath else (DATA_DIR / "daily_history.json")
    if not json_path.exists():
        return 0

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        if not isinstance(entries, list):
            return 0
    except Exception as e:
        log(f"⚠️  [DB] Impossible de lire {json_path} pour le rattrapage : {e}")
        return 0

    try:
        rows = db.fetch_all("SELECT date FROM daily_puzzles;")
        existing_dates = {str(r["date"]) for r in rows}
    except Exception as e:
        log(f"⚠️  [DB] Erreur lecture daily_puzzles pour vérification : {e}")
        existing_dates = set()

    missing = [
        e for e in entries
        if str(e.get("date")) not in existing_dates and (e.get("word") or "").strip()
    ]
    if not missing:
        return 0

    log(f"🧩  [DB] Rattrapage SQL de {len(missing)} puzzle(s) depuis {json_path.name}...")
    inserted_count = 0
    for entry in missing:
        if save_daily_puzzle(entry):
            inserted_count += 1

    log(f"✨  [DB] Rattrapage SQL achevé : {inserted_count} puzzle(s) importé(s) dans daily_puzzles.")
    return inserted_count


