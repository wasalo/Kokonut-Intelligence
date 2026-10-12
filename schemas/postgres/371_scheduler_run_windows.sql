-- Opt-in dependency matching by scheduled UTC window. Legacy tasks retain
-- last-completed dependency semantics until explicitly reviewed and migrated.
ALTER TABLE scheduled_task
    ADD COLUMN dependency_mode TEXT NOT NULL DEFAULT 'last_completed'
        CHECK (dependency_mode IN ('last_completed', 'same_window')),
    ADD COLUMN run_window_at TIMESTAMPTZ;

ALTER TABLE task_run
    ADD COLUMN scheduled_for TIMESTAMPTZ;

CREATE INDEX idx_task_run_completed_window
    ON task_run (task_id, scheduled_for)
    WHERE status = 'completed' AND scheduled_for IS NOT NULL;
