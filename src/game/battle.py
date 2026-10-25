"""
Cémantix Solver — Session de Mode Battle (Joueur vs Bot IA)
===========================================================
Moteur de jeu pour les duels asynchrones ou en direct contre l'IA RAG :
- RAG duel player (RagDuelPlayer) avec différents niveaux d'heuristique
- Double mot secret (mot du joueur vs mot de l'IA)
- Tour par tour strict avec réplique instantanée du bot
- 3 paliers d'indices gradués (Général, Intermédiaire, Proche)
"""
import time
from typing import Optional

from .common import get_weather_tier
from ..config import STOPWORDS
from ..engine import MockClient, RagDuelPlayer, VocabStore


class BattleSession:
    """Représente une manche ou session active de Mode Battle (Joueur vs Bot IA)."""

    def __init__(
        self,
        battle_id: str,
        difficulty: str,
        player_secret: str,
        ai_secret: str,
        store: VocabStore,
        stats: Optional[dict] = None,
    ):
        self.battle_id = battle_id
        self.difficulty = difficulty.lower() if difficulty in ("facile", "moyen", "expert") else "moyen"
        self.player_secret = player_secret.strip().lower()
        self.ai_secret = ai_secret.strip().lower()
        self.store = store

        self.game_human = MockClient(store, secret=self.player_secret)
        self.game_ai = MockClient(store, secret=self.ai_secret)
        self.ai_player = RagDuelPlayer(store, self.game_ai, difficulty=self.difficulty)

        self.turn_no = 0
        self.player_guesses: dict[str, dict] = {}
        self.ai_guesses: dict[str, dict] = {}
        self.hints_used: list[dict] = []  # max 3
        self.last_player_guess: Optional[dict] = None
        self.last_ai_guess: Optional[dict] = None

        self.winner: Optional[str] = None  # "player", "ai", "draw", "giveup"
        self.is_finished = False
        self.created_at = time.time()
        self.last_activity = time.time()

        self.stats = stats if stats else {
            "player": 0,
            "ai": 0,
            "draws": 0,
            "match": 1,
            "difficulty": self.difficulty,
        }

    def _calc_progress(self, guesses: dict[str, dict]) -> tuple[float, Optional[int], float]:
        """Retourne (meilleur score °C, meilleur permille, pourcentage de progression 0-100%)."""
        if not guesses:
            return 0.0, None, 0.0
        best_p = max([g["permille"] for g in guesses.values() if g["permille"] is not None], default=None)
        best_s = max([g["score"] for g in guesses.values()], default=0.0)
        if best_p is not None:
            pct = round(min(100.0, max(0.0, best_p / 10.0)), 1)
        else:
            # En dehors du top 1000, progression graduée jusqu'à 35% max
            pct = round(min(35.0, max(0.0, (best_s / 40.0) * 35.0)), 1)
        return best_s, best_p, pct

    def record_player_guess(self, word: str) -> dict:
        """Traite le mot joué par le joueur, fait répliquer le bot, et évalue l'issue."""
        if self.is_finished:
            return {"error": "Cette manche est déjà terminée.", "valid": False}

        self.last_activity = time.time()
        norm = self.store.normalize(word)
        if norm not in self.store or not self.store.is_valid_french(norm):
            return {
                "error": f"Le mot « {word} » n'est pas dans le dictionnaire ou la base vectorielle.",
                "valid": False,
            }

        if norm in self.player_guesses:
            return {
                "error": f"Vous avez déjà testé le mot « {word.upper()} » dans cette manche.",
                "valid": False,
            }

        # 1. Évaluation du coup humain
        res_h = self.game_human.score(norm)
        if res_h is None:
            return {"error": f"Le mot « {word} » a été rejeté par le moteur de jeu.", "valid": False}
        s_h, p_h = res_h
        score_deg_h = round(s_h * 100, 2)
        weather_h = get_weather_tier(score_deg_h, p_h)

        self.turn_no += 1
        guess_data_h = {
            "order": self.turn_no,
            "word": norm,
            "score": score_deg_h,
            "permille": p_h,
            "weather": weather_h,
            "is_hint": False,
            "timestamp": round(self.last_activity, 2),
        }
        self.player_guesses[norm] = guess_data_h
        self.last_player_guess = guess_data_h
        player_won = (norm == self.player_secret or p_h == 1000)

        # 2. Réplique immédiate du Bot IA
        w_ai, s_ai, p_ai, icon_ai, lbl_ai = self.ai_player.play_turn(self.turn_no)
        score_deg_ai = round(s_ai * 100, 2)
        weather_ai = f"{icon_ai} {lbl_ai}"
        guess_data_ai = {
            "order": self.turn_no,
            "word": w_ai,
            "score": score_deg_ai,
            "permille": p_ai,
            "weather": weather_ai,
            "timestamp": round(self.last_activity, 2),
        }
        self.ai_guesses[w_ai] = guess_data_ai
        self.last_ai_guess = guess_data_ai
        ai_won = (w_ai == self.ai_secret or p_ai == 1000)

        # 3. Vérification des conditions de victoire
        if player_won or ai_won:
            self.is_finished = True
            if player_won and ai_won:
                self.winner = "draw"
                self.stats["draws"] += 1
            elif player_won:
                self.winner = "player"
                self.stats["player"] += 1
            else:
                self.winner = "ai"
                self.stats["ai"] += 1

        return self.to_dict(reveal_secret=self.is_finished)

    def request_hint(self) -> dict:
        """Génère 1 des 3 indices autorisés (du plus général au plus proche) et consomme 1 tour."""
        if self.is_finished:
            return {"error": "Cette manche est déjà terminée.", "valid": False}
        if len(self.hints_used) >= 3:
            return {"error": "Vous avez déjà utilisé vos 3 indices autorisés pour cette manche.", "valid": False}

        self.last_activity = time.time()
        tier = len(self.hints_used) + 1  # 1, 2 ou 3
        tier_label = "Général" if tier == 1 else ("Intermédiaire" if tier == 2 else "Proche")

        v_sec = self.game_human.v_secret
        secret_stem = self.player_secret[:min(4, len(self.player_secret))]

        # Sélection des candidats gradués selon le palier (du plus général au plus proche)
        if tier == 1:
            # Indice 1 (Général) : Voisins modérément proches (rangs 120 à 300)
            raw_cands = self.store.knn(v_sec, k=min(320, len(self.store.words)))[100:]
        elif tier == 2:
            # Indice 2 (Intermédiaire) : Voisins plus proches (rangs 35 à 110)
            raw_cands = self.store.knn(v_sec, k=min(120, len(self.store.words)))[30:110]
        else:
            # Indice 3 (Proche) : Voisins très proches / brûlants (rangs 2 à 30)
            raw_cands = self.store.knn(v_sec, k=min(35, len(self.store.words)))[1:35]

        valid_hints = []
        for raw_w in raw_cands:
            w = self.store.normalize(raw_w)
            if (
                w not in self.player_guesses
                and w not in [h["word"] for h in self.hints_used]
                and w != self.player_secret
                and len(w) >= 4
                and w not in STOPWORDS
                and not w.startswith(secret_stem)
                and not self.player_secret.startswith(w[:min(4, len(w))])
                and self.store.is_valid_french(w)
            ):
                res = self.game_human.score(w)
                if res:
                    valid_hints.append((w, res[0], res[1]))

        # Fallback de secours si la tranche ciblée est vide
        if not valid_hints:
            broader = self.store.knn(v_sec, k=min(400, len(self.store.words)))
            for raw_w in broader:
                w = self.store.normalize(raw_w)
                if (
                    w not in self.player_guesses
                    and w not in [h["word"] for h in self.hints_used]
                    and w != self.player_secret
                    and len(w) >= 4
                    and w not in STOPWORDS
                    and not w.startswith(secret_stem)
                    and self.store.is_valid_french(w)
                ):
                    res = self.game_human.score(w)
                    if res:
                        valid_hints.append((w, res[0], res[1]))
                        if len(valid_hints) >= 20:
                            break

        if not valid_hints:
            return {"error": "Aucun indice supplémentaire disponible.", "valid": False}

        # Tri par score croissant pour choisir le milieu de tranche
        valid_hints.sort(key=lambda x: x[1])
        chosen_hint, s_h, p_h = valid_hints[len(valid_hints) // 2]

        score_deg_h = round(s_h * 100, 2)
        weather_h = get_weather_tier(score_deg_h, p_h)

        # 1 tour consommé pour le joueur
        self.turn_no += 1
        guess_data_h = {
            "order": self.turn_no,
            "word": chosen_hint,
            "score": score_deg_h,
            "permille": p_h,
            "weather": weather_h,
            "is_hint": True,
            "hint_tier": tier,
            "timestamp": round(self.last_activity, 2),
        }
        self.player_guesses[chosen_hint] = guess_data_h
        self.last_player_guess = guess_data_h
        player_won = (chosen_hint == self.player_secret or p_h == 1000)

        hint_info = {
            "tier": tier,
            "tier_label": tier_label,
            "word": chosen_hint,
            "score": score_deg_h,
            "permille": p_h,
            "weather": weather_h,
            "turn": self.turn_no,
        }
        self.hints_used.append(hint_info)

        # Réplique immédiate du bot IA pour ce tour consommé
        w_ai, s_ai, p_ai, icon_ai, lbl_ai = self.ai_player.play_turn(self.turn_no)
        score_deg_ai = round(s_ai * 100, 2)
        weather_ai = f"{icon_ai} {lbl_ai}"
        guess_data_ai = {
            "order": self.turn_no,
            "word": w_ai,
            "score": score_deg_ai,
            "permille": p_ai,
            "weather": weather_ai,
            "timestamp": round(self.last_activity, 2),
        }
        self.ai_guesses[w_ai] = guess_data_ai
        self.last_ai_guess = guess_data_ai
        ai_won = (w_ai == self.ai_secret or p_ai == 1000)

        if player_won or ai_won:
            self.is_finished = True
            if player_won and ai_won:
                self.winner = "draw"
                self.stats["draws"] += 1
            elif player_won:
                self.winner = "player"
                self.stats["player"] += 1
            else:
                self.winner = "ai"
                self.stats["ai"] += 1

        res = self.to_dict(reveal_secret=self.is_finished)
        res["hint_awarded"] = hint_info
        return res

    def give_up(self) -> dict:
        """Déclare forfait : le point va au bot IA et les mots secrets sont révélés."""
        if not self.is_finished:
            self.is_finished = True
            self.winner = "giveup"
            self.stats["ai"] += 1
        return self.to_dict(reveal_secret=True)

    def to_dict(self, reveal_secret: bool = False) -> dict:
        """Convertit l'état du duel en structure JSON optimisée pour l'IHM."""
        sorted_player = sorted(self.player_guesses.values(), key=lambda x: x["score"], reverse=True)
        chrono_player = sorted(self.player_guesses.values(), key=lambda x: x["order"], reverse=True)
        best_s_p, best_perm_p, prog_p = self._calc_progress(self.player_guesses)

        sorted_ai = sorted(self.ai_guesses.values(), key=lambda x: x["score"], reverse=True)
        chrono_ai = sorted(self.ai_guesses.values(), key=lambda x: x["order"], reverse=True)
        best_s_ai, best_perm_ai, prog_ai = self._calc_progress(self.ai_guesses)

        return {
            "valid": True,
            "battle_id": self.battle_id,
            "difficulty": self.difficulty,
            "turn_no": self.turn_no,
            "is_finished": self.is_finished,
            "winner": self.winner,
            "stats": self.stats,
            "hints_used": self.hints_used,
            "hints_remaining": max(0, 3 - len(self.hints_used)),
            "player": {
                "last_guess": self.last_player_guess,
                "top_guesses": sorted_player[:15],
                "history": chrono_player,
                "best_score": best_s_p,
                "best_permille": best_perm_p,
                "progress_pct": prog_p,
                "secret": self.player_secret if (self.is_finished or reveal_secret) else None,
            },
            "ai": {
                "target": self.ai_secret,
                "last_guess": self.last_ai_guess,
                "top_guesses": sorted_ai[:15],
                "history": chrono_ai,
                "best_score": best_s_ai,
                "best_permille": best_perm_ai,
                "progress_pct": prog_ai,
                "secret": self.ai_secret,
            },
            "created_at": self.created_at,
        }
