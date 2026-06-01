-- Usuários (populados via Discord OAuth)
CREATE TABLE IF NOT EXISTS users (
    discord_id  TEXT PRIMARY KEY,
    username    TEXT NOT NULL,
    avatar_url  TEXT,
    is_admin    BOOLEAN NOT NULL DEFAULT FALSE
);

-- Personagens de cada usuário (pode ter vários)
CREATE TABLE IF NOT EXISTS characters (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  TEXT NOT NULL REFERENCES users(discord_id) ON DELETE CASCADE,
    name     TEXT NOT NULL,
    class    TEXT
);

-- Parties (grupos de 4)
CREATE TABLE IF NOT EXISTS parties (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT
);

CREATE TABLE IF NOT EXISTS party_members (
    party_id  INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    user_id   TEXT    NOT NULL REFERENCES users(discord_id) ON DELETE CASCADE,
    role      TEXT    NOT NULL CHECK(role IN ('DPS','SUP','TANK')),
    PRIMARY KEY (party_id, user_id)
);

-- Horários agendados
CREATE TABLE IF NOT EXISTS schedules (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    party_id     INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    difficulty   TEXT NOT NULL CHECK(difficulty IN ('HARD','NW')),
    start_time   TEXT NOT NULL,   -- ISO-8601
    end_time     TEXT NOT NULL,   -- start_time + 3h
    status       TEXT NOT NULL DEFAULT 'pending'
                      CHECK(status IN ('pending','confirmed','rescheduled','missed','cancelled'))
);

-- Confirmações individuais por membro da party
CREATE TABLE IF NOT EXISTS schedule_confirmations (
    schedule_id  INTEGER NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    user_id      TEXT    NOT NULL REFERENCES users(discord_id) ON DELETE CASCADE,
    confirmed    BOOLEAN NOT NULL DEFAULT FALSE,
    last_ping    TEXT,   -- ISO-8601
    PRIMARY KEY (schedule_id, user_id)
);

-- Pokémons (já "capturados" — controle de quem vai usar)
CREATE TABLE IF NOT EXISTS pokemon (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    image_url    TEXT,
    category     TEXT NOT NULL CHECK(category IN ('A','B','C')),
    assigned_to  TEXT REFERENCES users(discord_id) ON DELETE SET NULL,
    assigned_at  TEXT   -- ISO-8601
);

-- Histórico geral de eventos (agendamentos, pokémons, remarcações)
CREATE TABLE IF NOT EXISTS history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id    TEXT REFERENCES users(discord_id) ON DELETE SET NULL,
    entity_type TEXT NOT NULL,   -- 'schedule' | 'pokemon' | 'party' | 'admin'
    entity_id   INTEGER,
    action      TEXT NOT NULL,   -- 'created' | 'confirmed' | 'rescheduled' | 'missed' | 'assigned' | 'unassigned' | 'overridden' | 'admin_granted' | 'admin_revoked'
    detail      TEXT,            -- JSON com contexto extra
    happened_at TEXT NOT NULL DEFAULT (datetime('now'))
);
