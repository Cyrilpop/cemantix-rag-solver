"""
Cémantix Solver — Contrôleur des Routes du Jeu Solo (/api/game/* et /api/solo/*)
================================================================================
Endpoints :
- GET  /api/game/daily-info   : Disponibilité et métadonnées du mot du jour
- GET  /api/game/daily        : Détails du mot du jour Solo (statistiques, quotas indices)
- GET  /api/game/leaderboard  : Classement communautaire des gagnants du jour
- GET  /api/game/trajectory/<id> : Trajectoire d'un joueur (protégée par anti-spoiler)
- POST /api/game/new          : Nouvelle partie (défi du jour ou illimité)
- POST /api/game/resume       : Reprise / reconnexion à une partie
- POST /api/game/guess        : Soumission d'une tentative de mot
- POST /api/game/hint         : Demande d'un indice (mot ou phrase, 1 indice = +1 coup)
- POST /api/game/giveup       : Abandon et révélation du mot secret
- POST /api/game/finish       : Clôture d'une victoire et persistance de la trajectoire
"""
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from ...config import log
from ...db.players import get_player_by_id, get_player_by_token
from ...db.solo import (
    finish_solo_player_game,
    get_or_create_solo_daily_puzzle,
    get_or_create_solo_player_game,
    get_solo_ai_hints,
    get_solo_daily_puzzle,
    get_solo_leaderboard,
    get_solo_player_game,
    get_solo_player_game_by_id,
    get_solo_player_trajectory,
    record_solo_hint_revealed,
)
from ...game import GameManager
from ...services.solo_daily import (
    ensure_solo_daily_puzzle,
    get_current_paris_date,
    is_solo_bots_simulated,
    simulate_solo_daily_bots,
)

PARIS_TZ = ZoneInfo("Europe/Paris")


def _extract_player_id(
    data: Optional[dict] = None,
    headers: Optional[Any] = None,
    query_params: Optional[dict] = None,
) -> Optional[str]:
    """Extrait l'ID joueur depuis le jeton Bearer, le corps JSON ou les paramètres d'URL."""
    if headers:
        auth = headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            if token:
                player = get_player_by_token(token)
                if player:
                    return player["id"]

    if data and data.get("player_id"):
        return str(data["player_id"]).strip()

    if query_params and query_params.get("player_id"):
        return str(query_params["player_id"]).strip()

    return None


def _canonical_path(path: str) -> str:
    """Normalise /api/solo/* en /api/game/* pour un routage unifié."""
    clean = path.split("?")[0].rstrip("/")
    if clean.startswith("/api/solo/"):
        return "/api/game/" + clean[10:]
    if clean == "/api/solo":
        return "/api/game/daily"
    return clean


def handle_solo_get(
    manager: Optional[GameManager],
    path: str,
    query: str = "",
    headers: Optional[Any] = None,
) -> tuple[dict, int]:
    """Traite les requêtes GET du mode Solo."""
    if not manager:
        return {"error": "Gestionnaire non initialisé"}, 503

    route = _canonical_path(path)
    parsed_query = {
        k: v[0] for k, v in urllib.parse.parse_qs(query).items() if v
    }
    today_str = get_current_paris_date()

    # 1. Disponibilité mot du jour
    if route in ("/api/game/daily-info", "/api/game/info"):
        word, puzzle_id, puzzle_date = manager.get_daily_secret()
        daily_puzzle = get_solo_daily_puzzle(today_str)
        diff = daily_puzzle["difficulty"] if daily_puzzle else "normal"
        return {
            "puzzle_id": puzzle_id,
            "puzzle_date": puzzle_date,
            "available": bool(word),
            "difficulty": diff,
        }, 200

    # 2. Métadonnées du mot du jour Solo (M15)
    if route in ("/api/game/daily", "/api/game"):
        puzzle = ensure_solo_daily_puzzle(manager.store, manager)
        player_id = _extract_player_id(headers=headers, query_params=parsed_query)
        hints_revealed = []
        if player_id:
            game = get_solo_player_game(today_str, player_id)
            if game:
                hints_revealed = game.get("hints_revealed", [])

        return {
            "puzzle_id": puzzle.get("id") or 1,
            "puzzle_date": puzzle["puzzle_date"],
            "difficulty": puzzle["difficulty"],
            "players_attempted": puzzle["players_attempted"],
            "players_succeeded": puzzle["players_succeeded"],
            "players_failed": puzzle["players_failed"],
            "hints_revealed": hints_revealed,
            "hints_used": len(hints_revealed),
            "max_hints": 3,
        }, 200

    # 3. Classement du jour (M15)
    if route == "/api/game/leaderboard":
        target_date = parsed_query.get("date", today_str)
        limit = min(int(parsed_query.get("limit", 100)), 200)

        # Si l'on consulte la date courante et qu'il est passé 6h30, la tuile ne doit jamais être vide
        paris_now = datetime.now(PARIS_TZ)
        is_after_630 = (paris_now.hour > 6) or (paris_now.hour == 6 and paris_now.minute >= 30)
        leaderboard = get_solo_leaderboard(target_date, limit=limit)

        if target_date == today_str and is_after_630 and len(leaderboard) == 0:
            try:
                simulate_solo_daily_bots(
                    store=manager.store if manager else None,
                    force=True,
                    puzzle_date=target_date,
                )
                leaderboard = get_solo_leaderboard(target_date, limit=limit)
            except Exception as e:
                log(f"⚠️  [LEADERBOARD] Auto-remplissage après 6h30 en échec : {e}")

        return {
            "puzzle_date": target_date,
            "count": len(leaderboard),
            "leaderboard": leaderboard,
        }, 200

    # 4. Trajectoire d'un joueur protégé par anti-spoiler (M15)
    if route.startswith("/api/game/trajectory/"):
        target_game_id = route[21:].strip()
        target_date = parsed_query.get("date", today_str)
        requesting_player_id = _extract_player_id(headers=headers, query_params=parsed_query)
        is_admin = bool(parsed_query.get("admin") == "1")
        requesting_game_id = parsed_query.get("game_id", "").strip()

        # Si le joueur transmet son ID de partie en cours/terminée, vérifier son statut
        if not is_admin and requesting_game_id and manager:
            req_session = manager.get_session(requesting_game_id)
            if req_session and (req_session.is_won or getattr(req_session, "is_given_up", False)):
                is_admin = True
                if not requesting_player_id and getattr(req_session, "player_id", None):
                    requesting_player_id = req_session.player_id

        trajectory, err = get_solo_player_trajectory(
            puzzle_date=target_date,
            target_game_id=target_game_id,
            requesting_player_id=requesting_player_id,
            is_admin=is_admin,
        )
        if err:
            return {"error": err, "unlocked": False}, 403

        # Si la trajectoire est vide en base relationnelle, vérifier si la session active existe en mémoire
        if not trajectory and manager:
            mem_session = manager.get_session(target_game_id)
            if mem_session and hasattr(mem_session, "guesses") and mem_session.guesses:
                sorted_guesses = sorted(mem_session.guesses.values(), key=lambda x: x.get("order", 0))
                trajectory = [
                    {
                        "order": int(g.get("order") or 0),
                        "word": str(g.get("word") or ""),
                        "score": float(g.get("score") or 0.0),
                        "permille": int(g["permille"]) if g.get("permille") is not None else None,
                        "weather": str(g.get("weather") or ""),
                        "is_hint": bool(g.get("is_hint", False)),
                    }
                    for g in sorted_guesses
                ]

        return {
            "game_id": target_game_id,
            "puzzle_date": target_date,
            "unlocked": True,
            "trajectory": trajectory or [],
        }, 200

    return {"error": "Route introuvable"}, 404


def handle_solo_post(
    manager: GameManager,
    path: str,
    data: dict,
    headers: Optional[Any] = None,
) -> tuple[dict, int]:
    """Traite les requêtes POST du mode Solo."""
    route = _canonical_path(path)
    today_str = get_current_paris_date()
    player_id = _extract_player_id(data=data, headers=headers)

    # 1. Nouvelle partie
    if route == "/api/game/new":
        mode = data.get("mode", "daily")
        difficulty = data.get("difficulty", "normal")
        force = bool(data.get("force", False))

        if mode == "daily":
            ensure_solo_daily_puzzle(manager.store, manager)
            if not player_id:
                from ...db.players import create_guest_player
                guest = create_guest_player()
                player_id = guest["id"]

        session = manager.new_game(
            mode=mode, difficulty=difficulty, force=force, player_id=player_id
        )

        # Synchronisation avec solo_player_games si joueur authentifié
        if mode == "daily" and player_id:
            db_game = get_or_create_solo_player_game(today_str, player_id)
            if db_game.get("status") == "won":
                session.is_won = True
            elif db_game.get("status") == "given_up":
                session.is_given_up = True
            if db_game.get("hints_revealed"):
                session.hints_revealed = db_game["hints_revealed"]
                session.hints = [
                    h["content"] for h in session.hints_revealed if h.get("type") == "word"
                ]
            if not session.guesses:
                try:
                    from ...db.connection import db
                    rows_g = db.fetch_all(
                        "SELECT word, score, permille, weather, guess_order, is_hint FROM solo_player_guesses WHERE game_id = %s ORDER BY guess_order ASC",
                        (db_game["id"],),
                    )
                    for rg in (rows_g or []):
                        session.guesses[rg["word"]] = {
                            "order": rg["guess_order"],
                            "word": rg["word"],
                            "score": float(rg["score"]),
                            "permille": rg["permille"],
                            "weather": rg["weather"],
                            "is_hint": bool(rg.get("is_hint", False)),
                        }
                except Exception as eg:
                    log(f"⚠️  [SOLO] Erreur chargement trajectoire SQL resume : {eg}")

        manager.save_solo_session(session)
        res_dict = session.to_dict(reveal_secret=False)
        if mode == "daily" and (session.is_won or getattr(session, "is_given_up", False)):
            res_dict["already_finished"] = True
        return res_dict, 200

    # 1b. Reprise / Synchronisation
    if route == "/api/game/resume":
        game_id = data.get("game_id", "")
        mode = data.get("mode", "daily")
        difficulty = data.get("difficulty", "normal")

        session = manager.get_session(game_id) if game_id else None
        if not session:
            log(f"🔄  [API JEU] Session « {game_id} » expirée/inconnue -> auto-renouvellement ({mode}, {difficulty})")
            session = manager.new_game(
                mode=mode, difficulty=difficulty, force=False, player_id=player_id
            )

        if mode == "daily" and player_id:
            db_game = get_or_create_solo_player_game(today_str, player_id)
            if db_game.get("status") == "won":
                session.is_won = True
            elif db_game.get("status") == "given_up":
                session.is_given_up = True
            if db_game.get("hints_revealed"):
                session.hints_revealed = db_game["hints_revealed"]
                session.hints = [
                    h["content"] for h in session.hints_revealed if h.get("type") == "word"
                ]
            if not session.guesses:
                try:
                    from ...db.connection import db
                    rows_g = db.fetch_all(
                        "SELECT word, score, permille, weather, guess_order, is_hint FROM solo_player_guesses WHERE game_id = %s ORDER BY guess_order ASC",
                        (db_game["id"],),
                    )
                    for rg in (rows_g or []):
                        session.guesses[rg["word"]] = {
                            "order": rg["guess_order"],
                            "word": rg["word"],
                            "score": float(rg["score"]),
                            "permille": rg["permille"],
                            "weather": rg["weather"],
                            "is_hint": bool(rg.get("is_hint", False)),
                        }
                except Exception as eg:
                    log(f"⚠️  [SOLO] Erreur chargement trajectoire SQL resume : {eg}")

        manager.save_solo_session(session)
        res_dict = session.to_dict(reveal_secret=False)
        if mode == "daily" and (session.is_won or getattr(session, "is_given_up", False)):
            res_dict["already_finished"] = True
        return res_dict, 200

    # 2. Proposition de mot
    if route == "/api/game/guess":
        game_id = data.get("game_id", "")
        raw_word = data.get("word", "").strip()

        session = manager.get_session(game_id)
        if not session:
            return {"error": "Session de jeu introuvable ou expirée. Relancez une partie.", "expired": True}, 404

        if session.is_won:
            return {"error": "Cette partie est déjà gagnée ! Vous avez trouvé le mot secret.", "valid": False}, 400
        if getattr(session, "is_given_up", False):
            return {"error": "Cette partie a été abandonnée. Le mot secret était déjà révélé.", "valid": False}, 400

        if not raw_word:
            return {"error": "Veuillez saisir un mot valide."}, 400

        cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", raw_word).lower()
        if not cleaned:
            return {"error": "Le mot contient des caractères non autorisés."}, 400

        result = session.record_guess(cleaned)
        if result.get("valid") and result.get("is_win"):
            # Enregistrement relationnel dès victoire pour le mode daily
            if session.mode == "daily":
                p_id = player_id or getattr(session, "player_id", None)
                if not p_id:
                    from ...db.players import create_guest_player
                    guest = create_guest_player()
                    p_id = guest["id"]
                    session.player_id = p_id

                sorted_guesses = sorted(session.guesses.values(), key=lambda x: x["order"])
                best_score = max((g["score"] for g in session.guesses.values()), default=100.0)
                best_pm = max((g.get("permille") or 0 for g in session.guesses.values()), default=1000)
                finish_solo_player_game(
                    puzzle_date=today_str,
                    player_id=p_id,
                    status="won",
                    tries_count=len(session.guesses) + len([h for h in getattr(session, "hints_revealed", []) if h.get("type") == "phrase"]),
                    duration_seconds=round(session.last_activity - session.created_at, 2),
                    best_score=best_score,
                    best_permille=best_pm,
                    guesses=sorted_guesses,
                    is_bot=False,
                    hints_revealed=getattr(session, "hints_revealed", []),
                    hints_used=len(getattr(session, "hints_revealed", [])),
                )
        elif result.get("valid") and session.mode == "daily":
            # Mise à jour partielle des compteurs en cours de partie
            p_id = player_id or getattr(session, "player_id", None)
            if p_id:
                try:
                    game = get_or_create_solo_player_game(today_str, p_id)
                    best_sc = max((g["score"] for g in session.guesses.values()), default=0.0)
                    best_pm = max((g.get("permille") or 0 for g in session.guesses.values()), default=None)
                    current_tries = len(session.guesses) + len([h for h in getattr(session, "hints_revealed", []) if h.get("type") == "phrase"])
                    from ...db.connection import db
                    db.execute(
                        """
                        UPDATE solo_player_games
                        SET tries_count = %s, best_score = %s, best_permille = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s AND status = 'in_progress'
                        """,
                        (current_tries, best_sc, best_pm, game["id"]),
                    )
                except Exception as e:
                    log(f"⚠️  [SOLO] Erreur mise à jour compteurs en cours : {e}")

        manager.save_solo_session(session)
        return result, 200

    # 3. Demande d'indice (+1 coup officiel, mot ou phrase au choix par niveau)
    if route == "/api/game/hint":
        game_id = data.get("game_id", "")
        hint_type = str(data.get("type") or data.get("hint_type") or "word").strip().lower()
        requested_level = data.get("level") or data.get("hint_level")

        session = manager.get_session(game_id)
        if not session:
            return {"error": "Session de jeu introuvable ou expirée. Relancez une partie.", "expired": True}, 404

        if session.is_won:
            return {"error": "Partie déjà gagnée !"}, 400
        if session.is_given_up:
            return {"error": "Partie déjà abandonnée."}, 400

        # Mode Défi Quotidien (M15)
        if session.mode == "daily":
            p_id = player_id or getattr(session, "player_id", None)
            if not p_id:
                from ...db.players import create_guest_player
                guest = create_guest_player()
                p_id = guest["id"]
                session.player_id = p_id

            revealed = getattr(session, "hints_revealed", [])
            if len(revealed) >= 3:
                return {"error": "Quota maximum de 3 indices déjà atteint pour cette partie."}, 400

            target_level = int(requested_level) if requested_level else (len(revealed) + 1)
            if target_level > 3:
                return {"error": "Niveau d'indice invalide (maximum 3)."}, 400

            # Vérification d'immuabilité : si ce niveau a déjà été révélé
            for rev in revealed:
                if rev.get("level") == target_level:
                    return {
                        "valid": True,
                        "already_revealed": True,
                        "hint_level": target_level,
                        "hint_type": rev.get("type"),
                        "content": rev.get("content"),
                        "hints_revealed": list(revealed),
                        "tries": len(session.guesses) + len([h for h in revealed if h.get("type") == "phrase"]),
                    }, 200

            # Récupération de l'indice précalculé pour le jour
            daily_hints = get_solo_ai_hints(today_str)
            h1 = next((h for h in daily_hints if h.get("hint_level") == 1), None)
            h2 = next((h for h in daily_hints if h.get("hint_level") == 2), None)
            h3 = next((h for h in daily_hints if h.get("hint_level") == 3), None)
            p1 = h1.get("permille") if h1 else None
            p2 = h2.get("permille") if h2 else None
            p3 = h3.get("permille") if h3 else None

            # Vérification du calibrage croissant (#1 ~700 < #2 ~825 < #3 ~950)
            if not (len(daily_hints) == 3 and p1 and p2 and p3 and 650 <= p1 <= 750 and 935 <= p3 <= 965 and p1 < p2 < p3):
                ensure_solo_daily_puzzle(manager.store, manager)
                daily_hints = get_solo_ai_hints(today_str)

            target_hint = next((h for h in daily_hints if h.get("hint_level") == target_level), None)

            if not target_hint:
                # Repli sur le générateur sémantique local
                result = session.request_hint()
                manager.save_solo_session(session)
                return result, 200

            if hint_type == "phrase":
                phrase_content = target_hint.get("hint_phrase", "")
                rev_entry = {
                    "level": target_level,
                    "type": "phrase",
                    "content": phrase_content,
                    "revealed_at": datetime.now(timezone.utc).isoformat(),
                }
                session.hints_revealed.append(rev_entry)
                session.last_activity = datetime.now(timezone.utc).timestamp()

                record_solo_hint_revealed(
                    puzzle_date=today_str,
                    player_id=p_id,
                    hint_level=target_level,
                    hint_type="phrase",
                    content=phrase_content,
                )

                manager.save_solo_session(session)
                current_tries = len(session.guesses) + len([h for h in session.hints_revealed if h.get("type") == "phrase"])
                return {
                    "valid": True,
                    "hint_type": "phrase",
                    "hint_level": target_level,
                    "content": phrase_content,
                    "tries": current_tries,
                    "hints_revealed": list(session.hints_revealed),
                    "hints_remaining": 3 - len(session.hints_revealed),
                    "player_id": p_id,
                }, 200

            else:
                # Format Mot : évalué comme un coup officiel
                word_content = target_hint.get("hint_word", "").strip().lower()
                guess_res = session.record_guess(word_content)
                if word_content in session.guesses:
                    session.guesses[word_content]["is_hint"] = True
                if guess_res.get("last_guess"):
                    guess_res["last_guess"]["is_hint"] = True

                rev_entry = {
                    "level": target_level,
                    "type": "word",
                    "content": word_content,
                    "score": guess_res.get("score", 0.0),
                    "permille": guess_res.get("permille"),
                    "revealed_at": datetime.now(timezone.utc).isoformat(),
                }
                session.hints_revealed.append(rev_entry)
                session.hints.append(word_content)

                record_solo_hint_revealed(
                    puzzle_date=today_str,
                    player_id=p_id,
                    hint_level=target_level,
                    hint_type="word",
                    content=word_content,
                    score=guess_res.get("score", 0.0),
                    permille=guess_res.get("permille"),
                )

                manager.save_solo_session(session)
                guess_res["hint_type"] = "word"
                guess_res["hint_level"] = target_level
                guess_res["hints_revealed"] = list(session.hints_revealed)
                guess_res["hints_remaining"] = 3 - len(session.hints_revealed)
                guess_res["player_id"] = p_id
                return guess_res, 200

        # Mode Illimité : calcul local standard
        result = session.request_hint()
        manager.save_solo_session(session)
        status_code = 400 if "error" in result and not result.get("valid") else 200
        return result, status_code

    # 4. Abandonner / Révéler le mot secret
    if route == "/api/game/giveup":
        game_id = data.get("game_id", "")
        session = manager.get_session(game_id)
        if not session:
            return {"error": "Session introuvable."}, 404

        if session.is_won:
            return {"error": "Partie déjà gagnée !"}, 400
        if getattr(session, "is_given_up", False):
            return session.to_dict(reveal_secret=True), 200

        res = manager.give_up(game_id)
        if not res:
            return {"error": "Session introuvable."}, 404

        session = manager.get_session(game_id)
        if session and session.mode == "daily":
            p_id = player_id or getattr(session, "player_id", None)
            if not p_id:
                from ...db.players import create_guest_player
                guest = create_guest_player()
                p_id = guest["id"]
                session.player_id = p_id

            sorted_guesses = sorted(session.guesses.values(), key=lambda x: x["order"])
            best_score = max((g["score"] for g in session.guesses.values()), default=0.0)
            best_pm = max((g.get("permille") or 0 for g in session.guesses.values()), default=None)
            finish_solo_player_game(
                puzzle_date=today_str,
                player_id=p_id,
                status="given_up",
                tries_count=len(session.guesses) + len([h for h in getattr(session, "hints_revealed", []) if h.get("type") == "phrase"]),
                duration_seconds=round(session.last_activity - session.created_at, 2),
                best_score=best_score,
                best_permille=best_pm,
                guesses=sorted_guesses,
                is_bot=False,
                hints_revealed=getattr(session, "hints_revealed", []),
                hints_used=len(getattr(session, "hints_revealed", [])),
            )
            manager.save_solo_session(session)

        return res, 200

    # 5. Clôture explicite (finish)
    if route == "/api/game/finish":
        game_id = data.get("game_id", "")
        session = manager.get_session(game_id)
        if not session:
            return {"error": "Session introuvable."}, 404

        session.is_won = True
        p_id = player_id or getattr(session, "player_id", None)
        if session.mode == "daily":
            if not p_id:
                from ...db.players import create_guest_player
                guest = create_guest_player()
                p_id = guest["id"]
                session.player_id = p_id

            sorted_guesses = sorted(session.guesses.values(), key=lambda x: x["order"])
            best_score = max((g["score"] for g in session.guesses.values()), default=100.0)
            best_pm = max((g.get("permille") or 0 for g in session.guesses.values()), default=1000)
            finish_solo_player_game(
                puzzle_date=today_str,
                player_id=p_id,
                status="won",
                tries_count=len(session.guesses) + len([h for h in getattr(session, "hints_revealed", []) if h.get("type") == "phrase"]),
                duration_seconds=round(session.last_activity - session.created_at, 2),
                best_score=best_score,
                best_permille=best_pm,
                guesses=sorted_guesses,
                is_bot=False,
            )

        manager.save_solo_session(session)
        return {"success": True, "secret": session.secret}, 200

    return {"error": "Route introuvable"}, 404
