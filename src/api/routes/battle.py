"""
Cémantix Solver — Contrôleur des Routes du Mode Battle (/api/battle/*)
======================================================================
Endpoints :
- POST /api/battle/new    : Nouvelle manche de duel vs IA RAG
- POST /api/battle/resume : Reprise / synchronisation d'une manche
- POST /api/battle/guess  : Coup joué par l'humain et réplique de l'IA
- POST /api/battle/hint   : Demande d'indice gradué (1 tour consommé)
- POST /api/battle/giveup : Déclaration de forfait (point à l'IA)
"""
import re
from typing import Optional

from ...config import log
from ...game import GameManager


def handle_battle_post(manager: GameManager, path: str, data: dict) -> tuple[dict, int]:
    """Traite les requêtes POST du Mode Battle (Joueur vs Bot IA)."""
    # 5. Nouvelle manche de Battle
    if path == "/api/battle/new":
        difficulty = data.get("difficulty", "moyen")
        battle_id = data.get("battle_id")
        ai_word = data.get("ai_word", "")
        session, err = manager.new_battle(difficulty=difficulty, battle_id=battle_id, ai_word=ai_word)
        if err:
            return {"error": err, "valid": False}, 400
        return session.to_dict(reveal_secret=False), 200

    # 6. Reprise / Synchronisation de Battle
    if path == "/api/battle/resume":
        battle_id = data.get("battle_id", "")
        difficulty = data.get("difficulty", "moyen")
        session = manager.get_battle(battle_id) if battle_id else None
        if not session:
            log(f"🔄  [API BATTLE] Session « {battle_id} » expirée/inconnue -> nouvelle manche ({difficulty})")
            session, _ = manager.new_battle(difficulty=difficulty, battle_id=None)
        return session.to_dict(reveal_secret=False), 200

    # 7. Coup joué par le joueur en Battle (tour par tour immédiat)
    if path == "/api/battle/guess":
        battle_id = data.get("battle_id", "")
        raw_word = data.get("word", "").strip()

        session = manager.get_battle(battle_id)
        if not session:
            return {
                "error": "Session de duel introuvable ou expirée. Veuillez relancer une manche.",
                "expired": True,
                "valid": False,
            }, 404

        if not raw_word:
            return {"error": "Veuillez saisir un mot valide.", "valid": False}, 400

        cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", raw_word).lower()
        if not cleaned:
            return {"error": "Le mot contient des caractères non autorisés.", "valid": False}, 400

        result = session.record_player_guess(cleaned)
        status_code = 400 if "error" in result and not result.get("valid") else 200
        return result, status_code

    # 8. Demande d'indice en Battle (3 max, du général au proche, 1 indice = 1 tour)
    if path == "/api/battle/hint":
        battle_id = data.get("battle_id", "")
        session = manager.get_battle(battle_id)
        if not session:
            return {
                "error": "Session de duel introuvable ou expirée. Relancez une manche.",
                "expired": True,
                "valid": False,
            }, 404

        result = session.request_hint()
        status_code = 400 if "error" in result and not result.get("valid") else 200
        return result, status_code

    # 9. Forfait / Abandon en Battle
    if path == "/api/battle/giveup":
        battle_id = data.get("battle_id", "")
        session = manager.get_battle(battle_id)
        if not session:
            return {"error": "Session de duel introuvable.", "valid": False}, 404
        result = session.give_up()
        return result, 200

    return {"error": "Route introuvable"}, 404
