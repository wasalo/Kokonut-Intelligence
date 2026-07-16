-- ============================================================
-- 295_sequential_decision_engine.sql
-- Posterior threshold evaluations and stopping decisions.
-- ============================================================

CREATE TABLE IF NOT EXISTS decision_threshold_evaluation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES decision_hypothesis(id) ON DELETE CASCADE,
    posterior_update_id UUID REFERENCES decision_posterior_update(id) ON DELETE SET NULL,
    action VARCHAR(30) NOT NULL CHECK (action IN ('continue', 'act', 'escalate', 'stop', 'reject', 'insufficient_evidence')),
    posterior_probability NUMERIC(12,10) NOT NULL CHECK (posterior_probability > 0 AND posterior_probability < 1),
    action_threshold NUMERIC(12,10),
    continue_threshold NUMERIC(12,10),
    expected_action_utility NUMERIC(20,8),
    expected_wait_utility NUMERIC(20,8),
    stopping_reason TEXT,
    calculation_version VARCHAR(40) NOT NULL,
    evaluated_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_threshold_hypothesis
    ON decision_threshold_evaluation(hypothesis_id, evaluated_at DESC);

COMMENT ON TABLE decision_threshold_evaluation IS 'Auditable continue/act/stop decision from posterior probability and expected utility';
