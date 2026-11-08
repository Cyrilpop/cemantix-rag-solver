"""
Cémantix Solver — Suite de Tests Unitaires & Intégration Solo Quotidien (Jalon M15)
===================================================================================
Valide :
- Le tirage aléatoire pondéré du mot du jour et l'isolation du pool « Extrême ».
- Le modèle relationnel (puzzles, indices IA roulants, sessions joueurs, trajectoires).
- La simulation sémantique IA des 20 habitués à 6h30 et les verrous d'idempotence.
- L'étanchéité anti-spoiler sur les trajectoires du classement.
- La gestion stricte des 3 indices (1 indice = +1 coup, choix mot/phrase immuable par palier).
"""
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from src.ai.trajectory_sim import simulate_batch_trajectories
from src.db.connection import db
from src.db.players import FIXED_BOT_HABITUES, get_bot_uuid, seed_bot_players_if_empty
from src.db.solo import (
    clear_solo_bots_simulated,
    finish_solo_player_game,
    get_or_create_solo_daily_puzzle,
    get_or_create_solo_player_game,
    get_solo_ai_hints,
    get_solo_daily_puzzle,
    get_solo_leaderboard,
    get_solo_player_game,
    get_solo_player_trajectory,
    has_real_player_won,
    is_solo_bots_simulated,
    lock_solo_bots_simulated,
    purge_old_solo_ai_hints,
    record_solo_hint_revealed,
    save_solo_ai_hints,
)
from src.engine.vocab import VocabStore
from src.game.manager import GameManager
from src.services.solo_daily import (
    ensure_solo_daily_puzzle,
    simulate_solo_daily_bots,
)


class TestSoloDailyWordDraw(unittest.TestCase):
    """Vérifie l'initialisation des pools de difficulté et la distribution pondérée."""

    @classmethod
    def setUpClass(cls):
        cls.store = VocabStore(with_chroma=False)
        cls.manager = GameManager(cls.store)

    def test_extreme_pool_initialized(self):
        """Vérifie que le pool extrême contient les 1% des mots les moins fréquents."""
        self.assertTrue(hasattr(self.manager, "extreme_pool"))
        self.assertGreater(len(self.manager.extreme_pool), 0)
        self.assertGreater(len(self.manager.easy_pool), 0)
        self.assertGreater(len(self.manager.medium_pool), 0)
        self.assertGreater(len(self.manager.expert_pool), 0)

    def test_draw_solo_daily_word(self):
        """Vérifie le tirage aléatoire et la conformité des catégories retournées."""
        valid_difficulties = {"facile", "normal", "difficile", "extreme"}
        for _ in range(50):
            word, diff = self.manager.draw_solo_daily_word()
            self.assertIn(diff, valid_difficulties)
            self.assertIn(word, self.store)
            self.assertGreaterEqual(len(word), 4)

    def test_weighted_draw_distribution(self):
        """Vérifie que la distribution statistique respecte les ordres de grandeur."""
        counts = {"facile": 0, "normal": 0, "difficile": 0, "extreme": 0}
        total = 1000
        for _ in range(total):
            _, diff = self.manager.draw_solo_daily_word()
            counts[diff] += 1

        # Normal doit représenter la majorité écrasante (~75%)
        self.assertGreater(counts["normal"], counts["facile"])
        self.assertGreater(counts["facile"], counts["difficile"])
        # Extrême doit rester rare (~1%)
        self.assertLess(counts["extreme"], counts["normal"])


class TestSoloDailyDAO(unittest.TestCase):
    """Vérifie les opérations en base relationnelle pour le mode Solo M15."""

    def setUp(self):
        db.init_db()
        day_num = (int(datetime.now().strftime('%S')) % 28) + 1
        self.test_date = f"2099-01-{day_num:02d}"
        db.execute("DELETE FROM solo_daily_puzzles WHERE puzzle_date = %s", (self.test_date,))
        self.secret = "boussole"
        get_or_create_solo_daily_puzzle(self.test_date, self.secret, "normal")

    def test_create_and_get_puzzle(self):
        puzzle = get_or_create_solo_daily_puzzle(self.test_date, self.secret, "normal")
        self.assertEqual(puzzle["puzzle_date"], self.test_date)
        self.assertEqual(puzzle["secret_word"], self.secret)
        self.assertEqual(puzzle["difficulty"], "normal")
        self.assertFalse(puzzle["bots_simulated"])

        fetched = get_solo_daily_puzzle(self.test_date)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["secret_word"], self.secret)

    def test_ai_hints_lifecycle_and_purge(self):
        hints = [
            {"hint_level": 1, "weight": 0.33, "hint_word": "azimut", "hint_phrase": "Une direction lointaine.", "score": 25.4, "permille": 450},
            {"hint_level": 2, "weight": 0.66, "hint_word": "navigation", "hint_phrase": "Un usage maritime.", "score": 48.2, "permille": 820},
            {"hint_level": 3, "weight": 1.00, "hint_word": "aiguille", "hint_phrase": "La pointe aimantée.", "score": 85.0, "permille": 995},
        ]
        save_solo_ai_hints(self.test_date, hints)
        retrieved = get_solo_ai_hints(self.test_date)
        self.assertEqual(len(retrieved), 3)
        self.assertEqual(retrieved[0]["hint_word"], "azimut")
        self.assertEqual(retrieved[2]["hint_phrase"], "La pointe aimantée.")

        # Test purge
        future_date = "2099-02-01"
        purged = purge_old_solo_ai_hints(future_date)
        self.assertGreaterEqual(purged, 3)
        self.assertEqual(len(get_solo_ai_hints(self.test_date)), 0)

    def test_solo_player_game_and_hints_immutability(self):
        from src.db.players import create_guest_player
        import uuid
        player_id = str(uuid.uuid4())
        player = create_guest_player(player_id, f"tok_{player_id[:8]}", f"Joueur{player_id[:6]}")

        game = get_or_create_solo_player_game(self.test_date, player["id"])
        self.assertEqual(game["status"], "in_progress")
        self.assertEqual(game["hints_used"], 0)

        # Révéler indice #1 en mot
        updated1 = record_solo_hint_revealed(self.test_date, player["id"], 1, "word", "azimut", score=25.4, permille=450)
        self.assertEqual(updated1["hints_used"], 1)
        self.assertEqual(updated1["tries_count"], 1)
        self.assertEqual(len(updated1["hints_revealed"]), 1)
        self.assertEqual(updated1["hints_revealed"][0]["type"], "word")

        # Tentative de réécrire indice #1 en phrase -> immuabilité stricte
        updated_conflict = record_solo_hint_revealed(self.test_date, player["id"], 1, "phrase", "Une phrase concurrente")
        self.assertEqual(updated_conflict["hints_revealed"][0]["type"], "word")
        self.assertEqual(updated_conflict["hints_used"], 1)

        # Révéler indice #2 en phrase -> autorisé
        updated2 = record_solo_hint_revealed(self.test_date, player["id"], 2, "phrase", "Une énigme de navigation")
        self.assertEqual(updated2["hints_used"], 2)
        self.assertEqual(updated2["tries_count"], 2)
        self.assertEqual(len(updated2["hints_revealed"]), 2)
        self.assertEqual(updated2["hints_revealed"][1]["type"], "phrase")


class TestSoloAntiSpoilerAndLeaderboard(unittest.TestCase):
    """Vérifie l'étanchéité anti-spoiler des trajectoires et le classement."""

    def setUp(self):
        db.init_db()
        day_num = (int(datetime.now().strftime('%S')) % 28) + 1
        self.test_date = f"2098-05-{day_num:02d}"
        db.execute("DELETE FROM solo_daily_puzzles WHERE puzzle_date = %s", (self.test_date,))
        get_or_create_solo_daily_puzzle(self.test_date, "boussole", "normal")

        # Création de 2 joueurs : un gagnant et un joueur en cours
        import uuid
        from src.db.players import create_guest_player

        self.winner_id = str(uuid.uuid4())
        self.ongoing_id = str(uuid.uuid4())
        create_guest_player(self.winner_id, f"tok_{self.winner_id[:8]}", f"Gagnant{self.winner_id[:6]}")
        create_guest_player(self.ongoing_id, f"tok_{self.ongoing_id[:8]}", f"EnCours{self.ongoing_id[:6]}")

        # Clôturer la partie du gagnant
        guesses = [
            {"order": 1, "word": "voyage", "score": 20.0, "permille": 300, "weather": "Froid", "is_hint": False},
            {"order": 2, "word": "mer", "score": 35.0, "permille": 600, "weather": "Tiède", "is_hint": False},
            {"order": 3, "word": "boussole", "score": 100.0, "permille": 1000, "weather": "Trouvé", "is_hint": False},
        ]
        self.winner_game = finish_solo_player_game(
            puzzle_date=self.test_date,
            player_id=self.winner_id,
            status="won",
            tries_count=3,
            duration_seconds=120.5,
            best_score=100.0,
            best_permille=1000,
            guesses=guesses,
            is_bot=False,
        )

        # Initialiser le joueur en cours
        get_or_create_solo_player_game(self.test_date, self.ongoing_id)

    def test_leaderboard_includes_winner(self):
        leaderboard = get_solo_leaderboard(self.test_date)
        self.assertGreaterEqual(len(leaderboard), 1)
        first = leaderboard[0]
        self.assertEqual(first["game_id"], self.winner_game["id"])
        self.assertEqual(first["tries_count"], 3)
        self.assertFalse(first["is_bot"])

    def test_anti_spoiler_blocks_ongoing_player(self):
        """Un joueur en cours ne doit PAS pouvoir consulter la trajectoire d'un gagnant."""
        traj, err = get_solo_player_trajectory(
            puzzle_date=self.test_date,
            target_game_id=self.winner_game["id"],
            requesting_player_id=self.ongoing_id,
            is_admin=False,
        )
        self.assertIsNone(traj)
        self.assertIsNotNone(err)
        self.assertIn("Anti-spoiler actif", err)

    def test_anti_spoiler_allows_after_giveup_or_win(self):
        """Dès que le joueur termine (ici abandon), il peut voir la trajectoire."""
        finish_solo_player_game(
            puzzle_date=self.test_date,
            player_id=self.ongoing_id,
            status="given_up",
            tries_count=5,
            duration_seconds=300.0,
            best_score=40.0,
            best_permille=700,
            guesses=[],
            is_bot=False,
        )
        traj, err = get_solo_player_trajectory(
            puzzle_date=self.test_date,
            target_game_id=self.winner_game["id"],
            requesting_player_id=self.ongoing_id,
            is_admin=False,
        )
        self.assertIsNone(err)
        self.assertIsNotNone(traj)
        self.assertEqual(len(traj), 3)
        self.assertEqual(traj[2]["word"], "boussole")

    def test_admin_bypass_anti_spoiler(self):
        """L'administrateur peut toujours voir la trajectoire sans restriction."""
        traj, err = get_solo_player_trajectory(
            puzzle_date=self.test_date,
            target_game_id=self.winner_game["id"],
            requesting_player_id=None,
            is_admin=True,
        )
        self.assertIsNone(err)
        self.assertIsNotNone(traj)
        self.assertEqual(len(traj), 3)

    def test_leaderboard_includes_given_up_players_after_winners(self):
        """Le classement quotidien doit afficher tous les participants (gagnants et abandons), les gagnants en premier."""
        finish_solo_player_game(
            puzzle_date=self.test_date,
            player_id=self.ongoing_id,
            status="given_up",
            tries_count=12,
            duration_seconds=450.0,
            best_score=38.5,
            best_permille=680,
            guesses=[],
            is_bot=False,
        )
        leaderboard = get_solo_leaderboard(self.test_date)
        statuses = [item["status"] for item in leaderboard]
        self.assertIn("won", statuses)
        self.assertIn("given_up", statuses)
        # Le premier doit être le gagnant
        self.assertEqual(leaderboard[0]["status"], "won")
        # Le joueur ayant abandonné doit être dans le classement
        given_up_item = next(p for p in leaderboard if p["status"] == "given_up")
        self.assertEqual(given_up_item["tries_count"], 12)

    def test_trajectory_route_unlocked_via_finished_game_id(self):
        """L'endpoint /api/game/trajectory/<id> doit autoriser l'accès si game_id a abandonné."""
        store = VocabStore(with_chroma=False)
        manager = GameManager(store)
        session = manager.new_game(mode="daily", difficulty="normal", force=True)
        session.is_given_up = True
        manager.save_solo_session(session)

        from src.api.routes.solo import handle_solo_get
        res, code = handle_solo_get(
            manager=manager,
            path=f"/api/game/trajectory/{self.winner_game['id']}",
            query=f"game_id={session.game_id}&date={self.test_date}",
        )
        self.assertEqual(code, 200)
        self.assertTrue(res.get("unlocked"))
        self.assertGreaterEqual(len(res.get("trajectory", [])), 1)


class TestSoloBotSimulation(unittest.TestCase):
    """Vérifie le pool des 20 habitués et la simulation à 6h30."""

    @classmethod
    def setUpClass(cls):
        cls.store = VocabStore(with_chroma=False)
        seed_bot_players_if_empty()

    def setUp(self):
        db.init_db()
        day_num = (int(datetime.now().strftime('%S')) % 28) + 1
        self.test_date = f"2097-03-{day_num:02d}"

    def test_fixed_bot_pool_exists(self):
        """Vérifie que les 20 habitués sont amorcés en base avec leur pseudo réservé."""
        self.assertEqual(len(FIXED_BOT_HABITUES), 20)
        from src.db.players import get_player_by_username
        for bot_name in FIXED_BOT_HABITUES:
            player = get_player_by_username(bot_name)
            self.assertIsNotNone(player, f"Le bot {bot_name} devrait être amorcé en base")
            self.assertEqual(player["auth_provider"], "bot")
            self.assertFalse(player["can_change_username"])

    @mock.patch("src.services.solo_daily.GeminiClient.is_configured", return_value=False)
    def test_batch_simulation_runner(self, mock_gemini):
        """Vérifie la simulation locale d'un contingent de bots."""
        puzzle = get_or_create_solo_daily_puzzle(self.test_date, "boussole", "normal")
        sim_res = simulate_solo_daily_bots(self.store, force=True, puzzle_date=self.test_date)
        self.assertTrue(sim_res["simulated"])
        self.assertGreaterEqual(sim_res["count"], 7)
        self.assertLessEqual(sim_res["count"], 20)

        # Vérifier que le verrou est actif
        self.assertTrue(is_solo_bots_simulated(self.test_date))

        # Rejeu sans --force bloqué par le verrou
        retry_res = simulate_solo_daily_bots(self.store, force=False, puzzle_date=self.test_date)
        self.assertFalse(retry_res["simulated"])
        self.assertEqual(retry_res["reason"], "already_simulated")

        # Vérifier présence des bots dans le classement
        leaderboard = get_solo_leaderboard(self.test_date)
        bot_entries = [p for p in leaderboard if p["is_bot"]]
        self.assertGreater(len(bot_entries), 0)


@mock.patch("src.services.solo_daily.GeminiClient.is_configured", return_value=False)
class TestSoloGameAPIRoutes(unittest.TestCase):
    """Vérifie les contrôleurs HTTP /api/game/* pour le mode Solo."""

    @classmethod
    def setUpClass(cls):
        cls.store = VocabStore(with_chroma=False)
        cls.manager = GameManager(cls.store)
        seed_bot_players_if_empty()

    def test_daily_info_endpoint(self, mock_gemini):
        from src.api.routes.solo import handle_solo_get
        res, code = handle_solo_get(self.manager, "/api/game/daily-info")
        self.assertEqual(code, 200)
        self.assertTrue(res["available"])

    def test_daily_metadata_endpoint(self, mock_gemini):
        from src.api.routes.solo import handle_solo_get
        res, code = handle_solo_get(self.manager, "/api/game/daily")
        self.assertEqual(code, 200)
        self.assertIn("puzzle_date", res)
        self.assertIn("difficulty", res)
        self.assertEqual(res["max_hints"], 3)
        self.assertNotIn("secret_word", res)  # Zéro fuite du secret

    def test_new_and_guess_flow(self, mock_gemini):
        from src.api.routes.solo import handle_solo_post
        # 1. Nouvelle partie
        res_new, code_new = handle_solo_post(self.manager, "/api/game/new", {"mode": "unlimited", "difficulty": "facile"})
        self.assertEqual(code_new, 200)
        game_id = res_new["game_id"]
        self.assertEqual(res_new["tries"], 0)

        # 2. Coup invalide
        res_inv, code_inv = handle_solo_post(self.manager, "/api/game/guess", {"game_id": game_id, "word": "xyzabc123"})
        self.assertEqual(code_inv, 200)
        self.assertFalse(res_inv.get("valid", True))

        # 3. Coup valide
        res_val, code_val = handle_solo_post(self.manager, "/api/game/guess", {"game_id": game_id, "word": "maison"})
        self.assertEqual(code_val, 200)
        self.assertTrue(res_val.get("valid"))
        self.assertEqual(res_val["tries"], 1)

    def test_daily_hints_strictly_increasing_and_calibrated(self, mock_gemini):
        """Vérifie que les 3 indices du jour ont des millièmes strictement croissants :
        #1 ~700‰ < #2 ~825‰ < #3 ~950‰.
        """
        from src.services.solo_daily import ensure_solo_daily_puzzle, get_solo_ai_hints, get_current_paris_date
        today_str = get_current_paris_date()
        ensure_solo_daily_puzzle(self.store, self.manager, puzzle_date=today_str)
        hints = get_solo_ai_hints(today_str)
        self.assertEqual(len(hints), 3)

        p1 = hints[0].get("permille")
        p2 = hints[1].get("permille")
        p3 = hints[2].get("permille")

        self.assertIsNotNone(p1)
        self.assertIsNotNone(p2)
        self.assertIsNotNone(p3)

        # #1 proche des 700‰
        self.assertLessEqual(abs(p1 - 700), 50)
        # #3 proche des 950‰
        self.assertLessEqual(abs(p3 - 950), 20)
        # Strictement croissant
        self.assertLess(p1, p2)
        self.assertLess(p2, p3)

    def test_hint_quota_and_format_selection(self, mock_gemini):
        from src.api.routes.solo import handle_solo_post
        res_new, _ = handle_solo_post(self.manager, "/api/game/new", {"mode": "daily"})
        game_id = res_new["game_id"]

        # Indice #1 au format phrase
        h1, code1 = handle_solo_post(self.manager, "/api/game/hint", {"game_id": game_id, "type": "phrase", "level": 1})
        self.assertEqual(code1, 200)
        self.assertEqual(h1["hint_type"], "phrase")
        self.assertEqual(h1["hint_level"], 1)

        # Indice #2 au format mot
        h2, code2 = handle_solo_post(self.manager, "/api/game/hint", {"game_id": game_id, "type": "word", "level": 2})
        self.assertEqual(code2, 200)
        self.assertEqual(h2["hint_type"], "word")
        self.assertEqual(h2["hint_level"], 2)

        # Indice #3 au format mot -> calibré à ~950‰
        h3, code3 = handle_solo_post(self.manager, "/api/game/hint", {"game_id": game_id, "type": "word", "level": 3})
        self.assertEqual(code3, 200)
        self.assertEqual(h3["hint_type"], "word")
        self.assertEqual(h3["hint_level"], 3)
        self.assertIsNotNone(h3.get("permille"))
        self.assertLessEqual(abs(h3["permille"] - 950), 20)

    def test_daily_puzzle_non_replayable_once_finished(self, mock_gemini):
        """Vérifie qu'une partie du jour gagnée ou abandonnée est verrouillée et non rejouable."""
        from src.api.routes.solo import handle_solo_post
        from src.db.players import create_guest_player
        import uuid
        test_pid = str(uuid.uuid4())
        create_guest_player(test_pid, f"tok_{test_pid[:8]}", f"Joueur{test_pid[:6]}")

        # 1. Créer une partie du jour
        res_new, _ = handle_solo_post(self.manager, "/api/game/new", {"mode": "daily", "player_id": test_pid})
        gid = res_new["game_id"]
        self.assertFalse(res_new.get("is_won", False))
        self.assertFalse(res_new.get("is_given_up", False))

        # 2. Abandonner
        res_giveup, code_g = handle_solo_post(self.manager, "/api/game/giveup", {"game_id": gid, "player_id": test_pid})
        self.assertEqual(code_g, 200)
        self.assertTrue(res_giveup["is_given_up"])
        self.assertIsNotNone(res_giveup["secret"])

        # 3. Interdiction de soumettre de nouveaux mots ou indices
        res_guess, code_guess = handle_solo_post(self.manager, "/api/game/guess", {"game_id": gid, "word": "soleil", "player_id": test_pid})
        self.assertEqual(code_guess, 400)
        self.assertIn("error", res_guess)

        res_hint, code_hint = handle_solo_post(self.manager, "/api/game/hint", {"game_id": gid, "type": "word", "level": 1, "player_id": test_pid})
        self.assertEqual(code_hint, 400)

        # 4. Tentative de forcer une nouvelle partie en mode daily -> retourne la partie verrouillée (intégrité classement)
        res_force, code_force = handle_solo_post(self.manager, "/api/game/new", {"mode": "daily", "force": True, "player_id": test_pid})
        self.assertEqual(code_force, 200)
        self.assertTrue(res_force["is_given_up"])
        self.assertTrue(res_force.get("already_finished", False))
        self.assertIsNotNone(res_force["secret"])


class TestSoloStartupSimulation(unittest.TestCase):
    """Vérifie la procédure de remplissage automatique au démarrage du conteneur Docker."""

    @classmethod
    def setUpClass(cls):
        cls.store = VocabStore(with_chroma=False)
        seed_bot_players_if_empty()

    def setUp(self):
        db.init_db()
        day_num = (int(datetime.now().strftime('%S')) % 28) + 1
        self.test_date = f"2096-06-{day_num:02d}"
        db.execute("DELETE FROM solo_daily_puzzles WHERE puzzle_date = %s", (self.test_date,))
        db.execute("DELETE FROM solo_player_games WHERE puzzle_date = %s", (self.test_date,))

    @mock.patch("src.services.solo_daily.GeminiClient.is_configured", return_value=False)
    def test_startup_before_630_does_not_simulate(self, mock_gemini):
        """Avant 06h30, aucun remplissage n'est déclenché."""
        from src.services.solo_daily import PARIS_TZ, check_and_run_startup_simulation
        dt_before = datetime(2096, 6, 15, 5, 45, tzinfo=PARIS_TZ)
        res = check_and_run_startup_simulation(self.store, now=dt_before, puzzle_date=self.test_date)
        self.assertIsNone(res)
        # Vérifie que la table reste vide
        row = db.fetch_one("SELECT COUNT(*) as cnt FROM solo_player_games WHERE puzzle_date = %s", (self.test_date,))
        self.assertEqual(row["cnt"], 0)

    @mock.patch("src.services.solo_daily.GeminiClient.is_configured", return_value=False)
    def test_startup_after_630_empty_table_triggers_simulation(self, mock_gemini):
        """Après 06h30 et avec table vide, le remplissage des habitués est exécuté."""
        from src.services.solo_daily import PARIS_TZ, check_and_run_startup_simulation
        dt_after = datetime(2096, 6, 15, 8, 15, tzinfo=PARIS_TZ)
        res = check_and_run_startup_simulation(self.store, now=dt_after, puzzle_date=self.test_date)
        self.assertIsNotNone(res)
        self.assertTrue(res["simulated"])
        self.assertGreaterEqual(res["count"], 7)

        # Vérifie que la table est maintenant pourvue
        row = db.fetch_one("SELECT COUNT(*) as cnt FROM solo_player_games WHERE puzzle_date = %s", (self.test_date,))
        self.assertGreater(row["cnt"], 0)

        # Un second démarrage ne doit rien réexécuter (table non vide)
        res_retry = check_and_run_startup_simulation(self.store, now=dt_after, puzzle_date=self.test_date)
        self.assertIsNone(res_retry)

    @mock.patch("src.services.solo_daily.GeminiClient.is_configured", return_value=False)
    def test_leaderboard_auto_populates_after_630_if_empty(self, mock_gemini):
        """Passé 06h30, si le classement du jour est vide, l'endpoint /api/game/leaderboard le remplit automatiquement."""
        from src.api.routes.solo import handle_solo_get
        from src.game.manager import GameManager
        from src.services.solo_daily import PARIS_TZ
        manager = GameManager(self.store)
        dt_after = datetime(2096, 6, 15, 9, 30, tzinfo=PARIS_TZ)
        with mock.patch("src.api.routes.solo.get_current_paris_date", return_value=self.test_date):
            with mock.patch("src.api.routes.solo.datetime") as mock_dt:
                mock_dt.now.return_value = dt_after
                res, status = handle_solo_get(
                    manager,
                    path="/api/game/leaderboard",
                    query=f"date={self.test_date}",
                )
                self.assertEqual(status, 200)
                self.assertGreater(res["count"], 0)
                self.assertGreaterEqual(len(res["leaderboard"]), 1)

                # Vérifie que les habitués ont bien été simulés en base
                row = db.fetch_one("SELECT COUNT(*) as cnt FROM solo_player_games WHERE puzzle_date = %s", (self.test_date,))
                self.assertGreaterEqual(row["cnt"], 7)

    @mock.patch("src.services.solo_daily.GeminiClient.is_configured", return_value=False)
    def test_hints_revealed_persists_across_container_restart(self, mock_gemini):
        """Vérifie que les indices débloqués et l'état de la partie survivent à un redémarrage du conteneur."""
        from src.api.routes.solo import handle_solo_post
        from src.game.manager import GameManager
        from src.db.players import create_guest_player
        from src.services.solo_daily import ensure_solo_daily_puzzle

        ensure_solo_daily_puzzle(self.store, puzzle_date=self.test_date)
        guest = create_guest_player()
        player_id = guest["id"]

        with mock.patch("src.api.routes.solo.get_current_paris_date", return_value=self.test_date):
            manager1 = GameManager(self.store, persist=True)
            res_new, status = handle_solo_post(
                manager1,
                path="/api/game/new",
                data={"mode": "daily", "player_id": player_id},
            )
            self.assertEqual(status, 200)
            game_id = res_new["game_id"]

            # Débloquer indice #1 (mot)
            h1_res, s1 = handle_solo_post(
                manager1,
                path="/api/game/hint",
                data={"game_id": game_id, "type": "word", "level": 1, "player_id": player_id},
            )
            self.assertEqual(s1, 200)
            self.assertEqual(h1_res.get("hints_remaining"), 2)

            # Débloquer indice #2 (phrase)
            h2_res, s2 = handle_solo_post(
                manager1,
                path="/api/game/hint",
                data={"game_id": game_id, "type": "phrase", "level": 2, "player_id": player_id},
            )
            self.assertEqual(s2, 200)
            self.assertEqual(h2_res.get("hints_remaining"), 1)

            # SIMULATION D'UN REDÉMARRAGE DU CONTENEUR DOCKER
            # Un nouveau GameManager vierge est instancié avec son propre dictionnaire en mémoire
            manager2 = GameManager(self.store, persist=True)

            # Le client envoie une requête de reprise (resume) ou new_game avec son player_id
            res_resume, s_resume = handle_solo_post(
                manager2,
                path="/api/game/resume",
                data={"game_id": game_id, "mode": "daily", "player_id": player_id},
            )
            self.assertEqual(s_resume, 200)
            # Les indices débloqués doivent être 100% restaurés depuis la BDD
            self.assertEqual(len(res_resume.get("hints_revealed", [])), 2)
            levels = [h["level"] for h in res_resume["hints_revealed"]]
            self.assertIn(1, levels)
            self.assertIn(2, levels)

            # Une nouvelle demande d'indice continue au palier #3
            h3_res, s3 = handle_solo_post(
                manager2,
                path="/api/game/hint",
                data={"game_id": game_id, "type": "word", "level": 3, "player_id": player_id},
            )
            self.assertEqual(s3, 200)
            self.assertEqual(h3_res.get("hints_remaining"), 0)

    @mock.patch("src.services.solo_daily.GeminiClient.is_configured", return_value=False)
    def test_purge_strictly_preserves_today_and_future_dates(self, mock_gemini):
        """Vérifie que la purge quotidienne respecte strictement : uniquement < aujourd'hui, jamais la journée en cours."""
        from src.services.solo_daily import (
            maybe_purge_old_daily_data,
            ensure_solo_daily_puzzle,
        )
        from src.db.solo import save_solo_ai_hints, get_solo_ai_hints

        yesterday = "2095-12-31"
        today = "2096-01-01"
        tomorrow = "2096-01-02"

        # Création des puzzles
        ensure_solo_daily_puzzle(self.store, puzzle_date=yesterday)
        ensure_solo_daily_puzzle(self.store, puzzle_date=today)
        ensure_solo_daily_puzzle(self.store, puzzle_date=tomorrow)

        # Insertion d'indices fictifs
        hints = [
            {"hint_level": 1, "weight": 0.33, "hint_word": "alpha", "hint_phrase": "p1", "score": 20.0, "permille": 700},
            {"hint_level": 2, "weight": 0.66, "hint_word": "beta", "hint_phrase": "p2", "score": 30.0, "permille": 825},
            {"hint_level": 3, "weight": 1.00, "hint_word": "gamma", "hint_phrase": "p3", "score": 40.0, "permille": 950},
        ]
        save_solo_ai_hints(yesterday, hints)
        save_solo_ai_hints(today, hints)
        save_solo_ai_hints(tomorrow, hints)

        # Exécution de la purge pour 'today'
        maybe_purge_old_daily_data(today)

        # Hier (< today) doit être purgé
        self.assertEqual(len(get_solo_ai_hints(yesterday)), 0)
        # Aujourd'hui et Demain doivent être STRICTEMENT PRÉSERVÉS
        self.assertEqual(len(get_solo_ai_hints(today)), 3)
        self.assertEqual(len(get_solo_ai_hints(tomorrow)), 3)


if __name__ == "__main__":
    unittest.main()
