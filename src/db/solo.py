"""
Cémantix Solver — Persistance des Sessions Solo / Défi Libre (solo_sessions)
=============================================================================
Gère la persistance relationnelle et la reprise des parties individuelles (Solo).
"""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .connection import db


def _to_json_param(val: Any) -> Any:
    """Sérialise proprement un conteneur Python en JSON/JSONB selon l'engine actif."""
    engine = db.get_engine_type()
    if engine == "postgres":
        try:
            from psycopg.types.json import Jsonb
            return Jsonb(val)
        except Exception:
            return json.dumps(val)
    return json.dumps(val)


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
        _to_json_param(state),
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
    """Supprime les sessions libres inactives depuis plus de max_age_seconds (défaut : 24 heures).
    
    Les sessions en mode 'daily' ne sont JAMAIS purgées pour la journée en cours.
    """
    now = time.time()
    cutoff_dt = datetime.fromtimestamp(now - max_age_seconds, tz=timezone.utc).isoformat()
    query = "DELETE FROM solo_sessions WHERE mode != 'daily' AND updated_at < %s;"
    return db.execute(query, (cutoff_dt,))


def save_game_session(session) -> bool:
    """Sauvegarde directement une instance de GameSession en base de données."""
    state = {
        "guesses": session.guesses,
        "hints": session.hints,
        "hints_revealed": getattr(session, "hints_revealed", []),
        "is_won": session.is_won,
        "is_given_up": getattr(session, "is_given_up", False),
        "puzzle_date": getattr(session, "puzzle_date", None),
        "player_id": getattr(session, "player_id", None),
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

    state = _parse_json_field(row.get("state"), {})
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
        puzzle_date=state.get("puzzle_date") or row.get("puzzle_id"),
    )
    session.created_at = created_at
    session.last_activity = last_activity
    session.is_won = bool(state.get("is_won", False))
    session.is_given_up = bool(state.get("is_given_up", False))
    session.guesses = state.get("guesses", {})
    session.hints = state.get("hints", [])
    session.hints_revealed = state.get("hints_revealed", [])
    session.player_id = state.get("player_id") or row.get("player_id")
    return session


# =============================================================================
# M15: Mot du Jour Solo Aléatoire, Classement & Indices IA Roulants
# =============================================================================


def _parse_json_field(val: Any, default: Any) -> Any:
    """Décode un champ JSON en structure Python compatible Postgres/SQLite."""
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return default
    return default


def _row_to_puzzle(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "puzzle_date": str(row.get("puzzle_date") or ""),
        "secret_word": str(row.get("secret_word") or ""),
        "difficulty": str(row.get("difficulty") or "normal"),
        "players_attempted": int(row.get("players_attempted") or 0),
        "players_succeeded": int(row.get("players_succeeded") or 0),
        "players_failed": int(row.get("players_failed") or 0),
        "bots_simulated": bool(row.get("bots_simulated", False)),
        "bots_simulated_at": str(row.get("bots_simulated_at") or "") if row.get("bots_simulated_at") else None,
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


def _row_to_player_game(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    return {
        "id": str(row.get("id") or ""),
        "puzzle_date": str(row.get("puzzle_date") or ""),
        "player_id": str(row.get("player_id") or ""),
        "status": str(row.get("status") or "in_progress"),
        "tries_count": int(row.get("tries_count") or 0),
        "hints_used": int(row.get("hints_used") or 0),
        "hints_revealed": _parse_json_field(row.get("hints_revealed"), []),
        "best_score": float(row.get("best_score") or 0.0),
        "best_permille": int(row["best_permille"]) if row.get("best_permille") is not None else None,
        "duration_seconds": float(row.get("duration_seconds") or 0.0),
        "is_bot": bool(row.get("is_bot", False)),
        "won_at": str(row.get("won_at") or "") if row.get("won_at") else None,
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


def get_or_create_solo_daily_puzzle(
    puzzle_date: str, secret_word: str, difficulty: str
) -> dict:
    """Récupère ou crée l'énigme solo quotidienne du jour de manière idempotente."""
    existing = get_solo_daily_puzzle(puzzle_date)
    if existing:
        return existing

    engine = db.get_engine_type()
    if engine == "postgres":
        query = """
        INSERT INTO solo_daily_puzzles (puzzle_date, secret_word, difficulty, created_at, updated_at)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (puzzle_date) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
        """
    else:
        query = """
        INSERT INTO solo_daily_puzzles (puzzle_date, secret_word, difficulty, created_at, updated_at)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(puzzle_date) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
        """
    db.execute(query, (puzzle_date, secret_word.strip().lower(), difficulty.strip().lower()))
    puzzle = get_solo_daily_puzzle(puzzle_date)
    if not puzzle:
        raise RuntimeError(f"Impossible de créer ou récupérer le puzzle solo du {puzzle_date}")
    return puzzle


def get_solo_daily_puzzle(puzzle_date: str) -> Optional[dict]:
    """Récupère l'énigme solo du jour par sa date (YYYY-MM-DD)."""
    if not puzzle_date:
        return None
    row = db.fetch_one(
        "SELECT * FROM solo_daily_puzzles WHERE puzzle_date = %s",
        (str(puzzle_date),),
    )
    return _row_to_puzzle(row)


def update_solo_puzzle_stats(
    puzzle_date: str,
    attempted_inc: int = 0,
    succeeded_inc: int = 0,
    failed_inc: int = 0,
) -> None:
    """Incrémente atomiquement les compteurs de joueurs sur l'énigme quotidienne."""
    if not puzzle_date:
        return
    query = """
    UPDATE solo_daily_puzzles
    SET players_attempted = players_attempted + %s,
        players_succeeded = players_succeeded + %s,
        players_failed = players_failed + %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE puzzle_date = %s
    """
    db.execute(query, (attempted_inc, succeeded_inc, failed_inc, str(puzzle_date)))


def is_solo_bots_simulated(puzzle_date: str) -> bool:
    """Vérifie si la simulation de 6h30 a déjà été exécutée pour la date donnée."""
    if not puzzle_date:
        return False
    row = db.fetch_one(
        "SELECT bots_simulated FROM solo_daily_puzzles WHERE puzzle_date = %s",
        (str(puzzle_date),),
    )
    return bool(row.get("bots_simulated", False)) if row else False


def lock_solo_bots_simulated(puzzle_date: str) -> bool:
    """Active le verrou d'idempotence des faux joueurs pour la journée."""
    if not puzzle_date:
        return False
    engine = db.get_engine_type()
    true_val = True if engine == "postgres" else 1
    query = """
    UPDATE solo_daily_puzzles
    SET bots_simulated = %s,
        bots_simulated_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE puzzle_date = %s
    """
    return db.execute(query, (true_val, str(puzzle_date))) > 0


def clear_solo_bots_simulated(puzzle_date: str) -> bool:
    """Réinitialise le verrou pour permettre une réexécution forcée (--force)."""
    if not puzzle_date:
        return False
    engine = db.get_engine_type()
    false_val = False if engine == "postgres" else 0
    query = """
    UPDATE solo_daily_puzzles
    SET bots_simulated = %s,
        bots_simulated_at = NULL,
        updated_at = CURRENT_TIMESTAMP
    WHERE puzzle_date = %s
    """
    return db.execute(query, (false_val, str(puzzle_date))) > 0


def save_solo_ai_hints(puzzle_date: str, hints: list[dict]) -> None:
    """Persiste les 3 indices IA (mot + phrase) pour le puzzle solo du jour."""
    if not puzzle_date or not hints:
        return
    engine = db.get_engine_type()
    for h in hints:
        level = int(h.get("hint_level") or h.get("level") or 1)
        weight = float(h.get("weight") or 1.0)
        word = str(h.get("hint_word") or h.get("word") or "").strip().lower()
        phrase = str(h.get("hint_phrase") or h.get("phrase") or "").strip()
        score = float(h.get("score") or 0.0)
        permille = h.get("permille")
        if permille is not None:
            permille = int(permille)

        if engine == "postgres":
            query = """
            INSERT INTO solo_daily_ai_hints (
                puzzle_date, hint_level, weight, hint_word, hint_phrase, score, permille, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (puzzle_date, hint_level) DO UPDATE SET
                weight = EXCLUDED.weight,
                hint_word = EXCLUDED.hint_word,
                hint_phrase = EXCLUDED.hint_phrase,
                score = EXCLUDED.score,
                permille = EXCLUDED.permille
            """
        else:
            query = """
            INSERT INTO solo_daily_ai_hints (
                puzzle_date, hint_level, weight, hint_word, hint_phrase, score, permille, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT(puzzle_date, hint_level) DO UPDATE SET
                weight = EXCLUDED.weight,
                hint_word = EXCLUDED.hint_word,
                hint_phrase = EXCLUDED.hint_phrase,
                score = EXCLUDED.score,
                permille = EXCLUDED.permille
            """
        db.execute(query, (str(puzzle_date), level, weight, word, phrase, score, permille))


def get_solo_ai_hints(puzzle_date: str) -> list[dict]:
    """Récupère les indices IA enregistrés pour la date donnée, ordonnés par niveau."""
    if not puzzle_date:
        return []
    rows = db.fetch_all(
        """
        SELECT * FROM solo_daily_ai_hints
        WHERE puzzle_date = %s
        ORDER BY hint_level ASC
        """,
        (str(puzzle_date),),
    )
    res = []
    for r in rows or []:
        res.append({
            "id": r.get("id"),
            "puzzle_date": str(r.get("puzzle_date")),
            "hint_level": int(r.get("hint_level")),
            "weight": float(r.get("weight") or 1.0),
            "hint_word": str(r.get("hint_word") or ""),
            "hint_phrase": str(r.get("hint_phrase") or ""),
            "score": float(r.get("score") or 0.0),
            "permille": int(r["permille"]) if r.get("permille") is not None else None,
            "created_at": str(r.get("created_at") or ""),
        })
    return res


def purge_old_solo_ai_hints(before_date: str) -> int:
    """Supprime les indices IA des jours strictement antérieurs à before_date (rétention 1j)."""
    if not before_date:
        return 0
    query = "DELETE FROM solo_daily_ai_hints WHERE puzzle_date < %s"
    return db.execute(query, (str(before_date),))


def get_or_create_solo_player_game(
    puzzle_date: str, player_id: str, is_bot: bool = False
) -> dict:
    """Récupère ou initialise la session quotidienne d'un joueur."""
    existing = get_solo_player_game(puzzle_date, player_id)
    if existing:
        return existing

    new_id = str(uuid.uuid4())
    engine = db.get_engine_type()
    bot_val = True if engine == "postgres" else (1 if is_bot else 0)
    if engine == "postgres":
        bot_val = bool(is_bot)

    query = """
    INSERT INTO solo_player_games (
        id, puzzle_date, player_id, status, tries_count, hints_used, hints_revealed,
        best_score, best_permille, duration_seconds, is_bot, created_at, updated_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """
    empty_hints = _to_json_param([])
    db.execute(
        query,
        (
            new_id,
            str(puzzle_date),
            str(player_id),
            "in_progress",
            0,
            0,
            empty_hints,
            0.0,
            None,
            0.0,
            bot_val,
        ),
    )
    game = get_solo_player_game(puzzle_date, player_id)
    if not game:
        raise RuntimeError(f"Échec de création du player_game {player_id} au {puzzle_date}")
    return game


def get_solo_player_game(puzzle_date: str, player_id: str) -> Optional[dict]:
    """Récupère la session d'un joueur pour une énigme quotidienne donnée."""
    if not puzzle_date or not player_id:
        return None
    row = db.fetch_one(
        "SELECT * FROM solo_player_games WHERE puzzle_date = %s AND player_id = %s",
        (str(puzzle_date), str(player_id)),
    )
    return _row_to_player_game(row)


def get_solo_player_game_by_id(game_id: str) -> Optional[dict]:
    """Récupère une session de jeu solo par son UUID."""
    if not game_id:
        return None
    row = db.fetch_one(
        "SELECT * FROM solo_player_games WHERE id = %s",
        (str(game_id),),
    )
    return _row_to_player_game(row)


def record_solo_hint_revealed(
    puzzle_date: str,
    player_id: str,
    hint_level: int,
    hint_type: str,
    content: str,
    score: float = 0.0,
    permille: Optional[int] = None,
) -> dict:
    """Enregistre un indice dévoilé (mot ou phrase) pour ce joueur et incrémente tries_count et hints_used."""
    game = get_or_create_solo_player_game(puzzle_date, player_id)
    revealed = list(game.get("hints_revealed") or [])

    # Vérification anti-doublon pour ce palier
    for rev in revealed:
        if rev.get("level") == hint_level:
            return game  # Déjà révélé, immuable

    revealed.append({
        "level": hint_level,
        "type": hint_type,
        "content": content,
        "score": score,
        "permille": permille,
        "revealed_at": datetime.now(timezone.utc).isoformat(),
    })

    new_hints_used = game.get("hints_used", 0) + 1
    new_tries_count = game.get("tries_count", 0) + 1

    query = """
    UPDATE solo_player_games
    SET hints_revealed = %s,
        hints_used = %s,
        tries_count = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s
    """
    db.execute(query, (_to_json_param(revealed), new_hints_used, new_tries_count, game["id"]))
    updated = get_solo_player_game_by_id(game["id"])
    return updated or game


def finish_solo_player_game(
    puzzle_date: str,
    player_id: str,
    status: str,
    tries_count: int,
    duration_seconds: float,
    best_score: float,
    best_permille: Optional[int],
    guesses: list[dict],
    is_bot: bool = False,
    hints_revealed: Optional[list[dict]] = None,
    hints_used: Optional[int] = None,
) -> dict:
    """Clôture une partie solo (won ou given_up) et persiste sa trajectoire complète."""
    game = get_or_create_solo_player_game(puzzle_date, player_id, is_bot=is_bot)
    game_id = game["id"]

    won_at_clause = "CURRENT_TIMESTAMP" if status == "won" else "NULL"
    if hints_revealed is not None:
        hints_json = _to_json_param(hints_revealed)
        h_count = hints_used if hints_used is not None else len(hints_revealed)
        query = f"""
        UPDATE solo_player_games
        SET status = %s,
            tries_count = %s,
            duration_seconds = %s,
            best_score = %s,
            best_permille = %s,
            hints_revealed = %s,
            hints_used = %s,
            won_at = {won_at_clause},
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        db.execute(
            query,
            (status, tries_count, duration_seconds, best_score, best_permille, hints_json, h_count, game_id),
        )
    else:
        query = f"""
        UPDATE solo_player_games
        SET status = %s,
            tries_count = %s,
            duration_seconds = %s,
            best_score = %s,
            best_permille = %s,
            won_at = {won_at_clause},
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        db.execute(
            query,
            (status, tries_count, duration_seconds, best_score, best_permille, game_id),
        )

    # Insertion en masse des coups dans solo_player_guesses
    if guesses:
        engine = db.get_engine_type()
        with db.transaction() as conn:
            cur = conn.cursor()
            placeholder = "%s" if engine == "postgres" else "?"
            insert_sql = f"""
            INSERT INTO solo_player_guesses (
                game_id, player_id, puzzle_date, guess_order, word, score, permille, weather, is_hint, created_at
            ) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, CURRENT_TIMESTAMP)
            """
            for g in guesses:
                order = int(g.get("order") or g.get("guess_order") or 1)
                w = str(g.get("word") or "").strip().lower()
                sc = float(g.get("score") or 0.0)
                pm = g.get("permille")
                if pm is not None:
                    pm = int(pm)
                weather = str(g.get("weather") or "")
                is_hint = bool(g.get("is_hint", False))
                hint_val = True if engine == "postgres" else (1 if is_hint else 0)
                if engine == "postgres":
                    hint_val = is_hint

                try:
                    cur.execute(
                        insert_sql,
                        (game_id, str(player_id), str(puzzle_date), order, w, sc, pm, weather, hint_val),
                    )
                except Exception:
                    # En cas de doublon (game_id, guess_order), on ignore
                    pass

    # Mise à jour des compteurs globaux du puzzle (uniquement si première finalisation)
    already_finished = (game.get("status") in ("won", "given_up"))
    if not already_finished:
        succeeded_inc = 1 if status == "won" else 0
        failed_inc = 1 if status == "given_up" else 0
        update_solo_puzzle_stats(
            puzzle_date=puzzle_date,
            attempted_inc=1,
            succeeded_inc=succeeded_inc,
            failed_inc=failed_inc,
        )

    updated = get_solo_player_game_by_id(game_id)
    return updated or game


def has_real_player_won(puzzle_date: str) -> bool:
    """Vérifie si au moins un joueur humain (non-bot) a résolu le puzzle du jour."""
    if not puzzle_date:
        return False
    engine = db.get_engine_type()
    bot_filter = "is_bot = FALSE" if engine == "postgres" else "is_bot = 0"
    query = f"""
    SELECT COUNT(*) AS cnt FROM solo_player_games
    WHERE puzzle_date = %s AND status = 'won' AND {bot_filter}
    """
    row = db.fetch_one(query, (str(puzzle_date),))
    return int(row.get("cnt") or 0) > 0 if row else False


def get_solo_leaderboard(puzzle_date: str, limit: int = 100) -> list[dict]:
    """Récupère le classement des participants du jour (vrais joueurs et bots, gagnants et abandons)."""
    if not puzzle_date:
        return []
    query = """
    SELECT g.id, g.status, g.tries_count, g.duration_seconds, g.is_bot, g.won_at, g.best_score, g.best_permille, p.username
    FROM solo_player_games g
    JOIN players p ON g.player_id = p.id
    WHERE g.puzzle_date = %s AND g.status IN ('won', 'given_up')
    ORDER BY (CASE WHEN g.status = 'won' THEN 0 ELSE 1 END) ASC,
             (CASE WHEN g.status = 'won' THEN g.tries_count ELSE 999999 END) ASC,
             (CASE WHEN g.status = 'won' THEN g.duration_seconds ELSE 999999 END) ASC,
             (CASE WHEN g.status = 'won' THEN g.won_at ELSE '9999-12-31' END) ASC,
             g.tries_count DESC,
             g.updated_at ASC
    LIMIT %s
    """
    rows = db.fetch_all(query, (str(puzzle_date), limit))
    leaderboard = []
    for idx, r in enumerate(rows or []):
        leaderboard.append({
            "rank": idx + 1,
            "game_id": str(r.get("id")),
            "username": str(r.get("username")),
            "status": str(r.get("status") or "won"),
            "tries_count": int(r.get("tries_count") or 0),
            "duration_seconds": float(r.get("duration_seconds") or 0.0),
            "is_bot": bool(r.get("is_bot", False)),
            "best_score": float(r.get("best_score") or 0.0),
            "best_permille": int(r["best_permille"]) if r.get("best_permille") is not None else None,
            "won_at": str(r.get("won_at") or "") if r.get("won_at") else None,
        })
    return leaderboard


def get_solo_player_trajectory(
    puzzle_date: str,
    target_game_id: str,
    requesting_player_id: Optional[str] = None,
    is_admin: bool = False,
) -> tuple[Optional[list[dict]], Optional[str]]:
    """Récupère la trajectoire d'un joueur, protégée par l'étanchéité anti-spoiler.

    Retourne (guesses, None) si autorisé, ou (None, "Message d'erreur") si bloqué.
    """
    if not target_game_id:
        return None, "Identifiant de partie manquant"

    # Vérification anti-spoiler stricte si le demandeur n'est pas admin
    if not is_admin:
        if not requesting_player_id:
            return None, "Anti-spoiler actif : veuillez terminer votre partie avant de consulter les trajectoires."

        # S'il consulte sa propre session de jeu, autoriser
        target_game = get_solo_player_game_by_id(target_game_id)
        if target_game and target_game.get("player_id") == requesting_player_id:
            pass
        else:
            req_game = get_solo_player_game(puzzle_date, requesting_player_id)
            if not req_game or req_game.get("status") not in ("won", "given_up"):
                return None, "Anti-spoiler actif : vous devez trouver le mot ou abandonner votre partie pour consulter les trajectoires des autres joueurs."

    query = """
    SELECT guess_order, word, score, permille, weather, is_hint
    FROM solo_player_guesses
    WHERE game_id = %s
    ORDER BY guess_order ASC
    """
    rows = db.fetch_all(query, (str(target_game_id),))
    if not rows:
        return [], None

    trajectory = []
    for r in rows:
        trajectory.append({
            "order": int(r.get("guess_order") or 0),
            "word": str(r.get("word") or ""),
            "score": float(r.get("score") or 0.0),
            "permille": int(r["permille"]) if r.get("permille") is not None else None,
            "weather": str(r.get("weather") or ""),
            "is_hint": bool(r.get("is_hint", False)),
        })
    return trajectory, None


def get_admin_daily_history() -> list[dict]:
    """Récupère l'historique complet des mots du jour Solo et leurs indices IA pour la console /panier-9x.

    Trié par date décroissante (le plus récent est toujours en haut).
    """
    puzzles = db.fetch_all(
        """
        SELECT id, puzzle_date, secret_word, difficulty,
               players_attempted, players_succeeded, players_failed,
               bots_simulated, bots_simulated_at, created_at
        FROM solo_daily_puzzles
        ORDER BY puzzle_date DESC
        """
    )
    if not puzzles:
        return []

    hints = db.fetch_all(
        """
        SELECT puzzle_date, hint_level, weight, hint_word, hint_phrase, score, permille
        FROM solo_daily_ai_hints
        ORDER BY puzzle_date DESC, hint_level ASC
        """
    )
    hints_by_date: dict[str, list[dict]] = {}
    for h in hints:
        dt_key = str(h["puzzle_date"])
        hints_by_date.setdefault(dt_key, []).append({
            "hint_level": int(h["hint_level"]),
            "weight": float(h["weight"]),
            "hint_word": str(h["hint_word"]),
            "hint_phrase": str(h["hint_phrase"]),
            "score": float(h["score"]) if h.get("score") is not None else 0.0,
            "permille": int(h["permille"]) if h.get("permille") is not None else None,
        })

    # Enrichir avec la liste des parties jouées par date
    player_games = db.fetch_all(
        """
        SELECT g.id, g.puzzle_date, g.status, g.tries_count, g.duration_seconds, g.is_bot, g.won_at, g.best_score, g.best_permille, p.username
        FROM solo_player_games g
        JOIN players p ON g.player_id = p.id
        ORDER BY g.puzzle_date DESC, (CASE WHEN g.status = 'won' THEN 0 ELSE 1 END) ASC, g.tries_count ASC
        """
    )
    games_by_date: dict[str, list[dict]] = {}
    for g in player_games or []:
        dt_key = str(g["puzzle_date"])
        games_by_date.setdefault(dt_key, []).append({
            "id": str(g["id"]),
            "username": str(g["username"]),
            "status": str(g.get("status") or "in_progress"),
            "tries_count": int(g.get("tries_count") or 0),
            "duration_seconds": float(g.get("duration_seconds") or 0.0),
            "is_bot": bool(g.get("is_bot", False)),
            "best_score": float(g.get("best_score") or 0.0),
            "best_permille": int(g["best_permille"]) if g.get("best_permille") is not None else None,
            "won_at": str(g.get("won_at") or "") if g.get("won_at") else None,
        })

    result = []
    for p in puzzles:
        dt_key = str(p["puzzle_date"])
        item = {
            "id": int(p["id"]),
            "puzzle_date": dt_key,
            "secret_word": str(p["secret_word"]),
            "difficulty": str(p["difficulty"]),
            "players_attempted": int(p.get("players_attempted") or 0),
            "players_succeeded": int(p.get("players_succeeded") or 0),
            "players_failed": int(p.get("players_failed") or 0),
            "bots_simulated": bool(p.get("bots_simulated", False)),
            "bots_simulated_at": p["bots_simulated_at"].isoformat() if p.get("bots_simulated_at") and hasattr(p["bots_simulated_at"], "isoformat") else None,
            "hints": hints_by_date.get(dt_key, []),
            "games": games_by_date.get(dt_key, []),
        }
        result.append(item)
    return result
