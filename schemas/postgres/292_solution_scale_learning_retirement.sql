-- ============================================================
-- 292_solution_scale_learning_retirement.sql
-- Replication/scale gates, learning transfer, and retirement.
-- ============================================================

CREATE TABLE IF NOT EXISTS solution_scale_gate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    scope_type VARCHAR(30) NOT NULL,
    scope_id UUID NOT NULL,
    gate_type VARCHAR(30) NOT NULL CHECK (gate_type IN ('impact', 'safety', 'financial_sustainability', 'operational_capacity', 'supply_chain', 'regulatory', 'community_acceptance', 'equity', 'data_quality', 'maintainability', 'replicability')),
    requirement TEXT NOT NULL,
    measured_value TEXT,
    threshold TEXT,
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'passed', 'failed', 'waived')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    UNIQUE (solution_id, scope_type, scope_id, gate_type)
);

CREATE TABLE IF NOT EXISTS solution_learning_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    source_experiment_id UUID REFERENCES solution_experiment(id) ON DELETE SET NULL,
    source_replication_id UUID REFERENCES solution_replication(id) ON DELETE SET NULL,
    lesson_type VARCHAR(30) NOT NULL CHECK (lesson_type IN ('validated_assumption', 'invalidated_assumption', 'implementation', 'adoption', 'safety', 'economic', 'equity', 'context_transfer')),
    finding TEXT NOT NULL,
    confidence VARCHAR(20) NOT NULL DEFAULT 'moderate'
        CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    transferability VARCHAR(20) NOT NULL DEFAULT 'unknown'
        CHECK (transferability IN ('high', 'medium', 'low', 'unknown')),
    affected_assumptions JSONB NOT NULL DEFAULT '[]',
    affected_metrics JSONB NOT NULL DEFAULT '[]',
    recommended_action TEXT NOT NULL,
    decision_status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (decision_status IN ('proposed', 'accepted', 'rejected', 'applied')),
    applied_to_version VARCHAR(80),
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS solution_retirement (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    retirement_type VARCHAR(30) NOT NULL CHECK (retirement_type IN ('unsafe', 'ineffective', 'too_costly', 'superseded', 'not_adopted', 'context_invalidated', 'evidence_withdrawn', 'maintenance_failure', 'governance_breach', 'mission_complete')),
    trigger_reason TEXT NOT NULL,
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    affected_users JSONB NOT NULL DEFAULT '[]',
    dependent_solutions JSONB NOT NULL DEFAULT '[]',
    replacement_solution_id UUID REFERENCES solution(id) ON DELETE SET NULL,
    migration_plan TEXT,
    residual_risk TEXT,
    data_preservation_plan TEXT,
    compensation_or_remedy_plan TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'impact_review', 'approved', 'migration', 'sunset', 'completed', 'rejected')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    effective_at TIMESTAMPTZ,
    post_retirement_review_at DATE,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_solution_scale_gate_solution ON solution_scale_gate(solution_id, scope_type, scope_id, status);
CREATE INDEX IF NOT EXISTS idx_solution_learning_solution ON solution_learning_record(solution_id, decision_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_solution_retirement_solution ON solution_retirement(solution_id, status);

COMMENT ON TABLE solution_scale_gate IS 'Evidence gates for expanding a solution across contexts or network scope';
COMMENT ON TABLE solution_learning_record IS 'Validated lessons transferred from experiments and replications into future decisions';
COMMENT ON TABLE solution_retirement IS 'Safe retirement, migration, remedy, and post-retirement review for solutions';
