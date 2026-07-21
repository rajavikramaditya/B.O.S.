-- One-brain Phase 1 — actor-scoped durable memory + soft-fade fields.
-- Safe to re-run (IF NOT EXISTS). Local/dev first; VM only with owner approve.

ALTER TABLE neena_memories
    ADD COLUMN IF NOT EXISTS actor_role TEXT NOT NULL DEFAULT 'owner';

ALTER TABLE neena_memories
    ADD COLUMN IF NOT EXISTS subject_key TEXT NOT NULL DEFAULT 'owner';

ALTER TABLE neena_memories
    ADD COLUMN IF NOT EXISTS salience DOUBLE PRECISION NOT NULL DEFAULT 1;

ALTER TABLE neena_memories
    ADD COLUMN IF NOT EXISTS last_recalled_at TIMESTAMPTZ;

ALTER TABLE neena_memories
    ADD COLUMN IF NOT EXISTS recall_count INTEGER NOT NULL DEFAULT 0;

UPDATE neena_memories
SET actor_role = 'owner'
WHERE actor_role IS NULL OR actor_role = '';

UPDATE neena_memories
SET subject_key = 'owner'
WHERE subject_key IS NULL OR subject_key = '';

CREATE INDEX IF NOT EXISTS idx_neena_memories_actor_subject
    ON neena_memories (actor_role, subject_key);
