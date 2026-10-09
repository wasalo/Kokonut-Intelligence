-- ============================================================
-- 289_solution_experiments.sql
-- Governed experiments and replication evidence for solutions.
-- ============================================================

CREATE TABLE IF NOT EXISTS solution_experiment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    hypothesis TEXT NOT NULL,
    null_hypothesis TEXT,
    protocol_version VARCHAR(40) NOT NULL DEFAULT 'v1',
    baseline_definition TEXT NOT NULL,
    treatment_definition TEXT NOT NULL,
    comparator_definition TEXT,
    unit_of_analysis TEXT NOT NULL,
    sample_plan JSONB NOT NULL DEFAULT '{}',
    primary_metric_keys JSONB NOT NULL DEFAULT '[]',
    secondary_metric_keys JSONB NOT NULL DEFAULT '[]',
    minimum_detectable_effect NUMERIC,
    confidence_target NUMERIC,
    duration_days INTEGER CHECK (duration_days IS NULL OR duration_days > 0),
    stopping_rules JSONB NOT NULL DEFAULT '{}',
    rollback_plan TEXT NOT NULL,
    safety_boundaries JSONB NOT NULL DEFAULT '{}',
    consent_requirements JSONB NOT NULL DEFAULT '{}',
    preregistration_uri TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'protocol_approved', 'baseline_ready', 'active', 'paused', 'completed', 'results_review', 'validated', 'invalidated', 'inconclusive', 'requires_replication')),
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS solution_experiment_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES solution_experiment(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unit_ref TEXT,
    metric_key VARCHAR(120) NOT NULL,
    value NUMERIC,
    arm VARCHAR(30) NOT NULL CHECK (arm IN ('baseline', 'treatment', 'comparator', 'unknown')),
    adverse_event BOOLEAN NOT NULL DEFAULT FALSE,
    evidence JSONB NOT NULL DEFAULT '{}',
    recorded_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS solution_experiment_result (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES solution_experiment(id) ON DELETE CASCADE,
    outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('validated', 'invalidated', 'inconclusive', 'requires_replication')),
    primary_results JSONB NOT NULL DEFAULT '{}',
    secondary_results JSONB NOT NULL DEFAULT '{}',
    adverse_events JSONB NOT NULL DEFAULT '[]',
    evidence JSONB NOT NULL DEFAULT '[]',
    limitations TEXT,
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (experiment_id)
);

CREATE TABLE IF NOT EXISTS solution_replication (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    source_experiment_id UUID NOT NULL REFERENCES solution_experiment(id) ON DELETE RESTRICT,
    target_scope_type VARCHAR(30) NOT NULL,
    target_scope_id UUID NOT NULL,
    target_context TEXT NOT NULL,
    context_similarity NUMERIC(6,3),
    adaptation_required TEXT,
    replication_protocol JSONB NOT NULL DEFAULT '{}',
    result VARCHAR(20) CHECK (result IS NULL OR result IN ('successful', 'failed', 'mixed', 'inconclusive')),
    evidence_maturity INTEGER REFERENCES evidence_maturity_level(level),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'approved', 'active', 'completed', 'failed')),
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_solution_experiment_solution ON solution_experiment(solution_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_solution_experiment_observation ON solution_experiment_observation(experiment_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_solution_replication_solution ON solution_replication(solution_id, status, created_at DESC);

DROP TRIGGER IF EXISTS trg_solution_experiment_updated_at ON solution_experiment;
CREATE TRIGGER trg_solution_experiment_updated_at BEFORE UPDATE ON solution_experiment
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE solution_experiment IS 'Bounded hypothesis-driven solution experiment with baseline, comparator, safeguards, stopping, and rollback protocol';
COMMENT ON TABLE solution_replication IS 'Evidence that a validated solution transfers to a different context with explicit local adaptation';
