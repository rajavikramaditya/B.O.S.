-- Stage M1 permanent memory schema preview only.
-- Do not run this file during M1-A.
-- Do not apply it without explicit owner approval for M1-B.

CREATE TABLE IF NOT EXISTS neena_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    owner_confirmed INTEGER NOT NULL DEFAULT 0,
    importance INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'owner_message',
    retention TEXT NOT NULL DEFAULT 'permanent',
    sensitivity_level TEXT NOT NULL DEFAULT 'normal',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    embedding_model TEXT,
    embedding_vector TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS neena_memory_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER,
    event_type TEXT NOT NULL,
    user_message TEXT,
    assistant_response TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT,
    FOREIGN KEY(memory_id) REFERENCES neena_memories(id)
);

CREATE INDEX IF NOT EXISTS idx_neena_memories_type
    ON neena_memories(memory_type);

CREATE INDEX IF NOT EXISTS idx_neena_memories_retention
    ON neena_memories(retention);

CREATE INDEX IF NOT EXISTS idx_neena_memories_sensitivity
    ON neena_memories(sensitivity_level);

CREATE INDEX IF NOT EXISTS idx_neena_memories_expires_at
    ON neena_memories(expires_at);

CREATE INDEX IF NOT EXISTS idx_neena_memory_events_memory_id
    ON neena_memory_events(memory_id);
