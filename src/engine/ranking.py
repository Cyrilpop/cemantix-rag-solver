"""
Cémantix Solver — Algorithmes Mathématiques, Ridge & Reranking (src.engine.ranking)
==================================================================================
Fournit les fonctions pures pour :
- La conversion météo officielle Cémantix (weather_for_score)
- L'estimation de direction sémantique par régression Ridge de Tikhonov (estimate_secret)
- Le reranking multicritère par cohérence quadratique pondérée (rerank)
"""
from typing import Optional, TYPE_CHECKING
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
