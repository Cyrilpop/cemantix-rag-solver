"""
Cémantix Solver — Serveur HTTP REST & Passerelle API
====================================================
Serveur HTTP multi-threadé léger :
- Parsing JSON, gestion du CORS et transmission réseau
- Dispatching déclaratif vers les contrôleurs sous `src.api.routes` :
  - `src.api.routes.system`  : Métriques système, santé et mot du jour (/api/health, /api/daily)
  - `src.api.routes.solo`    : Défi du Jour & Mode Illimité (/api/game/*)
  - `src.api.routes.battle`  : Mode Battle vs IA RAG (/api/battle/*)
  - `src.api.routes.multi`   : Mode Multijoueur 1v1 (/api/multi/*)
- Gestion du cycle de vie du serveur (start_api_server, start_api_thread)
"""
import json
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
)
from ..engine import VocabStore

# Instance globale unique du gestionnaire de jeu
_manager: Optional[GameManager] = None


class GameAPIHandler(BaseHTTPRequestHandler):
    """Handler HTTP REST léger avec dispatching vers les contrôleurs de routes."""

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def _send_json(self, data: dict, status: int = 200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> Optional[dict]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return None
        raw_body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        query = self.path.split("?")[1] if "?" in self.path else ""

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
        if not _manager:
            self._send_json({"error": "Gestionnaire non initialisé"}, status=503)
            return

        data = self._read_json() or {}

        if path.startswith("/api/game/"):
            res, status = handle_solo_post(_manager, path, data)
        elif path.startswith("/api/battle/"):
            res, status = handle_battle_post(_manager, path, data)
        elif path.startswith("/api/multi/"):
            res, status = handle_multi_post(_manager, path, data)
        else:
            res, status = {"error": "Route introuvable"}, 404

        self._send_json(res, status=status)

    def log_message(self, format, *args):
        # Silence les logs HTTP standards pour garder la console propre
        pass


def start_api_server(
    store: VocabStore,
    host: str = "0.0.0.0",
    port: int = 8000,
    persist: bool = True,
) -> ThreadingHTTPServer:
    """Initialise et lance le serveur HTTP multi-threadé."""
    global _manager
    _manager = GameManager(store, persist=persist)
    server = ThreadingHTTPServer((host, port), GameAPIHandler)
    log(f"🌐  [API JEU] Serveur HTTP opérationnel sur http://{host}:{port}/api")
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
