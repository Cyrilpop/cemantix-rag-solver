"""
Cémantix Solver — Cœur Algorithmique & Moteur IA (src.engine)
=============================================================
Sous-paquet regroupant l'intelligence artificielle et l'espace sémantique :
- vocab   : VocabStore, lemmes officiels Lexique 3.83, index vectoriel ChromaDB
- clients : CemantixClient (API officielle) & MockClient (simulateur haute performance)
- ranking : Régression Ridge, cohérence quadratique pondérée & conversion météo
- llm     : Interface de prompt et client OpenAI ChatCompletions local
- duel    : Agent autonome RagDuelPlayer pour les duels tour par tour
- solvers : Orchestration autonome Cémantix (Solver / CemantixSolver)
"""
from .clients import CemantixClient, MockClient
from .solvers import (
    CemantixSolver,
    RagDuelPlayer,
    Solver,
    ask_llm,
    estimate_secret,
    rerank,
    weather_for_score,
)
from .vocab import VocabStore, ensure_lexique, load_lexique, strip_accents

__all__ = [
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
]
