-- ============================================================
-- 164_scheduler_durability.sql - Durable multi-worker scheduling
-- ============================================================

ALTER TABLE scheduled_task
    ADD COLUMN IF NOT EXISTS command_args JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS allow_overlap BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS lease_owner VARCHAR(100),
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS retry_attempt INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS retry_at TIMESTAMPTZ;

ALTER TABLE scheduled_task
    DROP CONSTRAINT IF EXISTS scheduled_task_command_args_array;
ALTER TABLE scheduled_task
    ADD CONSTRAINT scheduled_task_command_args_array
    CHECK (jsonb_typeof(command_args) = 'array');

ALTER TABLE task_run
    ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS allow_overlap BOOLEAN NOT NULL DEFAULT FALSE;

-- The snapshot on task_run makes non-overlap enforceable under concurrency.
CREATE UNIQUE INDEX IF NOT EXISTS uq_task_run_no_overlap
    ON task_run (task_id)
    WHERE status = 'running' AND allow_overlap = FALSE;

CREATE INDEX IF NOT EXISTS idx_scheduled_task_retry
    ON scheduled_task (retry_at)
    WHERE is_enabled = TRUE AND retry_at IS NOT NULL;
