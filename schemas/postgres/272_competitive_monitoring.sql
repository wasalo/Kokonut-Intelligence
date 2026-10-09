-- ============================================================
-- 272_competitive_monitoring.sql
-- Durable signal-to-strategy-review monitoring.
-- ============================================================

ALTER TABLE strategy_review_task DROP CONSTRAINT IF EXISTS strategy_review_task_review_type_check;
ALTER TABLE strategy_review_task ADD CONSTRAINT strategy_review_task_review_type_check
    CHECK (review_type IN ('scheduled', 'kpi_breach', 'risk_change', 'assumption_failure', 'coherence_breach', 'portfolio_variance', 'competitive_change'));

CREATE TABLE IF NOT EXISTS competitive_signal_trigger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL UNIQUE REFERENCES competitive_signal(id) ON DELETE CASCADE,
    review_task_id UUID NOT NULL REFERENCES strategy_review_task(id) ON DELETE CASCADE,
    trigger_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_competitive_signal_trigger_task ON competitive_signal_trigger(review_task_id);

COMMENT ON TABLE competitive_signal_trigger IS 'Idempotent link from material external signals to strategy review tasks';
