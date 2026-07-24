-- Explicit scheduler run ownership and stale-worker protection.

ALTER TABLE scheduled_task
    ADD COLUMN IF NOT EXISTS lease_token UUID;

ALTER TABLE task_run
    ADD COLUMN IF NOT EXISTS lease_token UUID,
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_task_run_lease
    ON task_run (lease_token)
    WHERE status = 'running';
