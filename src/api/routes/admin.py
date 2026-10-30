"""
Cémantix Solver — Console d'Administration (hors index)
=======================================================
Contrôleur protégé par mot de passe, monté sur un chemin non devinable :

- POST <BASE>/auth              : échange le mot de passe contre un jeton (TTL 2 h)
- GET  <BASE>/stats             : métriques runtime (sessions, pool, base, heartbeat)
- GET  <BASE>/logs?source=&tail : journaux (app en mémoire, worker/web via Docker)
- GET  <BASE>/logs/stream       : suivi temps réel (Server-Sent Events)
- POST <BASE>/actions/solve     : force la découverte du mot du jour
- POST <BASE>/actions/chroma    : reconstruit l'index vectoriel ChromaDB
- POST <BASE>/actions/export    : régénère data.json et les pages SEO

Sécurité : `ADMIN_PASSWORD` doit être présent dans l'environnement, sinon toutes
les routes répondent 403 (fonctionnalité désactivée par défaut). Le jeton est un
HMAC signé dérivé du mot de passe : il n'est jamais stocké en clair et expire.
"""
import collections
import hashlib
import hmac
import ipaddress
import json
import os
import shutil
import threading
import time
import urllib.parse
from datetime import datetime
from typing import Optional

from ...config import CHROMA_DIR, log, recent_logs, logs_since
from ...services.daemon import HEARTBEAT_FILE, PARIS_TZ
from ..ratelimit import RateLimiter

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
# Chemin non devinable : l'obscurité n'est qu'un premier filtre, l'authentification
# reste obligatoire. Surchargeable par ADMIN_API_PATH pour changer de chemin.
ADMIN_BASE_PATH = os.getenv("ADMIN_API_PATH", "/api/snap-9x").rstrip("/")
ADMIN_TOKEN_TTL = float(os.getenv("ADMIN_TOKEN_TTL", "7200"))
DOCKER_SOCKET = os.getenv("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
ADMIN_CONTAINERS = {
    "worker": os.getenv("ADMIN_CONTAINER_WORKER", "cemantix_worker"),
    "web": os.getenv("ADMIN_CONTAINER_WEB", "cemantix_web"),
}

_login_limiter = RateLimiter(default_capacity=6.0, refill_per_second=0.1, burst_capacity=6.0)
_api_limiter = RateLimiter(default_capacity=120.0, refill_per_second=2.0, burst_capacity=40.0)

_STARTED_AT = time.time()
_sessions: "collections.OrderedDict[str, float]" = collections.OrderedDict()
_sessions_lock = threading.Lock()
_action_lock = threading.Lock()
_action_running: Optional[str] = None


# --------------------------------------------------------------------------- #
# Authentification
# --------------------------------------------------------------------------- #
def _admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "")


def _token_secret() -> bytes:
    """Secret de signature dérivé du mot de passe (jamais le mot de passe lui-même)."""
    return hashlib.sha256(("cemantix-admin|" + _admin_password()).encode("utf-8")).digest()


def _issue_token() -> str:
    nonce = os.urandom(16).hex()
    expires = int(time.time() + ADMIN_TOKEN_TTL)
    payload = f"{nonce}.{expires}"
    signature = hmac.new(_token_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{payload}.{signature}"
    with _sessions_lock:
        _sessions[token] = time.time()
        while len(_sessions) > 50:
            _sessions.popitem(last=False)
    return token


def _check_token(token: str) -> bool:
    if not token:
        return False
    parts = token.split(".")
    if len(parts) != 3:
        return False
    nonce, expires, signature = parts
    payload = f"{nonce}.{expires}"
    expected = hmac.new(_token_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        return int(expires) > time.time()
    except ValueError:
        return False


def extract_token(headers, params: Optional[dict] = None) -> str:
    """Récupère le jeton d'administration.

    En-tête `X-Admin-Token` ou `Authorization: Bearer` en temps normal. Le flux
    `text/event-stream` est ouvert par un `EventSource`, qui ne peut pas ajouter
    d'en-tête : pour ce seul cas, le jeton peut arriver par le paramètre `token`.
    """
    direct = headers.get("X-Admin-Token", "")
    if direct:
        return direct.strip()
    authorization = headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if params:
        return str(params.get("token", "")).strip()
    return ""


def is_admin_path(path: str) -> bool:
    return path == ADMIN_BASE_PATH or path.startswith(ADMIN_BASE_PATH + "/")


def authorize(headers, params: Optional[dict] = None) -> bool:
    return bool(_admin_password()) and _check_token(extract_token(headers, params))


# --------------------------------------------------------------------------- #
# Logs des conteneurs (API Docker sur socket Unix, en lecture seule)
# --------------------------------------------------------------------------- #
def http_unix_connection(socket_path: str):
    """Connexion HTTP:: sur un socket Unix (l'API Docker n'est pas exposée en TCP)."""
    import http.client
    import socket as unix_socket

    class _UnixConnection(http.client.HTTPConnection):
        def __init__(self, path):
            super().__init__("localhost")
            self._socket_path = path

        def connect(self):
            sock = unix_socket.socket(unix_socket.AF_UNIX, unix_socket.SOCK_STREAM)
            sock.settimeout(60)
            sock.connect(self._socket_path)
            self.sock = sock

    return _UnixConnection(socket_path)


def _dechunk_docker_stream(raw: bytes) -> str:
    """Dépile les en-têtes de 8 octets du flux multiplexé Docker (stdout/stderr)."""
    if len(raw) < 8:
        return raw.decode("utf-8", "replace")
    frames, index = [], 0
    while index + 8 <= len(raw):
        size = int.from_bytes(raw[index + 4:index + 8], "big")
        start = index + 8
        frames.append(raw[start:start + size])
        index = start + size
    if not frames:
        return raw.decode("utf-8", "replace")
    return b"".join(frames).decode("utf-8", "replace")


def container_logs(container: str, tail: int = 200) -> list:
    """Dernières `tail` lignes de log d'un conteneur."""
    try:
        conn = http_unix_connection(DOCKER_SOCKET)
        conn.request("GET", f"/containers/{container}/logs?stdout=1&stderr=1&tail={int(tail)}")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        if response.status >= 400:
            return [f"⚠️  Docker a répondu {response.status} pour {container}"]
    except Exception as e:
        return [f"⚠️  Logs {container} indisponibles : {e}"]
    return _dechunk_docker_stream(raw).splitlines()[-max(1, int(tail)):]


def container_log_stream(container: str, emit) -> None:
    """Relit le flux de log d'un conteneur en continu et appelle `emit(ligne)`."""
    conn = None
    try:
        conn = http_unix_connection(DOCKER_SOCKET)
        conn.request("GET", f"/containers/{container}/logs?stdout=1&stderr=1&follow=1&tail=50")
        response = conn.getresponse()
        if response.status >= 400:
            emit(f"⚠️  Docker a répondu {response.status} pour {container}")
            return
        buffer = b""
        while True:
            chunk = response.read(512)
            if not chunk:
                break
            buffer += chunk
            while len(buffer) >= 8:
                size = int.from_bytes(buffer[4:8], "big")
                if len(buffer) < 8 + size:
                    break
                line = buffer[8:8 + size].decode("utf-8", "replace").rstrip("\n")
                buffer = buffer[8 + size:]
                if line:
                    emit(line)
    except Exception as e:
        emit(f"⚠️  Suivi des logs {container} interrompu : {e}")
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Statistiques
# --------------------------------------------------------------------------- #
def _directory_size(path) -> Optional[int]:
    if not path.exists():
        return None
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def collect_stats(manager) -> dict:
    """Agrège les métriques de diagnostic de l'application."""
    from ...db import db, get_db_type, get_history_summary

    heartbeat = None
    if HEARTBEAT_FILE.exists():
        try:
            with open(HEARTBEAT_FILE, "r", encoding="utf-8") as handle:
                heartbeat = json.load(handle)
        except Exception:
            heartbeat = {"status": "illisible"}

    chroma_size = _directory_size(CHROMA_DIR)
    try:
        sessions = len(manager.sessions) if manager else 0
    except Exception:
        sessions = 0

    return {
        "generated_at": datetime.now(PARIS_TZ).isoformat(),
        "uptime_seconds": round(time.time() - _STARTED_AT, 1),
        "api": {
            "sessions_jeu": sessions,
            "admin_sessions_actives": len(_sessions),
            "action_en_cours": _action_running,
        },
        "base": {
            "moteur": get_db_type(),
            "pool": db.pool_stats(),
            "solde": get_history_summary(),
        },
        "demon": heartbeat,
        "index": {
            "chroma_existe": CHROMA_DIR.exists(),
            "chroma_octets": chroma_size,
            "chroma_mega_octets": round(chroma_size / 1048576, 1) if chroma_size else 0,
        },
        "conteneurs": ADMIN_CONTAINERS,
    }


# --------------------------------------------------------------------------- #
# Actions longues (thread dédié, jamais dans la requête HTTP)
# --------------------------------------------------------------------------- #
class _SolveArgs:
    """Arguments minimaux pour `run_daily_solver` depuis la console d'admin."""
    max_tries = 300
    retrieve = 60
    rag_words = 3
    llm_words = 6
    rag_only = True
    delay = 0.25
    verbose = False
    seeds = ""
    seeds_file = ""
    seed_count = 12
    static_seeds = False
    mock = False
    secret = None
    benchmark = 0
    store = None


def action_solve(manager=None) -> None:
    """Ordonne au conteneur worker d'exécuter la résolution immédiate."""
    from ...services.daemon import DAEMON_COMMAND_FILE
    order = {"action": "solve", "requested_at": time.time()}
    try:
        DAEMON_COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)
        DAEMON_COMMAND_FILE.write_text(json.dumps(order), encoding="utf-8")
        log("⚡  [ADMIN] Ordre de résolution transmis au worker via cemantix_data/daemon_command.json")
    except Exception as e:
        log(f"⚠️  [ADMIN] Impossible d'écrire l'ordre pour le worker ({e}), repli exécution locale.", level="WARNING")
        from ...services.daemon import run_daily_solver
        args = _SolveArgs()
        if manager and getattr(manager, "store", None):
            args.store = manager.store
        run_daily_solver(args)


def action_chroma_rebuild(manager=None) -> None:
    """Supprime l'index vectoriel puis le régénère intégralement."""
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
        log(f"🛠️  [ADMIN] Index ChromaDB supprimé : {CHROMA_DIR}")
    from ...engine import VocabStore
    store = VocabStore(with_chroma=True)
    if store.col is None:
        log("🛠️  [ADMIN] Reconstruction ChromaDB impossible : moteur indisponible", level="ERROR")
    else:
        log(f"🛠️  [ADMIN] Index ChromaDB reconstruit : {store.col.count()} lemmes")


def action_export(manager=None) -> None:
    from ...services.web import export_web_data
    from .system import invalidate_system_cache
    export_web_data()
    invalidate_system_cache()


_ACTIONS = {
    "solve": action_solve,
    "chroma": action_chroma_rebuild,
    "export": action_export,
}


def _launch_action(name: str, target, manager=None) -> tuple[dict, int]:
    """Démarre une action dans un thread, une seule à la fois (verrou global)."""
    global _action_running
    with _action_lock:
        if _action_running:
            return {"error": f"Une action est déjà en cours : {_action_running}"}, 409
        _action_running = name

    def _runner():
        global _action_running
        try:
            log(f"🛠️  [ADMIN] Action démarrée : {name}")
            target(manager)
            log(f"🛠️  [ADMIN] Action terminée : {name}")
        except Exception as e:
            log(f"🛠️  [ADMIN] Action en échec ({name}) : {e}", level="ERROR")
        finally:
            with _action_lock:
                _action_running = None

    threading.Thread(target=_runner, name=f"CemantixAdmin-{name}", daemon=True).start()
    return {"accepted": True, "action": name, "message": f"Action « {name} » lancée."}, 202


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
def _parse_query(query: str) -> dict:
    parsed = urllib.parse.parse_qs(query)
    return {key: values[0] for key, values in parsed.items() if values}


def handle_admin_get(manager, path: str, query: str, headers, send_json, send_sse) -> None:
    """Route les GET d'administration.

    `send_json(payload, status)` et `send_sse(producer)` sont fournis par le
    serveur : le contrôleur ne connaît rien de la couche HTTP.
    """
    sub = path[len(ADMIN_BASE_PATH):].strip("/")
    params = _parse_query(query)

    if not _admin_password():
        send_json({"error": "Console d'administration désactivée (ADMIN_PASSWORD absent)"}, 403)
        return
    if not authorize(headers, params):
        send_json({"error": "Authentification requise"}, 401)
        return

    if sub == "stats":
        send_json(collect_stats(manager), 200)
    elif sub == "logs":
        source = params.get("source", "app")
        try:
            tail = min(int(params.get("tail", "200")), 2000)
        except ValueError:
            tail = 200
        if source == "app":
            lines = recent_logs(tail)
        elif source in ADMIN_CONTAINERS:
            lines = container_logs(ADMIN_CONTAINERS[source], tail)
        else:
            send_json({"error": f"Source inconnue : {source}"}, 400)
            return
        send_json({"source": source, "lines": lines, "count": len(lines)}, 200)
    elif sub == "logs/stream":
        source = params.get("source", "app")
        container = ADMIN_CONTAINERS.get(source)

        def _produce(emit):
            if container:
                container_log_stream(container, emit)
                return
            emit("Suivi en direct de la console applicative…")
            last_seq = 0
            # Charge d'abord l'historique récent
            for line in recent_logs(100):
                emit(line)
            last_seq, _ = logs_since(0)
            while True:
                last_seq, new_lines = logs_since(last_seq)
                for line in new_lines:
                    emit(line)
                time.sleep(0.25)

        send_sse(_produce)
    elif sub == "whitelist":
        from ...db import get_whitelist
        send_json({"entries": get_whitelist()}, 200)
    elif sub == "whoami":
        send_json({"ok": True, "expires_in": int(ADMIN_TOKEN_TTL)}, 200)
    else:
        send_json({"error": "Route introuvable"}, 404)


def handle_admin_post(manager, path: str, data: dict, headers, client_ip: str) -> tuple[dict, int]:
    """Route les POST d'administration.

    `/auth` est le seul point public (fortement limité en débit) ; tout le reste
    exige le jeton signé.
    """
    sub = path[len(ADMIN_BASE_PATH):].strip("/")

    if not _admin_password():
        return {"error": "Console d'administration désactivée (ADMIN_PASSWORD absent)"}, 403

    if sub == "auth":
        allowed, retry = _login_limiter.allow(client_ip)
        if not allowed:
            return {"error": "Trop de tentatives, réessayez dans quelques minutes.",
                    "retry_after": round(retry, 1)}, 429
        supplied = str((data or {}).get("password", ""))
        if not hmac.compare_digest(supplied, _admin_password()):
            log("🛡️  [ADMIN] Tentative d'authentification refusée", level="WARNING")
            return {"error": "Mot de passe incorrect"}, 401
        log("🛡️  [ADMIN] Authentification réussie")
        return {"token": _issue_token(), "expires_in": int(ADMIN_TOKEN_TTL)}, 200

    if not authorize(headers):
        return {"error": "Authentification requise"}, 401

    allowed, retry = _api_limiter.allow(client_ip)
    if not allowed:
        return {"error": "Trop de requêtes.", "retry_after": round(retry, 1)}, 429

    if sub.startswith("actions/"):
        name = sub.split("/", 1)[1]
        action = _ACTIONS.get(name)
        if not action:
            return {"error": f"Action inconnue : {name}"}, 404
        return _launch_action(name, action, manager)

    if sub == "whitelist":
        from ...db import add_whitelist_ip, get_whitelist
        ip_value = str((data or {}).get("ip_address", "")).strip()
        if not _valid_ip(ip_value):
            return {"error": "Adresse IP invalide (IPv4 ou IPv6 attendue)."}, 400
        add_whitelist_ip(ip_value, str((data or {}).get("description", "")))
        log("🛡️  [ADMIN] Whitelist des défis au bot : adresse ajoutée")
        return {"ok": True, "entries": get_whitelist()}, 200

    return {"error": "Route introuvable"}, 404


# --------------------------------------------------------------------------- #
# Whitelist des défis au bot (DEFI-18) — suppression
# --------------------------------------------------------------------------- #
def _valid_ip(value: str) -> bool:
    """IPv4 ou IPv6 exacte, sinon rien n'entre dans la whitelist."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def handle_admin_delete(manager, path: str, headers, client_ip: str) -> tuple[dict, int]:
    """`DELETE <ADMIN_BASE_PATH>/whitelist/<ip>` : retire une exemption de quota."""
    sub = path[len(ADMIN_BASE_PATH):].strip("/")

    if not _admin_password():
        return {"error": "Console d'administration désactivée (ADMIN_PASSWORD absent)"}, 403
    if not authorize(headers):
        return {"error": "Authentification requise"}, 401

    allowed, retry = _api_limiter.allow(client_ip)
    if not allowed:
        return {"error": "Trop de requêtes.", "retry_after": round(retry, 1)}, 429

    if sub.startswith("whitelist/"):
        from ...db import get_whitelist, remove_whitelist_ip
        ip_value = urllib.parse.unquote(sub.split("/", 1)[1])
        if not _valid_ip(ip_value):
            return {"error": "Adresse IP invalide (IPv4 ou IPv6 attendue)."}, 400
        removed = remove_whitelist_ip(ip_value)
        if removed:
            log("🛡️  [ADMIN] Whitelist des défis au bot : adresse retirée")
        return {"ok": bool(removed), "entries": get_whitelist()}, (200 if removed else 404)

    return {"error": "Route introuvable"}, 404

