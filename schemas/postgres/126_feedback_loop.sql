-- ============================================================
-- 126_feedback_loop.sql — Feedback controller and adaptation
-- ============================================================
-- Tracks action outcomes and feeds them back to orientation,
-- enabling adaptive thresholds and learning from results.

CREATE TABLE IF NOT EXISTS action_outcome (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type VARCHAR(100) NOT NULL,
    action_source VARCHAR(100) NOT NULL,
    action_source_id UUID,
    location_id UUID NOT NULL,
    correlation_id UUID,
    decision_id UUID REFERENCES decision_log(id) ON DELETE SET NULL,
    outcome_type VARCHAR(50) NOT NULL
        CHECK (outcome_type IN ('effective', 'partially_effective', 'ineffective',
                                'no_effect', 'counterproductive', 'unknown')),
    outcome_evidence JSONB NOT NULL DEFAULT '{}',
    measured_delta JSONB NOT NULL DEFAULT '{}',
    measurement_period_hours INTEGER NOT NULL DEFAULT 24,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    measured_by VARCHAR(100) NOT NULL DEFAULT 'system',
    confidence VARCHAR(20) NOT NULL DEFAULT 'low'
        CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    feedback_applied BOOLEAN NOT NULL DEFAULT FALSE,
    feedback_applied_at TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_action_outcome_location
    ON action_outcome (location_id, measured_at DESC);
CREATE INDEX IF NOT EXISTS idx_action_outcome_type
    ON action_outcome (outcome_type, measured_at DESC);
CREATE INDEX IF NOT EXISTS idx_action_outcome_correlation
    ON action_outcome (correlation_id);
CREATE INDEX IF NOT EXISTS idx_action_outcome_decision
    ON action_outcome (decision_id);
CREATE INDEX IF NOT EXISTS idx_action_outcome_unprocessed
    ON action_outcome (measured_at) WHERE NOT feedback_applied;

CREATE TABLE IF NOT EXISTS feedback_loop (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loop_type VARCHAR(50) NOT NULL
        CHECK (loop_type IN ('threshold_adjustment', 'weight_shift', 'sampling_rate',
                             'priority_change', 'policy_update', 'model_retrain')),
    source_outcome_id UUID NOT NULL REFERENCES action_outcome(id) ON DELETE CASCADE,
    target_entity VARCHAR(100) NOT NULL,
    target_entity_id UUID,
    target_field VARCHAR(100) NOT NULL,
    previous_value JSONB,
    new_value JSONB NOT NULL,
    adjustment_reason TEXT NOT NULL,
    adjustment_magnitude DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'applied', 'rejected', 'reverted')),
    applied_at TIMESTAMPTZ,
    applied_by VARCHAR(100),
    reverted_at TIMESTAMPTZ,
    reverted_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_loop_type
    ON feedback_loop (loop_type, status);
CREATE INDEX IF NOT EXISTS idx_feedback_loop_target
    ON feedback_loop (target_entity, target_entity_id);
CREATE INDEX IF NOT EXISTS idx_feedback_loop_status
    ON feedback_loop (status, created_at DESC);

CREATE TABLE IF NOT EXISTS adaptive_threshold (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    threshold_key VARCHAR(100) NOT NULL UNIQUE,
    entity_type VARCHAR(50) NOT NULL
        CHECK (entity_type IN ('alert_rule', 'crisp_weight', 'sampling_rate',
                               'anomaly_sensitivity', 'score_band')),
    entity_id UUID,
    location_id UUID,
    threshold_name VARCHAR(100) NOT NULL,
    current_value JSONB NOT NULL,
    baseline_value JSONB NOT NULL,
    min_value JSONB,
    max_value JSONB,
    adaptation_rate DOUBLE PRECISION NOT NULL DEFAULT 0.1,
    last_adjusted_at TIMESTAMPTZ,
    adjustment_count INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_adaptive_threshold_entity
    ON adaptive_threshold (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_adaptive_threshold_location
    ON adaptive_threshold (location_id, threshold_name);
CREATE INDEX IF NOT EXISTS idx_adaptive_threshold_enabled
    ON adaptive_threshold (is_enabled, last_adjusted_at);
