"""
Cémantix Solver — Algorithmes Mathématiques, Ridge & Reranking (src.engine.ranking)
==================================================================================
Fournit les fonctions pures pour :
- La conversion météo officielle Cémantix (weather_for_score)
- L'estimation de direction sémantique par régression Ridge de Tikhonov (estimate_secret)
- Le reranking multicritère par cohérence quadratique pondérée (rerank)
"""
from typing import Any, Optional, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .vocab import VocabStore


def weather_for_score(s: float, p: Optional[int]) -> tuple[str, str]:
    """Retourne l'icône et le libellé météo officiel selon le score et le permille."""
    if p == 1000:
        return "🥳", "GAGNÉ"
    elif p and p >= 999:
        return "😱", "BRÛL."
    elif p and p >= 990:
        return "🔥", "CHAUD"
    elif p and p >= 900:
        return "🥵", "CHAUD"
    elif p and p >= 1:
        return "😎", "TIÈDE"
    elif s >= 0.15:
        return "🥶", "FRAIS"
    elif s >= 0:
        return "🥶", "FROID"
    else:
        return "🧊", "GLAC."


def estimate_secret(G: np.ndarray, s: np.ndarray, lam: float = 0.1) -> np.ndarray:
    """Ridge : q = Gᵀ (G Gᵀ + λI)⁻¹ s  -> direction telle que G q ≈ s."""
    q = G.T @ np.linalg.solve(G @ G.T + lam * np.eye(len(s)), s)
    return q / np.linalg.norm(q)


def rerank(store: "VocabStore", cands: list, G: np.ndarray, s: np.ndarray, q_est: np.ndarray) -> list:
    """Reranking multicritère : combine la température estimée et la cohérence
    quadratique pondérée vers les essais chauds."""
    if not cands:
        return []
    C = np.vstack([store.vec(w) for w in cands])
    weights = np.exp((s - s.max()) / 0.1)
    err = (((C @ G.T) - s) ** 2 * weights).sum(axis=1) / weights.sum()
    pred_temp = (C @ q_est) * 100.0
    # Score d'excellence : favorise les candidats chauds tout en pénalisant l'incohérence
    rank_score = pred_temp - 120.0 * np.sqrt(err)
    order = np.argsort(rank_score)[::-1]
    return [(cands[i], float(pred_temp[i]), float(err[i])) for i in order]


class WordScorer:
    """Calculateur optimisé de score (°C) et de permille (1..999) pour un mot secret donné."""

    def __init__(self, secret_word: str, store: Any):
        self.store = store
        self.raw_secret = secret_word
        self.norm_secret = store.normalize(secret_word) if hasattr(store, "normalize") else secret_word.strip().lower()
        self.is_valid = bool(self.norm_secret and self.store and self.norm_secret in self.store)
        self.v_secret = None
        self.threshold = None
        self.top_scores = None

        if self.is_valid:
            self.v_secret = self.store.vec(self.norm_secret)
            all_cos = self.store.vecs @ self.v_secret
            k = min(1000, len(all_cos))
            self.threshold = float(np.partition(all_cos, -k)[-k])
            self.top_scores = np.sort(all_cos[all_cos >= self.threshold])

    def score(self, word: str) -> tuple[float, Optional[int]]:
        """Calcule (score_deg, permille) pour le mot donné par rapport au mot secret.

        Retourne (score, permille) où permille est un entier dans [1, 999] si dans le top 1000, sinon None.
        Si le mot ou le secret est hors vocabulaire, retourne (0.0, None).
        """
        if not self.is_valid or not word:
            return 0.0, None

        norm_w = self.store.normalize(word) if hasattr(self.store, "normalize") else word.strip().lower()
        if norm_w not in self.store:
            return 0.0, None

        cos_val = float(self.store.vec(norm_w) @ self.v_secret)
        deg_score = round(cos_val * 100.0, 2)

        if self.threshold is not None and cos_val >= self.threshold and self.top_scores is not None:
            pm = int(np.searchsorted(self.top_scores, cos_val))
            permille = min(999, max(1, pm))
            return deg_score, permille

        return deg_score, None

