"""
Tests unitaires pour l'authentification des joueurs sans email (M14).
Couvre le schéma idempotent, le DAO, le service métier, les routes REST et l'admin.
"""
import os
import tempfile
import unittest
from pathlib import Path

import _context  # noqa: F401

from src.db.connection import db
from src.db.players import (
    add_dictionary_word,
    admin_create_player,
    admin_update_player,
    claim_player_account,
    count_players,
    create_guest_player,
    delete_dictionary_word,
    delete_player_account,
    get_active_dictionary,
    get_dictionary_words,
    get_player_by_id,
    get_player_by_token,
    get_player_by_username,
    get_players_stats,
    list_players,
    seed_default_dictionary_if_empty,
    toggle_dictionary_word,
    update_player_password,
    update_player_username,
)
from src.services.player_auth import (
    claim_account,
    delete_player,
    generate_auth_token,
    generate_random_username,
    generate_recovery_phrase,
    hash_password,
    hash_recovery_phrase,
    init_or_get_guest,
    invalidate_dictionary_cache,
    login_player,
    normalize_recovery_phrase,
    rename_player,
    reset_password_with_recovery,
    validate_username,
    verify_password,
    verify_recovery_phrase,
)
from src.api.routes.player import handle_player_post
from src.api.routes.admin import (
    ADMIN_BASE_PATH,
    handle_admin_delete,
    handle_admin_get,
    handle_admin_post,
)


class TestPlayerAuth(unittest.TestCase):
    def setUp(self):
        # Isolation complète sur base SQLite temporaire
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.sqlite_file = Path(self.tmp_dir.name) / "test_player_auth.sqlite3"
        self.old_sqlite_path = os.environ.get("SQLITE_PATH")
        os.environ["SQLITE_PATH"] = str(self.sqlite_file)

        self.old_db_host = os.environ.get("DB_HOST")
        self.old_db_name = os.environ.get("DB_NAME")
        if "DB_HOST" in os.environ:
            del os.environ["DB_HOST"]
        if "DB_NAME" in os.environ:
            del os.environ["DB_NAME"]

        db.reset()
        db.init_db()
        invalidate_dictionary_cache()

    def tearDown(self):
        db.reset()
        self.tmp_dir.cleanup()
        if self.old_sqlite_path:
            os.environ["SQLITE_PATH"] = self.old_sqlite_path
        else:
            os.environ.pop("SQLITE_PATH", None)
        if self.old_db_host:
            os.environ["DB_HOST"] = self.old_db_host
        if self.old_db_name:
            os.environ["DB_NAME"] = self.old_db_name

    # --- 1. Schéma SQL & Idempotence -----------------------------------------
    def test_schema_idempotence(self):
        """Vérifie que init_db et le seeding peuvent être réexécutés sans erreur."""
        for _ in range(5):
            db.init_db()
            seed_default_dictionary_if_empty()

        # Le dictionnaire doit être bien alimenté
        nouns = get_active_dictionary("noun")
        adjectives = get_active_dictionary("adjective")
        recovery = get_active_dictionary("recovery")

        self.assertGreaterEqual(len(nouns), 40)
        self.assertGreaterEqual(len(adjectives), 40)
        self.assertGreaterEqual(len(recovery), 250)

    # --- 2. Générateur de Pseudos Loufoques [Nom][Adjectif] -------------------
    def test_generate_random_username(self):
        """Vérifie la syntaxe CamelCase, la longueur 8-24 et l'ordre Nom-Adjectif."""
        for _ in range(25):
            name = generate_random_username()
            self.assertGreaterEqual(len(name), 8)
            self.assertLessEqual(len(name), 24)
            # Pas d'espace ni de ponctuation interdite
            self.assertTrue(name.isalnum())
            # Au moins 2 majuscules (CamelCase de [Nom][Adjectif])
            capitals = [c for c in name if c.isupper()]
            self.assertGreaterEqual(len(capitals), 2)

    # --- 3. Phrases de Secours & Normalisation --------------------------------
    def test_generate_and_normalize_recovery_phrase(self):
        """Vérifie la génération de 4 mots et leur normalisation insensible."""
        phrase = generate_recovery_phrase(num_words=4)
        words = phrase.split()
        self.assertEqual(len(words), 4)

        # Normalisation
        norm1 = normalize_recovery_phrase("  citron   falaise  navire   vortex  ")
        norm2 = normalize_recovery_phrase("Citron - Falaise - Navire - Vortex")
        norm3 = normalize_recovery_phrase("cîtron-falaïse-navire-vortex")

        self.assertEqual(norm1, "citron-falaise-navire-vortex")
        self.assertEqual(norm2, "citron-falaise-navire-vortex")
        self.assertEqual(norm3, "citron-falaise-navire-vortex")

    # --- 4. Hachage Cryptographique PBKDF2 ------------------------------------
    def test_pbkdf2_hashing_and_verification(self):
        """Vérifie la sécurité et l'unicité du sel du hachage PBKDF2."""
        pwd = "MonSuperMotDePasse123!"
        hash1 = hash_password(pwd)
        hash2 = hash_password(pwd)

        # Deux condensats du même mot de passe doivent différer (sels différents)
        self.assertNotEqual(hash1, hash2)
        self.assertTrue(hash1.startswith("pbkdf2:sha256:200000:"))

        # Vérification valide et invalide
        self.assertTrue(verify_password(pwd, hash1))
        self.assertTrue(verify_password(pwd, hash2))
        self.assertFalse(verify_password("MauvaisPasse", hash1))
        self.assertFalse(verify_password("", hash1))

        # Phrase de récupération
        rec_phrase = "citron falaise navire vortex"
        rec_hash = hash_recovery_phrase(rec_phrase)
        self.assertTrue(verify_recovery_phrase("Citron-Falaise-Navire-Vortex", rec_hash))
        self.assertFalse(verify_recovery_phrase("citron falaise volcan vortex", rec_hash))

    # --- 5. Validation des Pseudos --------------------------------------------
    def test_validate_username(self):
        """Vérifie les critères de validation des pseudos (8-24 car, anti-abus)."""
        # Trop court
        ok, msg = validate_username("Court")
        self.assertFalse(ok)
        self.assertIn("entre 8 et 24", msg)

        # Trop long
        ok, msg = validate_username("UnPseudoVraimentBeaucoupTropLongPourLeJeu")
        self.assertFalse(ok)

        # Caractères invalides
        ok, msg = validate_username("Pseudo<script>")
        self.assertFalse(ok)

        # Mots réservés
        ok, msg = validate_username("administrator")
        self.assertFalse(ok)
        self.assertIn("terme réservé", msg)

        # Termes abusifs
        ok, msg = validate_username("salope_1234")
        self.assertFalse(ok)

        # Termes réservés pour habitués bots
        ok, msg = validate_username("CastorCosmique")
        self.assertFalse(ok)
        self.assertIn("terme réservé", msg)

        # Valides
        ok, msg = validate_username("ExplorateurVeloce")
        self.assertTrue(ok)
        ok, msg = validate_username("Loup-Solitaire_42")
        self.assertTrue(ok)

    # --- 6. Scénario Complet du Cycle de Vie Joueur ---------------------------
    def test_full_player_lifecycle(self):
        """Scénario complet : invité -> renommage -> claim -> login -> reset -> suppression."""
        # 1. Visite invité
        guest = init_or_get_guest()
        player_id = guest["player_id"]
        auth_token = guest["auth_token"]
        initial_name = guest["username"]

        self.assertTrue(guest["can_change_username"])
        self.assertFalse(guest["is_claimed"])

        # Re-visite avec token existant
        same_guest = init_or_get_guest(player_id=player_id, auth_token=auth_token)
        self.assertEqual(same_guest["username"], initial_name)

        # 2. Renommage unique réussi
        new_name = "SuperPangolin99"
        ok, msg, updated = rename_player(auth_token, new_name)
        self.assertTrue(ok)
        self.assertEqual(updated["username"], new_name)
        self.assertFalse(updated["can_change_username"])

        # 3. Tentative de second renommage (rejetée)
        ok2, msg2, _ = rename_player(auth_token, "AutrePseudo2026")
        self.assertFalse(ok2)
        self.assertIn("déjà personnalisé", msg2)

        # 4. Conflit de pseudo avec un second joueur
        guest2 = init_or_get_guest()
        ok_conflict, msg_conflict, _ = rename_player(guest2["auth_token"], new_name)
        self.assertFalse(ok_conflict)
        self.assertIn("déjà utilisé", msg_conflict)

        # 5. Protection du compte (claim)
        pwd = "PasswordSecret88!"
        ok_claim, msg_claim, phrase = claim_account(auth_token, pwd)
        self.assertTrue(ok_claim)
        self.assertEqual(len(phrase.split()), 4)

        # 6. Connexion sur un nouvel appareil
        ok_login, msg_login, session_login = login_player(new_name, pwd)
        self.assertTrue(ok_login)
        self.assertEqual(session_login["player_id"], player_id)
        self.assertTrue(session_login["is_claimed"])

        # Échec mauvais mot de passe
        ok_bad, _, _ = login_player(new_name, "MauvaisPasse99")
        self.assertFalse(ok_bad)

        # 7. Réinitialisation du mot de passe avec la phrase de 4 mots
        new_pwd = "NouveauMotDePasse2026!"
        ok_reset, msg_reset, new_token = reset_password_with_recovery(new_name, phrase, new_pwd)
        self.assertTrue(ok_reset)
        self.assertTrue(bool(new_token))

        # Connexion avec le nouveau mot de passe
        ok_new_login, _, _ = login_player(new_name, new_pwd)
        self.assertTrue(ok_new_login)

        # Échec avec mauvaise phrase
        ok_bad_reset, _, _ = reset_password_with_recovery(new_name, "mot1 mot2 faux mot4", "EncoreUnPasse123")
        self.assertFalse(ok_bad_reset)

        # 8. Droit à l'effacement RGPD
        ok_del, _ = delete_player(new_token)
        self.assertTrue(ok_del)
        self.assertIsNone(get_player_by_id(player_id))

    # --- 7. Endpoints API REST HTTP (/api/player/*) ---------------------------
    def test_api_player_routes(self):
        """Vérifie le comportement et les codes de retour des endpoints /api/player/*."""
        # POST /api/player/guest
        res, status = handle_player_post("/api/player/guest", {})
        self.assertEqual(status, 200)
        token = res["auth_token"]
        self.assertTrue(token)

        # POST /api/player/rename
        headers = {"Authorization": f"Bearer {token}"}
        res_rename, status = handle_player_post("/api/player/rename", {"new_username": "CastorSolaire99"}, headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(res_rename["username"], "CastorSolaire99")

        # Second rename -> 400
        res_rename2, status = handle_player_post("/api/player/rename", {"new_username": "AutreTentative"}, headers=headers)
        self.assertEqual(status, 400)

        # POST /api/player/claim
        res_claim, status = handle_player_post("/api/player/claim", {"password": "MonPasswordSecurise1!"}, headers=headers)
        self.assertEqual(status, 200)
        self.assertTrue(res_claim["is_claimed"])
        recovery_phrase = res_claim["recovery_phrase"]

        # POST /api/player/login
        res_login, status = handle_player_post("/api/player/login", {
            "username": "CastorSolaire99",
            "password": "MonPasswordSecurise1!",
        })
        self.assertEqual(status, 200)
        self.assertEqual(res_login["username"], "CastorSolaire99")

        # POST /api/player/reset-password
        res_reset, status = handle_player_post("/api/player/reset-password", {
            "username": "CastorSolaire99",
            "recovery_phrase": recovery_phrase,
            "new_password": "MonNouveauPassword2026!",
        })
        self.assertEqual(status, 200)
        self.assertTrue(res_reset["success"])
        new_token = res_reset["auth_token"]

        # POST /api/player/delete-account avec le nouveau token issu du reset
        new_headers = {"Authorization": f"Bearer {new_token}"}
        res_del, status = handle_player_post("/api/player/delete-account", {}, headers=new_headers)
        self.assertEqual(status, 200)

    # --- 8. Endpoints Admin Dictionnaire (/api/snap-9x/dictionary) ------------
    def test_api_admin_dictionary(self):
        """Vérifie l'administration protégée des listes de vocabulaire."""
        os.environ["ADMIN_PASSWORD"] = "secret_admin_test_123"
        # Obtention du token admin
        auth_res, _ = handle_admin_post(None, f"{ADMIN_BASE_PATH}/auth", {"password": "secret_admin_test_123"}, {}, "127.0.0.1")
        admin_token = auth_res["token"]
        headers = {"X-Admin-Token": admin_token}

        # GET /dictionary
        dict_payload = {}
        def mock_send_json(data, status=200):
            dict_payload.update(data)

        handle_admin_get(None, f"{ADMIN_BASE_PATH}/dictionary", "", headers, send_json=mock_send_json, send_sse=None, client_ip="127.0.0.1")
        self.assertIn("nouns", dict_payload)
        self.assertIn("adjectives", dict_payload)
        self.assertIn("recovery", dict_payload)

        # POST /dictionary (ajout d'un mot)
        add_res, status = handle_admin_post(
            None,
            f"{ADMIN_BASE_PATH}/dictionary",
            {"word_type": "noun", "word": "Licorne"},
            headers,
            "127.0.0.1",
        )
        self.assertEqual(status, 200)
        word_id = add_res["id"]
        self.assertGreater(word_id, 0)

        # DELETE /dictionary/<id>
        del_res, status = handle_admin_delete(
            None,
            f"{ADMIN_BASE_PATH}/dictionary/{word_id}",
            headers,
            "127.0.0.1",
        )
        self.assertEqual(status, 200)
        self.assertTrue(del_res["success"])

    # --- 9. Gestion Admin des Utilisateurs en BDD (/api/snap-9x/users) --------
    def test_api_admin_users_management(self):
        """Vérifie le cycle complet d'administration des joueurs en BDD."""
        os.environ["ADMIN_PASSWORD"] = "secret_admin_test_123"
        auth_res, _ = handle_admin_post(None, f"{ADMIN_BASE_PATH}/auth", {"password": "secret_admin_test_123"}, {}, "127.0.0.1")
        headers = {"X-Admin-Token": auth_res["token"]}

        # 1. Création de joueurs de test via DAO et via admin API
        p1 = admin_create_player("TestUserAlpha", is_claimed=True)
        p2 = create_guest_player("11111111-2222-3333-4444-555555555555", "token123", "ExplorateurCosmique")

        # Création via POST /users
        create_res, status = handle_admin_post(
            None,
            f"{ADMIN_BASE_PATH}/users",
            {"username": "AdminCreatedUser", "is_claimed": True, "password": "Password123!"},
            headers,
            "127.0.0.1",
        )
        self.assertEqual(status, 201)
        self.assertTrue(create_res["success"])
        p3_id = create_res["user"]["id"]
        self.assertEqual(create_res["user"]["username"], "AdminCreatedUser")

        # 2. GET /users (liste complète & stats)
        captured = {}
        def mock_send_users(data, status=200):
            captured.update(data=data, status=status)

        handle_admin_get(None, f"{ADMIN_BASE_PATH}/users", "limit=10&offset=0", headers, send_json=mock_send_users, send_sse=None, client_ip="127.0.0.1")
        self.assertEqual(captured["status"], 200)
        users = captured["data"]["users"]
        self.assertGreaterEqual(len(users), 3)
        self.assertGreaterEqual(captured["data"]["total"], 3)
        stats = captured["data"]["stats"]
        self.assertGreaterEqual(stats["total"], 3)
        self.assertGreaterEqual(stats["claimed"], 2)
        self.assertGreaterEqual(stats["guests"], 1)

        # 3. GET /users avec filtre recherche
        captured.clear()
        handle_admin_get(None, f"{ADMIN_BASE_PATH}/users", "search=Alpha", headers, send_json=mock_send_users, send_sse=None, client_ip="127.0.0.1")
        self.assertEqual(len(captured["data"]["users"]), 1)
        self.assertEqual(captured["data"]["users"][0]["username"], "TestUserAlpha")

        # 4. GET /users/<id>
        captured.clear()
        handle_admin_get(None, f"{ADMIN_BASE_PATH}/users/{p1['id']}", "", headers, send_json=mock_send_users, send_sse=None, client_ip="127.0.0.1")
        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["data"]["user"]["username"], "TestUserAlpha")
        self.assertNotIn("password_hash", captured["data"]["user"])

        # 5. POST /users/<id> (Mise à jour : modification pseudo et réinitialisation du renommage)
        up_res, status = handle_admin_post(
            None,
            f"{ADMIN_BASE_PATH}/users/{p2['id']}",
            {"username": "CastorRenomme", "can_change_username": True},
            headers,
            "127.0.0.1",
        )
        self.assertEqual(status, 200)
        self.assertTrue(up_res["success"])
        self.assertEqual(up_res["user"]["username"], "CastorRenomme")
        self.assertTrue(up_res["user"]["can_change_username"])

        # 6. DELETE /users/<id>
        del_res, status = handle_admin_delete(
            None,
            f"{ADMIN_BASE_PATH}/users/{p3_id}",
            headers,
            "127.0.0.1",
        )
        self.assertEqual(status, 200)
        self.assertTrue(del_res["success"])
        self.assertIsNone(get_player_by_id(p3_id))


if __name__ == "__main__":
    unittest.main()

