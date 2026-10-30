"""Tests de l'évolution « Défier le bot » (2026-10-06-defier-le-bot, QUAL-20).

Lancement :  python -m unittest discover -s tests -v

Aucune dépendance extérieure : repli SQLite (via `_context`) et faux magasins
vectoriels ; la résolution bout-en-bout est testée avec un moteur simulé, le
vrai solveur RAG étant validé hors CI par la recette docker (QUAL-22).
"""
import os
import threading
import types
import unittest
from unittest import mock

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.db import challenges as dao  # noqa: E402
from src.db.connection import db  # noqa: E402


def _clean():
    db.execute("DELETE FROM bot_challenges;")
    db.execute("DELETE FROM bot_challenge_whitelist;")


class TestValidationMot(unittest.TestCase):
    """DEFI-08 : regex + lexique, message unique, pas d'oracle."""

    class _Store:
        WORDS = {"chaussette", "volcan", "amour"}

        def normalize(self, word):
            return word

        def is_valid_french(self, word):
            return word in self.WORDS

    def setUp(self):
        from src.api.routes.challenge import validate_word
        self.validate = validate_word
        self.store = self._Store()

    def test_mot_valide_accepte(self):
        self.assertEqual(self.validate("Chaussette", self.store), "chaussette")

    def test_script_refuse(self):
        self.assertIsNone(self.validate("<script>", self.store))

    def test_trop_court_refuse(self):
        self.assertIsNone(self.validate("A", self.store))

    def test_mot_inconnu_refuse(self):
        self.assertIsNone(self.validate("zzztopinconnu", self.store))

    def test_25_caracteres_refuse(self):
        self.assertIsNone(self.validate("a" * 25, self.store))

    def test_non_texte_refuse(self):
        self.assertIsNone(self.validate(42, self.store))
        self.assertIsNone(self.validate(None, self.store))


class TestQuotaEtRoutes(unittest.TestCase):
    """DEFI-04/05/07, SEC-20/24 : quota base persisté, anti-rafale, file bornée."""

    class _Store:
        WORDS = {"chaussette", "volcan", "amour"}

        def normalize(self, word):
            return word

        def is_valid_french(self, word):
            return word in self.WORDS

    class _Manager:
        def __init__(self, store):
            self.store = store

    def setUp(self):
        _clean()
        from src.api.routes import challenge as routes
        self.routes = routes
        self.mgr = self._Manager(self._Store())
        self.routes._challenge_limiter._buckets.clear()
        self._saved_queue = dao.CHALLENGE_MAX_QUEUE
        dao.CHALLENGE_MAX_QUEUE = 1000  # la file bornée a son propre test

    def tearDown(self):
        dao.CHALLENGE_MAX_QUEUE = self._saved_queue
        self.routes._challenge_limiter._buckets.clear()

    def _post(self, word, ip="8.8.8.8", anon="8.8.8.0"):
        self.routes._challenge_limiter._buckets.clear()  # isole le quota BASE
        return self.routes.handle_challenge_post(self.mgr, "/api/challenge",
                                                 {"word": word}, ip, anon)

    def test_dix_puis_quarante_deux(self):
        for i in range(10):
            payload, status = self._post("volcan")
            self.assertEqual(status, 201, payload)
            self.assertEqual(payload["quota_restant"], 9 - i)
        payload, status = self._post("volcan")
        self.assertEqual(status, 429)
        self.assertIn("retry_after", payload)

    def test_quota_survit_au_rechargement_memoire(self):
        for _ in range(10):
            self._post("volcan")
        # Un nouveau « processus » web (mémoire vide) doit quand même refuser :
        # le quota est lu en base, pas en mémoire.
        payload, status = self._post("volcan")
        self.assertEqual(status, 429)

    def test_antirafale_memoire(self):
        statuses = [
            self.routes.handle_challenge_post(self.mgr, "/api/challenge",
                                              {"word": "amour"}, "7.7.7.7", "7.7.7.0")[1]
            for _ in range(8)
        ]
        self.assertEqual(statuses.count(201), 6)
        self.assertEqual(statuses.count(429), 2)

    def test_file_bornee(self):
        dao.CHALLENGE_MAX_QUEUE = 1
        # File vide : accepté, la file passe à 1.
        self.assertEqual(self._post("volcan", "6.6.6.6", "6.6.6.0")[1], 201)
        # File pleine (1 >= 1) : le suivant est refusé, même sous une autre IP.
        payload, status = self._post("volcan", "5.5.5.5", "5.5.5.0")
        self.assertEqual(status, 429)
        self.assertIn("occupé", payload["error"])

    def test_get_borne_sans_spoiler(self):
        payload, status = self._post("amour")
        cid = payload["id"]
        view, status = self.routes.handle_challenge_get(self.mgr, f"/api/challenge/{cid}")
        self.assertEqual(status, 200)
        self.assertEqual(view["status"], "queued")
        self.assertNotIn("word", view)  # SEC-26 : jamais le mot avant le terminal

    def test_get_id_inconnu_404(self):
        _payload, status = self.routes.handle_challenge_get(self.mgr, "/api/challenge/" + "0" * 32)
        self.assertEqual(status, 404)
        _payload, status = self.routes.handle_challenge_get(self.mgr, "/api/challenge/pas-un-id")
        self.assertEqual(status, 404)


class TestWhitelist(unittest.TestCase):
    """DEFI-18 / SEC-20 : exemption totale + administration."""

    def setUp(self):
        _clean()

    def test_add_list_remove(self):
        dao.add_whitelist_ip("12.34.56.78", "Bureau Cyril")
        self.assertTrue(dao.is_ip_whitelisted("12.34.56.78"))
        entries = dao.get_whitelist()
        self.assertEqual(entries[0]["ip_address"], "12.34.56.78")
        self.assertEqual(entries[0]["description"], "Bureau Cyril")
        self.assertTrue(dao.remove_whitelist_ip("12.34.56.78"))
        self.assertFalse(dao.is_ip_whitelisted("12.34.56.78"))
        self.assertFalse(dao.remove_whitelist_ip("1.2.3.4"))

    def test_ip_whitelistee_sans_quota(self):
        from src.api.routes import challenge as routes

        class Store:
            WORDS = {"amour"}

            def normalize(self, w):
                return w

            def is_valid_french(self, w):
                return w in self.WORDS

        class Mgr:
            store = Store()

        dao.add_whitelist_ip("9.9.9.9", "test")
        for _ in range(12):
            payload, status = routes.handle_challenge_post(
                Mgr(), "/api/challenge", {"word": "amour"}, "9.9.9.9", "9.9.9.0")
            self.assertEqual(status, 201, payload)
            self.assertEqual(payload["quota_restant"], "unlimited")

    def test_admin_gere_la_whitelist(self):
        os.environ["ADMIN_PASSWORD"] = "test-whitelist"
        from src.api.routes import admin
        admin._sessions.clear()
        token_payload, status = admin.handle_admin_post(
            None, admin.ADMIN_BASE_PATH + "/auth",
            {"password": "test-whitelist"}, {}, "127.0.0.1")
        self.assertEqual(status, 200)
        headers = {"X-Admin-Token": token_payload["token"]}
        try:
            _payload, status = admin.handle_admin_post(
                None, admin.ADMIN_BASE_PATH + "/whitelist",
                {"ip_address": "pas-une-ip", "description": "x"}, headers, "127.0.0.1")
            self.assertEqual(status, 400)
            payload, status = admin.handle_admin_post(
                None, admin.ADMIN_BASE_PATH + "/whitelist",
                {"ip_address": "88.175.123.252", "description": "Bureau"}, headers, "127.0.0.1")
            self.assertEqual(status, 200)
            self.assertTrue(any(e["ip_address"] == "88.175.123.252" for e in payload["entries"]))
            _payload, status = admin.handle_admin_delete(
                None, admin.ADMIN_BASE_PATH + "/whitelist/88.175.123.252", headers, "127.0.0.1")
            self.assertEqual(status, 200)
            self.assertFalse(dao.is_ip_whitelisted("88.175.123.252"))
            _payload, status = admin.handle_admin_delete(
                None, admin.ADMIN_BASE_PATH + "/whitelist/inexistante", headers, "127.0.0.1")
            self.assertEqual(status, 400)
        finally:
            admin._sessions.clear()
            os.environ.pop("ADMIN_PASSWORD", None)


class TestFileDeTaches(unittest.TestCase):
    """DEFI-02/03 : claim atomique, orphelins, purge."""

    def setUp(self):
        _clean()
        self.h = dao.ip_hash("203.0.113.0")

    def test_claim_atomique_deux_threads(self):
        cid = dao.create_challenge("amour", self.h)
        gains = []
        barriere = threading.Barrier(2)

        def claim():
            barriere.wait()
            obtenu = dao.claim_next_challenge()
            gains.append(obtenu["id"] if obtenu else None)

        threads = [threading.Thread(target=claim) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(gains, key=str), sorted([cid, None], key=str))
        self.assertEqual(dao.get_challenge(cid)["status"], "running")

    def test_requeue_orphelin_puis_error(self):
        cid = dao.create_challenge("amour", self.h)
        dao.claim_next_challenge()
        self.assertEqual(dao.requeue_stale_running(max_age_seconds=-1), 1)
        self.assertEqual(dao.get_challenge(cid)["status"], "queued")
        dao.claim_next_challenge()
        dao.requeue_stale_running(max_age_seconds=-1)
        self.assertEqual(dao.get_challenge(cid)["status"], "error")

    def test_release_ne_marque_pas_orphelin(self):
        cid = dao.create_challenge("amour", self.h)
        dao.claim_next_challenge()
        dao.release_challenge(cid)
        self.assertEqual(dao.get_challenge(cid)["status"], "queued")
        self.assertIsNone(dao.get_challenge(cid)["error"])

    def test_purge(self):
        dao.create_challenge("amour", self.h)
        self.assertGreaterEqual(dao.purge_older_than(days=-30), 1)
        self.assertEqual(dao.count_queued(), 0)

    def test_statut_terminal_reserve(self):
        cid = dao.create_challenge("amour", self.h)
        dao.claim_next_challenge()
        with self.assertRaises(ValueError):
            dao.finish_challenge(cid, "queued", 1, 1.0)



class TestResolutionBoutEnBout(unittest.TestCase):
    """DEFI-10/11/12 : pick-up + résolution + statut terminal (moteur simulé).

    Le vrai moteur (`Solver` + `MockClient`) exige numpy/word2vec : il est
    validé par la recette docker (QUAL-22). Ici on vérifie l'orchestration du
    worker avec un moteur simulé injecté dans `sys.modules`.
    """

    def setUp(self):
        _clean()
        self.h = dao.ip_hash("203.0.113.0")

    def _modules_simules(self, gain=True):
        class FauxSolver:
            def __init__(self, args, store=None, game=None):
                self.trajectory = []
                self.guesses = {}
                self.args = args

            def run(self):
                for i in (1, 2, 3):
                    self.trajectory.append({"step": i, "word": f"mot{i}", "score": 10.0 * i,
                                            "permille": i, "source": "rag",
                                            "weather": "🙂", "is_record": True})
                    self.guesses[f"mot{i}"] = (10.0 * i, i)
                if gain:
                    return {"win": True, "tries": 3, "time": 0.5, "word": "amour"}
                return {"win": False, "tries": 3, "time": 0.7, "word": "?"}

        class MockClient:
            def __init__(self, store, secret=None):
                if secret != "amour":
                    raise ValueError("mot hors lexique")

        engine = types.ModuleType("src.engine")
        engine.Solver = FauxSolver
        clients = types.ModuleType("src.engine.clients")
        clients.MockClient = MockClient
        return {"src.engine": engine, "src.engine.clients": clients}

    def test_defi_gagne(self):
        from src.services import challenges as worker
        cid = dao.create_challenge("amour", self.h)
        with mock.patch.dict("sys.modules", self._modules_simules(gain=True)):
            self.assertTrue(worker.process_next_challenge(store=types.SimpleNamespace(col=object())))
        challenge = dao.get_challenge(cid)
        self.assertEqual(challenge["status"], "solved")
        self.assertEqual(challenge["tries_count"], 3)
        self.assertEqual(len(challenge["trajectory"]), 3)
        self.assertAlmostEqual(challenge["duration_seconds"], 0.5, places=1)

    def test_defi_perdu(self):
        from src.services import challenges as worker
        cid = dao.create_challenge("amour", self.h)
        with mock.patch.dict("sys.modules", self._modules_simules(gain=False)):
            self.assertTrue(worker.process_next_challenge(store=types.SimpleNamespace(col=object())))
        self.assertEqual(dao.get_challenge(cid)["status"], "lost")

    def test_mot_devenu_invalide_en_error(self):
        from src.services import challenges as worker
        cid = dao.create_challenge("amour", self.h)
        modules = self._modules_simules(gain=True)

        def _client_invalide(store, secret=None):
            raise ValueError("hors lexique")

        modules["src.engine.clients"].MockClient = _client_invalide
        with mock.patch.dict("sys.modules", modules):
            self.assertTrue(worker.process_next_challenge(store=types.SimpleNamespace(col=object())))
        self.assertEqual(dao.get_challenge(cid)["status"], "error")

    def test_chroma_absent_le_defi_reste_en_file(self):
        from src.services import challenges as worker
        cid = dao.create_challenge("amour", self.h)
        self.assertFalse(worker.process_next_challenge(store=types.SimpleNamespace(col=None)))
        self.assertEqual(dao.get_challenge(cid)["status"], "queued")

    def test_kill_switch(self):
        from src.services import challenges as worker
        dao.create_challenge("amour", self.h)
        with mock.patch.object(worker, "CHALLENGE_ENABLED", False):
            self.assertFalse(worker.process_next_challenge(store=types.SimpleNamespace(col=object())))
        self.assertEqual(dao.count_queued(), 1)


if __name__ == "__main__":
    unittest.main()

