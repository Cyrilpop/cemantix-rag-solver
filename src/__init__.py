"""
Cémantix Solver — Package Source Modulaire (src)
================================================
Architecture en couches étanches :
- api/      : Exposition HTTP REST (/api/*), ThreadingHTTPServer & contrôleurs
- game/     : Domaine métier & règles de jeu (Solo, Battle vs IA, Multi 1v1, GameManager)
- engine/   : Cœur algorithmique & IA (Ridge, Rerank, VocabStore, ChromaDB, clients)
- cli/      : Expérience terminal & console (jauges, menus, modes benchmark/battle)
- services/ : Démon 24h/24, veille quotidienne 00h00, export web Caddy
- config.py : Configuration transversale, chemins & styles ANSI
"""
from .config import *
from .engine import (
    CemantixClient,
    CemantixSolver,
    MockClient,
    RagDuelPlayer,
    Solver,
    VocabStore,
    ask_llm,
    ensure_lexique,
    estimate_secret,
    load_lexique,
    rerank,
    strip_accents,
    weather_for_score,
)
from .cli import (
    ReturnToMenu,
    clear_screen,
    make_gauge,
    pad_visible,
    prompt_choice,
    render_duel_board,
    render_duel_debrief,
    render_game_board,
    render_main_menu,
    render_settings_menu,
    run_battle,
    run_benchmark,
    run_duel_loop,
    run_game,
    run_main_menu,
    run_solo_loop,
    strip_ansi,
    visible_width,
)
from .services import (
    DAILY_HISTORY_FILE,
    DASHBOARD_DATA_FILE,
    HEARTBEAT_FILE,
    PARIS_TZ,
    WEB_DATA_FILE,
    build_web_data,
    check_health,
    export_web_data,
    format_duration,
    get_next_run,
    has_solved_today,
    load_history,
    run_daemon_loop,
    run_daily_solver,
    update_heartbeat,
)
from .game import (
    BattleSession,
    GameManager,
    GameSession,
    MultiplayerSession,
    get_weather_tier,
)
from .api import (
    GameAPIHandler,
    start_api_server,
    start_api_thread,
)

__all__ = [
    # Engine
    "CemantixClient",
    "MockClient",
    "VocabStore",
    "ensure_lexique",
    "load_lexique",
    "strip_accents",
    "Solver",
    "CemantixSolver",
    "RagDuelPlayer",
    "estimate_secret",
    "rerank",
    "ask_llm",
    "weather_for_score",
    # CLI
    "clear_screen",
    "make_gauge",
    "strip_ansi",
    "visible_width",
    "pad_visible",
    "render_game_board",
    "render_duel_board",
    "render_duel_debrief",
    "render_main_menu",
    "render_settings_menu",
    "ReturnToMenu",
    "prompt_choice",
    "run_main_menu",
    "run_benchmark",
    "run_battle",
    "run_solo_loop",
    "run_duel_loop",
    "run_game",
    # Services
    "PARIS_TZ",
    "DAILY_HISTORY_FILE",
    "HEARTBEAT_FILE",
    "DASHBOARD_DATA_FILE",
    "WEB_DATA_FILE",
    "load_history",
    "has_solved_today",
    "get_next_run",
    "format_duration",
    "update_heartbeat",
    "check_health",
    "run_daily_solver",
    "run_daemon_loop",
    "build_web_data",
    "export_web_data",
    # Game & API
    "GameSession",
    "BattleSession",
    "MultiplayerSession",
    "GameManager",
    "GameAPIHandler",
    "start_api_server",
    "start_api_thread",
    "get_weather_tier",
]
