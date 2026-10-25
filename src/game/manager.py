"""
Cémantix Solver — Gestionnaire Centralisé des Parties & Persistance
===================================================================
Orchestre l'ensemble des modes de jeu en mémoire et sur disque :
- Persistance atomique des sessions (web_sessions.json & multi_sessions.json)
- Pools de mots par niveau de difficulté (Facile, Moyen, Expert)
- Verrouillage multi-thread (threading.Lock) pour accès concurrentiel sécurisé
- Cycle de vie complet des parties (Solo, Battle IA, Multijoueur 1v1)
- Nettoyage automatique des sessions inactives
"""
import json
import re
import threading
import time
import uuid
from typing import Optional

import numpy as np

from .battle import BattleSession
from .common import MULTI_SESSIONS_FILE, WEB_SESSIONS_FILE
from .multi import MultiplayerSession
from .solo import GameSession
from ..config import DATA_DIR, STOPWORDS, log
from ..engine import VocabStore, strip_accents
from ..services import DAILY_HISTORY_FILE, load_history


class GameManager:
    """Gestionnaire centralisé des parties en mémoire et sur disque (persistance volume)."""

    def __init__(self, store: VocabStore, persist: bool = True):
        self.store = store
        self.persist = persist
        self.sessions: dict[str, GameSession] = {}
        self.battle_sessions: dict[str, BattleSession] = {}
        self.multi_sessions: dict[str, MultiplayerSession] = {}
        self.lock = threading.Lock()
        self._init_difficulty_pools()
        if self.persist:
            self._load_sessions()

    def _save_sessions(self):
        """Persiste les sessions actives sur disque (volume Docker)."""
        if not self.persist:
            return
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
