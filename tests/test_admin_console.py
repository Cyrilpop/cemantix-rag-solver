"""Tests de la console d'exploitation (API d'administration).

Lancement :  python -m unittest discover -s tests -v

Le mot de passe est posé dans l'environnement de chaque test : la console est
désactivée par défaut, et un test vérifie justement ce comportement.
"""
import os
import time
import unittest
from unittest import mock

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.api.routes import admin  # noqa: E402
from src.config import log  # noqa: E402


def _ascii(text: str) -> str:
    """Retire les accents pour comparer des messages en français sans se soucier
    de l'encodage du fichier de test."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", str(text)) if not unicodedata.combining(c))


class _Headers(dict):
    """Mini-porte-en-têtes HTTP (les en-têtes sont insensibles à la casse)."""

    def get(self, key, default=None):
        for existing, value in self.items():
            if existing.lower() == key.lower():
                return value
        return default


class TestAdminAuth(unittest.TestCase):
    PASSWORD = "test-mot-de-passe-admin"

    def setUp(self):
        self._saved = os.environ.get("ADMIN_PASSWORD")
        os.environ["ADMIN_PASSWORD"] = self.PASSWORD
        admin._sessions.clear()

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self._saved
        admin._sessions.clear()

    def _login(self, ip="1.2.3.4"):
        return admin.handle_admin_post(
            None, admin.ADMIN_BASE_PATH + "/auth", {"password": self.PASSWORD}, _Headers(), ip
        )

    def test_sans_mot_de_passe_la_console_est_desactivee(self):
        os.environ["ADMIN_PASSWORD"] = ""
        payload, status = admin.handle_admin_post(
            None, admin.ADMIN_BASE_PATH + "/stats", {}, _Headers(), "1.2.3.4"
        )
        self.assertEqual(status, 403)
        # Comparaison insensible aux accents : le message est en français.
        self.assertIn("desactive", _ascii(payload["error"]))

    def test_mot_de_passe_incorrect_rejete(self):
        payload, status = admin.handle_admin_post(
            None, admin.ADMIN_BASE_PATH + "/auth", {"password": "mauvais"}, _Headers(), "1.2.3.4"
        )
        self.assertEqual(status, 401)
        self.assertNotIn("token", payload)

    def test_mot_de_passe_correct_delivre_un_jeton(self):
        payload, status = self._login()
        self.assertEqual(status, 200)
        self.assertTrue(payload.get("token"))
        self.assertTrue(admin.authorize(_Headers({"X-Admin-Token": payload["token"]})))

    def test_post_ohne_jeton_en_401(self):
        payload, status = admin.handle_admin_post(
            None, admin.ADMIN_BASE_PATH + "/actions/solve", {}, _Headers(), "1.2.3.4"
        )
        self.assertEqual(status, 401)

    def test_get_sans_jeton_en_401(self):
        captured = {}
        admin.handle_admin_get(
            None, admin.ADMIN_BASE_PATH + "/stats", "", _Headers(),
            send_json=lambda data, status=200: captured.update(status=status),
            send_sse=lambda produce: None,
        )
        self.assertEqual(captured.get("status"), 401)

    def test_jeton_altere_refuse(self):
        token = self._login()[0]["token"]
        self.assertFalse(admin.authorize(_Headers({"X-Admin-Token": token + "0"})))
        self.assertFalse(admin.authorize(_Headers({"X-Admin-Token": "nimporte"})))

    def test_jeton_accepte_en_parametre_pour_le_flux_sse(self):
        token = self._login()[0]["token"]
        self.assertTrue(admin.authorize(_Headers(), {"token": token}))

    def test_is_admin_path_ne_capture_que_le_chemin_admin(self):
        self.assertTrue(admin.is_admin_path(admin.ADMIN_BASE_PATH))
        self.assertTrue(admin.is_admin_path(admin.ADMIN_BASE_PATH + "/stats"))
        self.assertFalse(admin.is_admin_path("/api/daily"))
        self.assertFalse(admin.is_admin_path(admin.ADMIN_BASE_PATH + "-espion/stats"))


class TestAdminLogs(unittest.TestCase):
    def test_le_tampon_de_journal_recupere_les_messages(self):
        log("ligne de test admin 42")
        lines = admin.recent_logs(200)
        self.assertTrue(any("ligne de test admin 42" in line for line in lines))

    def test_le_tampon_reste_borne(self):
        from src.config import _MEMORY_HANDLER
        for i in range(1500):
            log(f"remplissage {i}")
        self.assertLessEqual(len(_MEMORY_HANDLER.tail(5000)), 5000)
        self.assertGreater(len(_MEMORY_HANDLER.tail(5000)), 0)


class TestAdminStats(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("ADMIN_PASSWORD")
        os.environ["ADMIN_PASSWORD"] = "x"

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self._saved

    def test_collect_stats_renvoie_les_bloques_attendus(self):
        stats = admin.collect_stats(None)
        for key in ("uptime_seconds", "api", "base", "demon", "index"):
            self.assertIn(key, stats)
        self.assertIn("moteur", stats["base"])

    def test_logs_dapp_via_get(self):
        token = admin._issue_token()
        captured = {}
        admin.handle_admin_get(
            None, admin.ADMIN_BASE_PATH + "/logs", "source=app&tail=10",
            _Headers({"X-Admin-Token": token}),
            send_json=lambda data, status=200: captured.update(data=data, status=status),
            send_sse=lambda produce: None,
        )
        self.assertEqual(captured.get("status"), 200)
        self.assertEqual(captured["data"]["source"], "app")
        self.assertIsInstance(captured["data"]["lines"], list)

    def test_source_inconnue_en_400(self):
        token = admin._issue_token()
        captured = {}
        admin.handle_admin_get(
            None, admin.ADMIN_BASE_PATH + "/logs", "source=nimporte",
            _Headers({"X-Admin-Token": token}),
            send_json=lambda data, status=200: captured.update(data=data, status=status),
            send_sse=lambda produce: None,
        )
        self.assertEqual(captured.get("status"), 400)


class TestAdminActions(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("ADMIN_PASSWORD")
        os.environ["ADMIN_PASSWORD"] = "x"
        admin._action_running = None
        self.headers = _Headers({"X-Admin-Token": admin._issue_token()})

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self._saved
        admin._action_running = None

    def test_action_inconnue_en_404(self):
        _, status = admin.handle_admin_post(
            None, admin.ADMIN_BASE_PATH + "/actions/boom", {}, self.headers, "1.1.1.1"
        )
        self.assertEqual(status, 404)

    def test_action_deja_en_cours_en_409(self):
        admin._action_running = "solve"
        payload, status = admin.handle_admin_post(
            None, admin.ADMIN_BASE_PATH + "/actions/solve", {}, self.headers, "1.1.1.1"
        )
        self.assertEqual(status, 409)
        self.assertIn("deja en cours", _ascii(payload["error"]))

    def test_action_acceptee_puis_terminee(self):
        appelee = []
        with mock.patch.dict(admin._ACTIONS, {"export": lambda *a: appelee.append(1)}):
            payload, status = admin.handle_admin_post(
                None, admin.ADMIN_BASE_PATH + "/actions/export", {}, self.headers, "1.1.1.1"
            )
        self.assertEqual(status, 202)
        self.assertTrue(payload["accepted"])
        for _ in range(100):
            if appelee and admin._action_running is None:
                break
            time.sleep(0.02)
        self.assertEqual(appelee, [1])
        self.assertIsNone(admin._action_running)

    def test_echec_dune_action_ne_bloque_pas_la_suivante(self):
        def _boom(*a):
            raise RuntimeError("panne simulée")

        with mock.patch.dict(admin._ACTIONS, {"export": _boom}):
            admin.handle_admin_post(
                None, admin.ADMIN_BASE_PATH + "/actions/export", {}, self.headers, "1.1.1.1"
            )
            for _ in range(100):
                if admin._action_running is None:
                    break
                time.sleep(0.02)
        self.assertIsNone(admin._action_running)


if __name__ == "__main__":
    unittest.main(verbosity=2)

