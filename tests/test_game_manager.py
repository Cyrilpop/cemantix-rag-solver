"""Tests déterministes de non-régression pour GameManager (Phase B).

Vérifie de manière strictement reproductible :
- Le cycle de vie des sessions solo (création, coups, abandon, détection de victoire)
- L'invariant critique anti-spoiler (le mot secret ne fuite JAMAIS avant abandon ou victoire)
- Le cycle de vie des sessions Battle contre le bot IA
- Le cycle de vie des sessions Multijoueur (même mot ou mots choisis) avec hachage des clés
- L'isolation stricte entre sessions et joueurs
- La persistance O(1) et le rechargement depuis la base SQLite temporaire
- La purge des sessions périmées (_cleanup_stale) respectant les TTL distincts.
"""
import sys
from pathlib import Path
_tests_dir = str(Path(__file__).resolve().parent)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)
import _context  # noqa: F401
import unittest
import time
import numpy as np

from src.game.manager import GameManager
from src.game.solo import GameSession
from src.game.battle import BattleSession
from src.game.multi import MultiplayerSession


class SyntheticVocabStore:
    """Doublure synthétique légère en mémoire pour VocabStore."""
    def __init__(self, words_vecs: dict[str, np.ndarray]):
        self.words = list(words_vecs.keys())
        self.index = {w: i for i, w in enumerate(self.words)}
        raw_vecs = np.array([words_vecs[w] for w in self.words], dtype=np.float32)
        norms = np.linalg.norm(raw_vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.vecs = raw_vecs / norms
        self.valid_lemmas = set(self.words)
        self.accent_map = {}
        self.clean_french_words = list(self.words)
        self.col = None

    def normalize(self, word: str) -> str:
        return word.strip().lower()

    def is_valid_french(self, word: str) -> bool:
        return word.strip().lower() in self.index

    def has_word(self, word: str) -> bool:
        return word.strip().lower() in self.index

    def __contains__(self, word: str) -> bool:
        return word.strip().lower() in self.index

    def vec(self, word: str) -> np.ndarray:
        return self.vecs[self.index[word.strip().lower()]]

    def knn(self, query: np.ndarray, k: int) -> list[str]:
        q_norm = np.linalg.norm(query)
        q = query / q_norm if q_norm > 0 else query
        sims = self.vecs @ q
        k_val = min(k, len(self.words))
        top_idx = np.argpartition(sims, -k_val)[-k_val:]
        top_sorted = top_idx[np.argsort(sims[top_idx])[::-1]]
        return [self.words[i] for i in top_sorted]


def _build_test_store() -> SyntheticVocabStore:
    rng = np.random.default_rng(42)
    dim = 8
    # Liste de mots suffisante pour alimenter les pools facile, moyen, expert
    words = [
        "soleil", "lumiere", "rayon", "etoile", "planete", "espace",
        "pomme", "poire", "arbre", "fruit", "foret", "feuille",
        "chat", "chien", "cheval", "oiseau", "poisson", "animal",
        "maison", "porte", "fenetre", "toit", "jardin", "table",
        "livre", "page", "ecole", "stylo", "papier", "cahier"
    ]
    words_vecs = {w: rng.standard_normal(dim) for w in words}
    # Alignements relatifs
    words_vecs["lumiere"] = words_vecs["soleil"] * 0.95 + rng.standard_normal(dim) * 0.05
    words_vecs["rayon"] = words_vecs["soleil"] * 0.90 + rng.standard_normal(dim) * 0.10
    return SyntheticVocabStore(words_vecs)


class TestSoloSessionLifecycle(unittest.TestCase):
    """Cycle de vie et invariants des sessions Solo."""

    def setUp(self):
        self.store = _build_test_store()
        self.mgr = GameManager(store=self.store, persist=True)

    def test_new_game_unlimited_mode(self):
        session = self.mgr.new_game(mode="unlimited", difficulty="facile")
        self.assertIsInstance(session, GameSession)
        self.assertEqual(session.mode, "unlimited")
        self.assertEqual(session.difficulty, "facile")
        self.assertIn(session.secret, self.store)
        self.assertFalse(session.is_won)
        self.assertFalse(session.is_given_up)

        # Invariant anti-spoiler : secret masqué dans to_dict
        data = session.to_dict()
        self.assertIsNone(data["secret"], "Le mot secret ne doit jamais fuiter en cours de partie !")
        self.assertEqual(data["tries"], 0)

    def test_record_guess_progression_and_anti_spoiler(self):
        session = self.mgr.new_game(mode="unlimited", difficulty="moyen")
        secret = session.secret

        # Trouve un mot distinct du secret
        other_words = [w for w in self.store.words if w != secret]
        guess_word = other_words[0]

        res = session.record_guess(guess_word)
        self.assertIn("score", res)
        self.assertIn("weather", res)
        self.assertFalse(session.is_won)

        # Vérification anti-spoiler continue
        data = session.to_dict()
        self.assertIsNone(data["secret"])
        self.assertEqual(data["tries"], 1)

        # Mot invalide (inconnu du store)
        bad_res = session.record_guess("motinconnuaulexique")
        self.assertIn("error", bad_res)
        self.assertEqual(session.to_dict()["tries"], 1)

    def test_give_up_reveals_secret_and_locks_state(self):
        session = self.mgr.new_game(mode="unlimited", difficulty="expert")
        gid = session.game_id
        secret = session.secret

        revealed = self.mgr.give_up(gid)
        self.assertIsNotNone(revealed)
        self.assertTrue(revealed["is_given_up"])
        self.assertEqual(revealed["secret"], secret, "L'abandon doit révéler le mot secret.")

        # Vérifie que la session en mémoire conserve l'état abandonné
        fetched = self.mgr.get_session(gid)
        self.assertTrue(fetched.is_given_up)
        self.assertEqual(fetched.to_dict(reveal_secret=True)["secret"], secret)

    def test_winning_session_reveals_secret(self):
        session = self.mgr.new_game(mode="unlimited", difficulty="facile")
        secret = session.secret

        res = session.record_guess(secret)
        self.assertTrue(session.is_won)
        self.assertEqual(res.get("permille"), 1000)

        # La victoire autorise to_dict() standard à afficher le secret
        data = session.to_dict()
        self.assertTrue(data["is_won"])
        self.assertEqual(data["secret"], secret)

    def test_request_hint_solo_lifecycle(self):
        session = self.mgr.new_game(mode="unlimited", difficulty="moyen")
        # Demande un indice
        hint1 = session.request_hint()
        self.assertIn("word", hint1)
        self.assertIn(hint1["word"], self.store)
        self.assertEqual(len(session.hints), 1)

        # Un coup d'indice est automatiquement enregistré dans les guesses
        self.assertIn(hint1["word"], session.guesses)
        self.assertTrue(session.guesses[hint1["word"]].get("is_hint"))

    def test_solo_serialization_roundtrip(self):
        session = self.mgr.new_game(mode="unlimited", difficulty="facile")
        session.record_guess("pomme")
        data = session.to_serializable()

        rebuilt = GameSession.from_serializable(data, self.store)
        self.assertEqual(rebuilt.game_id, session.game_id)
        self.assertEqual(rebuilt.secret, session.secret)
        self.assertEqual(len(rebuilt.guesses), 1)
        self.assertIn("pomme", rebuilt.guesses)


class TestBattleSessionLifecycle(unittest.TestCase):
    """Cycle de vie et invariants des duels contre l'IA (BattleSession)."""

    def setUp(self):
        self.store = _build_test_store()
        self.mgr = GameManager(store=self.store, persist=True)

    def test_create_battle_session(self):
        battle, err = self.mgr.new_battle(difficulty="facile")
        self.assertIsNone(err)
        self.assertIsInstance(battle, BattleSession)
        self.assertIn(battle.player_secret, self.store)
        self.assertIn(battle.ai_secret, self.store)
        self.assertFalse(battle.is_finished)

        # Invariant anti-spoiler : secret masqué dans to_dict
        data = battle.to_dict()
        self.assertIsNone(data["player"]["secret"])

    def test_battle_player_turn_and_bot_reply(self):
        battle, err = self.mgr.new_battle(difficulty="expert")
        self.assertIsNone(err)

        secret = battle.player_secret
        other_words = [w for w in self.store.words if w != secret]
        guess_word = other_words[0]

        turn_res = battle.record_player_guess(guess_word)
        self.assertTrue(turn_res.get("valid"))
        self.assertEqual(turn_res.get("turn_no"), 1)
        self.assertIsNotNone(turn_res["player"]["last_guess"])
        self.assertEqual(turn_res["player"]["last_guess"]["word"], guess_word)
        self.assertIsNotNone(turn_res["ai"]["last_guess"])
        self.assertIn(turn_res["ai"]["last_guess"]["word"], self.store)

    def test_battle_give_up(self):
        battle, _ = self.mgr.new_battle(difficulty="moyen")
        secret = battle.player_secret

        res = battle.give_up()
        self.assertTrue(res["is_finished"])
        self.assertEqual(res["winner"], "giveup")
        self.assertEqual(res["player"]["secret"], secret)


class TestMultiplayerSessionLifecycle(unittest.TestCase):
    """Cycle de vie et invariants des salons multijoueur (MultiplayerSession)."""

    def setUp(self):
        self.store = _build_test_store()
        self.mgr = GameManager(store=self.store, persist=True)

    def test_create_same_word_multiplayer_room(self):
        room, err = self.mgr.create_multiplayer(
            mode="same_word",
            difficulty="facile",
            player_name="Alice"
        )
        self.assertIsNone(err)
        self.assertIsInstance(room, MultiplayerSession)
        self.assertTrue(room.room_id.startswith("DUEL-"))
        self.assertEqual(room.p1_name, "Alice")
        self.assertIsNotNone(room.key_p1)
        self.assertIsNotNone(room.key_p2)
        self.assertNotEqual(room.key_p1, room.key_p2, "Les clés de P1 et P2 doivent être strictement distinctes !")

        # Même mot secret pour les deux
        self.assertEqual(room.target_for_p1, room.target_for_p2)
        self.assertIn(room.target_for_p1, self.store)

    def test_create_custom_words_multiplayer_room(self):
        # P1 choisit un mot pour P2
        room, err = self.mgr.create_multiplayer(
            mode="custom_words",
            difficulty="moyen",
            player_name="Bob",
            custom_target="soleil"
        )
        self.assertIsNone(err)
        self.assertEqual(room.target_for_p2, "soleil")

        # P2 configure ensuite son mot pour P1
        setup_res = room.setup_word(room.key_p2, "lumiere")
        self.assertIn("state", setup_res)
        self.assertEqual(room.target_for_p1, "lumiere")
        self.assertEqual(room.state, "in_progress")

    def test_anti_cheat_masking_in_multiplayer_views(self):
        room, _ = self.mgr.create_multiplayer(mode="same_word", player_name="P1")
        # P1 joue un coup
        other_word = [w for w in self.store.words if w != room.target_for_p1][0]
        room.record_guess(room.key_p1, other_word)

        # La vue de P2 ne doit pas révéler le mot précis joué par P1 (mot masqué par puces)
        view_p2 = room.to_dict(player_key=room.key_p2)
        opponent_last = view_p2.get("opponent", {}).get("last_guess")
        self.assertIsNotNone(opponent_last)
        self.assertEqual(opponent_last.get("word"), "••••••••", "Le mot de l'adversaire doit être masqué pour éviter la triche !")

    def test_multiplayer_serialization_roundtrip(self):
        room, _ = self.mgr.create_multiplayer(mode="same_word", player_name="P1")
        room.record_guess(room.key_p1, "pomme")
        data = room.to_serializable()

        rebuilt = MultiplayerSession.from_serializable(data, self.store)
        self.assertEqual(rebuilt.room_id, room.room_id)
        self.assertEqual(rebuilt.target_for_p1, room.target_for_p1)
        self.assertIn("pomme", rebuilt.p1_guesses)


class TestPersistenceAndCleanup(unittest.TestCase):
    """Validation de la persistance relationnelle et de la purge des sessions expirées."""

    def setUp(self):
        self.store = _build_test_store()
        self.mgr = GameManager(store=self.store, persist=True)

    def test_session_retrieval_and_persistence(self):
        session = self.mgr.new_game(mode="unlimited", difficulty="moyen")
        gid = session.game_id
        session.record_guess("soleil")

        # Sauvegarde ciblée O(1)
        self.mgr.save_solo_session(session)

        # Simule un rechargement par un autre manager ou après purge mémoire
        del self.mgr.sessions[gid]
        reloaded = self.mgr.get_session(gid)

        self.assertIsNotNone(reloaded, "La session doit être restaurée depuis la base SQLite.")
        self.assertEqual(reloaded.game_id, gid)
        self.assertIn("soleil", reloaded.guesses)

    def test_cleanup_stale_removes_old_sessions_only(self):
        session_fresh = self.mgr.new_game(mode="unlimited", difficulty="facile")
        session_stale = self.mgr.new_game(mode="unlimited", difficulty="facile")

        # Vieillit artificiellement session_stale au-delà de 2 heures
        session_stale.last_activity = time.time() - 7500.0

        with self.mgr.lock:
            removed = self.mgr._cleanup_stale(max_age=7200.0)

        self.assertGreaterEqual(removed, 1)
        self.assertIn(session_fresh.game_id, self.mgr.sessions)
        self.assertNotIn(session_stale.game_id, self.mgr.sessions)


if __name__ == "__main__":
    unittest.main()
