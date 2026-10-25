"""
Cémantix Solver — Session de Jeu Solo & Défi Quotidien
======================================================
Moteur de jeu pour les parties individuelles :
- Mode Défi du Jour (sur le mot officiel du jour)
- Mode Illimité (parties aléatoires rejouables à volonté)
- Niveaux de difficulté : Facile, Moyen, Expert
- Calcul vectoriel instantané en mémoire (NumPy cosinus + rangs ‰)
"""
import time
from typing import Optional

import numpy as np

from .common import get_weather_tier
from ..config import STOPWORDS
from ..engine import VocabStore, strip_accents


class GameSession:
    """Représente une partie de jeu active."""

    def __init__(
        self,
        game_id: str,
        mode: str,
        difficulty: str,
        puzzle_id: str,
        secret: str,
        store: VocabStore,
    ):
        self.game_id = game_id
        self.mode = mode
        self.difficulty = difficulty
        self.puzzle_id = puzzle_id
        self.secret = secret.strip().lower()
        self.store = store
        self.v_secret = store.vec(self.secret)
        self.is_won = False
        self.is_given_up = False
        self.guesses: dict[str, dict] = {}
        self.hints: list[str] = []
        self.created_at = time.time()
        self.last_activity = time.time()

        # Précalcul du seuil top 1000 pour les rangs permille exacts
        all_cos = self.store.vecs @ self.v_secret
        k = min(1000, len(all_cos))
        self.p1000_threshold = float(np.partition(all_cos, -k)[-k])
        self.top_scores = np.sort(all_cos[all_cos >= self.p1000_threshold])

    def score_word(self, word: str) -> tuple[Optional[float], Optional[int]]:
        """Calcule le score cosinus et le millième d'un mot."""
        norm = self.store.normalize(word)
        if norm not in self.store or not self.store.is_valid_french(norm):
            return None, None

        if norm == self.secret:
            return 1.0, 1000

        s = float(self.store.vec(norm) @ self.v_secret)
        p = None
        if s >= self.p1000_threshold and len(self.top_scores) > 0:
            rank = int(np.searchsorted(self.top_scores, s))
            scale = 1000.0 / len(self.top_scores)
            p = min(999, max(1, int(rank * scale)))
        return s, p

    def record_guess(self, word: str) -> dict:
        """Enregistre une tentative et retourne le résultat complet."""
        self.last_activity = time.time()
        norm = self.store.normalize(word)

        s, p = self.score_word(norm)
        if s is None:
            return {
                "error": f"Le mot « {word} » n'est pas dans le dictionnaire ou la base vectorielle.",
                "valid": False,
            }

        score_deg = round(s * 100, 2)
        weather = get_weather_tier(score_deg, p)
        is_win = (norm == self.secret)
        if is_win:
            self.is_won = True

        order = len(self.guesses) + 1
        guess_data = {
            "order": order,
            "word": norm,
            "score": score_deg,
            "permille": p,
            "weather": weather,
            "timestamp": round(self.last_activity, 2),
        }
        self.guesses[norm] = guess_data

        # Top 15 des meilleurs mots trouvés par le joueur
        sorted_guesses = sorted(
            self.guesses.values(),
            key=lambda x: x["score"],
            reverse=True,
        )

        return {
            "valid": True,
            "word": norm,
            "score": score_deg,
            "permille": p,
            "weather": weather,
            "is_win": is_win,
            "tries": len(self.guesses),
            "top_guesses": sorted_guesses[:15],
            "last_guess": guess_data,
            "secret": self.secret if is_win else None,
        }

    def request_hint(self) -> dict:
        """Génère un indice sémantique pertinent qui compte comme 1 coup au compteur."""
        if self.is_won:
            return {"error": "Partie déjà gagnée !"}
        if self.is_given_up:
            return {"error": "Partie déjà abandonnée."}

        ranked = sorted(self.guesses.values(), key=lambda x: x["score"], reverse=True)
        top_word = ranked[0]["word"] if ranked else None
        best_s = (ranked[0]["score"] / 100.0) if ranked else -1.0

        k_offset = 30 if len(self.store.words) >= 50 else 0
        if best_s > 0.10 and top_word and (top_word in self.store):
            v_best = self.store.vec(top_word)
            v_target = 0.35 * v_best + 0.65 * self.v_secret
            norm_target = np.linalg.norm(v_target)
            if norm_target > 0:
                v_target = v_target / norm_target
            cands = self.store.knn(v_target, k=80)
        else:
            cands = self.store.knn(self.v_secret, k=150)
            if k_offset > 0:
                cands = cands[k_offset:]

        secret_stem = self.secret[:min(4, len(self.secret))]
        valid_hints = []
        for w in cands:
            w_norm = self.store.normalize(w)
            if (
                w_norm not in self.guesses
                and w_norm not in self.hints
                and w_norm != self.secret
                and len(w_norm) >= 4
                and w_norm not in STOPWORDS
                and not w_norm.startswith(secret_stem)
                and not self.secret.startswith(w_norm[:min(4, len(w_norm))])
                and self.store.is_valid_french(w_norm)
            ):
                score_cos = float(np.dot(self.v_secret, self.store.vec(w_norm)))
                valid_hints.append((w_norm, score_cos))

        if not valid_hints:
            broader = self.store.knn(self.v_secret, k=min(400, len(self.store.words)))
            if k_offset > 0:
                broader = broader[k_offset:]
            for w in broader:
                w_norm = self.store.normalize(w)
                if (
                    w_norm not in self.guesses
                    and w_norm not in self.hints
                    and w_norm != self.secret
                    and len(w_norm) >= 4
                    and w_norm not in STOPWORDS
                    and not w_norm.startswith(secret_stem)
                    and not self.secret.startswith(w_norm[:min(4, len(w_norm))])
                    and self.store.is_valid_french(w_norm)
                ):
                    score_cos = float(np.dot(self.v_secret, self.store.vec(w_norm)))
                    valid_hints.append((w_norm, score_cos))

        if not valid_hints:
            for w in self.store.knn(self.v_secret, k=len(self.store.words)):
                w_norm = self.store.normalize(w)
                if w_norm != self.secret and w_norm not in self.guesses and w_norm not in self.hints:
                    score_cos = float(np.dot(self.v_secret, self.store.vec(w_norm)))
                    valid_hints.append((w_norm, score_cos))

        if not valid_hints:
            return {"error": "Aucun indice supplémentaire disponible."}

        valid_hints.sort(key=lambda x: x[1])
        chosen_hint = valid_hints[len(valid_hints) // 2][0]

        # Enregistrer l'indice comme un coup officiel (+1 coup)
        res = self.record_guess(chosen_hint)
        self.hints.append(chosen_hint)
        if chosen_hint in self.guesses:
            self.guesses[chosen_hint]["is_hint"] = True
        if res.get("last_guess"):
            res["last_guess"]["is_hint"] = True
        res["hint_word"] = chosen_hint
        return res

    def to_serializable(self) -> dict:
        return {
            "game_id": self.game_id,
            "mode": self.mode,
            "difficulty": self.difficulty,
            "puzzle_id": self.puzzle_id,
            "secret": self.secret,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "is_won": self.is_won,
            "is_given_up": getattr(self, "is_given_up", False),
            "guesses": self.guesses,
            "hints": self.hints,
        }

    @classmethod
    def from_serializable(cls, data: dict, store: VocabStore) -> "GameSession":
        session = cls(
            game_id=data["game_id"],
            mode=data["mode"],
            difficulty=data.get("difficulty", "moyen"),
            puzzle_id=data.get("puzzle_id", "--"),
            secret=data["secret"],
            store=store,
        )
        session.created_at = data.get("created_at", time.time())
        session.last_activity = data.get("last_activity", time.time())
        session.is_won = data.get("is_won", False)
        session.is_given_up = data.get("is_given_up", False)
        session.guesses = data.get("guesses", {})
        session.hints = data.get("hints", [])
        return session

    def to_dict(self, reveal_secret: bool = False) -> dict:
        sorted_guesses = sorted(
            self.guesses.values(),
            key=lambda x: x["score"],
            reverse=True,
        )
        chronological_guesses = sorted(
            self.guesses.values(),
            key=lambda x: x["order"],
            reverse=True,
        )
        last_guess = chronological_guesses[0] if chronological_guesses else None
        return {
            "game_id": self.game_id,
            "mode": self.mode,
            "difficulty": self.difficulty,
            "puzzle_id": self.puzzle_id,
            "tries": len(self.guesses),
            "is_won": self.is_won,
            "is_given_up": getattr(self, "is_given_up", False),
            "hints": list(self.hints),
            "secret": self.secret if (self.is_won or reveal_secret) else None,
            "top_guesses": sorted_guesses[:15],
            "history": chronological_guesses,
            "last_guess": last_guess,
            "created_at": self.created_at,
        }
