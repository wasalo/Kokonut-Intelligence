-- ============================================================
-- 291_solution_adoption.sql
-- Adoption journey, local adaptation, and adopter readiness.
-- ============================================================

CREATE TABLE IF NOT EXISTS solution_adoption_program (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    target_scope_type VARCHAR(30) NOT NULL,
    target_scope_id UUID NOT NULL,
    target_population JSONB NOT NULL DEFAULT '{}',
    adoption_pathway TEXT NOT NULL,
    champion_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    enablement_plan TEXT,
    training_requirements JSONB NOT NULL DEFAULT '{}',
    support_model TEXT,
    affordability_model TEXT,
    incentive_model TEXT,
    local_adaptation_policy TEXT,
    minimum_fidelity NUMERIC(6,3),
    acceptable_variation NUMERIC(6,3),
    target_adoption_rate NUMERIC(8,4),
    target_retention_rate NUMERIC(8,4),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'community_review', 'enablement_ready', 'launch', 'onboarding', 'active', 'paused', 'assessed', 'expand', 'redesign', 'retired')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS solution_adoption_cohort (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID NOT NULL REFERENCES solution_adoption_program(id) ON DELETE CASCADE,
    cohort_key VARCHAR(160) NOT NULL,
    scope_id UUID,
    target_count INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'onboarding', 'active', 'paused', 'completed', 'abandoned')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE (program_id, cohort_key)
);

CREATE TABLE IF NOT EXISTS solution_adoption_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID NOT NULL REFERENCES solution_adoption_program(id) ON DELETE CASCADE,
    cohort_id UUID REFERENCES solution_adoption_cohort(id) ON DELETE SET NULL,
    adopter_ref TEXT NOT NULL,
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('aware', 'interested', 'eligible', 'committed', 'onboarded', 'first_use', 'repeat_use', 'habitual_use', 'advocating', 'paused', 'abandoned')),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fidelity_score NUMERIC(8,3),
    support_required TEXT,
    outcome JSONB NOT NULL DEFAULT '{}',
    consent_checked BOOLEAN NOT NULL DEFAULT FALSE,
    evidence JSONB NOT NULL DEFAULT '{}',
    recorded_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    CHECK (consent_checked = TRUE OR event_type IN ('aware', 'interested'))
);

CREATE TABLE IF NOT EXISTS solution_configuration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    scope_type VARCHAR(30) NOT NULL,
    scope_id UUID NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    invariant_components JSONB NOT NULL DEFAULT '{}',
    configurable_components JSONB NOT NULL DEFAULT '{}',
    prohibited_components JSONB NOT NULL DEFAULT '{}',
    local_assumptions JSONB NOT NULL DEFAULT '{}',
    adaptation_owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    comparability_class VARCHAR(30) NOT NULL DEFAULT 'comparable'
        CHECK (comparability_class IN ('comparable', 'partially_comparable', 'not_comparable')),
    evidence_impact TEXT,
    approval_status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (approval_status IN ('draft', 'submitted', 'approved', 'rejected')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    UNIQUE (solution_id, scope_type, scope_id, version)
);

CREATE TABLE IF NOT EXISTS solution_adopter_readiness (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    adopter_scope_type VARCHAR(30) NOT NULL,
    adopter_scope_id UUID NOT NULL,
    current_level NUMERIC(6,3) NOT NULL DEFAULT 0,
    required_level NUMERIC(6,3) NOT NULL,
    gap NUMERIC(6,3) GENERATED ALWAYS AS (required_level - current_level) STORED,
    remediation_plan TEXT,
    readiness_status VARCHAR(20) NOT NULL DEFAULT 'not_ready'
        CHECK (readiness_status IN ('not_ready', 'remediating', 'ready', 'expired')),
    assessed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    assessed_at TIMESTAMPTZ,
    UNIQUE (solution_id, adopter_scope_type, adopter_scope_id)
);

CREATE INDEX IF NOT EXISTS idx_solution_adoption_program_solution ON solution_adoption_program(solution_id, status);
CREATE INDEX IF NOT EXISTS idx_solution_adoption_event_program ON solution_adoption_event(program_id, event_type, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_solution_configuration_scope ON solution_configuration(solution_id, scope_type, scope_id, approval_status);
CREATE INDEX IF NOT EXISTS idx_solution_adopter_readiness ON solution_adopter_readiness(solution_id, readiness_status);

DROP TRIGGER IF EXISTS trg_solution_adoption_program_updated_at ON solution_adoption_program;
CREATE TRIGGER trg_solution_adoption_program_updated_at BEFORE UPDATE ON solution_adoption_program
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE solution_adoption_program IS 'Consent-aware adoption journey with enablement, support, affordability, and local adaptation policy';
COMMENT ON TABLE solution_configuration IS 'Global reference solution configuration and explicitly approved local variants';
