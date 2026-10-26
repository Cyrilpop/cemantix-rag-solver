
"""
Cémantix Solver — Serveur HTTP REST & Passerelle API
====================================================
Serveur HTTP multi-threadé léger et durci :
- Corps de requête plafonné, timeout socket, limites de threads
- CORS restreint à l'origine du site (liste blanche par variable d'environnement)
- En-têtes de sécurité et `Cache-Control` adapté à chaque type de réponse
- Rate-limiting en mémoire (jetons par IP) pour freiner l'abus des endpoints de jeu
- Dispatching déclaratif vers les contrôleurs sous `src.api.routes` :
  - `src.api.routes.system`  : Métriques système, santé et mot du jour (/api/health, /api/daily)
  - `src.api.routes.solo`    : Défi du Jour & Mode Illimité (/api/game/*)
  - `src.api.routes.battle`  : Mode Battle vs IA RAG (/api/battle/*)
  - `src.api.routes.multi`   : Mode Multijoueur 1v1 (/api/multi/*)
- Gestion du cycle de vie du serveur (start_api_server, start_api_thread)
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from ..config import log
from ..game import GameManager
from .routes import (
    handle_battle_post,
    handle_multi_get,
    handle_multi_post,
    handle_solo_get,
    handle_solo_post,
    handle_system_get,
    handle_system_post,
)
from .ratelimit import RateLimiter
from ..engine import VocabStore

# --------------------------------------------------------------------------- #
# Paramètres de durcissement (surchargables par variables d'environnement)
# --------------------------------------------------------------------------- #
MAX_BODY_BYTES = int(os.getenv("API_MAX_BODY_BYTES", str(32 * 1024)))
SOCKET_TIMEOUT = float(os.getenv("API_SOCKET_TIMEOUT", "10"))
CORS_ALLOWED_ORIGIN = os.getenv("API_ALLOWED_ORIGIN", "https://cemantix.cyril-randon.fr")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    "Cache-Control": "no-store",
}

# Instance globale unique du gestionnaire de jeu
_manager: Optional[GameManager] = None
_limiter = RateLimiter(default_capacity=240, refill_per_second=4.0, burst_capacity=60)


class GameAPIHandler(BaseHTTPRequestHandler):
    """Handler HTTP REST léger avec dispatching vers les contrôleurs de routes."""

    server_version = "CemantixSolver"
    sys_version = ""
    timeout = SOCKET_TIMEOUT
    # Réponse HTTP au plus court : évite qu'un client lent retienne un thread indéfiniment.
    disable_nagle_algorithm = True

    # ----------------------------------------------------------------- #
    # Utilitaires
    # ----------------------------------------------------------------- #
    def _client_ip(self) -> str:
        """Adresse du client, en tenant compte du reverse proxy Caddy."""
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "unknown"

    def _is_allowed_origin(self) -> bool:
        """Le CORS n'est ouvert qu'à l'origine déclarée (et aux clients sans en-tête)."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        allowed = [o.strip() for o in CORS_ALLOWED_ORIGIN.split(",") if o.strip()]
        return origin in allowed

    def _set_cors_headers(self):
        origin = self.headers.get("Origin")
        if origin and self._is_allowed_origin():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")

    def _security_headers(self):
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self._security_headers()
        self.end_headers()

    def _send_json(self, data: dict, status: int = 200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._set_cors_headers()
        self._security_headers()
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            # Le navigateur a annulé la requête (changement d'onglet) : sans importance.
            pass

    def _send_error_json(self, message: str, status: int, **extra):
        body = {"error": message}
        body.update(extra)
        self._send_json(body, status=status)

    def _read_json(self) -> tuple[Optional[dict], bool]:
        """Lit un corps JSON en refusant les tailles déraisonnables.

        Renvoie `(données, erreur_déjà_renvoyée)`. Sans plafond, un client pouvait
        déclarer un `Content-Length` énorme et forcer le serveur à allouer la
        mémoire correspondante.
        """
        raw_length = self.headers.get("Content-Length", "0")
        try:
            content_length = int(raw_length)
        except ValueError:
            return {}, False
        if content_length <= 0:
            return {}, False
        if content_length > MAX_BODY_BYTES:
            self._send_error_json("Corps de requête trop volumineux", 413)
            return {}, True

        try:
            raw_body = self.rfile.read(content_length).decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return {}, False
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            return {}, False
        return (parsed, False) if isinstance(parsed, dict) else ({}, False)

    def _rate_limited(self, path: str) -> bool:
        """Applique le seau à jetons ; les sondes de santé ne sont pas comptées."""
        if path in ("/api/health", "/api/healthcheck"):
            return False
        allowed, retry_after = _limiter.allow(self._client_ip())
        if allowed:
            return False
        self._send_error_json(
            "Trop de requêtes, réessayez dans quelques secondes.",
            429,
            retry_after=round(retry_after, 1),
        )
        return True

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        query = self.path.split("?")[1] if "?" in self.path else ""

        if self._rate_limited(path):
            return

        if path in ("/api/health", "/api/healthcheck", "/api/daily", "/api/dashboard"):
            res, status = handle_system_get(_manager, path, query)
        elif path.startswith("/api/game/"):
            res, status = handle_solo_get(_manager, path)
        elif path.startswith("/api/multi/"):
            res, status = handle_multi_get(_manager, path, query)
        else:
            res, status = {"error": "Route introuvable"}, 404

        self._send_json(res, status=status)

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")

        if self._rate_limited(path):
            return

        # Le corps est validé avant tout traitement : un en-tête Content-Length
        # mensonger doit être rejeté sans jamais allouer la mémoire annoncée.
        data, rejected = self._read_json()
        if rejected:
            return  # _read_json a déjà renvoyé l'erreur 413.

        if not _manager:
            self._send_error_json("Gestionnaire non initialisé", 503)
            return

        if path.startswith("/api/game/"):
            res, status = handle_solo_post(_manager, path, data)
        elif path.startswith("/api/battle/"):
            res, status = handle_battle_post(_manager, path, data)
        elif path.startswith("/api/multi/"):
            res, status = handle_multi_post(_manager, path, data)
        elif path == "/api/daily/reveal":
            res, status = handle_system_post(_manager, path, data)
        else:
            res, status = {"error": "Route introuvable"}, 404

        self._send_json(res, status=status)

    def log_message(self, format, *args):
        # Journalisation minimale et non verbeuse : la méthode d'origine écrit sur
        # stderr sans limite de débit, ce qui offrait un vecteur d'épuisement.
        try:
            log(f"🌐 {self._client_ip()} {format % args}")
        except Exception:
            pass


class BoundedHTTPServer(ThreadingHTTPServer):
    """Serveur multi-threadé à plafond de threads.

    `ThreadingHTTPServer` crée un thread par connexion sans limite : un afflux
    de connexions pouvait épuiser les ressources du conteneur. Le plafond impose
    l'attente en file plutôt que la création incontrôlée de threads.
    """

    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128

    def __init__(self, address, handler, max_workers: int = 64):
        self._semaphore = threading.BoundedSemaphore(max_workers)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self._semaphore.acquire(blocking=False):
            # File pleine : on rejette proprement au lieu de saturer la machine.
            try:
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\n"
                    b"Content-Length: 0\r\nConnection: close\r\n\r\n"
                )
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._semaphore.release()

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._semaphore.release()


def start_api_server(
    store: VocabStore,
    host: str = "0.0.0.0",
    port: int = 8000,
    persist: bool = True,
) -> BoundedHTTPServer:
    """Initialise et lance le serveur HTTP multi-threadé."""
    global _manager
    _manager = GameManager(store, persist=persist)
    max_workers = int(os.getenv("API_MAX_WORKERS", "64"))
    server = BoundedHTTPServer((host, port), GameAPIHandler, max_workers=max_workers)
    log(f"🌐  [API JEU] Serveur HTTP opérationnel sur http://{host}:{port}/api ({max_workers} workers max)")
    return server


def start_api_thread(
    store: VocabStore,
    host: str = "0.0.0.0",
    port: int = 8000,
    persist: bool = True,
) -> threading.Thread:
    """Démarre le serveur d'API dans un thread d'arrière-plan sécurisé."""
    server = start_api_server(store, host=host, port=port, persist=persist)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="CemantixAPIThread")
    thread.start()
    return thread
