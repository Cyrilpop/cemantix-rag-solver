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
    google_indexed_at TIMESTAMPTZ DEFAULT NULL,
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

-- 4. File de tâches « Défier le bot » (DEFI-01) : le conteneur web enqueue,
--    le worker résout, l'API sert l'état et le direct. Aucune donnée personnelle :
--    ip_hash est un HMAC-SHA256 salé de l'IP anonymisée /24 (SEC-21).
CREATE TABLE IF NOT EXISTS bot_challenges (
    id               VARCHAR(32) PRIMARY KEY,
    secret_word      VARCHAR(64) NOT NULL,
    ip_hash          CHAR(64) NOT NULL,
    status           VARCHAR(16) NOT NULL DEFAULT 'queued',
    tries_count      INT NOT NULL DEFAULT 0,
    duration_seconds NUMERIC(8, 2),
    max_tries        INT NOT NULL DEFAULT 100,
    trajectory       JSONB NOT NULL DEFAULT '[]'::jsonb,
    error            VARCHAR(200),
    player_name      VARCHAR(64),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at       TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ,
    heartbeat_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_bot_challenges_queue ON bot_challenges (status, created_at);
CREATE INDEX IF NOT EXISTS idx_bot_challenges_ip ON bot_challenges (ip_hash, created_at);

-- 5. IPs exemptées de quota (whitelist administrable, DEFI-18)
CREATE TABLE IF NOT EXISTS bot_challenge_whitelist (
    ip_address       VARCHAR(45) PRIMARY KEY,
    description      VARCHAR(100),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. Table analytique pérenne des défis visiteurs (M8 - KPIs & Traçage)
CREATE TABLE IF NOT EXISTS bot_challenge_stats (
    id               SERIAL PRIMARY KEY,
    challenge_id     VARCHAR(32) NOT NULL UNIQUE,
    secret_word      VARCHAR(64) NOT NULL,
    player_anon_id   VARCHAR(32) NOT NULL,
    outcome          VARCHAR(16) NOT NULL, -- 'won', 'lost', 'error'
    tries_count      INT NOT NULL DEFAULT 0,
    duration_seconds NUMERIC(8, 2),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_bot_challenge_stats_word ON bot_challenge_stats(secret_word);
CREATE INDEX IF NOT EXISTS idx_bot_challenge_stats_player ON bot_challenge_stats(player_anon_id);
CREATE INDEX IF NOT EXISTS idx_bot_challenge_stats_outcome ON bot_challenge_stats(outcome);
CREATE INDEX IF NOT EXISTS idx_bot_challenge_stats_created ON bot_challenge_stats(created_at);

-- 7. Table relationnelle normalisée du chemin de résolution (M8 - Trajectoire de l'IA)
CREATE TABLE IF NOT EXISTS bot_challenge_guesses (
    id           SERIAL PRIMARY KEY,
    challenge_id VARCHAR(32) NOT NULL REFERENCES bot_challenge_stats(challenge_id) ON DELETE CASCADE,
    step_num     INT NOT NULL,
    word         VARCHAR(64) NOT NULL,
    score        NUMERIC(6, 2) NOT NULL,
    permille     INT,
    weather      VARCHAR(32),
    is_record    BOOLEAN DEFAULT FALSE,
    source       VARCHAR(16) DEFAULT 'rag',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(challenge_id, step_num)
);
CREATE INDEX IF NOT EXISTS idx_bcg_challenge ON bot_challenge_guesses(challenge_id);
CREATE INDEX IF NOT EXISTS idx_bcg_word ON bot_challenge_guesses(word);

-- 8. Table des indices IA propulsés par Google Gemini (M12 - Indices IA Gemini)
CREATE TABLE IF NOT EXISTS daily_puzzle_ai_hints (
    id SERIAL PRIMARY KEY,
    puzzle_date DATE NOT NULL REFERENCES daily_puzzles(date) ON DELETE CASCADE,
    hint_level INT NOT NULL,
    weight NUMERIC(4, 2) NOT NULL,
    hint_word VARCHAR(100) NOT NULL,
    hint_phrase TEXT NOT NULL,
    model VARCHAR(64) DEFAULT 'gemini-3.8-flash',
    is_revealed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(puzzle_date, hint_level)
);
CREATE INDEX IF NOT EXISTS idx_ai_hints_date ON daily_puzzle_ai_hints(puzzle_date);

-- 9. Table des joueurs et authentification sans email (M14)
CREATE TABLE IF NOT EXISTS players (
    id UUID PRIMARY KEY,
    auth_token VARCHAR(64) NOT NULL UNIQUE,
    username VARCHAR(32) NOT NULL UNIQUE,
    can_change_username BOOLEAN NOT NULL DEFAULT TRUE,
    is_claimed BOOLEAN NOT NULL DEFAULT FALSE,
    password_hash VARCHAR(255),
    recovery_key_hash VARCHAR(255),
    auth_provider VARCHAR(16) NOT NULL DEFAULT 'local',
    google_sub VARCHAR(64) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    renamed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_players_token ON players(auth_token);
CREATE INDEX IF NOT EXISTS idx_players_username ON players(username);
CREATE INDEX IF NOT EXISTS idx_players_google_sub ON players(google_sub);
CREATE INDEX IF NOT EXISTS idx_players_created_at ON players(created_at);

-- 10. Dictionnaire dynamique de vocabulaire pour identités & récupération (M14)
-- Types : 'noun' (Noms), 'adjective' (Adjectifs), 'recovery' (Mots de secours)
CREATE TABLE IF NOT EXISTS player_dictionary (
    id SERIAL PRIMARY KEY,
    word_type VARCHAR(16) NOT NULL,            -- 'noun', 'adjective', 'recovery'
    word VARCHAR(32) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(word_type, word)
);
CREATE INDEX IF NOT EXISTS idx_dict_type ON player_dictionary(word_type, is_active);

-- ============================================================================
-- 11. Tables du Mot du Jour Solo Aléatoire, Classement & Coups Joueurs (Jalon M15)
-- ============================================================================

-- A. Table des puzzles quotidiens Solo (mot unique du jour tiré au sort)
CREATE TABLE IF NOT EXISTS solo_daily_puzzles (
    id                SERIAL PRIMARY KEY,
    puzzle_date       DATE NOT NULL UNIQUE,
    secret_word       VARCHAR(64) NOT NULL,
    difficulty        VARCHAR(16) NOT NULL,     -- 'facile', 'normal', 'difficile', 'extreme'
    players_attempted INT NOT NULL DEFAULT 0,
    players_succeeded INT NOT NULL DEFAULT 0,
    players_failed    INT NOT NULL DEFAULT 0,
    bots_simulated    BOOLEAN NOT NULL DEFAULT FALSE, -- Lock anti-rejeu simulation faux joueurs
    bots_simulated_at TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_solo_daily_puzzles_date ON solo_daily_puzzles(puzzle_date);
CREATE INDEX IF NOT EXISTS idx_solo_daily_puzzles_diff ON solo_daily_puzzles(difficulty);

-- B. Table des indices IA Gemini roulants (1 seule journée active, purge auto à minuit)
CREATE TABLE IF NOT EXISTS solo_daily_ai_hints (
    id          SERIAL PRIMARY KEY,
    puzzle_date DATE NOT NULL REFERENCES solo_daily_puzzles(puzzle_date) ON DELETE CASCADE,
    hint_level  INT NOT NULL,                  -- 1 (éloigné), 2 (intermédiaire), 3 (proche)
    weight      NUMERIC(4, 2) NOT NULL,        -- 0.33, 0.66, 1.00
    hint_word   VARCHAR(100) NOT NULL,
    hint_phrase TEXT NOT NULL,
    score       NUMERIC(6, 2) DEFAULT 0.0,
    permille    INT DEFAULT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(puzzle_date, hint_level)
);
CREATE INDEX IF NOT EXISTS idx_solo_ai_hints_date ON solo_daily_ai_hints(puzzle_date);

-- C. Table des sessions et scores des joueurs pour le puzzle du jour
CREATE TABLE IF NOT EXISTS solo_player_games (
    id                 UUID PRIMARY KEY,
    puzzle_date        DATE NOT NULL REFERENCES solo_daily_puzzles(puzzle_date) ON DELETE CASCADE,
    player_id          UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    status             VARCHAR(16) NOT NULL DEFAULT 'in_progress', -- 'won', 'given_up'
    tries_count        INT NOT NULL DEFAULT 0,
    hints_used         INT NOT NULL DEFAULT 0,                     -- Max 3
    hints_revealed     JSONB NOT NULL DEFAULT '[]'::jsonb,         -- Détail [{level, type, content}]
    best_score         NUMERIC(6, 2) DEFAULT 0.0,
    best_permille      INT DEFAULT NULL,
    duration_seconds   NUMERIC(8, 2) DEFAULT 0.0,
    is_bot             BOOLEAN NOT NULL DEFAULT FALSE,             -- Flag admin pour faux joueurs
    won_at             TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(puzzle_date, player_id)
);
CREATE INDEX IF NOT EXISTS idx_solo_player_games_date ON solo_player_games(puzzle_date);
CREATE INDEX IF NOT EXISTS idx_solo_player_games_player ON solo_player_games(player_id);
CREATE INDEX IF NOT EXISTS idx_solo_player_games_leaderboard ON solo_player_games(puzzle_date, status, tries_count, duration_seconds);
CREATE INDEX IF NOT EXISTS idx_solo_player_games_bot ON solo_player_games(is_bot);

-- D. Table d'historisation des trajectoires de parties terminées (Gagnées ou Abandonnées)
CREATE TABLE IF NOT EXISTS solo_player_guesses (
    id          BIGSERIAL PRIMARY KEY,
    game_id     UUID NOT NULL REFERENCES solo_player_games(id) ON DELETE CASCADE,
    player_id   UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    puzzle_date DATE NOT NULL,
    guess_order INT NOT NULL,
    word        VARCHAR(64) NOT NULL,
    score       NUMERIC(6, 2) NOT NULL,
    permille    INT,
    weather     VARCHAR(32),
    is_hint     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, guess_order)
);
CREATE INDEX IF NOT EXISTS idx_solo_player_guesses_game ON solo_player_guesses(game_id);
CREATE INDEX IF NOT EXISTS idx_solo_player_guesses_player_date ON solo_player_guesses(player_id, puzzle_date);
CREATE INDEX IF NOT EXISTS idx_solo_player_guesses_word ON solo_player_guesses(word);

-- ============================================================================
-- 12. Extensions de Sécurité et Mots de Récupération Compte (Jalon M16)
-- ============================================================================

-- A. Table des mots de récupération aléatoires associés au profil joueur
CREATE TABLE IF NOT EXISTS player_recovery_words (
    id          SERIAL PRIMARY KEY,
    player_id   UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    word_hash   VARCHAR(255) NOT NULL,          -- Hash sécurisé du mot aléatoire de récupération
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, word_hash)
);
CREATE INDEX IF NOT EXISTS idx_player_recovery_words_player ON player_recovery_words(player_id);

-- B. Ajout de colonnes de suivi de sécurité dans la table players si non présentes
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='players' AND column_name='password_updated_at') THEN
        ALTER TABLE players ADD COLUMN password_updated_at TIMESTAMPTZ DEFAULT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='players' AND column_name='last_login_at') THEN
        ALTER TABLE players ADD COLUMN last_login_at TIMESTAMPTZ DEFAULT NULL;
    END IF;
END $$;





