-- ============================================================
-- 127_ooda_cycles.sql — OODA cycle tracking
-- ============================================================
-- Tracks the full Observe→Orient→Decide→Act cycle with timing,
-- correlation IDs, and performance metrics.

CREATE TABLE IF NOT EXISTS ooda_cycle_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL,
    location_id UUID NOT NULL,
    cycle_type VARCHAR(50) NOT NULL DEFAULT 'automated'
        CHECK (cycle_type IN ('automated', 'manual', 'hybrid', 'simulated')),
    decision_type VARCHAR(100) NOT NULL,
    trigger_event_type VARCHAR(100),
    trigger_event_id UUID,

    observe_started_at TIMESTAMPTZ,
    observe_completed_at TIMESTAMPTZ,
    observe_duration_ms INTEGER,
    observe_sources JSONB NOT NULL DEFAULT '[]',

    orient_started_at TIMESTAMPTZ,
    orient_completed_at TIMESTAMPTZ,
    orient_duration_ms INTEGER,
    orient_frameworks_used JSONB NOT NULL DEFAULT '[]',
    orient_assessment_id UUID REFERENCES situation_assessment(id) ON DELETE SET NULL,

    decide_started_at TIMESTAMPTZ,
    decide_completed_at TIMESTAMPTZ,
    decide_duration_ms INTEGER,
    decide_policy_id UUID REFERENCES decision_policy(id) ON DELETE SET NULL,
    decide_decision_id UUID REFERENCES decision_log(id) ON DELETE SET NULL,

    act_started_at TIMESTAMPTZ,
    act_completed_at TIMESTAMPTZ,
    act_duration_ms INTEGER,
    act_outcome_id UUID REFERENCES action_outcome(id) ON DELETE SET NULL,
    act_action_type VARCHAR(100),

    total_cycle_time_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed', 'failed', 'timeout', 'abandoned')),
    failure_phase VARCHAR(20)
        CHECK (failure_phase IS NULL OR failure_phase IN ('observe', 'orient', 'decide', 'act')),
    error_message TEXT,

    outcome_type VARCHAR(50)
        CHECK (outcome_type IS NULL OR outcome_type IN (
            'effective', 'partially_effective', 'ineffective',
            'no_effect', 'counterproductive', 'unknown')),

    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ooda_cycle_correlation
    ON ooda_cycle_log (correlation_id);
CREATE INDEX IF NOT EXISTS idx_ooda_cycle_location
    ON ooda_cycle_log (location_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ooda_cycle_status
    ON ooda_cycle_log (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ooda_cycle_type
    ON ooda_cycle_log (decision_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ooda_cycle_timing
    ON ooda_cycle_log (total_cycle_time_ms) WHERE status = 'completed';
CREATE INDEX IF NOT EXISTS idx_ooda_cycle_in_progress
    ON ooda_cycle_log (correlation_id) WHERE status = 'in_progress';
