"""
Cémantix Solver — Tests Automatisés de l'Espace « Mon compte » (Jalon M16)
========================================================================
Valide l'ensemble des composants de gestion du compte :
- Schéma relationnel idempotent (player_recovery_words, colonnes de sécurité)
- DAO et sécurité (hachage PBKDF2, changement de mot de passe, génération aléatoire)
- Endpoints REST (/api/account/profile, password, recovery, stats, logout)
- Agrégation des statistiques de jeu personnelles
"""
import json
import unittest
import uuid
from datetime import datetime, timezone

import _context  # noqa: F401 — isole la suite de l'environnement d'exécution

from src.api.routes.account import handle_account_get, handle_account_post
from src.db.account import (
    change_account_password,
    generate_system_recovery_words,
    get_account_profile,
    get_account_stats,
    get_recovery_status,
    regenerate_recovery_words,
    save_player_recovery_words,
    touch_last_login,
    verify_recovery_words,
)
from src.db.connection import db, init_db
from src.db.players import claim_player_account, create_guest_player, get_player_by_id
from src.services.player_auth import hash_password, verify_password


class TestAccountDatabaseSchema(unittest.TestCase):
    """Vérification du schéma relationnel et de l'idempotence (ACC-01)."""

    def setUp(self):
        init_db()

    def test_idempotence_schema(self):
        """L'initialisation de la base peut être rejouée 5 fois sans erreur."""
        for _ in range(5):
            db.init_db()

    def test_table_player_recovery_words_exists(self):
        """Vérifie l'existence et l'accès à la table player_recovery_words."""
        row = db.fetch_one("SELECT COUNT(*) as cnt FROM player_recovery_words")
        self.assertIsNotNone(row)
        self.assertGreaterEqual(row["cnt"], 0)

    def test_colonnes_securite_sur_players(self):
        """Vérifie la présence des colonnes password_updated_at et last_login_at."""
        p = create_guest_player()
        player_id = p["id"]
        row = db.fetch_one(
            "SELECT password_updated_at, last_login_at FROM players WHERE id = %s",
            (player_id,),
        )
        self.assertIsNotNone(row)
        self.assertIn("password_updated_at", row)
        self.assertIn("last_login_at", row)


class TestAccountDAOSecurity(unittest.TestCase):
    """Vérification des fonctions métier de sécurité et persistance (ACC-02)."""

    def setUp(self):
        init_db()
        self.guest = create_guest_player()
        self.player_id = self.guest["id"]
        self.token = self.guest["auth_token"]

    def test_get_account_profile(self):
        """Récupère fidèlement les informations d'un profil invité puis revendiqué."""
        profile = get_account_profile(self.player_id)
        self.assertIsNotNone(profile)
        self.assertEqual(profile["id"], self.player_id)
        self.assertFalse(profile["isClaimed"])
        self.assertIsNone(profile["passwordUpdatedAt"])

        # Revendication du compte
        pwd_hash = hash_password("MonSecret2026!")
        claim_player_account(self.player_id, pwd_hash, "rec-hash")

        updated = get_account_profile(self.player_id)
        self.assertTrue(updated["isClaimed"])

    def test_touch_last_login(self):
        """Met à jour l'horodatage de dernière connexion."""
        touch_last_login(self.player_id)
        profile = get_account_profile(self.player_id)
        self.assertIsNotNone(profile["lastLoginAt"])

    def test_change_account_password_validation(self):
        """Valide les règles de modification du mot de passe."""
        # Échec sur profil invité non protégé
        ok, msg = change_account_password(self.player_id, "vieux", "nouveau123")
        self.assertFalse(ok)
        self.assertIn("pas encore été revendiqué", msg)

        # Protection du compte
        claim_player_account(self.player_id, hash_password("AncienPass123!"), "rec-key")

        # Échec : mot de passe actuel erroné
        ok, msg = change_account_password(self.player_id, "MauvaisPass123!", "NouveauPass123!")
        self.assertFalse(ok)
        self.assertIn("actuel est incorrect", msg)

        # Échec : nouveau mot de passe trop court (< 8 car.)
        ok, msg = change_account_password(self.player_id, "AncienPass123!", "court")
        self.assertFalse(ok)
        self.assertIn("au moins 8 caractères", msg)

        # Succès : modification valide
        ok, msg = change_account_password(self.player_id, "AncienPass123!", "NouveauPassValide123!")
        self.assertTrue(ok)

        # Vérification en base
        p = get_player_by_id(self.player_id)
        self.assertTrue(verify_password("NouveauPassValide123!", p["password_hash"]))
        self.assertIsNotNone(p["password_updated_at"])

    def test_generation_et_sauvegarde_mots_recuperation(self):
        """Génération de 4 mots uniques et hachage en base."""
        words = generate_system_recovery_words(count=4)
        self.assertEqual(len(words), 4)
        self.assertEqual(len(set(words)), 4)  # Mots tous uniques

        ok = save_player_recovery_words(self.player_id, words)
        self.assertTrue(ok)

        status = get_recovery_status(self.player_id)
        self.assertTrue(status["configured"])
        self.assertEqual(status["count"], 4)
        self.assertIsNotNone(status["createdAt"])

        # Vérification de correspondance cryptographique
        self.assertTrue(verify_recovery_words(self.player_id, words))
        # Échec si un mot est erroné
        wrong_words = [words[0], words[1], words[2], "mot-bidon"]
        self.assertFalse(verify_recovery_words(self.player_id, wrong_words))

    def test_regeneration_atomique_purge_anciens_mots(self):
        """La régénération invalide et remplace atomiquement l'ancien lot."""
        claim_player_account(self.player_id, hash_password("MonSecret2026!"), "rec-key")

        ok1, msg1, lot1 = regenerate_recovery_words(self.player_id, count=4)
        self.assertTrue(ok1)
        self.assertEqual(len(lot1), 4)
        self.assertTrue(verify_recovery_words(self.player_id, lot1))

        # Deuxième régénération
        ok2, msg2, lot2 = regenerate_recovery_words(self.player_id, count=4)
        self.assertTrue(ok2)
        self.assertTrue(verify_recovery_words(self.player_id, lot2))

        # Le premier lot n'est plus valide (purgé)
        if lot1 != lot2:
            self.assertFalse(verify_recovery_words(self.player_id, lot1))

    def test_statistiques_compte(self):
        """Agrégation des statistiques de jeu personnelles."""
        stats = get_account_stats(self.player_id)
        self.assertEqual(stats["totalGames"], 0)
        self.assertEqual(stats["victories"], 0)
        self.assertEqual(stats["winRate"], 0.0)

        # Insertion d'une partie solo gagnée et d'une partie abandonnée
        game_id1 = str(uuid.uuid4())
        game_id2 = str(uuid.uuid4())
        date1 = "2026-11-10"
        date2 = "2026-11-11"

        db.execute(
            "INSERT INTO solo_daily_puzzles (puzzle_date, secret_word, difficulty) VALUES (%s, %s, %s)",
            (date1, "pomme", "normal"),
        )
        db.execute(
            "INSERT INTO solo_daily_puzzles (puzzle_date, secret_word, difficulty) VALUES (%s, %s, %s)",
            (date2, "orange", "normal"),
        )
        db.execute(
            """INSERT INTO solo_player_games 
               (id, puzzle_date, player_id, status, tries_count, hints_used, best_score, duration_seconds)
               VALUES (%s, %s, %s, 'won', 12, 1, 100.0, 45.0)""",
            (game_id1, date1, self.player_id),
        )
        db.execute(
            """INSERT INTO solo_player_games 
               (id, puzzle_date, player_id, status, tries_count, hints_used, best_score, duration_seconds)
               VALUES (%s, %s, %s, 'given_up', 24, 2, 42.0, 120.0)""",
            (game_id2, date2, self.player_id),
        )

        updated_stats = get_account_stats(self.player_id)
        self.assertEqual(updated_stats["totalGames"], 2)
        self.assertEqual(updated_stats["victories"], 1)
        self.assertEqual(updated_stats["winRate"], 50.0)
        self.assertEqual(updated_stats["avgGuesses"], 12.0)
        self.assertEqual(updated_stats["bestScore"], 100.0)
        self.assertEqual(updated_stats["avgTimeSeconds"], 45.0)
        self.assertEqual(updated_stats["hintsUsed"], 3)


class TestAccountAPIRoutes(unittest.TestCase):
    """Vérification des routes REST /api/account/* (ACC-03)."""

    def setUp(self):
        init_db()
        self.guest = create_guest_player()
        self.player_id = self.guest["id"]
        self.token = self.guest["auth_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_routes_require_authentication(self):
        """Les endpoints protégés renvoient 401 si le token est absent ou erroné."""
        res, status = handle_account_get("/api/account/profile", headers={})
        self.assertEqual(status, 401)

        res, status = handle_account_get(
            "/api/account/profile", headers={"Authorization": "Bearer token-invalide"}
        )
        self.assertEqual(status, 401)

        res, status = handle_account_post("/api/account/password", {}, headers={})
        self.assertEqual(status, 401)

    def test_get_profile_success(self):
        """GET /api/account/profile renvoie les données complètes du profil."""
        res, status = handle_account_get("/api/account/profile", headers=self.headers)
        self.assertEqual(status, 200)
        self.assertEqual(res["id"], self.player_id)
        self.assertIn("username", res)
        self.assertIn("isClaimed", res)

    def test_post_password_lifecycle(self):
        """POST /api/account/password teste échecs et succès de modification."""
        # 1. Échec : champs manquants
        res, status = handle_account_post("/api/account/password", {}, headers=self.headers)
        self.assertEqual(status, 400)

        # 2. Protection préalable du compte
        claim_player_account(self.player_id, hash_password("SecretInitial1!"), "rec-key")

        # 3. Échec : mot de passe actuel faux
        res, status = handle_account_post(
            "/api/account/password",
            {"currentPassword": "FauxMotDePasse", "newPassword": "NouveauSecretValide1!"},
            headers=self.headers,
        )
        self.assertEqual(status, 401)

        # 4. Succès : mise à jour correcte
        res, status = handle_account_post(
            "/api/account/password",
            {"currentPassword": "SecretInitial1!", "newPassword": "NouveauSecretValide1!"},
            headers=self.headers,
        )
        self.assertEqual(status, 200)
        self.assertTrue(res["success"])

    def test_recovery_words_routes(self):
        """GET & POST /api/account/recovery pour consultation et régénération."""
        # 1. Avant configuration
        res, status = handle_account_get("/api/account/recovery", headers=self.headers)
        self.assertEqual(status, 200)
        self.assertFalse(res["configured"])
        self.assertEqual(res["count"], 0)

        # 2. Échec de régénération sur profil non protégé
        res, status = handle_account_post("/api/account/recovery", {}, headers=self.headers)
        self.assertEqual(status, 403)

        # 3. Protection du compte
        claim_player_account(self.player_id, hash_password("MotDePasseTest1!"), "rec-key")

        # 4. Régénération réussie
        res, status = handle_account_post(
            "/api/account/recovery", {"count": 4}, headers=self.headers
        )
        self.assertEqual(status, 200)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["recoveryWords"]), 4)

        # 5. Consultation de l'état mis à jour
        res, status = handle_account_get("/api/account/recovery", headers=self.headers)
        self.assertEqual(status, 200)
        self.assertTrue(res["configured"])
        self.assertEqual(res["count"], 4)

    def test_get_stats_route(self):
        """GET /api/account/stats retourne les statistiques de jeu."""
        res, status = handle_account_get("/api/account/stats", headers=self.headers)
        self.assertEqual(status, 200)
        self.assertIn("totalGames", res)
        self.assertIn("victories", res)
        self.assertIn("winRate", res)

    def test_post_logout_route(self):
        """POST /api/account/logout est idempotent et confirme la déconnexion."""
        res, status = handle_account_post("/api/account/logout", {}, headers=self.headers)
        self.assertEqual(status, 200)
        self.assertTrue(res["success"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
