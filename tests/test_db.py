"""
Tests unitaires pour la couche de persistance relationnelle (src/db).
"""
import os
import tempfile
import time
import unittest
from pathlib import Path

from src.db.connection import DatabaseManager
from src.db.daily import (
    get_all_daily_puzzles,
    get_daily_puzzle,
    get_latest_daily_puzzle,
    save_daily_puzzle,
)
from src.db.multi import (
    cleanup_old_rooms,
    delete_room,
    get_room,
    save_room,
)
from src.db.solo import (
    cleanup_old_solo,
    delete_solo_session,
    get_solo_session,
    save_solo_session_record,
)


class TestDatabaseLayer(unittest.TestCase):
    def setUp(self):
        # Isolation sur base SQLite temporaire dédiée pour les tests unitaires
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.sqlite_file = Path(self.tmp_dir.name) / "test_cemantix.sqlite3"
        self.old_sqlite_path = os.environ.get("SQLITE_PATH")
        os.environ["SQLITE_PATH"] = str(self.sqlite_file)

        self.old_db_host = os.environ.get("DB_HOST")
        self.old_db_name = os.environ.get("DB_NAME")
        if "DB_HOST" in os.environ:
            del os.environ["DB_HOST"]
        if "DB_NAME" in os.environ:
            del os.environ["DB_NAME"]

        from src.db.connection import db
        self.db = db
        self.db.reset()
        self.db.init_db()

    def tearDown(self):
        self.db.reset()
        self.tmp_dir.cleanup()
        if self.old_sqlite_path:
            os.environ["SQLITE_PATH"] = self.old_sqlite_path
        else:
            os.environ.pop("SQLITE_PATH", None)
        if self.old_db_host:
            os.environ["DB_HOST"] = self.old_db_host
        if self.old_db_name:
            os.environ["DB_NAME"] = self.old_db_name


    def test_daily_puzzle_crud(self):
        # 1. Insertion
        entry = {
            "date": "2026-10-26",
            "puzzle": 1700,
            "word": "aventure",
            "tries": 15,
            "attempts": 18,
            "source": "rag",
            "duration_seconds": 4.52,
            "win": True,
            "top_guesses": [{"word": "périple", "score": 82.5, "permille": 995}],
            "trajectory": [{"step": 1, "word": "voyage", "score": 45.0}],
            "is_revealed": False,
        }
        self.assertTrue(save_daily_puzzle(entry))

        # 2. Lecture par date
        loaded = get_daily_puzzle("2026-10-26")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["word"], "aventure")
        self.assertEqual(loaded["puzzle"], 1700)
        self.assertEqual(loaded["tries"], 15)
        self.assertEqual(len(loaded["top_guesses"]), 1)
        self.assertEqual(loaded["top_guesses"][0]["word"], "périple")

        # 3. Mise à jour (ON CONFLICT)
        entry["tries"] = 12
        save_daily_puzzle(entry)
        updated = get_daily_puzzle("2026-10-26")
        self.assertEqual(updated["tries"], 12)

        # 4. Dernier puzzle résolu
        latest = get_latest_daily_puzzle()
        self.assertIsNotNone(latest)
        self.assertEqual(latest["word"], "aventure")

        # 5. Liste de tous les puzzles
        all_puzzles = get_all_daily_puzzles()
        self.assertEqual(len(all_puzzles), 1)

    def test_multi_rooms_crud(self):
        room_id = "DUEL-TEST"
        p1_data = {"name": "Alice", "target": "arbre", "guesses": {"arbre": {"score": 100}}}
        p2_data = {"name": "Bob", "target": "fleur", "guesses": {}}

        # 1. Création du salon
        self.assertTrue(save_room(
            room_id=room_id,
            mode="same_word",
            difficulty="moyen",
            state="in_progress",
            player1_key="J1-1111",
            player2_key="J2-2222",
            current_turn="p1",
            winner=None,
            p1_data=p1_data,
            p2_data=p2_data,
        ))

        # 2. Récupération
        room = get_room(room_id)
        self.assertIsNotNone(room)
        self.assertEqual(room["player1_key"], "J1-1111")
        self.assertEqual(room["p1_data"]["name"], "Alice")

        # 3. Suppression
        self.assertTrue(delete_room(room_id))
        self.assertIsNone(get_room(room_id))

    def test_solo_sessions_crud(self):
        game_id = "solo-test-uuid"
        state = {"guesses": {"soleil": {"score": 50.0}}, "hints": [], "is_won": False}

        # 1. Sauvegarde
        self.assertTrue(save_solo_session_record(
            game_id=game_id,
            puzzle_id="LIBRE-999",
            difficulty="moyen",
            mode="unlimited",
            secret_word="étoile",
            state=state,
        ))

        # 2. Lecture
        session = get_solo_session(game_id)
        self.assertIsNotNone(session)
        self.assertEqual(session["secret_word"], "étoile")
        self.assertEqual(session["state"]["guesses"]["soleil"]["score"], 50.0)

        # 3. Suppression
        self.assertTrue(delete_solo_session(game_id))
        self.assertIsNone(get_solo_session(game_id))

    def test_daily_hints_crud(self):
        # 1. Prérequis : Sauvegarder un puzzle parent
        from src.db.daily import save_daily_hints, get_daily_hints, reveal_daily_hint_tier
        
        entry = {
            "date": "2026-11-01",
            "puzzle": 1800,
            "word": "secret",
            "tries": 10,
            "attempts": 10,
            "source": "rag",
        }
        self.assertTrue(save_daily_puzzle(entry))
        
        # 2. Insertion multi-paliers
        hints = [
            {"word": "froid", "score": 850.0, "tier": "800", "is_revealed": False},
            {"word": "tiède", "score": 910.0, "tier": "900", "is_revealed": False},
            {"word": "chaud", "score": 920.0, "tier": "900", "is_revealed": False},
            {"word": "brûlant", "score": 960.0, "tier": "950", "is_revealed": True}
        ]
        self.assertEqual(save_daily_hints("2026-11-01", hints), 4)
        
        # 3. Contrôle de lecture et filtre
        revealed = get_daily_hints("2026-11-01", revealed_only=True)
        self.assertEqual(len(revealed), 1)
        self.assertEqual(revealed[0]["word"], "brûlant")
        
        all_hints = get_daily_hints("2026-11-01", revealed_only=False)
        self.assertEqual(len(all_hints), 4)
        
        # 4. Révélation d'un palier
        affected = reveal_daily_hint_tier("2026-11-01", "900")
        self.assertEqual(affected, 2)
        
        new_revealed = get_daily_hints("2026-11-01", revealed_only=True)
        self.assertEqual(len(new_revealed), 3)


if __name__ == "__main__":
    unittest.main()
