-- ============================================================
-- 125_decision_policy.sql — Decision policy engine
-- ============================================================
-- Configurable rules that consume situation assessments and produce
-- action recommendations. All automated decisions require human approval.

CREATE TABLE IF NOT EXISTS decision_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name VARCHAR(100) NOT NULL UNIQUE,
    policy_type VARCHAR(50) NOT NULL DEFAULT 'rule'
        CHECK (policy_type IN ('rule', 'threshold', 'composite', 'ml_assisted')),
    description TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 0,
    trigger_event_type VARCHAR(100),
    trigger_situation_grade VARCHAR(20)
        CHECK (trigger_situation_grade IN ('critical', 'warning', 'stable', 'flourishing')),
    trigger_dimension VARCHAR(50),
    trigger_score_min DOUBLE PRECISION,
    trigger_score_max DOUBLE PRECISION,
    action_type VARCHAR(100) NOT NULL,
    action_config JSONB NOT NULL DEFAULT '{}',
    requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
    approval_role VARCHAR(50) NOT NULL DEFAULT 'admin'
        CHECK (approval_role IN ('admin', 'manager', 'operator', 'viewer')),
    cooldown_minutes INTEGER NOT NULL DEFAULT 60,
    max_executions_per_day INTEGER NOT NULL DEFAULT 10,
    risk_level VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    methodology_version VARCHAR(50) NOT NULL DEFAULT 'v1.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) NOT NULL DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_decision_policy_enabled
    ON decision_policy (is_enabled, priority DESC);
CREATE INDEX IF NOT EXISTS idx_decision_policy_trigger
    ON decision_policy (trigger_event_type, trigger_situation_grade);
CREATE INDEX IF NOT EXISTS idx_decision_policy_type
    ON decision_policy (policy_type);

CREATE TABLE IF NOT EXISTS decision_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id UUID NOT NULL REFERENCES decision_policy(id) ON DELETE CASCADE,
    location_id UUID NOT NULL,
    assessment_id UUID REFERENCES situation_assessment(id) ON DELETE SET NULL,
    correlation_id UUID,
    trigger_event_id UUID,
    trigger_event_type VARCHAR(100),
    action_type VARCHAR(100) NOT NULL,
    action_config JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'executed', 'failed', 'expired')),
    approval_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending', 'approved', 'rejected', 'auto_approved')),
    approved_by VARCHAR(100),
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,
    executed_at TIMESTAMPTZ,
    execution_result JSONB,
    execution_error TEXT,
    cycle_time_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_log_location
    ON decision_log (location_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decision_log_status
    ON decision_log (status, approval_status);
CREATE INDEX IF NOT EXISTS idx_decision_log_correlation
    ON decision_log (correlation_id);
CREATE INDEX IF NOT EXISTS idx_decision_log_policy
    ON decision_log (policy_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decision_log_pending_approval
    ON decision_log (approval_status) WHERE approval_status = 'pending';

CREATE TABLE IF NOT EXISTS decision_outcome (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES decision_log(id) ON DELETE CASCADE,
    outcome_type VARCHAR(50) NOT NULL
        CHECK (outcome_type IN ('success', 'partial', 'failure', 'timeout', 'reverted')),
    outcome_value DOUBLE PRECISION,
    outcome_text TEXT,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    measured_by VARCHAR(100) NOT NULL DEFAULT 'system',
    feedback_generated BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_outcome_decision
    ON decision_outcome (decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_outcome_type
    ON decision_outcome (outcome_type, measured_at DESC);
