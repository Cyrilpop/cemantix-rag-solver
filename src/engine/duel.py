"""
Cémantix Solver — Joueur IA pour le Mode Duel (src.engine.duel)
==============================================================
Agent autonome basé sur l'espace vectoriel et la régression Ridge,
jouant coup par coup avec une heuristique calibrée selon la difficulté
(facile, moyen, expert).
"""
import sys
from typing import Optional, TYPE_CHECKING
import numpy as np

from ..config import (
    STOPWORDS,
    SEED_WORDS,
    SEEDS_FACILE,
    SEEDS_MOYEN,
    SEEDS_EXPERT,
)
from .ranking import weather_for_score, estimate_secret, rerank

if TYPE_CHECKING:
    from .vocab import VocabStore
    from .clients import MockClient


def _resolve_ranking_fn(name: str, fallback):
    """Résolution tardive supportant le monkeypatching historique sur src.engine.solvers."""
    mod = sys.modules.get("src.engine.solvers")
    return getattr(mod, name, fallback) if mod is not None else fallback


class RagDuelPlayer:
    """Agent RAG mathématique jouant un coup par tour pour le mode Duel."""

    def __init__(self, store: "VocabStore", game: "MockClient", difficulty: str = "moyen"):
        self.store = store
        self.game = game
        self.difficulty = difficulty.lower() if difficulty else "moyen"
        if self.difficulty not in ("facile", "moyen", "expert"):
            self.difficulty = "moyen"
        self.tried = set()
        self.guesses = {}   # norm -> (s, p, num, w_icon, w_lbl)

        if self.difficulty == "facile":
            self.seeds = list(SEEDS_FACILE)
            self.min_seeds = 6
        elif self.difficulty == "expert":
            self.seeds = list(SEEDS_EXPERT)
            self.min_seeds = 2
        else:  # moyen
            self.seeds = list(SEEDS_MOYEN)
            self.min_seeds = 4
        self.seed_idx = 0

    def play_turn(self, turn_no: int) -> tuple[str, float, Optional[int], str, str]:
        word_to_play = None
        known = [(w, s) for w, (s, p, *_) in self.guesses.items() if w in self.store]
        best_score = max([s for w, s in known], default=-1.0)

        # 1. Amorçage initial selon niveau
        warm_threshold = 0.22 if self.difficulty == "facile" else (0.12 if self.difficulty == "expert" else 0.15)
        if (len(known) < self.min_seeds or best_score < warm_threshold) and self.seed_idx < len(self.seeds):
            while self.seed_idx < len(self.seeds):
                candidate_seed = self.store.normalize(self.seeds[self.seed_idx])
                self.seed_idx += 1
                if candidate_seed not in self.tried and candidate_seed in self.store:
                    word_to_play = candidate_seed
                    break

        # 2. Régression Ridge + k-NN + Rerank
        if not word_to_play and len(known) >= 2:
            fn_estimate = _resolve_ranking_fn("estimate_secret", estimate_secret)
            fn_rerank = _resolve_ranking_fn("rerank", rerank)

            G = np.vstack([self.store.vec(w) for w, s in known])
            s = np.array([s for w, s in known], dtype=np.float32)
            q_est = fn_estimate(G, s)
            k_knn = 150 if self.difficulty == "expert" else (100 if self.difficulty == "moyen" else 60)
            raw_pool = self.store.knn(q_est, k_knn)

            # Ajoute les voisins des meilleurs coups
            sorted_known = sorted(known, key=lambda x: x[1], reverse=True)
            k_best = 3 if self.difficulty == "expert" else 2
            for w, _ in sorted_known[:k_best]:
                raw_pool += self.store.knn(self.store.vec(w), 50)

            cands = []
            for raw_w in raw_pool:
                w = self.store.normalize(raw_w)
                if (w not in self.tried
                        and w not in cands
                        and len(w) >= 4
                        and w not in STOPWORDS
                        and self.store.is_valid_french(w)):
                    cands.append(w)
                    if len(cands) >= 60:
                        break

            if cands:
                reranked = fn_rerank(self.store, cands, G, s, q_est)
                if reranked:
                    if self.difficulty == "expert":
                        # Expert : joue toujours le top 1 absolu
                        word_to_play = reranked[0][0]
                    elif self.difficulty == "facile":
                        # Facile : sélectionne parmi le pool (rangs 3 à 8) pour ne pas converger trop vite
                        cand_pool = [c[0] for c in reranked[min(2, len(reranked)-1):min(8, len(reranked))]]
                        word_to_play = str(np.random.choice(cand_pool)) if cand_pool else reranked[0][0]
                    else:
                        # Moyen : équilibré, choisit dans le top 2
                        cand_pool = [c[0] for c in reranked[:min(2, len(reranked))]]
                        word_to_play = str(np.random.choice(cand_pool))

        # 3. Fallback sécurité
        if not word_to_play:
            for seed in SEED_WORDS:
                s_norm = self.store.normalize(seed)
                if s_norm not in self.tried and s_norm in self.store:
                    word_to_play = s_norm
                    break

        if not word_to_play:
            word_to_play = "science"

        self.tried.add(word_to_play)
        res = self.game.score(word_to_play)
        s, p = res if res else (0.0, None)
        fn_weather = _resolve_ranking_fn("weather_for_score", weather_for_score)
        w_icon, w_lbl = fn_weather(s, p)

        self.guesses[word_to_play] = (s, p, turn_no, w_icon, w_lbl)
        return word_to_play, s, p, w_icon, w_lbl
