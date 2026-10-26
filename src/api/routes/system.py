"""
Cémantix Solver — Contrôleur des Routes Système & Mot du Jour
=============================================================
Endpoints :
- GET  /api/health, /api/healthcheck : Statut de santé et sessions actives
- GET  /api/daily, /api/dashboard    : Données du tableau de bord Caddy & trajectoire
- POST /api/daily/reveal             : Révélation explicite du mot du jour

Le mot secret n'est **jamais** présent dans une réponse GET : il ne transite que par
`POST /api/daily/reveal`, une route volontairement exclue du cache et du crawl. Les
mots de la trajectoire et les indices qui révéleraient la cible sont masqués côté
serveur, jamais par le seul effet du CSS.
"""
from typing import Optional

from ...game import GameManager

MASK = "••••••••"


def _scrub_secret(data: dict) -> dict:
    """Retire toute trace du mot secret des données du tableau de bord.

    Le masquage s'applique au champ `word` mais aussi à la trajectoire et aux
    indices (`top_guesses`) : sans cela, la solution restait lisible dans un
    tableau annexe alors que le champ principal était vidé.
    """
    current = data.get("current")
    if not current:
        data["is_revealed"] = False
        return data

    secret = str(current.get("word") or "").strip().lower()
    current["word"] = None
    data["is_revealed"] = False

    if not secret:
        return data

    for key in ("trajectory", "top_guesses", "history"):
        steps = current.get(key)
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict) and str(step.get("word", "")).strip().lower() == secret:
                step["word"] = MASK

    # L'historique complet expose aussi le mot du jour (même entrée, clé "word").
    history = data.get("history")
    if isinstance(history, list):
        today = current.get("date")
        for entry in history:
            if (
                isinstance(entry, dict)
                and entry.get("date") == today
                and str(entry.get("word", "")).strip().lower() == secret
            ):
                entry["word"] = None
                entry["word_hidden"] = True

    return data


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

        return _scrub_secret(data), 200

    return {"error": "Route introuvable"}, 404


def handle_system_post(manager: Optional[GameManager], path: str, data: dict) -> tuple[dict, int]:
    """Révèle le mot du jour sur demande explicite de l'utilisateur.

    Volontairement en POST : un simple crawl, un prefetch de lien ou un `curl`
    ne peuvent pas récupérer la solution par accident.
    """
    if path != "/api/daily/reveal":
        return {"error": "Route introuvable"}, 404

    try:
        from ...services import build_web_data
        payload = build_web_data()
    except Exception as e:
        return {"error": f"Erreur chargement données dashboard: {e}"}, 500

    current = payload.get("current") or {}
    word = str(current.get("word") or "").strip()
    if not word:
        return {"error": "Le mot du jour n'a pas encore été résolu.", "word": None}, 404

    return {
        "word": word,
        "puzzle": current.get("puzzle"),
        "date": current.get("date"),
        "is_revealed": True,
    }, 200

