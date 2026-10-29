"""
Cémantix Solver — Couche API REST & Passerelle Réseau (src.api)
===============================================================
Paquet modulaire regroupant l'infrastructure HTTP et les contrôleurs de routes :
- server.py  : Serveur HTTP ThreadingHTTPServer, parsing JSON, CORS, lifecycle
- routes/    : Contrôleurs HTTP découplés :
  - system   : /api/health, /api/daily, /api/dashboard
  - solo     : /api/game/* (Défi du jour & Mode illimité)
  - battle   : /api/battle/* (Duel Joueur vs Bot IA RAG)
  - multi    : /api/multi/* (Multijoueur 1v1 joueurs réels)

Rétrocompatibilité 100% conservée :
Les symboles de jeu (GameSession, GameManager, etc.) restent ré-exportés ici
pour les tests et scripts externes historiques (`from src.api import ...`).
"""
from ..game import (
    BattleSession,
    GameManager,
    GameSession,
    MultiplayerSession,
    MULTI_SESSIONS_FILE,
    WEB_SESSIONS_FILE,
    get_weather_tier,
)
from .routes import (
    handle_battle_post,
    handle_multi_get,
    handle_multi_post,
    handle_solo_get,
    handle_solo_post,
    handle_system_get,
    handle_system_post,
)
from .ratelimit import RateLimiter
from .server import (
    BoundedHTTPServer,
    GameAPIHandler,
    start_api_server,
    start_api_thread,
)

__all__ = [
    "GameSession",
    "BattleSession",
    "MultiplayerSession",
    "GameManager",
    "GameAPIHandler",
    "BoundedHTTPServer",
    "RateLimiter",
    "start_api_server",
    "start_api_thread",
    "get_weather_tier",
    "WEB_SESSIONS_FILE",
    "MULTI_SESSIONS_FILE",
    "handle_system_get",
    "handle_system_post",
    "handle_solo_get",
    "handle_solo_post",
    "handle_battle_post",
    "handle_multi_get",
    "handle_multi_post",
]
