-- M2-A1 production memory stack schema (PostgreSQL + pgvector).
-- Shadow mode only. Do not apply to live Neena memory backend without owner approval.
-- Local dev defaults pair with docker-compose.memory.yml when Docker is available.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS neena_memories (
    id BIGSERIAL PRIMARY KEY,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    owner_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    importance INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'owner_message',
    retention TEXT NOT NULL DEFAULT 'permanent',
    sensitivity_level TEXT NOT NULL DEFAULT 'normal',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    embedding_model TEXT,
    -- gemini-embedding-2 dim=3072; halfvec required (pgvector HNSW max 2000 for vector).
    embedding_vector halfvec(3072),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS neena_memory_events (
    id BIGSERIAL PRIMARY KEY,
    memory_id BIGINT REFERENCES neena_memories(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    user_message TEXT,
    assistant_response TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS neena_activity_logs (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    message TEXT,
    tool_name TEXT,
    status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_neena_memories_active
    ON neena_memories (owner_confirmed, retention, expires_at)
    WHERE owner_confirmed = TRUE AND retention != 'blocked';

CREATE INDEX IF NOT EXISTS idx_neena_memories_type
    ON neena_memories (memory_type);

CREATE INDEX IF NOT EXISTS idx_neena_memories_created_at
    ON neena_memories (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_neena_memory_events_memory_id
    ON neena_memory_events (memory_id);

CREATE INDEX IF NOT EXISTS idx_neena_memory_events_created_at
    ON neena_memory_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_neena_activity_logs_created_at
    ON neena_activity_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_neena_activity_logs_event_type
    ON neena_activity_logs (event_type);

-- Approximate nearest-neighbor index for shadow vector search (cosine distance).
-- halfvec_cosine_ops supports dims up to 4000; vector HNSW is capped at 2000.
CREATE INDEX IF NOT EXISTS idx_neena_memories_embedding_vector
    ON neena_memories
    USING hnsw (embedding_vector halfvec_cosine_ops)
    WHERE embedding_vector IS NOT NULL;
