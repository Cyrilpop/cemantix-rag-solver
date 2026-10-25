"""
Cémantix Solver — Contrôleur des Routes Système & Mot du Jour
=============================================================
Endpoints :
- GET /api/health, /api/healthcheck : Statut de santé et sessions actives
- GET /api/daily, /api/dashboard    : Données du tableau de bord Caddy & trajectoire
"""
from typing import Optional

from ...game import GameManager


def handle_system_get(manager: Optional[GameManager], path: str, query: str) -> tuple[dict, int]:
    """Traite les requêtes de santé et de consultation du tableau de bord."""
    if path in ("/api/health", "/api/healthcheck"):
        count = len(manager.sessions) if manager else 0
        return {"status": "ok", "active_sessions": count}, 200

    if path in ("/api/daily", "/api/dashboard"):
        try:
            from ...services import build_web_data
            data = build_web_data()
        except Exception as e:
            return {"error": f"Erreur chargement données dashboard: {e}"}, 500

        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p) if query else {}
        reveal = params.get("reveal", "").lower() in ("true", "1", "yes")

        if not reveal and data.get("current"):
            secret = data["current"].get("word")
            data["current"]["word"] = None
            data["current"]["is_revealed"] = False
            if secret and "trajectory" in data["current"]:
                for step in data["current"]["trajectory"]:
                    if str(step.get("word", "")).lower() == secret.lower():
                        step["word"] = "••••••••"
        elif data.get("current"):
            data["current"]["is_revealed"] = True

        return data, 200

    return {"error": "Route introuvable"}, 404
