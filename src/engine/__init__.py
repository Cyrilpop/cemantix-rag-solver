"""
Cémantix Solver — Cœur Algorithmique & Moteur IA (src.engine)
=============================================================
Sous-paquet regroupant l'intelligence artificielle et l'espace sémantique :
- vocab   : VocabStore, lemmes officiels Lexique 3.83, index vectoriel ChromaDB
- clients : CemantixClient (API officielle) & MockClient (simulateur haute performance)
- solvers : Régression Ridge, reranking sémantique, solveur autonome & bot RagDuelPlayer
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
