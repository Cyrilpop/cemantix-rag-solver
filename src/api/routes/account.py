"""
Cémantix Solver — Contrôleur API REST de l'Espace Compte (Jalon M16)
===================================================================
Achemine et traite les requêtes pour l'espace « Mon compte » (/api/account/*) :
- GET  /api/account/profile   : Informations du profil connecté
- POST /api/account/password  : Modification sécurisée du mot de passe
- GET  /api/account/recovery  : Statut des mots de récupération
- POST /api/account/recovery  : Régénération des mots de récupération (affichage unique)
- GET  /api/account/stats     : Statistiques de jeu personnelles agrégées
- POST /api/account/logout    : Déconnexion et clôture de session
"""
import urllib.parse
from typing import Optional, Tuple

from ...db.account import (
    change_account_password,
    get_account_profile,
    get_account_stats,
    get_recovery_status,
    regenerate_recovery_words,
    touch_last_login,
)
from ...db.players import get_player_by_token


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


def _get_authenticated_player(headers, token_param: Optional[str] = None) -> Optional[dict]:
    """Récupère le joueur associé au jeton Bearer ou passé en paramètre."""
    token = _extract_bearer_token(headers) or token_param
    if not token or not isinstance(token, str):
        return None
    token = token.strip()
    if not token:
        return None
    return get_player_by_token(token)


def handle_account_get(path: str, query: str = "", headers=None) -> Tuple[dict, int]:
    """Traite les requêtes HTTP GET sur /api/account/*."""
    subpath = path.rstrip("/")

    # Extraction des paramètres d'URL (ex: ?token=...)
    params = {}
    if query:
        params = dict(urllib.parse.parse_qsl(query))

    token_param = params.get("auth_token") or params.get("token")
    player = _get_authenticated_player(headers, token_param)

    if not player:
        return {"error": "Authentification requise pour accéder à cet espace."}, 401

    player_id = str(player["id"])

    if subpath == "/api/account/profile":
        profile = get_account_profile(player_id)
        if not profile:
            return {"error": "Profil introuvable."}, 404
        return profile, 200

    elif subpath == "/api/account/recovery":
        status_data = get_recovery_status(player_id)
        return status_data, 200

    elif subpath == "/api/account/stats":
        stats_data = get_account_stats(player_id)
        return stats_data, 200

    return {"error": f"Endpoint GET non reconnu: {subpath}"}, 404


def handle_account_post(path: str, data: dict, headers=None) -> Tuple[dict, int]:
    """Traite les requêtes HTTP POST sur /api/account/*."""
    subpath = path.rstrip("/")

    token_param = data.get("auth_token") or data.get("token")
    player = _get_authenticated_player(headers, token_param)

    # Déconnexion : tolérante même sans jeton valide (idempotente)
    if subpath == "/api/account/logout":
        return {"success": True, "message": "Déconnexion réussie."}, 200

    if not player:
        return {"error": "Authentification requise."}, 401

    player_id = str(player["id"])

    if subpath == "/api/account/password":
        current_pwd = data.get("current_password") or data.get("currentPassword") or ""
        new_pwd = data.get("new_password") or data.get("newPassword") or ""

        if not current_pwd or not new_pwd:
            return {"error": "Le mot de passe actuel et le nouveau mot de passe sont requis."}, 400

        success, msg = change_account_password(player_id, current_pwd, new_pwd)
        if not success:
            status = 401 if "incorrect" in msg.lower() else 400
            return {"error": msg}, status

        return {"success": True, "message": msg}, 200

    elif subpath == "/api/account/recovery":
        count = int(data.get("count") or 4)
        if count < 2 or count > 8:
            count = 4

        success, msg, words = regenerate_recovery_words(player_id, count=count)
        if not success:
            status = 403 if "protégé" in msg.lower() else 400
            return {"error": msg}, status

        return {
            "success": True,
            "message": msg,
            "count": len(words),
            "recoveryWords": words,
        }, 200

    return {"error": f"Endpoint POST non reconnu: {subpath}"}, 404
