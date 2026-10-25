"""
Cémantix Solver — Contrôleur des Routes du Jeu Solo (/api/game/*)
================================================================
Endpoints :
- GET  /api/game/daily-info : Vérifie la disponibilité du mot du jour
- POST /api/game/new        : Nouvelle partie (défi du jour ou illimité)
- POST /api/game/resume     : Reprise / reconnexion à une partie
- POST /api/game/guess      : Soumission d'une tentative de mot
- POST /api/game/hint       : Demande d'un indice vectoriel (+1 coup)
- POST /api/game/giveup     : Déclaration d'abandon et révélation du secret
"""
import re
from typing import Optional

from ...config import log
from ...game import GameManager


def handle_solo_get(manager: Optional[GameManager], path: str) -> tuple[dict, int]:
    """Traite les requêtes GET du mode Solo."""
    if not manager:
        return {"error": "Gestionnaire non initialisé"}, 503

    if path == "/api/game/daily-info":
        word, puzzle = manager.get_daily_secret()
        return {
            "puzzle_id": puzzle,
            "available": bool(word),
        }, 200

    return {"error": "Route introuvable"}, 404


def handle_solo_post(manager: GameManager, path: str, data: dict) -> tuple[dict, int]:
    """Traite les requêtes POST du mode Solo."""
    # 1. Nouvelle partie
    if path == "/api/game/new":
        mode = data.get("mode", "daily")
        difficulty = data.get("difficulty", "moyen")
        force = bool(data.get("force", False))
        session = manager.new_game(mode=mode, difficulty=difficulty, force=force)
        return session.to_dict(reveal_secret=False), 200

    # 1b. Reprise / Synchronisation
    if path == "/api/game/resume":
        game_id = data.get("game_id", "")
        mode = data.get("mode", "daily")
        difficulty = data.get("difficulty", "moyen")

        session = manager.get_session(game_id) if game_id else None
        if not session:
            log(f"🔄  [API JEU] Session « {game_id} » expirée/inconnue -> auto-renouvellement ({mode}, {difficulty})")
            session = manager.new_game(mode=mode, difficulty=difficulty, force=False)

        return session.to_dict(reveal_secret=False), 200

    # 2. Proposition de mot
    if path == "/api/game/guess":
        game_id = data.get("game_id", "")
        raw_word = data.get("word", "").strip()

        session = manager.get_session(game_id)
        if not session:
            return {"error": "Session de jeu introuvable ou expirée. Veuillez relancer une partie.", "expired": True}, 404

        if not raw_word:
            return {"error": "Veuillez saisir un mot valide."}, 400

        cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", raw_word).lower()
        if not cleaned:
            return {"error": "Le mot contient des caractères non autorisés."}, 400

        result = session.record_guess(cleaned)
        manager._save_sessions()
        return result, 200

    # 3. Demande d'indice (+1 coup officiel au compteur)
    if path == "/api/game/hint":
        game_id = data.get("game_id", "")
        session = manager.get_session(game_id)
        if not session:
            return {"error": "Session de jeu introuvable ou expirée. Relancez une partie.", "expired": True}, 404

        result = session.request_hint()
        manager._save_sessions()
        status_code = 400 if "error" in result and not result.get("valid") else 200
        return result, status_code

    # 4. Abandonner / Révéler le mot secret
    if path == "/api/game/giveup":
        game_id = data.get("game_id", "")
        res = manager.give_up(game_id)
        if not res:
            return {"error": "Session introuvable."}, 404
        return res, 200

    return {"error": "Route introuvable"}, 404
