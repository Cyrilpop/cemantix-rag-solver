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
"""


class DatabaseManager:
    """Gestionnaire de connexion thread-safe avec support Postgres et SQLite."""

    def __init__(self):
        self._local = threading.local()
        self._lock = threading.RLock()
        self._all_conns = set()
        self._engine_type: Optional[str] = None
        self._initialized = False


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
        """Retourne la connexion dédiée au thread courant."""
        engine = self._determine_engine()
        conn = getattr(self._local, "conn", None)

        if conn is not None:
            # Vérification de validité de la connexion
            try:
                if engine == "postgres":
                    if conn.closed:
                        conn = None
                    else:
                        conn.execute("SELECT 1;")
                elif engine == "sqlite":
                    conn.execute("SELECT 1;")
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None

        if conn is None:
            if engine == "postgres":
                conn = self._connect_postgres()
            else:
                conn = self._connect_sqlite()
            self._local.conn = conn
            with self._lock:
                self._all_conns.add(conn)

        return conn

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

    @contextmanager
    def transaction(self):
        """Gestionnaire de transaction atomique thread-safe."""
        self.init_db()
        conn = self.get_connection()
        engine = self._determine_engine()
        with self._lock if engine == "sqlite" else nullcontext():
            try:
                yield conn
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise

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
        with self._lock if engine == "sqlite" else nullcontext():
            with closing(conn.cursor()) as cur:
                cur.execute(formatted_query, formatted_params or ())
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_dict(row)

    def fetch_all(self, query: str, params: Optional[Any] = None) -> list[dict]:
        """Exécute une requête SELECT et retourne l'ensemble des lignes."""
        self.init_db()
        engine = self._determine_engine()
        formatted_query, formatted_params = self._format_query(query, params, engine)
        conn = self.get_connection()
        with self._lock if engine == "sqlite" else nullcontext():
            with closing(conn.cursor()) as cur:
                cur.execute(formatted_query, formatted_params or ())
                rows = cur.fetchall()
                return [self._row_to_dict(r) for r in rows]


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
