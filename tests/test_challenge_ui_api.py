"""
Tests d'intégration M9 — Wall of Fame, KPIs en direct, replay des défis.

Couvre `GET /api/challenge/kpis` (cache TTL 15 s, Wall of Fame, bilan et quota
visiteur) et `GET /api/challenge/<id>/guesses` sur une base SQLite temporaire.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _context  # noqa: F401

from src.api.routes import challenge as route
from src.db import challenges as dao
from src.db.connection import db

PATH_KPIS = "/api/challenge/kpis"
ANON_IP = "203.0.113.0"
CID_1 = "1" * 32
CID_2 = "2" * 32
CID_3 = "3" * 32
CID_LEGACY = "4" * 32
CID_REA = "5" * 32


class TestChallengeUiApi(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self._orig = {k: os.environ.get(k) for k in ("SQLITE_PATH", "DB_HOST", "DATABASE_URL")}
        os.environ["SQLITE_PATH"] = str(Path(self.tmp_dir) / "test_ui.sqlite3")
        os.environ.pop("DB_HOST", None)
        os.environ.pop("DATABASE_URL", None)
        db.reset()
        db.init_db()
        route.reset_kpis_cache()
        dao.reset_legacy_sync()
        self.ip_hash = dao.ip_hash(ANON_IP)

    def tearDown(self):
        route.reset_kpis_cache()
        dao.reset_legacy_sync()
        db.reset()
        for key, value in self._orig.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _stat(self, cid, word, outcome, tries=10, ip_hash=None):
        dao.record_challenge_stat(cid, word, ip_hash or self.ip_hash, outcome, tries, 5.0)

    def _kpis(self, anonymized_ip=ANON_IP):
        return route.handle_challenge_get(None, PATH_KPIS, "", "198.51.100.7", anonymized_ip)

    # -- WOF-01 : cache TTL -------------------------------------------------
    def test_kpis_cache_avoids_second_aggregation(self):
        self._stat(CID_1, "alambic", "lost", 100)
        with mock.patch.object(dao, "get_challenge_kpis", wraps=dao.get_challenge_kpis) as spy, \
                mock.patch.object(dao, "get_wall_of_fame", wraps=dao.get_wall_of_fame) as spy_wall:
            first, status1 = self._kpis()
            second, status2 = self._kpis()
        self.assertEqual((status1, status2), (200, 200))
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(spy_wall.call_count, 1)
        self.assertEqual(first["global"], second["global"])

    def test_kpis_cache_expires_after_ttl(self):
        with mock.patch.object(dao, "get_challenge_kpis", wraps=dao.get_challenge_kpis) as spy, \
                mock.patch.object(route, "time") as fake_time:
            fake_time.monotonic.side_effect = [100.0, 116.0]
            self._kpis()
            self._kpis()
        self.assertEqual(spy.call_count, 2)

    def test_kpis_global_values(self):
        self._stat(CID_1, "alambic", "lost", 100)
        self._stat(CID_2, "pomme", "solved", 20)
        self._stat(CID_3, "arbre", "solved", 40)
        payload, status = self._kpis()
        self.assertEqual(status, 200)
        glob = payload["global"]
        self.assertEqual(glob["total_challenges"], 3)
        self.assertEqual(glob["bot_wins"], 2)
        self.assertEqual(glob["bot_win_rate_pct"], 66.7)
        self.assertEqual(glob["wall_of_fame_count"], 1)
        self.assertEqual(glob["avg_tries"], 30.0)

    # -- WOF-03 : Wall of Fame ---------------------------------------------
    def test_wall_of_fame_only_lost_challenges(self):
        self._stat(CID_1, "alambic", "lost", 100)
        self._stat(CID_2, "pomme", "solved", 20)
        payload, _ = self._kpis()
        wall = payload["wall_of_fame"]
        self.assertEqual([w["secret_word"] for w in wall], ["alambic"])
        self.assertEqual(wall[0]["challenge_id"], CID_1)
        self.assertTrue(wall[0]["player"].startswith("Visiteur #"))
        self.assertEqual(wall[0]["tries_count"], 100)

    # -- WOF-02 : guesses ---------------------------------------------------
    def test_guesses_ordered_and_formatted(self):
        self._stat(CID_1, "alambic", "lost", 3)
        dao.save_challenge_guesses(CID_1, [
            {"step": 3, "word": "c", "score": 30.0, "permille": 900, "weather": "🔥",
             "is_record": True, "source": "rag"},
            {"step": 1, "word": "a", "score": -5.5, "permille": None, "weather": "🥶",
             "is_record": False, "source": "seed"},
            {"step": 2, "word": "b", "score": 8.4, "permille": 7, "weather": "😎",
             "is_record": True, "source": "seed"},
        ])
        payload, status = route.handle_challenge_get(None, f"/api/challenge/{CID_1}/guesses")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["guesses_count"], 3)
        self.assertEqual([s["step"] for s in payload["steps"]], [1, 2, 3])
        self.assertEqual(
            set(payload["steps"][0]),
            {"step", "word", "score", "permille", "weather", "is_record", "source"})
        self.assertTrue(payload["steps"][1]["is_record"])

    def test_guesses_unknown_or_malformed_id_is_404(self):
        for path in (f"/api/challenge/{'f' * 32}/guesses", "/api/challenge/../guesses",
                     "/api/challenge/a b/guesses", "/api/challenge/invalid_len/guesses"):
            _, status = route.handle_challenge_get(None, path)
            self.assertEqual(status, 404, path)

    # -- WOF-05 : bilan & quota --------------------------------------------
    def test_player_block_and_quota(self):
        self._stat(CID_1, "alambic", "lost", 100)
        self._stat(CID_2, "pomme", "solved", 20)
        self._stat(CID_3, "arbre", "solved", 40)
        for i in range(3):
            dao.create_challenge(f"mot{i}abc", self.ip_hash, max_tries=100)
        payload, _ = self._kpis()
        player = payload["player"]
        self.assertTrue(player["identified"])
        self.assertEqual(player["total_played"], 3)
        self.assertEqual(player["player_wins"], 1)
        self.assertEqual(player["player_losses"], 2)
        self.assertEqual(player["player_win_rate_pct"], 33.3)
        self.assertEqual(player["quota_max"], dao.CHALLENGE_QUOTA_PER_HOUR)
        self.assertEqual(player["quota_remaining"], dao.CHALLENGE_QUOTA_PER_HOUR - 3)

    def test_player_block_unidentified_has_full_quota(self):
        payload, status = self._kpis(anonymized_ip="")
        self.assertEqual(status, 200)
        self.assertFalse(payload["player"]["identified"])
        self.assertEqual(payload["player"]["quota_remaining"], dao.CHALLENGE_QUOTA_PER_HOUR)

    def test_player_block_is_not_cached_between_visitors(self):
        self._stat(CID_1, "alambic", "lost", 100)
        first, _ = self._kpis()
        other, _ = self._kpis(anonymized_ip="198.51.100.0")
        self.assertEqual(first["player"]["total_played"], 1)
        self.assertEqual(other["player"]["total_played"], 0)

    def test_kpis_db_failure_returns_503(self):
        with mock.patch.object(dao, "get_challenge_kpis", side_effect=RuntimeError("boom")):
            payload, status = self._kpis()
        self.assertEqual(status, 503)
        self.assertIn("error", payload)

    def test_sync_legacy_challenges_and_recent_challenges(self):
        """Les défis historiques stockés dans bot_challenges sont synchronisés et restitués."""
        # Insère un défi legacy dans bot_challenges (non présent dans bot_challenge_stats)
        cid = CID_LEGACY
        traj = [{"word": "p1", "score": 10.0, "permille": 50, "weather": "😎"}]
        db.execute(
            """
            INSERT INTO bot_challenges (id, secret_word, ip_hash, status, tries_count, duration_seconds, trajectory)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """,
            (cid, "quatorze", self.ip_hash, "solved", 62, 0.85, json.dumps(traj)),
        )
        self._stat(CID_REA, "réa", "lost", 103)

        payload, status = self._kpis()
        self.assertEqual(status, 200)
        self.assertIn("recent_challenges", payload)
        recents = payload["recent_challenges"]
        words = {r["secret_word"]: r["outcome"] for r in recents}
        self.assertIn("quatorze", words)
        self.assertEqual(words["quatorze"], "won")
        self.assertIn("réa", words)
        self.assertEqual(words["réa"], "lost")

        # Vérifie que guesses_get fonctionne pour le défi legacy
        g_payload, g_status = route.handle_challenge_get(None, f"/api/challenge/{cid}/guesses")
        self.assertEqual(g_status, 200)
        self.assertEqual(g_payload["secret_word"], "quatorze")
        self.assertEqual(g_payload["outcome"], "won")
        self.assertEqual(len(g_payload["steps"]), 1)


if __name__ == "__main__":
    unittest.main()
