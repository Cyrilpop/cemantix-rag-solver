-- ============================================================================
-- Cémantix Solver — Schéma Relationnel PostgreSQL
-- ============================================================================

-- 1. Table des résolutions quotidiennes du solveur RAG / Hybride
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

-- 2. Table des salons multijoueurs 1v1 (avec index d'expiration)
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

-- 3. Table des sessions Solo / Défi libre
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
