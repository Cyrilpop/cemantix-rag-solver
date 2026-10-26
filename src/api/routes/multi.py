"""
Cémantix Solver — Contrôleur des Routes Multijoueur 1v1 (/api/multi/*)
=====================================================================
Endpoints :
- GET  /api/multi/status     : État du salon en temps réel (polling)
- POST /api/multi/create     : Création d'un nouveau salon (code DUEL-XXXXXXXX)
- POST /api/multi/join       : Rejoindre un salon ou s'y reconnecter
- POST /api/multi/setup-word : Définition du mot secret (mode Mots Choisis)
- POST /api/multi/status     : Consultation de l'état (POST)
- POST /api/multi/guess      : Coup joué au tour par tour
- POST /api/multi/hint       : Demande d'indice (tour passé à l'adversaire)
- POST /api/multi/giveup     : Déclaration de forfait (victoire adverse)
"""
import re
from typing import Optional

from ...game import GameManager


def handle_multi_get(manager: Optional[GameManager], path: str, query: str) -> tuple[dict, int]:
    """Traite les requêtes GET du Mode Multijoueur (statut/polling)."""
    if not manager:
        return {"error": "Gestionnaire non initialisé"}, 503

    if path == "/api/multi/status":
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p) if query else {}
        room_id = params.get("r", params.get("room_id", "")).strip().upper()
        player_key = params.get("k", params.get("player_key", "")).strip().upper()

        session = manager.get_multiplayer(room_id)
        if not session:
            return {"error": "Salon de jeu introuvable ou expiré.", "valid": False}, 404

        res = session.to_dict(player_key)
        if not res.get("valid"):
            return res, 403
        return res, 200

    return {"error": "Route introuvable"}, 404


def handle_multi_post(manager: GameManager, path: str, data: dict) -> tuple[dict, int]:
    """Traite les requêtes POST du Mode Multijoueur."""
    # 10. Créer un salon multijoueur
    if path == "/api/multi/create":
        mode = str(data.get("mode") or "same_word").strip()
        difficulty = str(data.get("difficulty") or "moyen").strip()
        player_name = str(data.get("player_name") or "Joueur 1").strip()
        custom_target = data.get("custom_target")
        if custom_target is not None:
            custom_target = str(custom_target).strip()

        session, err = manager.create_multiplayer(
            mode=mode,
            difficulty=difficulty,
            player_name=player_name,
            custom_target=custom_target,
        )
        if err:
            return {"error": err, "valid": False}, 400

        return {
            "valid": True,
            "room_id": session.room_id,
            "player_key": session.key_p1,
            "role": "p1",
            "guest_key": session.key_p2,
            "share_url": f"/multi/?r={session.room_id}&k={session.key_p2}",
            "session": session.to_dict(session.key_p1),
        }, 200

    # 11. Rejoindre ou reconnecter un salon
    if path == "/api/multi/join":
        room_id = str(data.get("room_id") or "").strip().upper()
        player_key = str(data.get("player_key") or "").strip().upper()
        player_name = str(data.get("player_name") or "").strip()

        session = manager.get_multiplayer(room_id)
        if not session:
            return {"error": "Salon de jeu introuvable ou expiré.", "valid": False}, 404

        if player_key:
            role = session.get_role(player_key)
            if not role:
                return {"error": "Clé joueur invalide pour ce salon.", "valid": False}, 403
            if role == "p2":
                session.p2_joined = True
                if player_name:
                    session.p2_name = player_name
                manager._save_sessions()
            return {
                "valid": True,
                "room_id": session.room_id,
                "player_key": player_key,
                "role": role,
                "session": session.to_dict(player_key),
            }, 200

        if not session.p2_joined:
            session.p2_joined = True
            if player_name:
                session.p2_name = player_name
            manager._save_sessions()
            return {
                "valid": True,
                "room_id": session.room_id,
                "player_key": session.key_p2,
                "role": "p2",
                "session": session.to_dict(session.key_p2),
            }, 200

        return {
            "error": "Ce salon est déjà complet. Si vous êtes déjà participant, veuillez renseigner votre Clé Joueur.",
            "valid": False,
        }, 400

    # 12. Définition du mot secret pour l'adversaire (Mode Mots Choisis)
    if path == "/api/multi/setup-word":
        room_id = str(data.get("room_id") or "").strip().upper()
        player_key = str(data.get("player_key") or "").strip().upper()
        word = str(data.get("word") or "").strip()

        session = manager.get_multiplayer(room_id)
        if not session:
            return {"error": "Salon introuvable.", "valid": False}, 404

        res = session.setup_word(player_key, word)
        status_code = 400 if "error" in res and not res.get("valid") else 200
        if res.get("valid"):
            manager._save_sessions()
        return res, status_code

    # 13. Consultation de l'état du salon (POST)
    if path == "/api/multi/status":
        room_id = str(data.get("room_id") or "").strip().upper()
        player_key = str(data.get("player_key") or "").strip().upper()

        session = manager.get_multiplayer(room_id)
        if not session:
            return {"error": "Salon introuvable ou expiré.", "valid": False}, 404

        res = session.to_dict(player_key)
        if not res.get("valid"):
            return res, 403
        return res, 200

    # 14. Coup joué en Multijoueur
    if path == "/api/multi/guess":
        room_id = str(data.get("room_id") or "").strip().upper()
        player_key = str(data.get("player_key") or "").strip().upper()
        raw_word = str(data.get("word") or "").strip()

        session = manager.get_multiplayer(room_id)
        if not session:
            return {"error": "Salon introuvable ou expiré.", "valid": False}, 404

        if not raw_word:
            return {"error": "Veuillez saisir un mot valide.", "valid": False}, 400

        cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", raw_word).lower()
        if not cleaned:
            return {"error": "Le mot contient des caractères non autorisés.", "valid": False}, 400

        res = session.record_guess(player_key, cleaned)
        status_code = 400 if "error" in res and not res.get("valid") else 200
        if res.get("valid"):
            manager._save_sessions()
        return res, status_code

    # 15. Demande d'indice en Multijoueur
    if path == "/api/multi/hint":
        room_id = str(data.get("room_id") or "").strip().upper()
        player_key = str(data.get("player_key") or "").strip().upper()

        session = manager.get_multiplayer(room_id)
        if not session:
            return {"error": "Salon introuvable.", "valid": False}, 404

        res = session.request_hint(player_key)
        status_code = 400 if "error" in res and not res.get("valid") else 200
        if res.get("valid"):
            manager._save_sessions()
        return res, status_code

    # 16. Forfait / Déclaration d'abandon en Multijoueur
    if path == "/api/multi/giveup":
        room_id = str(data.get("room_id") or "").strip().upper()
        player_key = str(data.get("player_key") or "").strip().upper()

        session = manager.get_multiplayer(room_id)
        if not session:
            return {"error": "Salon introuvable.", "valid": False}, 404

        res = session.give_up(player_key)
        status_code = 400 if "error" in res and not res.get("valid") else 200
        if res.get("valid"):
            manager._save_sessions()
        return res, status_code

    return {"error": "Route introuvable"}, 404
