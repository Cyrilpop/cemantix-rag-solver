"""
Cémantix Solver — Package Source
=================================
Architecture modulaire pour le solveur Cémantix par RAG & LLM local.
"""
from .config import *
from .vocab import VocabStore
from .clients import CemantixClient, MockClient
from .ui import *
from .solvers import Solver, CemantixSolver, RagDuelPlayer
from .modes import run_benchmark, run_battle, run_solo_loop, run_duel_loop, run_game
from .menu import run_main_menu
