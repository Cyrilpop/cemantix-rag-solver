"""
Cémantix Solver — Contrôleurs de Routes HTTP REST (src.api.routes)
=================================================================
Exporte l'ensemble des contrôleurs modulaires d'API :
- system : /api/health, /api/daily, /api/dashboard, /api/daily/reveal
- solo   : /api/game/* (Défi du Jour & Mode Illimité)
- battle : /api/battle/* (Duel Joueur vs Bot IA RAG)
- multi  : /api/multi/* (Mode Multijoueur 1v1 joueurs réels)
"""
from .battle import handle_battle_post
from .challenge import handle_challenge_get, handle_challenge_post, handle_challenge_stream
from .admin import (
    ADMIN_BASE_PATH,
    handle_admin_delete,
    handle_admin_get,
    handle_admin_post,
    is_admin_path,
)
from .multi import handle_multi_get, handle_multi_post
from .solo import handle_solo_get, handle_solo_post
from .system import handle_system_get, handle_system_post

__all__ = [
    "handle_system_get",
    "handle_system_post",
    "handle_admin_get",
    "handle_admin_post",
    "handle_admin_delete",
    "is_admin_path",
    "ADMIN_BASE_PATH",
    "handle_solo_get",
    "handle_solo_post",
    "handle_battle_post",
    "handle_multi_get",
    "handle_multi_post",
    "handle_challenge_get",
    "handle_challenge_post",
    "handle_challenge_stream",
]
