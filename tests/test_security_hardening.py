"""Tests de durcissement de sécurité (Jalon M3 - Security Hardening & Trust Boundaries).

Vérifie de manière déterministe et isolée :
1. La résolution sécurisée des adresses IP clientes (fail-closed, chaîne X-Forwarded-For).
2. L'étanchéité face aux tentatives d'usurpation (spoofing) pour contourner le rate-limiting.
3. L'étanchéité face au contournement des quotas de défi au bot et fausse whitelist.
4. L'absence de socket Docker monté et le comportement gracieux des logs conteneurs.
5. La protection de la console d'administration (brute-force fail-closed, tokens, rate-limit GET).
"""
import os
import time
import unittest
from unittest import mock

import _context  # noqa: F401  — isole la suite de l'environnement d'exécution

from src.api.proxy import (  # noqa: E402
    anonymize_ip,
    extract_client_ip,
    get_trusted_proxies,
    is_ip_in_trusted,
    parse_ip,
    parse_trusted_proxies,
)
from src.api.ratelimit import RateLimiter  # noqa: E402
from src.api.routes import admin  # noqa: E402
from src.api.routes.challenge import handle_challenge_post  # noqa: E402
from src.api.server import GameAPIHandler  # noqa: E402


class _DummyHandler(GameAPIHandler):
    """Sous-classe de test sans socket réseau réel."""

    def __init__(self, peer_ip: str, headers: dict):
        self.client_address = (peer_ip, 54321) if peer_ip else None
        self.headers = headers
        self.rfile = None
        self.wfile = None


class TestTrustedClientIP(unittest.TestCase):
    """Validation de la résolution d'adresse IP et filtrage de confiance."""

    def setUp(self):
        self._saved_trusted = os.environ.get("TRUSTED_PROXIES")

    def tearDown(self):
        if self._saved_trusted is None:
            os.environ.pop("TRUSTED_PROXIES", None)
        else:
            os.environ["TRUSTED_PROXIES"] = self._saved_trusted

    def test_parse_ip_valide_ipv4_et_ipv6(self):
        self.assertEqual(str(parse_ip("192.0.2.1")), "192.0.2.1")
        self.assertEqual(str(parse_ip("192.0.2.1:8080")), "192.0.2.1")
        self.assertEqual(str(parse_ip("2001:db8::1")), "2001:db8::1")
        self.assertEqual(str(parse_ip("[2001:db8::1]:8443")), "2001:db8::1")
        self.assertEqual(str(parse_ip("[::1]")), "::1")

    def test_parse_ip_rejette_malformes(self):
        self.assertIsNone(parse_ip(None))
        self.assertIsNone(parse_ip(""))
        self.assertIsNone(parse_ip("   "))
        self.assertIsNone(parse_ip("<script>alert(1)</script>"))
        self.assertIsNone(parse_ip("999.999.999.999"))
        self.assertIsNone(parse_ip("not-an-ip"))

    def test_peer_non_de_confiance_ignore_completement_x_forwarded_for(self):
        """Un client direct non déclaré dans TRUSTED_PROXIES ne peut jamais injecter d'en-tête."""
        trusted = parse_trusted_proxies("127.0.0.1, 10.0.0.1")
        peer = "203.0.113.195"  # IP publique arbitraire
        # L'attaquant injecte une fausse IP ou une IP blanche
        forwarded = "12.34.56.78"

        client_ip = extract_client_ip(peer, forwarded, trusted_proxies=trusted)
        self.assertEqual(client_ip, peer)

    def test_default_fail_closed_sans_trusted_proxies(self):
        """Sans variable TRUSTED_PROXIES, aucun proxy n'est de confiance par défaut."""
        os.environ["TRUSTED_PROXIES"] = ""
        peer = "172.18.0.2"
        forwarded = "198.51.100.25"

        client_ip = extract_client_ip(peer, forwarded)
        self.assertEqual(client_ip, peer)

    def test_proxy_de_confiance_relais_simple(self):
        """Derrière un proxy déclaré, l'adresse client transmise est correctement extraite."""
        trusted = parse_trusted_proxies("172.18.0.2")
        client_ip = extract_client_ip("172.18.0.2", "198.51.100.42", trusted_proxies=trusted)
        self.assertEqual(client_ip, "198.51.100.42")

    def test_proxy_de_confiance_avec_chaine_usurpee(self):
        """L'attaquant tente d'ajouter un en-tête en amont du reverse proxy Caddy."""
        trusted = parse_trusted_proxies("172.18.0.2")
        # L'attaquant (198.51.100.42) a envoyé 'X-Forwarded-For: 1.1.1.1', Caddy a concaténé
        forwarded = "1.1.1.1, 198.51.100.42"

        # Le parcours de droite à gauche s'arrête au premier hôte hors du réseau de confiance
        client_ip = extract_client_ip("172.18.0.2", forwarded, trusted_proxies=trusted)
        self.assertEqual(client_ip, "198.51.100.42")

    def test_multi_proxys_avec_cdn_intermediaire_de_confiance(self):
        """Multi-sauts : Cloudflare (203.0.113.10) -> Caddy (172.18.0.2) -> Web."""
        trusted = parse_trusted_proxies("172.18.0.2, 203.0.113.0/24")
        forwarded = "198.51.100.77, 203.0.113.10"

        client_ip = extract_client_ip("172.18.0.2", forwarded, trusted_proxies=trusted)
        self.assertEqual(client_ip, "198.51.100.77")

    def test_multi_proxys_interrompu_par_relais_inconnu(self):
        """Si un relais intermédiaire n'est pas de confiance, il devient le client effectif."""
        trusted = parse_trusted_proxies("172.18.0.2")
        forwarded = "1.1.1.1, 8.8.8.8"

        client_ip = extract_client_ip("172.18.0.2", forwarded, trusted_proxies=trusted)
        self.assertEqual(client_ip, "8.8.8.8")

    def test_en_tete_malforme_fail_closed_vers_peer(self):
        """Un en-tête contenant des caractères invalides replie immédiatement sur le pair TCP."""
        trusted = parse_trusted_proxies("172.18.0.2")
        forwarded = "<bad-input>, 198.51.100.42"

        client_ip = extract_client_ip("172.18.0.2", forwarded, trusted_proxies=trusted)
        self.assertEqual(client_ip, "172.18.0.2")

    def test_anonymisation_rgpd_ipv4_et_ipv6(self):
        self.assertEqual(anonymize_ip("192.168.1.150"), "192.168.1.0")
        self.assertEqual(anonymize_ip("10.20.30.40"), "10.20.30.0")
        self.assertEqual(anonymize_ip("2001:0db8:85a3:0000:0000:8a2e:0370:7334"), "2001:db8:85a3::")
        self.assertEqual(anonymize_ip("unknown"), "unknown")


class TestRateLimitBypassMitigation(unittest.TestCase):
    """Validation de l'impossibilité de contourner les limites par rotation d'en-tête."""

    def setUp(self):
        self._saved_trusted = os.environ.get("TRUSTED_PROXIES")
        os.environ["TRUSTED_PROXIES"] = ""

    def tearDown(self):
        if self._saved_trusted is None:
            os.environ.pop("TRUSTED_PROXIES", None)
        else:
            os.environ["TRUSTED_PROXIES"] = self._saved_trusted

    def test_rotation_x_forwarded_for_ne_contourne_pas_le_rate_limiter(self):
        """Un attaquant direct qui fait varier son X-Forwarded-For consomme le même seau."""
        limiter = RateLimiter(default_capacity=3.0, refill_per_second=0.01)
        peer = "198.51.100.99"

        # 3 requêtes consécutives avec des IP différentes dans X-Forwarded-For
        for fake_ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
            handler = _DummyHandler(peer, {"X-Forwarded-For": fake_ip})
            effective_ip = handler._client_ip()
            self.assertEqual(effective_ip, peer)
            allowed, _ = limiter.allow(effective_ip)
            self.assertTrue(allowed)

        # La 4ème requête doit être refusée car l'IP effective est restée 198.51.100.99
        handler = _DummyHandler(peer, {"X-Forwarded-For": "4.4.4.4"})
        allowed, retry = limiter.allow(handler._client_ip())
        self.assertFalse(allowed)
        self.assertGreater(retry, 0)

    def test_rotation_x_forwarded_for_ne_contourne_pas_quota_defi_bot(self):
        """L'usurpation d'adresse n'échappe pas au quota anti-rafale de défi au bot."""
        peer = "198.51.100.99"
        mock_manager = mock.MagicMock()
        mock_manager.store.vocab = {"soleil": 0}

        # Déclarer le mock pour éviter tout appel BD
        with mock.patch("src.api.routes.challenge.is_ip_whitelisted", return_value=False), \
             mock.patch("src.api.routes.challenge._challenge_limiter.allow") as mock_limiter:
            mock_limiter.side_effect = [(True, 0.0), (True, 0.0), (False, 10.0)]

            # Requête 1 avec fake IP
            handler1 = _DummyHandler(peer, {"X-Forwarded-For": "10.0.0.1"})
            client_ip1 = handler1._client_ip()
            self.assertEqual(client_ip1, peer)

            # Requête 2 avec autre fake IP
            handler2 = _DummyHandler(peer, {"X-Forwarded-For": "10.0.0.2"})
            client_ip2 = handler2._client_ip()
            self.assertEqual(client_ip2, peer)

    def test_usurpation_adresse_whitelist_echoue(self):
        """Un attaquant ne peut pas se prétendre whitelisté via X-Forwarded-For."""
        whitelisted_office_ip = "12.34.56.78"
        attacker_peer = "198.51.100.123"

        with mock.patch("src.api.routes.challenge.is_ip_whitelisted") as mock_whitelist:
            mock_whitelist.side_effect = lambda ip: ip == whitelisted_office_ip

            # L'attaquant envoie X-Forwarded-For: 12.34.56.78
            handler = _DummyHandler(attacker_peer, {"X-Forwarded-For": whitelisted_office_ip})
            effective_ip = handler._client_ip()

            # L'IP effective doit être le peer TCP de l'attaquant
            self.assertEqual(effective_ip, attacker_peer)
            self.assertFalse(mock_whitelist(effective_ip))


class TestDockerSocketIsolation(unittest.TestCase):
    """Validation de l'isolation du socket Docker et repli propre."""

    def test_docker_socket_absent_de_docker_compose_web(self):
        """Le service cemantix_web ne doit plus monter /var/run/docker.sock."""
        compose_path = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Isoler la section du service cemantix_web
        self.assertIn("cemantix_web:", content)
        web_section = content.split("cemantix_web:")[1].split("cemantix:")[0]

        self.assertNotIn("/var/run/docker.sock", web_section)
        self.assertNotIn("DOCKER_GID", web_section)

    def test_container_logs_sans_socket_renvoie_message_explicite(self):
        """Sans socket monté, container_logs renvoie une explication claire sans exception."""
        with mock.patch.object(admin, "DOCKER_SOCKET", "/nonexistent/docker.sock"):
            logs = admin.container_logs("cemantix_worker")
            self.assertEqual(len(logs), 1)
            self.assertIn("non mont", logs[0])

    def test_container_log_stream_sans_socket_renvoie_message_explicite(self):
        """Sans socket monté, le flux de log conteneur émet une information explicite."""
        emitted = []
        with mock.patch.object(admin, "DOCKER_SOCKET", "/nonexistent/docker.sock"):
            admin.container_log_stream("cemantix_worker", emit=emitted.append)
            self.assertEqual(len(emitted), 1)
            self.assertIn("non mont", emitted[0])


class TestAdminSecurityHardening(unittest.TestCase):
    """Validation du durcissement des points d'administration."""

    def setUp(self):
        self._saved_pass = os.environ.get("ADMIN_PASSWORD")
        os.environ["ADMIN_PASSWORD"] = "test-secret-hardening"
        admin._sessions.clear()

    def tearDown(self):
        if self._saved_pass is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self._saved_pass
        admin._sessions.clear()

    def test_token_invalide_si_admin_password_vide(self):
        """Même avec un jeton valide sous un mot de passe précédent, vider le mot de passe révoque tout."""
        token = admin._issue_token()
        self.assertTrue(admin._check_token(token))

        # Retrait du mot de passe
        os.environ["ADMIN_PASSWORD"] = ""
        self.assertFalse(admin._check_token(token))
        self.assertFalse(admin.authorize({"X-Admin-Token": token}))

    def test_brute_force_auth_rate_limited_par_ip_reelle(self):
        """La protection brute force de /auth ne peut pas être réinitialisée par X-Forwarded-For."""
        admin._login_limiter = RateLimiter(default_capacity=3.0, refill_per_second=0.01)
        peer = "198.51.100.55"

        for i in range(3):
            # L'attaquant essaie de spoof l'IP
            handler = _DummyHandler(peer, {"X-Forwarded-For": f"10.0.0.{i}"})
            res, status = admin.handle_admin_post(
                None, admin.ADMIN_BASE_PATH + "/auth", {"password": "bad"},
                handler.headers, handler._client_ip()
            )
            self.assertEqual(status, 401)

        # 4ème essai : bloqué en 429
        handler = _DummyHandler(peer, {"X-Forwarded-For": "10.0.0.99"})
        res, status = admin.handle_admin_post(
            None, admin.ADMIN_BASE_PATH + "/auth", {"password": "bad"},
            handler.headers, handler._client_ip()
        )
        self.assertEqual(status, 429)
        self.assertIn("Trop de tentatives", res["error"])

    def test_admin_get_protege_par_api_limiter(self):
        """Les GET d'administration sont limités en débit par _api_limiter."""
        token = admin._issue_token()
        admin._api_limiter = RateLimiter(default_capacity=2.0, refill_per_second=0.01)

        captured = []
        def _send(data, status=200):
            captured.append(status)

        headers = {"X-Admin-Token": token}
        # 2 requêtes autorisées
        for _ in range(2):
            admin.handle_admin_get(None, admin.ADMIN_BASE_PATH + "/stats", "", headers,
                                  send_json=_send, send_sse=lambda p: None, client_ip="1.2.3.4")
            self.assertEqual(captured[-1], 200)

        # 3ème requête : rejetée en 429
        admin.handle_admin_get(None, admin.ADMIN_BASE_PATH + "/stats", "", headers,
                              send_json=_send, send_sse=lambda p: None, client_ip="1.2.3.4")
        self.assertEqual(captured[-1], 429)


if __name__ == "__main__":
    unittest.main(verbosity=2)
