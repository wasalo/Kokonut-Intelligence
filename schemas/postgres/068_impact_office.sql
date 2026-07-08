-- 068_impact_office.sql
-- Impact Office: Unified Orchestrator

BEGIN;

-- ============================================================================
-- IMPACT OFFICE RUN
-- ============================================================================

CREATE TABLE IF NOT EXISTS impact_office_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_key VARCHAR(100) UNIQUE NOT NULL,
    run_name VARCHAR(255),
    run_type VARCHAR(100) NOT NULL
        CHECK (run_type IN (
            'full_cycle', 'bounty_cycle', 'funding_cycle',
            'evidence_gap_cycle', 'landscape_refresh'
        )),
    trigger_source VARCHAR(100) NOT NULL DEFAULT 'manual'
        CHECK (trigger_source IN ('manual', 'scheduled', 'event_driven')),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organization(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'partial')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_office_run_location ON impact_office_run(location_id);
CREATE INDEX IF NOT EXISTS idx_office_run_status ON impact_office_run(status);
CREATE INDEX IF NOT EXISTS idx_office_run_type ON impact_office_run(run_type);

COMMENT ON TABLE impact_office_run IS 'Impact Office orchestration runs with status tracking';

-- ============================================================================
-- IMPACT OFFICE STEP
-- ============================================================================

CREATE TABLE IF NOT EXISTS impact_office_step (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES impact_office_run(id) ON DELETE CASCADE,
    step_order INT NOT NULL,
    step_type VARCHAR(100) NOT NULL
        CHECK (step_type IN (
            'ingest', 'compute_metric', 'generate_agent_task', 'review',
            'attest', 'fund_payout', 'refresh_view', 'export_report'
        )),
    step_name VARCHAR(255) NOT NULL,
    depends_on UUID,
    agent_task_key VARCHAR(100),
    input_params JSONB DEFAULT '{}'::jsonb,
    output_summary JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INT NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_office_step_run ON impact_office_step(run_id);
CREATE INDEX IF NOT EXISTS idx_office_step_status ON impact_office_step(status);

COMMENT ON TABLE impact_office_step IS 'Individual steps in an Impact Office orchestration run';

-- ============================================================================
-- IMPACT OFFICE ALERT
-- ============================================================================

CREATE TABLE IF NOT EXISTS impact_office_alert (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES impact_office_run(id) ON DELETE SET NULL,
    step_id UUID REFERENCES impact_office_step(id) ON DELETE SET NULL,
    alert_type VARCHAR(100) NOT NULL
        CHECK (alert_type IN (
            'evidence_gap', 'bounty_funded', 'campaign_goal_reached',
            'attestation_ready', 'payout_executed', 'anomaly_detected'
        )),
    severity VARCHAR(50) NOT NULL DEFAULT 'info'
        CHECK (severity IN ('info', 'warning', 'critical')),
    message TEXT NOT NULL,
    resolution_status VARCHAR(50) NOT NULL DEFAULT 'open'
        CHECK (resolution_status IN ('open', 'acknowledged', 'resolved')),
    resolved_by UUID,
    resolved_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_office_alert_run ON impact_office_alert(run_id);
CREATE INDEX IF NOT EXISTS idx_office_alert_type ON impact_office_alert(alert_type);
CREATE INDEX IF NOT EXISTS idx_office_alert_resolution ON impact_office_alert(resolution_status);

COMMENT ON TABLE impact_office_alert IS 'Alerts from Impact Office orchestration for evidence gaps, bounty completions, and anomalies';

COMMIT;
