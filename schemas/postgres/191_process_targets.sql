-- ============================================================
-- 191_process_targets.sql — To-Be Modeling + Gap Analysis + Maturity
-- ============================================================
-- Defines target-state process metrics, compares against as-is,
-- computes gaps, and assigns CMMI-inspired maturity levels.

-- Maturity level reference data (must exist before process_maturity FK)
CREATE TABLE IF NOT EXISTS process_maturity_level (
    level INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL
);

INSERT INTO process_maturity_level (level, name, description) VALUES
    (1, 'Initial', 'Processes are ad-hoc and chaotic. Success depends on individual effort.'),
    (2, 'Managed', 'Processes are planned and tracked. Basic project management exists.'),
    (3, 'Defined', 'Processes are well-documented and standardized across the organization.'),
    (4, 'Quantitatively Managed', 'Processes are measured and controlled with statistical techniques.'),
    (5, 'Optimizing', 'Continuous process improvement through incremental and innovative changes.')
ON CONFLICT (level) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;

-- Target-state process definitions
CREATE TABLE IF NOT EXISTS process_target (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_key VARCHAR(100) NOT NULL REFERENCES process_map(process_key) ON DELETE CASCADE,
    entity_type VARCHAR(100),
    metric_name VARCHAR(100) NOT NULL,
    target_value DOUBLE PRECISION NOT NULL,
    target_direction VARCHAR(10) CHECK (target_direction IN ('lte', 'gte', 'eq')),
    unit VARCHAR(40),
    period VARCHAR(40) DEFAULT 'all',
    source_ref VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (process_key, entity_type, metric_name)
);

CREATE INDEX IF NOT EXISTS idx_pt_process ON process_target(process_key);

-- Gap analysis results
CREATE TABLE IF NOT EXISTS process_gap (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_key VARCHAR(100) NOT NULL REFERENCES process_map(process_key) ON DELETE CASCADE,
    entity_type VARCHAR(100),
    metric_name VARCHAR(100) NOT NULL,
    target_value DOUBLE PRECISION,
    actual_value DOUBLE PRECISION,
    gap_value DOUBLE PRECISION,
    gap_pct DOUBLE PRECISION,
    maturity_level INTEGER CHECK (maturity_level BETWEEN 1 AND 5),
    assessment_notes TEXT,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assessed_by UUID
);

CREATE INDEX IF NOT EXISTS idx_pg_process ON process_gap(process_key);
CREATE INDEX IF NOT EXISTS idx_pg_assessed ON process_gap(assessed_at DESC);

-- Process maturity assessments
CREATE TABLE IF NOT EXISTS process_maturity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_key VARCHAR(100) NOT NULL REFERENCES process_map(process_key) ON DELETE CASCADE,
    maturity_level INTEGER NOT NULL CHECK (maturity_level BETWEEN 1 AND 5),
    level_name VARCHAR(100) NOT NULL,
    description TEXT,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assessed_by UUID
);

CREATE INDEX IF NOT EXISTS idx_pm_process ON process_maturity(process_key);
CREATE INDEX IF NOT EXISTS idx_pm_assessed ON process_maturity(assessed_at DESC);

-- ============================================================
-- Seed: Target-State Metrics for Core Processes
-- ============================================================

-- Farm Operations targets
INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('farm_operations', 'farm_activity', 'lead_time_days', 3.0, 'lte', 'days', 'BPM best practice: <3 days draft-to-published'),
    ('farm_operations', 'farm_activity', 'fty_pct', 85.0, 'gte', 'percent', 'Target: 85% first-time-through yield'),
    ('farm_operations', 'farm_activity', 'rework_rate_pct', 10.0, 'lte', 'percent', 'Target: <10% rework rate')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- Harvest Management targets
INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('harvest_management', 'harvest_event', 'lead_time_days', 2.0, 'lte', 'days', 'Target: <2 days for harvest recording'),
    ('harvest_management', 'harvest_event', 'fty_pct', 90.0, 'gte', 'percent', 'Target: 90% first-time-through yield')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- Data Publication targets
INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('data_publication', 'data_stream_post', 'lead_time_days', 5.0, 'lte', 'days', 'Target: <5 days for data publication'),
    ('data_publication', 'data_stream_post', 'fty_pct', 80.0, 'gte', 'percent', 'Target: 80% first-time-through yield'),
    ('data_publication', 'data_stream_post', 'cycle_time_days', 7.0, 'lte', 'days', 'Target: <7 days end-to-end cycle time')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- Impact Verification targets
INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('impact_verification', 'impact_claim', 'lead_time_days', 10.0, 'lte', 'days', 'Target: <10 days for impact claim verification'),
    ('impact_verification', 'impact_claim', 'fty_pct', 75.0, 'gte', 'percent', 'Target: 75% first-time-through yield')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- Metric Governance targets
INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('metric_governance', 'metric_value', 'lead_time_days', 1.0, 'lte', 'days', 'Target: <1 day for metric verification'),
    ('metric_governance', 'metric_value', 'fty_pct', 95.0, 'gte', 'percent', 'Target: 95% first-time-through yield')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- Work Management targets
INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('work_management', 'work_item', 'lead_time_days', 5.0, 'lte', 'days', 'Target: <5 days for work item completion'),
    ('work_management', 'work_item', 'fty_pct', 80.0, 'gte', 'percent', 'Target: 80% first-time-through yield'),
    ('work_management', 'work_item', 'cycle_time_days', 10.0, 'lte', 'days', 'Target: <10 days end-to-end cycle time')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- Event Delivery targets
INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('event_delivery', NULL, 'delivery_success_pct', 99.0, 'gte', 'percent', 'Target: 99% event delivery success rate'),
    ('event_delivery', NULL, 'avg_latency_ms', 500.0, 'lte', 'ms', 'Target: <500ms average event delivery latency')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- Stakeholder Feedback targets
INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('stakeholder_feedback', 'stakeholder_feedback', 'lead_time_days', 14.0, 'lte', 'days', 'Target: <14 days for feedback review cycle'),
    ('stakeholder_feedback', 'stakeholder_feedback', 'fty_pct', 70.0, 'gte', 'percent', 'Target: 70% first-time-through yield')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- Agent Execution targets
INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('agent_execution', 'agent_task', 'lead_time_days', 1.0, 'lte', 'days', 'Target: <1 day for agent task completion'),
    ('agent_execution', 'agent_task', 'fty_pct', 90.0, 'gte', 'percent', 'Target: 90% first-time-through yield')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- Reporting targets
INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('reporting', 'report_snapshot', 'lead_time_days', 3.0, 'lte', 'days', 'Target: <3 days for report generation'),
    ('reporting', 'report_snapshot', 'fty_pct', 85.0, 'gte', 'percent', 'Target: 85% first-time-through yield')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

COMMENT ON TABLE process_target IS 'Target-state process metrics for gap analysis and maturity assessment';
COMMENT ON TABLE process_gap IS 'Gap analysis results: target vs actual with maturity scoring';
COMMENT ON TABLE process_maturity IS 'CMMI-inspired maturity assessments per process';
COMMENT ON TABLE process_maturity_level IS 'Reference data: maturity levels 1-5 (Initial to Optimizing)';
