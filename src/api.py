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

from .config import DATA_DIR, STOPWORDS, log
from .daemon import DAILY_HISTORY_FILE, load_history
from .vocab import VocabStore, strip_accents

WEB_SESSIONS_FILE = DATA_DIR / "web_sessions.json"


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


class GameManager:
    """Gestionnaire centralisé des parties en mémoire et sur disque (persistance volume)."""

    def __init__(self, store: VocabStore):
        self.store = store
        self.sessions: dict[str, GameSession] = {}
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
        except Exception as e:
            log(f"⚠️  Erreur sauvegarde web_sessions.json : {e}")

    def _load_sessions(self):
        """Recharge les sessions sauvegardées depuis le volume Docker."""
        if not WEB_SESSIONS_FILE.exists():
            return
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



    def _cleanup_stale(self, max_age: float = 7200.0):
        """Nettoie les sessions inactives depuis plus de 2 heures."""
        now = time.time()
        to_del = [gid for gid, s in self.sessions.items() if (now - s.last_activity) > max_age]
        for gid in to_del:
            del self.sessions[gid]


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
