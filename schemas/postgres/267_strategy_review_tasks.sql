-- ============================================================
-- 267_strategy_review_tasks.sql
-- Durable scheduled strategy reviews and adaptation decisions.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_review_task (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    review_type VARCHAR(30) NOT NULL CHECK (review_type IN ('scheduled', 'kpi_breach', 'risk_change', 'assumption_failure', 'coherence_breach', 'portfolio_variance')),
    due_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'overdue', 'cancelled')),
    assigned_to_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    decision VARCHAR(20) CHECK (decision IN ('continue', 'adapt', 'stop', 'replace', 'scale', 'defer', 'investigate')),
    decision_note TEXT,
    evidence JSONB NOT NULL DEFAULT '{}',
    completed_at TIMESTAMPTZ,
    completed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status <> 'completed' OR completed_at IS NOT NULL),
    CHECK (status <> 'completed' OR completed_by_party_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_strategy_review_due
    ON strategy_review_task(status, due_at);
CREATE INDEX IF NOT EXISTS idx_strategy_review_plan
    ON strategy_review_task(strategy_plan_id, status, due_at);

DROP TRIGGER IF EXISTS trg_strategy_review_task_updated_at ON strategy_review_task;
CREATE TRIGGER trg_strategy_review_task_updated_at BEFORE UPDATE ON strategy_review_task
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE strategy_review_task IS 'Durable scheduled and trigger-based strategy review work requiring an explicit adaptation decision';
