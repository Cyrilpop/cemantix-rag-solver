"""
Cémantix Solver — Interface Console & Rendu Terminal (src.cli)
==============================================================
Sous-paquet dédié à l'expérience terminal et interactive :
- ui    : Rendu ANSI, thermomètres, jauges ASCII, tableaux de bord et débriefings
- menu  : Menu textuel interactif principal avec navigation /menu universelle
- modes : Boucles de jeu console (benchmark, battle, jeu solo et duel croisé)
"""
from .menu import ReturnToMenu, prompt_choice, run_main_menu
from .modes import (
    run_battle,
    run_benchmark,
    run_duel_loop,
    run_game,
    run_solo_loop,
)
from .ui import (
    clear_screen,
    make_gauge,
    pad_visible,
    render_duel_board,
    render_duel_debrief,
    render_game_board,
    render_main_menu,
    render_settings_menu,
    strip_ansi,
    visible_width,
    weather_for_score,
)

__all__ = [
    "clear_screen",
    "make_gauge",
    "strip_ansi",
    "visible_width",
    "pad_visible",
    "weather_for_score",
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
]
