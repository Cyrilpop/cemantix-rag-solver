"""
Cémantix Solver — Contrôleur API REST des Joueurs (src.api.routes.player)
========================================================================
Traite les requêtes d'authentification sans email pour les profils joueurs :
- POST /api/player/guest           : création ou rafraîchissement de session invité
- POST /api/player/rename          : personnalisation unique du pseudo
- POST /api/player/claim           : protection du compte par mot de passe + phrase 4 mots
- POST /api/player/login           : reconnexion multi-appareils
- POST /api/player/reset-password  : réinitialisation par phrase de secours
- POST /api/player/delete-account  : suppression définitive (droit à l'effacement RGPD)
"""
from typing import Optional, Tuple

from ...services.player_auth import (
    claim_account,
    delete_player,
    init_or_get_guest,
    login_player,
    rename_player,
    reset_password_with_recovery,
)


def _extract_bearer_token(headers) -> Optional[str]:
    """Extrait le jeton Bearer depuis l'en-tête HTTP Authorization."""
    if not headers:
        return None
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header:
        return None
    parts = auth_header.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def handle_player_post(path: str, data: dict, headers=None) -> Tuple[dict, int]:
    """Achemine et traite les requêtes POST sur /api/player/*."""
    subpath = path.rstrip("/")

    # Extraction du token (soit par Header Authorization, soit par le corps de requête)
    auth_token = _extract_bearer_token(headers) or data.get("auth_token")

    if subpath == "/api/player/guest":
        player_id = data.get("player_id")
        token = data.get("auth_token") or auth_token
        username = data.get("username")
        res = init_or_get_guest(player_id=player_id, auth_token=token, username=username)
        return res, 200

    elif subpath == "/api/player/rename":
        if not auth_token:
            return {"error": "Jeton d'authentification manquant."}, 401
        new_username = str(data.get("new_username") or "").strip()
        success, message, player = rename_player(auth_token, new_username)
        if not success:
            status = 409 if "déjà utilisé" in message else 400
            return {"error": message}, status
        return {
            "success": True,
            "username": player["username"],
            "can_change_username": player["can_change_username"],
        }, 200

    elif subpath == "/api/player/claim":
        if not auth_token:
            return {"error": "Jeton d'authentification manquant."}, 401
        password = str(data.get("password") or "")
        success, message, recovery_phrase = claim_account(auth_token, password)
        if not success:
            return {"error": message}, 400
        return {
            "success": True,
            "is_claimed": True,
            "recovery_phrase": recovery_phrase,
        }, 200

    elif subpath == "/api/player/login":
        username = str(data.get("username") or "").strip()
        password = str(data.get("password") or "")
        success, message, session = login_player(username, password)
        if not success:
            return {"error": message}, 401 if "Identifiants" in message else 400
        return session, 200

    elif subpath == "/api/player/reset-password":
        username = str(data.get("username") or "").strip()
        recovery_phrase = str(data.get("recovery_phrase") or "").strip()
        new_password = str(data.get("new_password") or "")
        success, message, new_token = reset_password_with_recovery(username, recovery_phrase, new_password)
        if not success:
            status = 401 if "invalide" in message or "introuvable" in message else 400
            return {"error": message}, status
        return {
            "success": True,
            "message": message,
            "auth_token": new_token,
        }, 200

    elif subpath == "/api/player/delete-account":
        if not auth_token:
            return {"error": "Jeton d'authentification manquant."}, 401
        success, message = delete_player(auth_token)
        if not success:
            return {"error": message}, 400
        return {"success": True, "message": message}, 200

    return {"error": "Route joueur introuvable"}, 404

