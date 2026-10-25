"""
Cémantix Solver — API Locale du Jeu Interactif (Web)
====================================================
Fournit une micro-API HTTP haute performance pour jouer à Cémantix directement
sur l'interface web :
- Mode Défi du Jour (sur le mot officiel du jour résolu par le démon)
- Mode Illimité (parties aléatoires rejouables à volonté)
- Niveaux de difficulté : Facile, Moyen, Expert
- Calcul vectoriel instantané en mémoire (NumPy cosinus + rangs ‰ en <0.1ms)
- Zéro dépendance externe (utilise http.server standard multi-threadé)
"""
import json
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

import numpy as np

from .clients import MockClient
from .config import DATA_DIR, STOPWORDS, log
from .daemon import DAILY_HISTORY_FILE, load_history
from .solvers import RagDuelPlayer
from .vocab import VocabStore, strip_accents

WEB_SESSIONS_FILE = DATA_DIR / "web_sessions.json"
MULTI_SESSIONS_FILE = DATA_DIR / "multi_sessions.json"


def get_weather_tier(score: float, permille: Optional[int]) -> str:
    """Retourne l'icône et libellé météo officiel de Cémantix."""
    if permille == 1000 or score >= 100.0:
        return "🥳 Trouvé !"
    if permille is not None:
        if permille >= 990:
            return "😱 Brûlant"
        if permille >= 900:
            return "🥵 Très chaud"
        return "😎 Chaud"
    if score >= 15.0:
        return "🥶 Frais"
    if score >= 0.0:
        return "🥶 Froid"
    return "🧊 Glacé"



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


class MultiplayerSession:
    """Représente une partie multijoueur 1v1 asynchrone ou en direct (Même Mot ou Mots Choisis)."""

    def __init__(
        self,
        room_id: str,
        mode: str,
        difficulty: str,
        store: VocabStore,
        key_p1: Optional[str] = None,
        key_p2: Optional[str] = None,
        target_for_p1: Optional[str] = None,
        target_for_p2: Optional[str] = None,
        p1_name: str = "Joueur 1",
        p2_name: str = "Joueur 2",
        current_turn: str = "p1",
        turn_no: int = 0,
        winner: Optional[str] = None,
        is_finished: bool = False,
        p1_guesses: Optional[dict[str, dict]] = None,
        p2_guesses: Optional[dict[str, dict]] = None,
        p1_hints_used: Optional[list[dict]] = None,
        p2_hints_used: Optional[list[dict]] = None,
        p2_joined: bool = False,
        state: Optional[str] = None,
        created_at: Optional[float] = None,
        last_activity: Optional[float] = None,
    ):
        self.room_id = room_id.strip().upper()
        self.mode = "custom_words" if mode == "custom_words" else "same_word"
        self.difficulty = difficulty.lower() if difficulty in ("facile", "moyen", "expert") else "moyen"
        self.store = store

        self.key_p1 = key_p1.strip().upper() if key_p1 else f"J1-{uuid.uuid4().hex[:4].upper()}"
        self.key_p2 = key_p2.strip().upper() if key_p2 else f"J2-{uuid.uuid4().hex[:4].upper()}"

        self.p1_name = p1_name.strip() or "Joueur 1"
        self.p2_name = p2_name.strip() or "Joueur 2"
        self.p2_joined = bool(p2_joined)

        self.current_turn = current_turn if current_turn in ("p1", "p2") else "p1"
        self.turn_no = turn_no
        self.winner = winner
        self.is_finished = is_finished

        self.p1_guesses: dict[str, dict] = p1_guesses if p1_guesses is not None else {}
        self.p2_guesses: dict[str, dict] = p2_guesses if p2_guesses is not None else {}
        self.p1_hints_used: list[dict] = p1_hints_used if p1_hints_used is not None else []
        self.p2_hints_used: list[dict] = p2_hints_used if p2_hints_used is not None else []

        self.last_p1_guess: Optional[dict] = None
        self.last_p2_guess: Optional[dict] = None
        if self.p1_guesses:
            latest_p1 = max(self.p1_guesses.values(), key=lambda x: x["order"])
            self.last_p1_guess = latest_p1
        if self.p2_guesses:
            latest_p2 = max(self.p2_guesses.values(), key=lambda x: x["order"])
            self.last_p2_guess = latest_p2

        self.created_at = created_at if created_at else time.time()
        self.last_activity = last_activity if last_activity else time.time()

        # Cibles secrètes et clients MockClient
        self.target_for_p1 = target_for_p1.strip().lower() if target_for_p1 else None
        self.target_for_p2 = target_for_p2.strip().lower() if target_for_p2 else None

        self.client_p1: Optional[MockClient] = None
        self.client_p2: Optional[MockClient] = None

        if self.mode == "same_word":
            if self.target_for_p1:
                self.target_for_p2 = self.target_for_p1
                self.client_p1 = MockClient(store, secret=self.target_for_p1)
                self.client_p2 = self.client_p1
            self.state = state if state else ("finished" if self.is_finished else "in_progress")
        else:
            if self.target_for_p1:
                self.client_p1 = MockClient(store, secret=self.target_for_p1)
            if self.target_for_p2:
                self.client_p2 = MockClient(store, secret=self.target_for_p2)
            if self.client_p1 and self.client_p2:
                self.state = state if state else ("finished" if self.is_finished else "in_progress")
            else:
                self.state = state if state else "waiting_words"

    def get_role(self, player_key: Optional[str]) -> Optional[str]:
        if not player_key:
            return None
        k = player_key.strip().upper()
        if k == self.key_p1.upper():
            return "p1"
        if k == self.key_p2.upper():
            return "p2"
        return None

    def _calc_progress(self, guesses: dict[str, dict]) -> tuple[float, Optional[int], float]:
        if not guesses:
            return 0.0, None, 0.0
        best_p = max([g["permille"] for g in guesses.values() if g.get("permille") is not None], default=None)
        best_s = max([g["score"] for g in guesses.values()], default=0.0)
        if best_p is not None:
            pct = round(min(100.0, max(0.0, best_p / 10.0)), 1)
        else:
            pct = round(min(35.0, max(0.0, (best_s / 40.0) * 35.0)), 1)
        return best_s, best_p, pct

    def setup_word(self, player_key: str, word: str) -> dict:
        role = self.get_role(player_key)
        if not role:
            return {"valid": False, "error": "Clé joueur invalide."}
        if self.mode != "custom_words":
            return {"valid": False, "error": "Cette partie utilise un mot commun généré automatiquement."}
        if self.is_finished:
            return {"valid": False, "error": "Cette partie est déjà terminée."}

        cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", word.strip()).lower()
        norm = self.store.normalize(cleaned)
        if not norm or norm not in self.store or not self.store.is_valid_french(norm):
            return {"valid": False, "error": f"Le mot « {word} » n'est pas reconnu dans le dictionnaire officiel."}

        if role == "p1":
            self.target_for_p2 = norm
            self.client_p2 = MockClient(self.store, secret=norm)
        else:
            self.target_for_p1 = norm
            self.client_p1 = MockClient(self.store, secret=norm)

        if self.client_p1 and self.client_p2:
            self.state = "in_progress"

        self.last_activity = time.time()
        return self.to_dict(player_key)

    def record_guess(self, player_key: str, word: str) -> dict:
        role = self.get_role(player_key)
        if not role:
            return {"valid": False, "error": "Clé joueur invalide."}
        if self.is_finished:
            return {"valid": False, "error": "Cette partie est déjà terminée."}
        if self.state != "in_progress":
            return {"valid": False, "error": "La partie n'a pas encore démarré (en attente des mots secrets)."}
        if self.current_turn != role:
            return {"valid": False, "error": "Ce n'est pas votre tour de jouer. En attente du coup adverse."}

        cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", word.strip()).lower()
        norm = self.store.normalize(cleaned)
        if not norm or norm not in self.store or not self.store.is_valid_french(norm):
            return {"valid": False, "error": f"Le mot « {word} » n'est pas dans le dictionnaire officiel."}

        my_guesses = self.p1_guesses if role == "p1" else self.p2_guesses
        if norm in my_guesses:
            return {"valid": False, "error": f"Vous avez déjà testé le mot « {word.upper()} » dans ce duel."}

        client = self.client_p1 if role == "p1" else self.client_p2
        if not client:
            return {"valid": False, "error": "Moteur de jeu non initialisé."}

        res = client.score(norm)
        if res is None:
            return {"valid": False, "error": f"Le mot « {word} » a été rejeté par le moteur de jeu."}

        s, p = res
        score_deg = round(s * 100, 2)
        weather = get_weather_tier(score_deg, p)

        self.turn_no += 1
        self.last_activity = time.time()

        guess_data = {
            "order": self.turn_no,
            "word": norm,
            "score": score_deg,
            "permille": p,
            "weather": weather,
            "is_hint": False,
            "timestamp": round(self.last_activity, 2),
        }
        my_guesses[norm] = guess_data
        if role == "p1":
            self.last_p1_guess = guess_data
        else:
            self.last_p2_guess = guess_data

        target = self.target_for_p1 if role == "p1" else self.target_for_p2
        is_win = (norm == target or p == 1000)

        if is_win:
            self.is_finished = True
            self.winner = role
            self.state = "finished"
        else:
            self.current_turn = "p2" if role == "p1" else "p1"

        return self.to_dict(player_key)

    def request_hint(self, player_key: str) -> dict:
        role = self.get_role(player_key)
        if not role:
            return {"valid": False, "error": "Clé joueur invalide."}
        if self.is_finished:
            return {"valid": False, "error": "Cette partie est déjà terminée."}
        if self.state != "in_progress":
            return {"valid": False, "error": "La partie n'a pas encore démarré."}
        if self.current_turn != role:
            return {"valid": False, "error": "Ce n'est pas votre tour de jouer."}

        my_hints = self.p1_hints_used if role == "p1" else self.p2_hints_used
        if len(my_hints) >= 3:
            return {"valid": False, "error": "Vous avez déjà utilisé vos 3 indices autorisés."}

        tier = len(my_hints) + 1
        tier_label = "Général" if tier == 1 else ("Intermédiaire" if tier == 2 else "Proche")

        client = self.client_p1 if role == "p1" else self.client_p2
        target = self.target_for_p1 if role == "p1" else self.target_for_p2
        v_sec = client.v_secret
        secret_stem = target[:min(4, len(target))]

        if tier == 1:
            raw_cands = self.store.knn(v_sec, k=min(320, len(self.store.words)))[100:]
        elif tier == 2:
            raw_cands = self.store.knn(v_sec, k=min(120, len(self.store.words)))[30:110]
        else:
            raw_cands = self.store.knn(v_sec, k=min(35, len(self.store.words)))[1:35]

        my_guesses = self.p1_guesses if role == "p1" else self.p2_guesses
        valid_hints = []
        for raw_w in raw_cands:
            w = self.store.normalize(raw_w)
            if (
                w != target
                and not w.startswith(secret_stem)
                and w not in my_guesses
                and w not in STOPWORDS
                and len(w) >= 4
                and self.store.is_valid_french(w)
            ):
                valid_hints.append(w)

        if not valid_hints:
            valid_hints = [w for w in raw_cands if w != target and w not in my_guesses]

        hint_word = str(np.random.choice(valid_hints[:15])) if valid_hints else "soleil"
        res = client.score(hint_word)
        s, p = res if res else (0.1, None)
        score_deg = round(s * 100, 2)
        weather = get_weather_tier(score_deg, p)

        self.turn_no += 1
        self.last_activity = time.time()
        guess_data = {
            "order": self.turn_no,
            "word": hint_word,
            "score": score_deg,
            "permille": p,
            "weather": weather,
            "is_hint": True,
            "timestamp": round(self.last_activity, 2),
        }
        my_guesses[hint_word] = guess_data
        if role == "p1":
            self.last_p1_guess = guess_data
        else:
            self.last_p2_guess = guess_data

        hint_info = {
            "tier": tier,
            "tier_label": tier_label,
            "word": hint_word,
            "score": score_deg,
            "permille": p,
        }
        my_hints.append(hint_info)

        # Passe le tour à l'adversaire
        self.current_turn = "p2" if role == "p1" else "p1"

        res = self.to_dict(player_key)
        res["hint_awarded"] = hint_info
        return res

    def give_up(self, player_key: str) -> dict:
        role = self.get_role(player_key)
        if not role:
            return {"valid": False, "error": "Clé joueur invalide."}
        if not self.is_finished:
            self.is_finished = True
            self.winner = "giveup_" + role
            self.state = "finished"
            self.last_activity = time.time()
        return self.to_dict(player_key)

    def to_dict(self, player_key: str) -> dict:
        role = self.get_role(player_key)
        if not role:
            return {"valid": False, "error": "Clé joueur invalide."}

        is_p1 = (role == "p1")
        my_guesses_dict = self.p1_guesses if is_p1 else self.p2_guesses
        opp_guesses_dict = self.p2_guesses if is_p1 else self.p1_guesses
        my_hints = self.p1_hints_used if is_p1 else self.p2_hints_used
        opp_hints = self.p2_hints_used if is_p1 else self.p1_hints_used
        my_last = self.last_p1_guess if is_p1 else self.last_p2_guess
        opp_last = self.last_p2_guess if is_p1 else self.last_p1_guess

        my_sorted = sorted(my_guesses_dict.values(), key=lambda x: x["score"], reverse=True)
        my_chrono = sorted(my_guesses_dict.values(), key=lambda x: x["order"], reverse=True)
        my_best_s, my_best_p, my_prog = self._calc_progress(my_guesses_dict)

        opp_sorted = sorted(opp_guesses_dict.values(), key=lambda x: x["score"], reverse=True)
        opp_chrono = sorted(opp_guesses_dict.values(), key=lambda x: x["order"], reverse=True)
        opp_best_s, opp_best_p, opp_prog = self._calc_progress(opp_guesses_dict)

        mask_opponent = (self.mode == "same_word" and not self.is_finished)

        def _mask(g: Optional[dict]) -> Optional[dict]:
            if not g:
                return None
            if not mask_opponent:
                return g
            masked = dict(g)
            masked["word"] = "••••••••"
            return masked

        opp_history_masked = [_mask(g) for g in opp_chrono]
        opp_top_masked = [_mask(g) for g in opp_sorted[:15]]
        opp_last_masked = _mask(opp_last)

        # Mots cibles secrets
        if self.mode == "same_word":
            my_target = self.target_for_p1 if self.is_finished else None
            opp_target = self.target_for_p2 if self.is_finished else None
        else:
            if is_p1:
                my_target = self.target_for_p1 if self.is_finished else None
                opp_target = self.target_for_p2
            else:
                my_target = self.target_for_p2 if self.is_finished else None
                opp_target = self.target_for_p1

        # Statut de victoire
        has_won = False
        has_lost = False
        is_draw = (self.winner == "draw")
        if self.is_finished and not is_draw:
            if self.winner == role or (self.winner == "giveup_p2" and is_p1) or (self.winner == "giveup_p1" and not is_p1):
                has_won = True
            else:
                has_lost = True

        is_my_turn = (self.current_turn == role) and (self.state == "in_progress") and (not self.is_finished)

        waiting_for_words = (self.state == "waiting_words")
        i_need_to_set_word = False
        if self.mode == "custom_words" and waiting_for_words:
            if is_p1 and not self.target_for_p2:
                i_need_to_set_word = True
            elif not is_p1 and not self.target_for_p1:
                i_need_to_set_word = True

        return {
            "valid": True,
            "room_id": self.room_id,
            "mode": self.mode,
            "difficulty": self.difficulty,
            "state": self.state,
            "current_turn": self.current_turn,
            "is_my_turn": is_my_turn,
            "turn_no": self.turn_no,
            "is_finished": self.is_finished,
            "winner": self.winner,
            "has_won": has_won,
            "has_lost": has_lost,
            "is_draw": is_draw,
            "role": role,
            "player_key": self.key_p1 if is_p1 else self.key_p2,
            "guest_key": self.key_p2 if is_p1 else None,
            "share_url": f"/multi/?r={self.room_id}&k={self.key_p2}",
            "p2_joined": self.p2_joined,
            "waiting_for_words": waiting_for_words,
            "i_need_to_set_word": i_need_to_set_word,
            "me": {
                "role": role,
                "name": self.p1_name if is_p1 else self.p2_name,
                "last_guess": my_last,
                "top_guesses": my_sorted[:15],
                "history": my_chrono,
                "best_score": my_best_s,
                "best_permille": my_best_p,
                "progress_pct": my_prog,
                "hints_used": my_hints,
                "hints_remaining": max(0, 3 - len(my_hints)),
                "target": my_target,
            },
            "opponent": {
                "role": "p2" if is_p1 else "p1",
                "name": self.p2_name if is_p1 else self.p1_name,
                "last_guess": opp_last_masked,
                "top_guesses": opp_top_masked,
                "history": opp_history_masked,
                "best_score": opp_best_s,
                "best_permille": opp_best_p,
                "progress_pct": opp_prog,
                "hints_used": opp_hints,
                "hints_remaining": max(0, 3 - len(opp_hints)),
                "target": opp_target,
            },
            "created_at": self.created_at,
            "last_activity": self.last_activity,
        }

    def to_serializable(self) -> dict:
        return {
            "room_id": self.room_id,
            "mode": self.mode,
            "difficulty": self.difficulty,
            "key_p1": self.key_p1,
            "key_p2": self.key_p2,
            "target_for_p1": self.target_for_p1,
            "target_for_p2": self.target_for_p2,
            "p1_name": self.p1_name,
            "p2_name": self.p2_name,
            "p2_joined": self.p2_joined,
            "current_turn": self.current_turn,
            "turn_no": self.turn_no,
            "winner": self.winner,
            "is_finished": self.is_finished,
            "p1_guesses": self.p1_guesses,
            "p2_guesses": self.p2_guesses,
            "p1_hints_used": self.p1_hints_used,
            "p2_hints_used": self.p2_hints_used,
            "state": self.state,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
        }

    @classmethod
    def from_serializable(cls, data: dict, store: VocabStore) -> "MultiplayerSession":
        return cls(
            room_id=data["room_id"],
            mode=data.get("mode", "same_word"),
            difficulty=data.get("difficulty", "moyen"),
            store=store,
            key_p1=data.get("key_p1"),
            key_p2=data.get("key_p2"),
            target_for_p1=data.get("target_for_p1"),
            target_for_p2=data.get("target_for_p2"),
            p1_name=data.get("p1_name", "Joueur 1"),
            p2_name=data.get("p2_name", "Joueur 2"),
            current_turn=data.get("current_turn", "p1"),
            turn_no=data.get("turn_no", 0),
            winner=data.get("winner"),
            is_finished=data.get("is_finished", False),
            p1_guesses=data.get("p1_guesses", {}),
            p2_guesses=data.get("p2_guesses", {}),
            p1_hints_used=data.get("p1_hints_used", []),
            p2_hints_used=data.get("p2_hints_used", []),
            p2_joined=data.get("p2_joined", False),
            state=data.get("state"),
            created_at=data.get("created_at"),
            last_activity=data.get("last_activity"),
        )


class GameManager:
    """Gestionnaire centralisé des parties en mémoire et sur disque (persistance volume)."""

    def __init__(self, store: VocabStore):
        self.store = store
        self.sessions: dict[str, GameSession] = {}
        self.battle_sessions: dict[str, BattleSession] = {}
        self.multi_sessions: dict[str, MultiplayerSession] = {}
        self.lock = threading.Lock()
        self._init_difficulty_pools()
        self._load_sessions()

    def _save_sessions(self):
        """Persiste les sessions actives sur disque (volume Docker)."""
        try:
            WEB_SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            serializable = {
                gid: s.to_serializable()
                for gid, s in self.sessions.items()
            }
            tmp = WEB_SESSIONS_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False)
            tmp.replace(WEB_SESSIONS_FILE)

            serializable_multi = {
                rid: s.to_serializable()
                for rid, s in self.multi_sessions.items()
            }
            tmp_multi = MULTI_SESSIONS_FILE.with_suffix(".tmp")
            with open(tmp_multi, "w", encoding="utf-8") as f:
                json.dump(serializable_multi, f, ensure_ascii=False)
            tmp_multi.replace(MULTI_SESSIONS_FILE)
        except Exception as e:
            log(f"⚠️  Erreur sauvegarde sessions : {e}")

    def _load_sessions(self):
        """Recharge les sessions sauvegardées depuis le volume Docker."""
        if WEB_SESSIONS_FILE.exists():
            try:
                with open(WEB_SESSIONS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                now = time.time()
                max_age = 86400.0  # 24 heures de conservation
                loaded_count = 0
                for gid, sdata in data.items():
                    if (now - sdata.get("last_activity", 0)) <= max_age:
                        secret = sdata.get("secret", "")
                        if secret and secret in self.store:
                            self.sessions[gid] = GameSession.from_serializable(sdata, self.store)
                            loaded_count += 1
                if loaded_count > 0:
                    log(f"💾  [API JEU] {loaded_count} session(s) active(s) restaurée(s) depuis le disque.")
            except Exception as e:
                log(f"⚠️  Erreur lecture web_sessions.json : {e}")

        if MULTI_SESSIONS_FILE.exists():
            try:
                with open(MULTI_SESSIONS_FILE, "r", encoding="utf-8") as f:
                    mdata = json.load(f)
                now = time.time()
                max_age_multi = 7 * 86400.0  # 7 jours de conservation
                loaded_multi = 0
                for rid, sdata in mdata.items():
                    if (now - sdata.get("last_activity", 0)) <= max_age_multi:
                        t1 = sdata.get("target_for_p1")
                        t2 = sdata.get("target_for_p2")
                        if (not t1 or t1 in self.store) and (not t2 or t2 in self.store):
                            try:
                                self.multi_sessions[rid] = MultiplayerSession.from_serializable(sdata, self.store)
                                loaded_multi += 1
                            except Exception:
                                pass
                if loaded_multi > 0:
                    log(f"💾  [API MULTI] {loaded_multi} session(s) multijoueur restaurée(s) depuis le disque.")
            except Exception as e:
                log(f"⚠️  Erreur lecture multi_sessions.json : {e}")

    def _init_difficulty_pools(self):
        """Initialise les pools de mots par niveau de difficulté."""
        pool = self.store.clean_french_words if self.store.clean_french_words else self.store.words
        cands = [
            w for w in pool
            if len(w) >= 4
            and w not in STOPWORDS
            and not w.endswith(('es', 'eaux', 'eux', 'aux'))
            and not (w.endswith('s') and not w.endswith(('is', 'us', 'as', 'ps', 'os')))
        ]

        # Division selon la fréquence dans frWac (les mots les plus fréquents en premier)
        word_ranks = {w: idx for idx, w in enumerate(self.store.words)}
        sorted_cands = sorted(cands, key=lambda w: word_ranks.get(w, 999999))

        n = len(sorted_cands)
        # Facile : mots du quotidien (top 4 000)
        self.easy_pool = sorted_cands[:min(4000, n)]
        # Moyen : vocabulaire courant (4 000 à 16 000)
        self.medium_pool = sorted_cands[min(4000, n):min(16000, n)] if n > 4000 else sorted_cands
        # Expert : vocabulaire plus rare et conceptuel (> 16 000)
        self.expert_pool = sorted_cands[min(16000, n):] if n > 16000 else sorted_cands

        log(f"🎮  [API JEU] Pools de mots prêts — Facile: {len(self.easy_pool)} | Moyen: {len(self.medium_pool)} | Expert: {len(self.expert_pool)}")

    def get_daily_secret(self) -> tuple[str, str]:
        """Récupère le mot secret du jour consigné dans l'historique."""
        try:
            history = load_history(DAILY_HISTORY_FILE)
            winning = [h for h in history if h.get("win") is True and h.get("word")]
            if winning:
                last = winning[-1]
                return last.get("word"), str(last.get("puzzle", "JOUR"))
        except Exception as e:
            log(f"⚠️  Impossible de charger le mot du jour pour l'API : {e}")

        # Fallback si le mot du jour n'a pas encore été résolu
        fallback = str(np.random.choice(self.easy_pool))
        return fallback, "JOUR-1"

    def new_game(self, mode: str = "daily", difficulty: str = "moyen", force: bool = False) -> GameSession:
        """Crée ou récupère une session de jeu."""
        mode = mode.lower() if mode in ("daily", "unlimited") else "unlimited"
        difficulty = difficulty.lower() if difficulty in ("facile", "moyen", "expert") else "moyen"

        if mode == "daily":
            secret, puzzle_id = self.get_daily_secret()
            game_id = f"daily-{puzzle_id}"
            with self.lock:
                if not force and game_id in self.sessions:
                    return self.sessions[game_id]
        else:
            if difficulty == "facile":
                secret = str(np.random.choice(self.easy_pool))
            elif difficulty == "expert":
                secret = str(np.random.choice(self.expert_pool))
            else:
                secret = str(np.random.choice(self.medium_pool))
            puzzle_id = f"LIBRE-{uuid.uuid4().hex[:6].upper()}"
            game_id = uuid.uuid4().hex

        session = GameSession(
            game_id=game_id,
            mode=mode,
            difficulty=difficulty,
            puzzle_id=puzzle_id,
            secret=secret,
            store=self.store,
        )

        with self.lock:
            self._cleanup_stale()
            self.sessions[game_id] = session
            self._save_sessions()

        log(f"🎮  [API JEU] Nouvelle partie #{session.puzzle_id} ({mode}, {difficulty}) | ID: {game_id}")
        return session

    def get_session(self, game_id: str) -> Optional[GameSession]:
        with self.lock:
            session = self.sessions.get(game_id)
            if session:
                return session

            # Si c'est le défi du jour et que la session n'était pas en mémoire sous cet ID
            if game_id.startswith("daily-") or game_id == "daily":
                secret, puzzle_id = self.get_daily_secret()
                canonical_id = f"daily-{puzzle_id}"
                if canonical_id in self.sessions:
                    self.sessions[game_id] = self.sessions[canonical_id]
                    return self.sessions[canonical_id]

                session = GameSession(
                    game_id=canonical_id,
                    mode="daily",
                    difficulty="moyen",
                    puzzle_id=puzzle_id,
                    secret=secret,
                    store=self.store,
                )
                self.sessions[canonical_id] = session
                if game_id != canonical_id:
                    self.sessions[game_id] = session
                self._save_sessions()
                log(f"🔄  [API JEU] Restauration automatique du Défi du Jour #{puzzle_id} ({canonical_id})")
                return session

            return None

    def give_up(self, game_id: str) -> Optional[dict]:
        with self.lock:
            session = self.sessions.get(game_id)
        if not session:
            return None
        session.is_given_up = True
        self._save_sessions()
        return session.to_dict(reveal_secret=True)

    def new_battle(
        self,
        difficulty: str = "moyen",
        battle_id: Optional[str] = None,
        ai_word: Optional[str] = None,
    ) -> tuple[Optional[BattleSession], Optional[str]]:
        """Initialise une nouvelle manche de Mode Battle (avec mot IA optionnel)."""
        difficulty = difficulty.lower() if difficulty in ("facile", "moyen", "expert") else "moyen"

        previous_stats = None
        if battle_id and battle_id in self.battle_sessions:
            old = self.battle_sessions[battle_id]
            previous_stats = {
                "player": old.stats.get("player", 0),
                "ai": old.stats.get("ai", 0),
                "draws": old.stats.get("draws", 0),
                "match": old.stats.get("match", 1) + 1,
                "difficulty": difficulty,
            }

        if difficulty == "facile":
            pool = self.easy_pool
        elif difficulty == "expert":
            pool = self.expert_pool
        else:
            pool = self.medium_pool

        player_secret = str(np.random.choice(pool))

        # Mot cible pour le bot IA : défini par le joueur ou tiré aléatoirement
        if ai_word and ai_word.strip():
            cleaned_ai = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", ai_word.strip()).lower()
            norm_ai = self.store.normalize(cleaned_ai)
            if not norm_ai or norm_ai not in self.store or not self.store.is_valid_french(norm_ai):
                return None, f"Le mot « {ai_word} » n'est pas reconnu dans le dictionnaire officiel."
            ai_secret = norm_ai
        else:
            ai_secret = str(np.random.choice(pool))
            while ai_secret == player_secret and len(pool) > 1:
                ai_secret = str(np.random.choice(pool))

        new_id = battle_id if battle_id else uuid.uuid4().hex
        session = BattleSession(
            battle_id=new_id,
            difficulty=difficulty,
            player_secret=player_secret,
            ai_secret=ai_secret,
            store=self.store,
            stats=previous_stats,
        )

        with self.lock:
            self._cleanup_stale()
            self.battle_sessions[new_id] = session

        custom_tag = " (choisi par le joueur)" if ai_word and ai_word.strip() else " (tirage aléatoire)"
        log(f"⚔️   [API BATTLE] Manche #{session.stats['match']} ({difficulty}) | ID: {new_id} | Humain: ??? | IA: {ai_secret.upper()}{custom_tag}")
        return session, None

    def get_battle(self, battle_id: str) -> Optional[BattleSession]:
        with self.lock:
            return self.battle_sessions.get(battle_id)

    def create_multiplayer(
        self,
        mode: str = "same_word",
        difficulty: str = "moyen",
        player_name: str = "Joueur 1",
        custom_target: Optional[str] = None,
    ) -> tuple[Optional[MultiplayerSession], Optional[str]]:
        """Crée un nouveau salon multijoueur (Même Mot ou Mots Choisis)."""
        difficulty = difficulty.lower() if difficulty in ("facile", "moyen", "expert") else "moyen"
        mode = "custom_words" if mode == "custom_words" else "same_word"

        # Génération d'un code de salon unique (ex: DUEL-4B1C)
        room_id = f"DUEL-{uuid.uuid4().hex[:4].upper()}"
        while room_id in self.multi_sessions:
            room_id = f"DUEL-{uuid.uuid4().hex[:4].upper()}"

        target_p1 = None
        target_p2 = None

        if mode == "same_word":
            if difficulty == "facile":
                pool = self.easy_pool
            elif difficulty == "expert":
                pool = self.expert_pool
            else:
                pool = self.medium_pool
            target_p1 = str(np.random.choice(pool))
            target_p2 = target_p1
        elif mode == "custom_words" and custom_target and custom_target.strip():
            cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", custom_target.strip()).lower()
            norm = self.store.normalize(cleaned)
            if not norm or norm not in self.store or not self.store.is_valid_french(norm):
                return None, f"Le mot « {custom_target} » n'est pas dans le dictionnaire officiel."
            target_p2 = norm  # Le mot choisi par P1 pour P2

        session = MultiplayerSession(
            room_id=room_id,
            mode=mode,
            difficulty=difficulty,
            store=self.store,
            target_for_p1=target_p1,
            target_for_p2=target_p2,
            p1_name=player_name.strip() or "Joueur 1",
        )

        with self.lock:
            self._cleanup_stale()
            self.multi_sessions[room_id] = session
            self._save_sessions()

        log(f"👥  [API MULTI] Nouveau salon #{room_id} ({mode}, {difficulty}) créé par {session.p1_name}")
        return session, None

    def get_multiplayer(self, room_id: str) -> Optional[MultiplayerSession]:
        if not room_id:
            return None
        rid = room_id.strip().upper()
        with self.lock:
            return self.multi_sessions.get(rid)

    def _cleanup_stale(self, max_age: float = 7200.0):
        """Nettoie les sessions inactives depuis plus de 2 heures (et 7 jours pour le multi)."""
        now = time.time()
        to_del = [gid for gid, s in self.sessions.items() if (now - s.last_activity) > max_age]
        for gid in to_del:
            del self.sessions[gid]
        to_del_battle = [bid for bid, b in self.battle_sessions.items() if (now - b.last_activity) > max_age]
        for bid in to_del_battle:
            del self.battle_sessions[bid]
        to_del_multi = [rid for rid, m in self.multi_sessions.items() if (now - m.last_activity) > (7 * 86400.0)]
        for rid in to_del_multi:
            del self.multi_sessions[rid]


# Instance globale du gestionnaire de jeu
_manager: Optional[GameManager] = None


class GameAPIHandler(BaseHTTPRequestHandler):
    """Handler HTTP REST pour l'API du jeu Cémantix."""

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def _send_json(self, data: dict, status: int = 200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> Optional[dict]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return None
        raw_body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        if path in ("/api/health", "/api/healthcheck"):
            count = len(_manager.sessions) if _manager else 0
            self._send_json({"status": "ok", "active_sessions": count})
            return

        if path == "/api/game/daily-info":
            if not _manager:
                self._send_json({"error": "Gestionnaire non initialisé"}, status=503)
                return
            word, puzzle = _manager.get_daily_secret()
            self._send_json({
                "puzzle_id": puzzle,
                "available": bool(word),
            })
        if path in ("/api/daily", "/api/dashboard"):
            try:
                from .web import build_web_data
                data = build_web_data()
            except Exception as e:
                self._send_json({"error": f"Erreur chargement données dashboard: {e}"}, status=500)
                return

            query = self.path.split("?")[1] if "?" in self.path else ""
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            reveal = params.get("reveal", "").lower() in ("true", "1", "yes")

            if not reveal and data.get("current"):
                secret = data["current"].get("word")
                data["current"]["word"] = None
                data["current"]["is_revealed"] = False
                if secret and "trajectory" in data["current"]:
                    for step in data["current"]["trajectory"]:
                        if str(step.get("word", "")).lower() == secret.lower():
                            step["word"] = "••••••••"
            elif data.get("current"):
                data["current"]["is_revealed"] = True

            self._send_json(data)
            return

        if path == "/api/multi/status":
            if not _manager:
                self._send_json({"error": "Gestionnaire non initialisé"}, status=503)
                return
            query = self.path.split("?")[1] if "?" in self.path else ""
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            room_id = params.get("r", params.get("room_id", "")).strip().upper()
            player_key = params.get("k", params.get("player_key", "")).strip().upper()

            session = _manager.get_multiplayer(room_id)
            if not session:
                self._send_json({"error": "Salon de jeu introuvable ou expiré.", "valid": False}, status=404)
                return

            res = session.to_dict(player_key)
            if not res.get("valid"):
                self._send_json(res, status=403)
                return
            self._send_json(res)
            return

        self._send_json({"error": "Route introuvable"}, status=404)

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if not _manager:
            self._send_json({"error": "Gestionnaire non initialisé"}, status=503)
            return

        data = self._read_json() or {}

        # 1. Nouvelle partie
        if path == "/api/game/new":
            mode = data.get("mode", "daily")
            difficulty = data.get("difficulty", "moyen")
            force = bool(data.get("force", False))
            session = _manager.new_game(mode=mode, difficulty=difficulty, force=force)
            self._send_json(session.to_dict(reveal_secret=False))
            return

        # 1b. Reprise / Synchronisation d'une partie existante
        if path == "/api/game/resume":
            game_id = data.get("game_id", "")
            mode = data.get("mode", "daily")
            difficulty = data.get("difficulty", "moyen")

            session = _manager.get_session(game_id) if game_id else None
            if not session:
                log(f"🔄  [API JEU] Session « {game_id} » expirée/inconnue -> auto-renouvellement ({mode}, {difficulty})")
                session = _manager.new_game(mode=mode, difficulty=difficulty, force=False)

            self._send_json(session.to_dict(reveal_secret=False))
            return

        # 2. Proposition de mot
        if path == "/api/game/guess":
            game_id = data.get("game_id", "")
            raw_word = data.get("word", "").strip()

            session = _manager.get_session(game_id)
            if not session:
                self._send_json({"error": "Session de jeu introuvable ou expirée. Veuillez relancer une partie.", "expired": True}, status=404)
                return

            if not raw_word:
                self._send_json({"error": "Veuillez saisir un mot valide."}, status=400)
                return

            # Sanitisation stricte du mot (alphabétique uniquement)
            cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", raw_word).lower()
            if not cleaned:
                self._send_json({"error": "Le mot contient des caractères non autorisés."}, status=400)
                return

            result = session.record_guess(cleaned)
            _manager._save_sessions()
            self._send_json(result)
            return

        # 3. Demande d'indice (+1 coup officiel au compteur)
        if path == "/api/game/hint":
            game_id = data.get("game_id", "")
            session = _manager.get_session(game_id)
            if not session:
                self._send_json({"error": "Session de jeu introuvable ou expirée. Relancez une partie.", "expired": True}, status=404)
                return
            result = session.request_hint()
            _manager._save_sessions()
            status_code = 400 if "error" in result and not result.get("valid") else 200
            self._send_json(result, status=status_code)
            return

        # 4. Abandonner / Révéler le mot secret
        if path == "/api/game/giveup":

            game_id = data.get("game_id", "")
            res = _manager.give_up(game_id)
            if not res:
                self._send_json({"error": "Session introuvable."}, status=404)
                return
            self._send_json(res)
            return

        # =====================================================================
        # ROUTES MODE BATTLE (DUEL JOUEUR VS BOT IA)
        # =====================================================================

        # 5. Nouvelle manche de Battle
        if path == "/api/battle/new":
            difficulty = data.get("difficulty", "moyen")
            battle_id = data.get("battle_id")
            ai_word = data.get("ai_word", "")
            session, err = _manager.new_battle(difficulty=difficulty, battle_id=battle_id, ai_word=ai_word)
            if err:
                self._send_json({"error": err, "valid": False}, status=400)
                return
            self._send_json(session.to_dict(reveal_secret=False))
            return

        # 6. Reprise / Synchronisation de Battle
        if path == "/api/battle/resume":
            battle_id = data.get("battle_id", "")
            difficulty = data.get("difficulty", "moyen")
            session = _manager.get_battle(battle_id) if battle_id else None
            if not session:
                log(f"🔄  [API BATTLE] Session « {battle_id} » expirée/inconnue -> nouvelle manche ({difficulty})")
                session, _ = _manager.new_battle(difficulty=difficulty, battle_id=None)
            self._send_json(session.to_dict(reveal_secret=False))
            return

        # 7. Coup joué par le joueur en Battle (tour par tour immédiat)
        if path == "/api/battle/guess":
            battle_id = data.get("battle_id", "")
            raw_word = data.get("word", "").strip()

            session = _manager.get_battle(battle_id)
            if not session:
                self._send_json({"error": "Session de duel introuvable ou expirée. Veuillez relancer une manche.", "expired": True, "valid": False}, status=404)
                return

            if not raw_word:
                self._send_json({"error": "Veuillez saisir un mot valide.", "valid": False}, status=400)
                return

            cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", raw_word).lower()
            if not cleaned:
                self._send_json({"error": "Le mot contient des caractères non autorisés.", "valid": False}, status=400)
                return

            result = session.record_player_guess(cleaned)
            status_code = 400 if "error" in result and not result.get("valid") else 200
            self._send_json(result, status=status_code)
            return

        # 8. Demande d'indice en Battle (3 max, du général au proche, 1 indice = 1 tour)
        if path == "/api/battle/hint":
            battle_id = data.get("battle_id", "")
            session = _manager.get_battle(battle_id)
            if not session:
                self._send_json({"error": "Session de duel introuvable ou expirée. Relancez une manche.", "expired": True, "valid": False}, status=404)
                return

            result = session.request_hint()
            status_code = 400 if "error" in result and not result.get("valid") else 200
            self._send_json(result, status=status_code)
            return

        # 9. Forfait / Abandon en Battle
        if path == "/api/battle/giveup":
            battle_id = data.get("battle_id", "")
            session = _manager.get_battle(battle_id)
            if not session:
                self._send_json({"error": "Session de duel introuvable.", "valid": False}, status=404)
                return
            result = session.give_up()
            self._send_json(result)
            return

        # =====================================================================
        # ROUTES MODE MULTIJOUEUR (1V1 SALON TOUR PAR TOUR)
        # =====================================================================

        # 10. Créer un salon multijoueur
        if path == "/api/multi/create":
            mode = str(data.get("mode") or "same_word").strip()
            difficulty = str(data.get("difficulty") or "moyen").strip()
            player_name = str(data.get("player_name") or "Joueur 1").strip()
            custom_target = data.get("custom_target")
            if custom_target is not None:
                custom_target = str(custom_target).strip()
            session, err = _manager.create_multiplayer(
                mode=mode,
                difficulty=difficulty,
                player_name=player_name,
                custom_target=custom_target,
            )
            if err:
                self._send_json({"error": err, "valid": False}, status=400)
                return
            self._send_json({
                "valid": True,
                "room_id": session.room_id,
                "player_key": session.key_p1,
                "role": "p1",
                "guest_key": session.key_p2,
                "share_url": f"/multi/?r={session.room_id}&k={session.key_p2}",
                "session": session.to_dict(session.key_p1),
            })
            return

        # 11. Rejoindre ou reconnecter un salon
        if path == "/api/multi/join":
            room_id = str(data.get("room_id") or "").strip().upper()
            player_key = str(data.get("player_key") or "").strip().upper()
            player_name = str(data.get("player_name") or "").strip()

            session = _manager.get_multiplayer(room_id)
            if not session:
                self._send_json({"error": "Salon de jeu introuvable ou expiré.", "valid": False}, status=404)
                return

            if player_key:
                role = session.get_role(player_key)
                if not role:
                    self._send_json({"error": "Clé joueur invalide pour ce salon.", "valid": False}, status=403)
                    return
                if role == "p2":
                    session.p2_joined = True
                    if player_name:
                        session.p2_name = player_name
                    _manager._save_sessions()
                self._send_json({
                    "valid": True,
                    "room_id": session.room_id,
                    "player_key": player_key,
                    "role": role,
                    "session": session.to_dict(player_key),
                })
                return

            if not session.p2_joined:
                session.p2_joined = True
                if player_name:
                    session.p2_name = player_name
                _manager._save_sessions()
                self._send_json({
                    "valid": True,
                    "room_id": session.room_id,
                    "player_key": session.key_p2,
                    "role": "p2",
                    "session": session.to_dict(session.key_p2),
                })
                return

            self._send_json({
                "error": "Ce salon est déjà complet. Si vous êtes déjà participant, veuillez renseigner votre Clé Joueur.",
                "valid": False,
            }, status=400)
            return

        # 12. Définition du mot secret pour l'adversaire (Mode Mots Choisis)
        if path == "/api/multi/setup-word":
            room_id = str(data.get("room_id") or "").strip().upper()
            player_key = str(data.get("player_key") or "").strip().upper()
            word = str(data.get("word") or "").strip()

            session = _manager.get_multiplayer(room_id)
            if not session:
                self._send_json({"error": "Salon introuvable.", "valid": False}, status=404)
                return

            res = session.setup_word(player_key, word)
            status_code = 400 if "error" in res and not res.get("valid") else 200
            if res.get("valid"):
                _manager._save_sessions()
            self._send_json(res, status=status_code)
            return

        # 13. Consultation de l'état du salon (POST)
        if path == "/api/multi/status":
            room_id = str(data.get("room_id") or "").strip().upper()
            player_key = str(data.get("player_key") or "").strip().upper()

            session = _manager.get_multiplayer(room_id)
            if not session:
                self._send_json({"error": "Salon introuvable ou expiré.", "valid": False}, status=404)
                return

            res = session.to_dict(player_key)
            if not res.get("valid"):
                self._send_json(res, status=403)
                return
            self._send_json(res)
            return

        # 14. Coup joué en Multijoueur
        if path == "/api/multi/guess":
            room_id = str(data.get("room_id") or "").strip().upper()
            player_key = str(data.get("player_key") or "").strip().upper()
            raw_word = str(data.get("word") or "").strip()

            session = _manager.get_multiplayer(room_id)
            if not session:
                self._send_json({"error": "Salon introuvable ou expiré.", "valid": False}, status=404)
                return

            if not raw_word:
                self._send_json({"error": "Veuillez saisir un mot valide.", "valid": False}, status=400)
                return

            cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\-]", "", raw_word).lower()
            if not cleaned:
                self._send_json({"error": "Le mot contient des caractères non autorisés.", "valid": False}, status=400)
                return

            res = session.record_guess(player_key, cleaned)
            status_code = 400 if "error" in res and not res.get("valid") else 200
            if res.get("valid"):
                _manager._save_sessions()
            self._send_json(res, status=status_code)
            return

        # 15. Demande d'indice en Multijoueur
        if path == "/api/multi/hint":
            room_id = str(data.get("room_id") or "").strip().upper()
            player_key = str(data.get("player_key") or "").strip().upper()

            session = _manager.get_multiplayer(room_id)
            if not session:
                self._send_json({"error": "Salon introuvable.", "valid": False}, status=404)
                return

            res = session.request_hint(player_key)
            status_code = 400 if "error" in res and not res.get("valid") else 200
            if res.get("valid"):
                _manager._save_sessions()
            self._send_json(res, status=status_code)
            return

        # 16. Forfait / Déclaration d'abandon en Multijoueur
        if path == "/api/multi/giveup":
            room_id = str(data.get("room_id") or "").strip().upper()
            player_key = str(data.get("player_key") or "").strip().upper()

            session = _manager.get_multiplayer(room_id)
            if not session:
                self._send_json({"error": "Salon introuvable.", "valid": False}, status=404)
                return

            res = session.give_up(player_key)
            status_code = 400 if "error" in res and not res.get("valid") else 200
            if res.get("valid"):
                _manager._save_sessions()
            self._send_json(res, status=status_code)
            return

        self._send_json({"error": "Route introuvable"}, status=404)

    def log_message(self, format, *args):
        # Silence les logs HTTP standards pour garder la console propre
        pass


def start_api_server(store: VocabStore, host: str = "0.0.0.0", port: int = 8000) -> ThreadingHTTPServer:
    """Initialise et lance le serveur HTTP multi-threadé."""
    global _manager
    _manager = GameManager(store)
    server = ThreadingHTTPServer((host, port), GameAPIHandler)
    log(f"🌐  [API JEU] Serveur HTTP opérationnel sur http://{host}:{port}/api")
    return server


def start_api_thread(store: VocabStore, host: str = "0.0.0.0", port: int = 8000) -> threading.Thread:
    """Démarre le serveur d'API dans un thread d'arrière-plan sécurisé."""
    server = start_api_server(store, host=host, port=port)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="CemantixAPIThread")
    thread.start()
    return thread
