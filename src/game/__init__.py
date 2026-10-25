"""
Cémantix Solver — Moteur de Jeu & Sessions
==========================================
Package regroupant les règles, la logique vectorielle et l'état des sessions :
- Solo & Défi Quotidien (GameSession)
- Mode Battle vs IA RAG (BattleSession)
- Mode Multijoueur 1v1 (MultiplayerSession)
- Gestionnaire centralisé des parties et persistance (GameManager)
- Constantes et météo sémantique (get_weather_tier, fichiers de persistance)
"""
from .common import MULTI_SESSIONS_FILE, WEB_SESSIONS_FILE, get_weather_tier
from .solo import GameSession
from .battle import BattleSession
from .multi import MultiplayerSession
from .manager import GameManager

__all__ = [
    "get_weather_tier",
    "WEB_SESSIONS_FILE",
    "MULTI_SESSIONS_FILE",
    "GameSession",
    "BattleSession",
    "MultiplayerSession",
    "GameManager",
]
