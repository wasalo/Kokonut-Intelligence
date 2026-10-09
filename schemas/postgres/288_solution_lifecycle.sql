-- ============================================================
-- 288_solution_lifecycle.sql
-- Canonical solution identity, lifecycle, links, and promotion gates.
-- ============================================================

CREATE TABLE IF NOT EXISTS solution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_key VARCHAR(160) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    solution_type VARCHAR(40) NOT NULL
        CHECK (solution_type IN ('practice', 'policy', 'technology', 'service', 'governance', 'business_model', 'ecological_intervention', 'data_product', 'other')),
    problem_statement TEXT NOT NULL,
    theory_of_change TEXT,
    baseline_alternative TEXT,
    originating_scope_type VARCHAR(30),
    originating_scope_id UUID,
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    current_stage VARCHAR(30) NOT NULL DEFAULT 'discovered'
        CHECK (current_stage IN ('discovered', 'triaged', 'framed', 'experiment_ready', 'testing', 'validated', 'investment_ready', 'funded', 'pilot_active', 'adoption_ready', 'adopting', 'scaled', 'maintained', 'paused', 'superseded', 'retired', 'failed')),
    reversibility VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (reversibility IN ('high', 'medium', 'low', 'unknown')),
    risk_class VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (risk_class IN ('low', 'medium', 'high', 'critical')),
    evidence_maturity INTEGER REFERENCES evidence_maturity_level(level),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'retired', 'superseded')),
    supersedes_solution_id UUID REFERENCES solution(id) ON DELETE SET NULL,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retired_at TIMESTAMPTZ,
    retirement_reason TEXT
);

CREATE TABLE IF NOT EXISTS solution_lifecycle_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    from_stage VARCHAR(30),
    to_stage VARCHAR(30) NOT NULL,
    rationale TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]',
    affected_stakeholders JSONB NOT NULL DEFAULT '[]',
    resource_commitment JSONB NOT NULL DEFAULT '{}',
    rollback_plan TEXT,
    actor_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS solution_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    entity_type VARCHAR(40) NOT NULL CHECK (entity_type IN ('opportunity', 'strategy_plan', 'strategy_choice', 'strategy_investment', 'technology_alternative', 'experiment', 'funding_case', 'pilot', 'adoption_program', 'scale_gate', 'artifact', 'evidence')),
    entity_id UUID NOT NULL,
    relationship VARCHAR(30) NOT NULL CHECK (relationship IN ('originated_from', 'supports', 'funded_by', 'tested_by', 'deployed_by', 'scales_through', 'evidence', 'supersedes', 'depends_on')),
    rationale TEXT,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (solution_id, entity_type, entity_id, relationship)
);

CREATE TABLE IF NOT EXISTS solution_stage_gate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    from_stage VARCHAR(30) NOT NULL,
    to_stage VARCHAR(30) NOT NULL,
    required_evidence_maturity INTEGER,
    required_experiment_count INTEGER NOT NULL DEFAULT 0 CHECK (required_experiment_count >= 0),
    requires_human_approval BOOLEAN NOT NULL DEFAULT TRUE,
    requirements JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'ready', 'approved', 'failed', 'retired')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (solution_id, from_stage, to_stage)
);

CREATE TABLE IF NOT EXISTS solution_gate_evaluation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_id UUID NOT NULL REFERENCES solution_stage_gate(id) ON DELETE CASCADE,
    passed BOOLEAN NOT NULL,
    observed JSONB NOT NULL DEFAULT '{}',
    evidence JSONB NOT NULL DEFAULT '[]',
    evaluated_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_solution_stage ON solution(current_stage, status);
CREATE INDEX IF NOT EXISTS idx_solution_event_solution ON solution_lifecycle_event(solution_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_solution_link_entity ON solution_link(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_solution_gate_solution ON solution_stage_gate(solution_id, from_stage, to_stage, status);

DROP TRIGGER IF EXISTS trg_solution_updated_at ON solution;
CREATE TRIGGER trg_solution_updated_at BEFORE UPDATE ON solution
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE solution IS 'Canonical identity for a solution from field discovery through experimentation, adoption, scaling, and retirement';
COMMENT ON TABLE solution_stage_gate IS 'Evidence and approval requirements for promoting a solution between lifecycle stages';
