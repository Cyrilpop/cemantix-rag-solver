"""
Cémantix Solver — Couche d'Accès aux Données & Connexion Thread-Safe
====================================================================
Gestionnaire centralisé de connexion aux bases de données :
- Connexion native PostgreSQL via psycopg 3 avec row_factory=dict_row.
- Repli gracieux et automatique sur SQLite local si PostgreSQL n'est pas configuré
  ou temporairement inaccessible (environnements de tests / hors conteneur).
- Gestionnaire de transactions et exécutions thread-safe.
- Normalisation transparente des requêtes SQL et types JSON/JSONB.
"""
import json
import os
import sqlite3
import threading
import time
import weakref
from contextlib import closing, contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional



from ..config import DATA_DIR, log

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False
    Jsonb = None

# Variables de configuration
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", str(DATA_DIR / "cemantix.sqlite3")))

# --- Pool de connexions (PERF-06) ---------------------------------------------
# Le serveur HTTP (`ThreadingHTTPServer`) crée **un thread OS par requête**. Sans
# pool, chaque requête ouvrait sa propre connexion PostgreSQL, conservée à jamais :
# la fuite menait à l'épuisement des `max_connections` du serveur.
# `DB_POOL_MAX` borne le nombre de connexions ouvertes ; `DB_POOL_TIMEOUT` est le
# délai maximal d'attente lorsqu'elles sont toutes occupées.
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "8"))
DB_POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "10"))
# Une connexion réutilisée moins de `DB_CONN_MAX_IDLE` secondes après son dernier
# usage est considérée valide sans vérification réseau (PERF-06b : le `SELECT 1`
# systématique coûtait un aller-retour par appel, donc deux par requête).
DB_CONN_MAX_IDLE = float(os.getenv("DB_CONN_MAX_IDLE", "30"))

# Schémas DDL
PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_puzzles (
    date DATE PRIMARY KEY,
    puzzle_id INT NOT NULL,
    secret_word VARCHAR(100) NOT NULL,
    tries_count INT NOT NULL,
    attempts_count INT NOT NULL,
    source VARCHAR(20) DEFAULT 'rag',
    duration_seconds NUMERIC(6, 2),
    win BOOLEAN DEFAULT TRUE,
    top_guesses JSONB NOT NULL DEFAULT '[]'::jsonb,
    trajectory JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_revealed BOOLEAN DEFAULT FALSE,
    solved_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_puzzle_hints (
    id SERIAL PRIMARY KEY,
    puzzle_date DATE NOT NULL REFERENCES daily_puzzles(date) ON DELETE CASCADE,
    tier VARCHAR(8) NOT NULL,
    word VARCHAR(100) NOT NULL,
    score NUMERIC(6, 2) NOT NULL,
    is_revealed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(puzzle_date, word)
);
CREATE INDEX IF NOT EXISTS idx_daily_hints_date ON daily_puzzle_hints(puzzle_date);

CREATE TABLE IF NOT EXISTS multi_rooms (
    room_id VARCHAR(16) PRIMARY KEY,
    mode VARCHAR(32) NOT NULL DEFAULT 'same_word',
    difficulty VARCHAR(16) NOT NULL DEFAULT 'moyen',
    state VARCHAR(32) NOT NULL DEFAULT 'in_progress',
    player1_key VARCHAR(32) NOT NULL,
    player2_key VARCHAR(32) NOT NULL,
    current_turn VARCHAR(4) NOT NULL DEFAULT 'p1',
    winner VARCHAR(4),
    p1_data JSONB NOT NULL,
    p2_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_multi_rooms_updated ON multi_rooms(updated_at);

CREATE TABLE IF NOT EXISTS solo_sessions (
    game_id VARCHAR(64) PRIMARY KEY,
    puzzle_id VARCHAR(32),
    difficulty VARCHAR(16),
    mode VARCHAR(32),
    secret_word VARCHAR(100) NOT NULL,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_solo_sessions_updated ON solo_sessions(updated_at);

CREATE TABLE IF NOT EXISTS bot_challenges (
    id VARCHAR(32) PRIMARY KEY,
    secret_word VARCHAR(64) NOT NULL,
    ip_hash CHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'queued',
    tries_count INT NOT NULL DEFAULT 0,
    duration_seconds NUMERIC(8, 2),
    max_tries INT NOT NULL DEFAULT 100,
    trajectory JSONB NOT NULL DEFAULT '[]'::jsonb,
    error VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_bot_challenges_queue ON bot_challenges (status, created_at);
CREATE INDEX IF NOT EXISTS idx_bot_challenges_ip ON bot_challenges (ip_hash, created_at);

CREATE TABLE IF NOT EXISTS bot_challenge_whitelist (
    ip_address VARCHAR(45) PRIMARY KEY,
    description VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_puzzles (
    date TEXT PRIMARY KEY,
    puzzle_id INTEGER NOT NULL,
    secret_word TEXT NOT NULL,
    tries_count INTEGER NOT NULL,
    attempts_count INTEGER NOT NULL,
    source TEXT DEFAULT 'rag',
    duration_seconds REAL,
    win BOOLEAN DEFAULT 1,
    top_guesses TEXT NOT NULL DEFAULT '[]',
    trajectory TEXT NOT NULL DEFAULT '[]',
    is_revealed BOOLEAN DEFAULT 0,
    solved_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_puzzle_hints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    puzzle_date TEXT NOT NULL REFERENCES daily_puzzles(date) ON DELETE CASCADE,
    tier TEXT NOT NULL,
    word TEXT NOT NULL,
    score REAL NOT NULL,
    is_revealed BOOLEAN DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(puzzle_date, word)
);
CREATE INDEX IF NOT EXISTS idx_daily_hints_date ON daily_puzzle_hints(puzzle_date);

CREATE TABLE IF NOT EXISTS multi_rooms (
    room_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT 'same_word',
    difficulty TEXT NOT NULL DEFAULT 'moyen',
    state TEXT NOT NULL DEFAULT 'in_progress',
    player1_key TEXT NOT NULL,
    player2_key TEXT NOT NULL,
    current_turn TEXT NOT NULL DEFAULT 'p1',
    winner TEXT,
    p1_data TEXT NOT NULL,
    p2_data TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_multi_rooms_updated ON multi_rooms(updated_at);

CREATE TABLE IF NOT EXISTS solo_sessions (
    game_id TEXT PRIMARY KEY,
    puzzle_id TEXT,
    difficulty TEXT,
    mode TEXT,
    secret_word TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_solo_sessions_updated ON solo_sessions(updated_at);

CREATE TABLE IF NOT EXISTS bot_challenges (
    id VARCHAR(32) PRIMARY KEY,
    secret_word VARCHAR(64) NOT NULL,
    ip_hash CHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'queued',
    tries_count INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL,
    max_tries INTEGER NOT NULL DEFAULT 100,
    trajectory TEXT NOT NULL DEFAULT '[]',
    error VARCHAR(200),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    finished_at TEXT,
    heartbeat_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_bot_challenges_queue ON bot_challenges (status, created_at);
CREATE INDEX IF NOT EXISTS idx_bot_challenges_ip ON bot_challenges (ip_hash, created_at);

CREATE TABLE IF NOT EXISTS bot_challenge_whitelist (
    ip_address VARCHAR(45) PRIMARY KEY,
    description VARCHAR(100),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class DatabaseManager:
    """Gestionnaire de connexion thread-safe avec support Postgres et SQLite."""

    def __init__(self):
        self._local = threading.local()
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        # Connexions libres, prêtes à être réutilisées : [(connexion, horodatage)]
        self._pool: list = []
        # Connexions prêtées : id(connexion) -> (connexion, identifiant du thread emprunteur)
        self._in_use: dict = {}
        self._all_conns = set()
        self._engine_type: Optional[str] = None
        self._initialized = False

    # --- Pool de connexions (PERF-06) -----------------------------------------

    @staticmethod
    def _owner_ref():
        """Référence faible sur le thread courant, qui sert d'emprunteur."""
        return weakref.ref(threading.current_thread())

    def _reclaim_dead_threads(self) -> int:
        """Récupère les connexions dont le thread emprunteur est mort.

        C'est ce qui ferme la fuite : un thread de requête meurt une fois la
        réponse envoyée, sa connexion redevient donc disponible au lieu d'être
        retenue indéfiniment. Retourne le nombre de connexions récupérées.

        L'emprunteur est suivi par référence faible à l'objet `Thread` : un
        identifiant de thread (`get_ident()`) est **réutilisable** après la mort
        du thread, ce qui ferait passer une connexion encore utilisée pour
        orpheline et provoquerait un double prêt.
        """
        if not self._in_use:
            return 0
        recovered = 0
        with self._cond:
            for key in list(self._in_use.keys()):
                entry = self._in_use.get(key)
                if entry is None:
                    continue
                conn, owner_ref = entry
                owner = owner_ref()
                if owner is not None and owner.is_alive():
                    continue
                del self._in_use[key]
                if len(self._pool) < DB_POOL_MAX:
                    self._pool.append((conn, self._now()))
                else:
                    self._discard(conn)
                recovered += 1
            if recovered:
                self._cond.notify_all()
        return recovered

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    def _discard(self, conn) -> None:
        """Ferme une connexion et la retire de tous les registres."""
        try:
            conn.close()
        except Exception:
            pass
        with self._lock:
            self._all_conns.discard(conn)
            self._in_use.pop(id(conn), None)

    def _conn_is_sane(self, conn, engine: str) -> bool:
        """Valide une connexion, sans coût réseau si elle vient d'être utilisée."""
        try:
            if engine == "postgres":
                if conn.closed:
                    return False
                # Une transaction laissée ouverte par un thread mort rendrait la
                # connexion inutilisable : on la rouvre avant de la prêter.
                if HAS_PSYCOPG and conn.info.transaction_status.name != "IDLE":
                    conn.rollback()
            if self._idle_seconds(conn) < DB_CONN_MAX_IDLE:
                return True  # déjà validée récemment : pas de SELECT 1 (PERF-06b)
            conn.execute("SELECT 1;")
            return True
        except Exception:
            return False

    def _idle_seconds(self, conn) -> float:
        """Temps écoulé depuis la dernière utilisation de cette connexion."""
        return self._now() - getattr(conn, "_cemantix_last_used", self._now())

    def _touch(self, conn) -> None:
        try:
            conn._cemantix_last_used = self._now()
        except Exception:
            pass

    def _create_connection(self, engine: str):
        return self._connect_postgres() if engine == "postgres" else self._connect_sqlite()


    def _determine_engine(self) -> str:
        """Détermine si PostgreSQL est disponible et configuré, sinon sélectionne SQLite."""
        if self._engine_type is not None:
            return self._engine_type

        db_url = os.getenv("DATABASE_URL")
        db_host = os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")

        # Vérification si PostgreSQL est configuré dans l'environnement
        has_pg_config = bool(db_url or (db_host and db_name and db_user))
        if has_pg_config and HAS_PSYCOPG:
            try:
                conn = self._connect_postgres()
                conn.close()
                self._engine_type = "postgres"
                log("🐘  [BASE DE DONNÉES] Connexion PostgreSQL 16/17 établie avec succès.")
                return self._engine_type
            except Exception as e:
                log(f"⚠️  [BASE DE DONNÉES] Impossible de joindre PostgreSQL ({e}). Bascule sur SQLite.")

        self._engine_type = "sqlite"
        log("📁  [BASE DE DONNÉES] Mode local SQLite actif (persistance locale).")
        return self._engine_type

    def _connect_postgres(self):
        """Crée une nouvelle connexion PostgreSQL."""
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return psycopg.connect(db_url, row_factory=dict_row)
        return psycopg.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", "5432")),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS", ""),
            row_factory=dict_row,
        )


    def _connect_sqlite(self):
        """Crée une nouvelle connexion SQLite."""
        db_path = Path(os.getenv("SQLITE_PATH", str(DATA_DIR / "cemantix.sqlite3")))
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Activation des fonctionnalités clés SQLite
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def get_connection(self):
        """Retourne une connexion du pool, liée au thread courant.

        Avant ce correctif (PERF-06), chaque thread ouvrait SA connexion et la
        gardait jusqu'à la fin du processus. Comme `ThreadingHTTPServer` crée un
        thread par requête, le nombre de connexions PostgreSQL ouvertes croissait
        indéfiniment. Elles sont désormais **empruntées, réutilisées et récupérées**.
        """
        engine = self._determine_engine()
        conn = getattr(self._local, "conn", None)

        if conn is not None:
            if self._conn_is_sane(conn, engine):
                self._touch(conn)
                return conn
            self._release(conn)
            self._local.conn = None

        # Les threads de requête meurent après la réponse : on récupère d'abord
        # leurs connexions, sinon le pool se saturerait pour rien.
        self._reclaim_dead_threads()

        deadline = self._now() + DB_POOL_TIMEOUT
        with self._cond:
            while True:
                if self._pool:
                    candidate, _ts = self._pool.pop(0)
                    if self._conn_is_sane(candidate, engine):
                        conn = candidate
                        self._in_use[id(conn)] = (conn, self._owner_ref())
                        break
                    self._discard(candidate)
                    continue
                if len(self._in_use) + len(self._pool) < DB_POOL_MAX:
                    conn = self._create_connection(engine)
                    self._all_conns.add(conn)
                    self._in_use[id(conn)] = (conn, self._owner_ref())
                    break
                # Pool plein : les threads prêteurs sont peut-être morts sans avoir
                # rendu leur connexion. On le vérifie à chaque tour, sinon un thread
                # en attende resterait bloqué alors que tout est libre.
                self._reclaim_dead_threads()
                if self._pool or len(self._in_use) + len(self._pool) < DB_POOL_MAX:
                    continue
                remaining = deadline - self._now()
                if remaining <= 0:
                    raise RuntimeError(
                        f"Pool de connexions saturé ({DB_POOL_MAX}) après {DB_POOL_TIMEOUT}s d'attente"
                    )
                self._cond.wait(remaining)

        self._local.conn = conn
        self._touch(conn)
        return conn

    def release_connection(self, conn=None) -> None:
        """Rend volontairement une connexion au pool.

        Facultatif : les connexions des threads morts sont récupérées automatiquement.
        À appeler par un code longue durée (worker, démon) qui veut libérer sa
        connexion entre deux tâches.
        """
        conn = conn or getattr(self._local, "conn", None)
        if conn is None:
            return
        self._release(conn)
        self._local.conn = None

    def _release(self, conn) -> None:
        with self._cond:
            if self._in_use.pop(id(conn), None) is None:
                # La connexion a déjà été récupérée (thread considéré mort) : la
                # remettre au pool créerait un second prêt de la même connexion.
                return
            if self._conn_is_sane(conn, self._determine_engine()) and len(self._pool) < DB_POOL_MAX:
                self._pool.append((conn, self._now()))
            else:
                self._discard(conn)
            self._cond.notify_all()

    def pool_stats(self) -> dict:
        """État du pool — utilisé par les tests et le diagnostic."""
        with self._lock:
            return {
                "idle": len(self._pool),
                "in_use": len(self._in_use),
                "opened_total": len(self._all_conns),
                "max": DB_POOL_MAX,
            }

    def get_engine_type(self) -> str:
        return self._determine_engine()

    def reset(self):
        """Réinitialise les connexions et l'état de l'engine (utile pour les tests)."""
        with self._lock:
            for c in list(self._all_conns):
                try:
                    c.close()
                except Exception:
                    pass
            self._all_conns.clear()
            self._pool.clear()
            self._in_use.clear()
            self._local.conn = None
            self._engine_type = None
            self._initialized = False


    def init_db(self):
        """Initialise les tables de la base de données si elles n'existent pas encore."""
        with self._lock:
            if self._initialized:
                return
            engine = self._determine_engine()
            schema = PG_SCHEMA if engine == "postgres" else SQLITE_SCHEMA
            conn = self.get_connection()
            try:
                if engine == "postgres":
                    with closing(conn.cursor()) as cur:
                        cur.execute(schema)
                    conn.commit()

                else:
                    conn.executescript(schema)
                    conn.commit()
                self._initialized = True
            except Exception as e:
                log(f"⚠️  Erreur initialisation schéma base de données : {e}")
                raise
            finally:
                # Le thread qui initialise ne doit pas rester propriétaire d'une
                # connexion du pool : il peut ne plus rien demander ensuite.
                self.release_connection(conn)

    @contextmanager
    def transaction(self):
        """Gestionnaire de transaction atomique thread-safe.

        La connexion est rendue au pool à la sortie du bloc : un appelant ne doit
        donc pas continuer à l'utiliser après le `with`.
        """
        self.init_db()
        conn = self.get_connection()
        engine = self._determine_engine()
        try:
            with self._lock if engine == "sqlite" else nullcontext():
                try:
                    yield conn
                    conn.commit()
                except Exception:
                    try:
                        conn.rollback()
                    except Exception as rollback_error:
                        # Un rollback qui échoue laisse la connexion dans un état
                        # inconnu : _release la validera et l'écartera du pool,
                        # mais la cause racine doit rester lisible.
                        log(f"⚠️  [BASE] Rollback impossible : {rollback_error}")
                    raise
        finally:
            self.release_connection(conn)

    def execute(self, query: str, params: Optional[Any] = None) -> int:
        """Exécute une commande SQL (INSERT, UPDATE, DELETE)."""
        self.init_db()
        engine = self._determine_engine()
        formatted_query, formatted_params = self._format_query(query, params, engine)
        with self.transaction() as conn:
            with closing(conn.cursor()) as cur:
                cur.execute(formatted_query, formatted_params or ())
                return cur.rowcount

    def fetch_one(self, query: str, params: Optional[Any] = None) -> Optional[dict]:
        """Exécute une requête SELECT et retourne une seule ligne sous forme de dictionnaire."""
        self.init_db()
        engine = self._determine_engine()
        formatted_query, formatted_params = self._format_query(query, params, engine)
        conn = self.get_connection()
        try:
            with self._lock if engine == "sqlite" else nullcontext():
                with closing(conn.cursor()) as cur:
                    cur.execute(formatted_query, formatted_params or ())
                    row = cur.fetchone()
                    if not row:
                        return None
                    return self._row_to_dict(row)
        finally:
            self.release_connection(conn)

    def fetch_all(self, query: str, params: Optional[Any] = None) -> list[dict]:
        """Exécute une requête SELECT et retourne l'ensemble des lignes."""
        self.init_db()
        engine = self._determine_engine()
        formatted_query, formatted_params = self._format_query(query, params, engine)
        conn = self.get_connection()
        try:
            with self._lock if engine == "sqlite" else nullcontext():
                with closing(conn.cursor()) as cur:
                    cur.execute(formatted_query, formatted_params or ())
                    rows = cur.fetchall()
                    return [self._row_to_dict(r) for r in rows]
        finally:
            self.release_connection(conn)


    def _format_query(self, query: str, params: Optional[Any], engine: str) -> tuple[str, Any]:
        """Adapte les requêtes et paramètres au moteur actif (Postgres ou SQLite)."""
        if engine == "sqlite":
            query = query.replace("%s", "?")
            if params is not None:
                new_params = []
                for p in params:
                    if isinstance(p, (dict, list)):
                        new_params.append(json.dumps(p, ensure_ascii=False))
                    elif Jsonb and isinstance(p, Jsonb):
                        new_params.append(json.dumps(p.obj, ensure_ascii=False))
                    elif isinstance(p, datetime):
                        new_params.append(p.isoformat())
                    else:
                        new_params.append(p)
                return query, tuple(new_params)
            return query, ()
        else:
            # PostgreSQL
            if params is not None:
                new_params = []
                for p in params:
                    if isinstance(p, (dict, list)):
                        new_params.append(Jsonb(p) if Jsonb else json.dumps(p))
                    else:
                        new_params.append(p)
                return query, tuple(new_params)
            return query, ()

    def _row_to_dict(self, row: Any) -> dict:
        """Convertit une ligne (sqlite3.Row ou dict_row) en dictionnaire standard."""
        d = dict(row)
        # Décodage transparent des champs JSON pour SQLite
        for k, v in d.items():
            if isinstance(v, str) and (v.startswith("{") or v.startswith("[")):
                try:
                    d[k] = json.loads(v)
                except Exception:
                    pass
        return d


# Instance singleton
db = DatabaseManager()


def init_db():
    db.init_db()


def get_db_type() -> str:
    return db.get_engine_type()
