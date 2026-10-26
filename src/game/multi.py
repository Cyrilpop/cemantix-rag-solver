"""
Cémantix Solver — Session Multijoueur 1v1 (Salons & Tours)
==========================================================
Moteur de jeu pour les duels multijoueurs humains (1 contre 1) :
- Deux modes de jeu : Mot Commun ou Mots Choisis mutuellement
- Machine à états de salon (waiting_words, in_progress, finished)
- Gestion des rôles Joueur 1 (J1) et Joueur 2 (J2) par clés de sécurité
- Masquage asymétrique de l'historique adverse en mode mot commun
- Tour par tour strict avec décompte des indices (3 max par joueur)
"""
import re
import time
import uuid
from typing import Optional

import numpy as np

from .common import get_weather_tier
from ..config import STOPWORDS
from ..engine import MockClient, VocabStore


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

        # Clés à 8 chiffres hexadécimaux (32 bits) : à 4 caractères, l'espace des
        # codes se limitait à 65 536 valeurs, ce qui autorisait une énumération
        # systématique des salons actifs depuis un navigateur.
        self.key_p1 = key_p1.strip().upper() if key_p1 else f"J1-{uuid.uuid4().hex[:8].upper()}"
        self.key_p2 = key_p2.strip().upper() if key_p2 else f"J2-{uuid.uuid4().hex[:8].upper()}"

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
