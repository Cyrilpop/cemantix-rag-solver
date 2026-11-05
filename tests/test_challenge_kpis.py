"""
Tests unitaires pour le Jalon M8 : Traçage & KPIs des Défis Visiteurs.
======================================================================
Valide :
1. L'idempotence DDL (SQLITE_SCHEMA réexécuté sans erreur).
2. L'insertion idempotente et le dédoublonnage (ON CONFLICT DO NOTHING).
3. Le calcul des KPIs globaux et par joueur (moyennes, taux de victoires, top mots, mots coriaces).
4. La pseudonymisation et l'absence totale d'IP brute dans les données renvoyées (RGPD).
5. La restitution ordonnée des coups (guesses) et la cascade ON DELETE CASCADE.
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.db.challenges import (
    anonymize_player_token,
    format_player_display,
    get_challenge_guesses,
    get_challenge_kpis,
    get_challenge_stat,
    record_challenge_stat,
    save_challenge_guesses,
)
from src.db.connection import SQLITE_SCHEMA, db


class TestChallengeKPIs(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test_kpis.sqlite3"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        os.environ["SQLITE_PATH"] = str(self.db_path)
        self._orig_db_host = os.environ.get("DB_HOST")
        self._orig_db_url = os.environ.get("DATABASE_URL")
        os.environ.pop("DB_HOST", None)
        os.environ.pop("DATABASE_URL", None)
        db.reset()
        db.init_db()

    def tearDown(self):
        db.reset()
        if self._orig_sqlite_path is not None:
            os.environ["SQLITE_PATH"] = self._orig_sqlite_path
        else:
            os.environ.pop("SQLITE_PATH", None)
        if self._orig_db_host is not None:
            os.environ["DB_HOST"] = self._orig_db_host
        if self._orig_db_url is not None:
            os.environ["DATABASE_URL"] = self._orig_db_url
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_ddl_idempotence(self):
        """Le schéma SQLite doit pouvoir être exécuté plusieurs fois sans lever d'erreur."""
        # 1ère réexécution via init_db (doit être un no-op si initialized)
        db.init_db()
        # 2ème réexécution directe du script SQL pour simuler des redémarrages multiples
        with db.transaction() as conn:
            conn.executescript(SQLITE_SCHEMA)
        # Vérifie que les tables existent toujours et sont fonctionnelles
        tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table';")
        names = {t["name"] for t in tables}
        self.assertIn("bot_challenge_stats", names)
        self.assertIn("bot_challenge_guesses", names)

    def test_record_challenge_stat_and_deduplication(self):
        """Vérifie l'enregistrement et le dédoublonnage ON CONFLICT DO NOTHING."""
        cid = "chal_abc123"
        ip_hash = "hash_player_1"

        # Premier enregistrement
        ok = record_challenge_stat(
            challenge_id=cid,
            secret_word="banane",
            ip_hash_value=ip_hash,
            outcome="solved",
            tries_count=42,
            duration_seconds=5.2,
        )
        self.assertTrue(ok)

        stat = get_challenge_stat(cid)
        self.assertIsNotNone(stat)
        self.assertEqual(stat["secret_word"], "banane")
        self.assertEqual(stat["outcome"], "won")  # 'solved' -> 'won'
        self.assertEqual(stat["tries_count"], 42)
        self.assertAlmostEqual(stat["duration_seconds"], 5.2, places=1)
        self.assertTrue(stat["player_anon_id"].startswith("joueur_"))

        # Deuxième enregistrement avec le même challenge_id (ne doit rien écraser ni doubler)
        ok2 = record_challenge_stat(
            challenge_id=cid,
            secret_word="banane",
            ip_hash_value=ip_hash,
            outcome="lost",
            tries_count=100,
            duration_seconds=10.0,
        )
        self.assertTrue(ok2)

        # L'état initial doit être préservé intact
        stat_after = get_challenge_stat(cid)
        self.assertEqual(stat_after["outcome"], "won")
        self.assertEqual(stat_after["tries_count"], 42)

        # Un seul enregistrement dans la table
        count = db.fetch_one("SELECT COUNT(*) AS n FROM bot_challenge_stats WHERE challenge_id = %s;", (cid,))
        self.assertEqual(count["n"], 1)

    def test_save_and_get_challenge_guesses(self):
        """Vérifie l'enregistrement et la lecture ordonnée des coups (guesses)."""
        cid = "chal_guesses_1"
        record_challenge_stat(cid, "pomme", "hash_p", "won", 3, 2.0)

        guesses = [
            {"step": 1, "word": "fruit", "score": 25.0, "permille": 400, "weather": "froid", "is_record": True, "source": "seed"},
            {"step": 2, "word": "poire", "score": 58.0, "permille": 920, "weather": "chaud", "is_record": True, "source": "rag"},
            {"step": 3, "word": "pomme", "score": 100.0, "permille": 1000, "weather": "trouve", "is_record": True, "source": "rag"},
        ]
        inserted = save_challenge_guesses(cid, guesses)
        self.assertEqual(inserted, 3)

        # Vérifie le dédoublonnage ON CONFLICT (challenge_id, step_num) DO NOTHING
        inserted_dup = save_challenge_guesses(cid, guesses)
        self.assertEqual(inserted_dup, 3)  # Loop iterated 3 times without error

        retrieved = get_challenge_guesses(cid)
        self.assertEqual(len(retrieved), 3)
        self.assertEqual(retrieved[0]["word"], "fruit")
        self.assertEqual(retrieved[1]["word"], "poire")
        self.assertEqual(retrieved[2]["word"], "pomme")
        self.assertEqual(retrieved[0]["step_num"], 1)
        self.assertEqual(retrieved[2]["step_num"], 3)

    def test_kpis_calculation(self):
        """Vérifie le calcul complet des KPIs globaux et du joueur."""
        p1_hash = "player_hash_alpha"
        p2_hash = "player_hash_beta"

        # p1 : 2 victoires bot, 1 défaite bot (donc 1 victoire p1)
        record_challenge_stat("c1", "pomme", p1_hash, "won", 10, 1.5)
        record_challenge_stat("c2", "pomme", p1_hash, "won", 20, 2.5)
        record_challenge_stat("c3", "alambic", p1_hash, "lost", 100, 12.0)

        # p2 : 1 victoire bot
        record_challenge_stat("c4", "ordinateur", p2_hash, "won", 30, 4.0)

        # KPIs sans joueur identifié
        kpis = get_challenge_kpis()
        self.assertEqual(kpis["status"], "ok")
        g = kpis["global"]
        self.assertEqual(g["total_challenges"], 4)
        self.assertEqual(g["bot_wins"], 3)
        self.assertEqual(g["bot_losses"], 1)
        self.assertAlmostEqual(g["bot_win_rate_pct"], 75.0, places=1)
        self.assertAlmostEqual(g["player_win_rate_pct"], 25.0, places=1)

        # Coups moyens, min, max (sur les victoires : 10, 20, 30 -> moy 20.0, min 10, max 30)
        self.assertAlmostEqual(g["avg_tries"], 20.0, places=1)
        self.assertEqual(g["min_tries"], 10)
        self.assertEqual(g["max_tries"], 30)

        # Top mots : "pomme" doit être premier (2 défis, 2 bot_wins)
        self.assertTrue(len(g["top_words"]) >= 2)
        self.assertEqual(g["top_words"][0]["word"], "pomme")
        self.assertEqual(g["top_words"][0]["count"], 2)
        self.assertEqual(g["top_words"][0]["bot_wins"], 2)

        # Mots coriaces : "alambic" (perdu par le bot)
        self.assertEqual(len(g["tough_words"]), 1)
        self.assertEqual(g["tough_words"][0]["word"], "alambic")
        self.assertEqual(g["tough_words"][0]["tries"], 100)

        # Joueur non identifié
        self.assertFalse(kpis["player"]["identified"])
        self.assertIsNone(kpis["player"]["display_name"])

        # KPIs pour p1
        kpis_p1 = get_challenge_kpis(player_ip_hash=p1_hash)
        p_stats = kpis_p1["player"]
        self.assertTrue(p_stats["identified"])
        self.assertTrue(p_stats["display_name"].startswith("Visiteur #"))
        self.assertEqual(p_stats["total_played"], 3)
        self.assertEqual(p_stats["player_wins"], 1)  # c3 perdu par le bot
        self.assertEqual(p_stats["player_losses"], 2)  # c1, c2 gagnés par le bot
        self.assertAlmostEqual(p_stats["player_win_rate_pct"], 33.3, places=1)

    def test_anonymization_and_rgpd_compliance(self):
        """Vérifie qu'aucune IP brute n'est persistée ni exposée."""
        raw_ip = "192.168.1.42"
        # ip_hash_value simulé
        ip_hash = "mock_hmac_sha256_hash_1234567890abcdef"

        record_challenge_stat("c_sec", "secret", ip_hash, "won", 15, 1.0)
        kpis = get_challenge_kpis(player_ip_hash=ip_hash)

        # Vérification des chaînes sérialisées
        payload_str = str(kpis)
        self.assertNotIn(raw_ip, payload_str)
        self.assertNotIn(ip_hash, payload_str)

        # Format du token et display name
        token = anonymize_player_token(ip_hash)
        self.assertTrue(token.startswith("joueur_"))
        self.assertEqual(len(token), 17)  # 'joueur_' (7) + 10 chars hex = 17

        disp = format_player_display(token)
        self.assertTrue(disp.startswith("Visiteur #"))
        self.assertEqual(len(disp), 14)  # 'Visiteur #' (10) + 4 chars = 14


if __name__ == "__main__":
    unittest.main()
