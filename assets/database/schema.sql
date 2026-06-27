-- Itsumi-pycord Consolidated Schema

-- Backflip streaks
CREATE TABLE IF NOT EXISTS backflips (
    user_id INTEGER,
    guild_id INTEGER,
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, guild_id)
);

-- Russian Roulette stats
CREATE TABLE IF NOT EXISTS roulette (
    user_id INTEGER,
    guild_id INTEGER,
    survived INTEGER DEFAULT 0,
    died INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, guild_id)
);

-- Moderation Cases
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    type TEXT,
    user_id INTEGER,
    user_name TEXT,
    moderator_id INTEGER,
    moderator_name TEXT,
    reason TEXT,
    duration TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    v_id TEXT,
    r_id TEXT,
    log_message_id INTEGER
);

-- Guild Settings
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER,
    key TEXT,
    value TEXT,
    PRIMARY KEY (guild_id, key)
);

-- Tags
CREATE TABLE IF NOT EXISTS tags (
    guild_id INTEGER,
    name TEXT,
    content TEXT,
    creator_id INTEGER,
    creator_name TEXT,
    uses INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_embed INTEGER DEFAULT 0,
    thumbnail_url TEXT,
    PRIMARY KEY (guild_id, name)
);

-- Permission Levels (Legacy Role/User -> Level)
CREATE TABLE IF NOT EXISTS permissions (
    guild_id INTEGER,
    entity_id INTEGER,
    entity_type TEXT, -- 'ROLE' or 'USER'
    level INTEGER,     -- 0: Everyone, 1: Helper, 2: Mod, 3: Admin, 4: Owner
    PRIMARY KEY (guild_id, entity_id)
);

-- Security Groups (v5 Overlord)
CREATE TABLE IF NOT EXISTS security_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    name TEXT,
    permissions_bitfield INTEGER DEFAULT 0,
    color INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Group Members (v5 Overlord)
CREATE TABLE IF NOT EXISTS group_members (
    group_id INTEGER,
    guild_id INTEGER,
    entity_id INTEGER,
    entity_type TEXT, -- 'ROLE' or 'USER'
    PRIMARY KEY (group_id, entity_id),
    FOREIGN KEY (group_id) REFERENCES security_groups(id) ON DELETE CASCADE
);

-- Permission Overrides (Command Node -> Level)
CREATE TABLE IF NOT EXISTS perm_overrides (
    guild_id INTEGER,
    node TEXT,
    required_level INTEGER,
    PRIMARY KEY (guild_id, node)
);

-- Message Logs (Forensic)
CREATE TABLE IF NOT EXISTS message_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    channel_id INTEGER,
    message_id INTEGER,
    author_id INTEGER,
    content TEXT,
    attachments TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT -- 'DELETE' or 'EDIT'
);

-- Member Logs (Forensic)
CREATE TABLE IF NOT EXISTS member_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    user_id INTEGER,
    event_type TEXT, -- 'JOIN', 'LEAVE', 'UPDATE'
    data TEXT,        -- JSON blob of changes
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Persistent Job Queue
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    name TEXT,
    payload TEXT,
    run_at DATETIME,
    status TEXT DEFAULT 'PENDING',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Universal Registry Snapshots (New)
CREATE TABLE IF NOT EXISTS registry_snapshots (
    id TEXT PRIMARY KEY,
    type TEXT, -- 'VIEW', 'RESPONSE', 'ERROR', 'TASK'
    guild_id INTEGER, -- Optional
    user_id INTEGER, -- Optional
    data TEXT, -- JSON blob
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indices for Massive Scale Performance
CREATE INDEX IF NOT EXISTS idx_tags_guild ON tags(guild_id);
CREATE INDEX IF NOT EXISTS idx_cases_guild ON cases(guild_id);
CREATE INDEX IF NOT EXISTS idx_cases_user ON cases(user_id);
CREATE INDEX IF NOT EXISTS idx_permissions_guild ON permissions(guild_id);
CREATE INDEX IF NOT EXISTS idx_message_logs_msg ON message_logs(message_id);
CREATE INDEX IF NOT EXISTS idx_registry_type ON registry_snapshots(type);
CREATE INDEX IF NOT EXISTS idx_registry_guild ON registry_snapshots(guild_id);

