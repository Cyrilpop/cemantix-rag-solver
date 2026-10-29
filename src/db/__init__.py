"""
Cémantix Solver — Module Base de Données Relationnelle
======================================================
Fournit l'accès centralisé aux tables PostgreSQL (ou SQLite de repli) :
- daily_puzzles : historique des résolutions quotidiennes
- multi_rooms   : salons et parties multijoueurs 1v1
- solo_sessions : sessions individuelles et défis
"""
from .connection import db, get_db_type, init_db
from .daily import (
    get_all_daily_puzzles,
    get_daily_puzzle,
    get_history_summary,
    get_latest_daily_puzzle,
    save_daily_puzzle,
)
from .multi import (
    cleanup_old_rooms,
    delete_room,
    get_room,
    load_multiplayer_session,
    save_multiplayer_session,
    save_room,
)
from .solo import (
    cleanup_old_solo,
    delete_solo_session,
    get_solo_session,
    load_game_session,
    save_game_session,
    save_solo_session_record,
)

__all__ = [
    "db",
    "init_db",
    "get_db_type",
    "save_daily_puzzle",
    "get_daily_puzzle",
    "get_latest_daily_puzzle",
    "get_all_daily_puzzles",
    "get_history_summary",
    "save_room",
    "get_room",
    "delete_room",
    "cleanup_old_rooms",
    "save_multiplayer_session",
    "load_multiplayer_session",
    "save_solo_session_record",
    "get_solo_session",
    "delete_solo_session",
    "cleanup_old_solo",
    "save_game_session",
    "load_game_session",
]
