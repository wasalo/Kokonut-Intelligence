-- ============================================================
-- 287_decision_execution_integrity.sql
-- Make approved decision execution atomic and idempotent.
-- ============================================================

ALTER TABLE decision_log DROP CONSTRAINT IF EXISTS decision_log_status_check;
ALTER TABLE decision_log ADD CONSTRAINT decision_log_status_check CHECK (
    status IN ('pending', 'approved', 'executing', 'rejected', 'executed', 'failed', 'expired')
);

CREATE INDEX IF NOT EXISTS idx_decision_log_executing
    ON decision_log(status, executed_at)
    WHERE status = 'executing';
