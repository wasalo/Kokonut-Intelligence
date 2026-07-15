-- ============================================================
-- 223_stakeholder_capabilities_value_streams.sql
-- ============================================================

ALTER TABLE business_capability ADD COLUMN IF NOT EXISTS stakeholder_promise TEXT;
ALTER TABLE business_capability ADD COLUMN IF NOT EXISTS criticality VARCHAR(20) NOT NULL DEFAULT 'medium'
    CHECK (criticality IN ('low', 'medium', 'high', 'critical'));
ALTER TABLE business_capability ADD COLUMN IF NOT EXISTS access_barriers JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE business_capability ADD COLUMN IF NOT EXISTS service_quality_target NUMERIC(8,3);
ALTER TABLE business_capability ADD COLUMN IF NOT EXISTS satisfaction_target NUMERIC(8,3);
ALTER TABLE business_capability ADD COLUMN IF NOT EXISTS harm_exposure NUMERIC(8,3);
ALTER TABLE business_capability ADD COLUMN IF NOT EXISTS dependency_risk NUMERIC(8,3);

CREATE TABLE IF NOT EXISTS capability_stakeholder (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capability_id UUID NOT NULL REFERENCES business_capability(id) ON DELETE CASCADE,
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    relationship_type VARCHAR(30) NOT NULL CHECK (relationship_type IN ('beneficiary', 'affected', 'customer', 'steward', 'provider', 'rights_holder', 'proxy')),
    desired_outcome TEXT NOT NULL,
    demand_level VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (demand_level IN ('low', 'medium', 'high', 'critical')),
    criticality VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (criticality IN ('low', 'medium', 'high', 'critical')),
    access_barriers JSONB NOT NULL DEFAULT '[]'::jsonb,
    satisfaction_measure VARCHAR(255),
    harm_exposure NUMERIC(8,3),
    dependency_risk NUMERIC(8,3),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('draft', 'active', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (capability_id, party_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_capability_stakeholder_party ON capability_stakeholder(party_id, status);

ALTER TABLE value_stream_definition ADD COLUMN IF NOT EXISTS stakeholder_promise TEXT;
ALTER TABLE value_stream_definition ADD COLUMN IF NOT EXISTS desired_end_state TEXT;
ALTER TABLE value_stream_definition ADD COLUMN IF NOT EXISTS pain_points JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE value_stream_definition ADD COLUMN IF NOT EXISTS experience_measures JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE value_stream_definition ADD COLUMN IF NOT EXISTS service_level_expectations JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE value_stream_definition ADD COLUMN IF NOT EXISTS equity_effects JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE value_stream_definition ADD COLUMN IF NOT EXISTS feedback_sources JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE value_stream_definition ADD COLUMN IF NOT EXISTS outcome_evidence JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS value_stream_stakeholder_outcome (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    value_stream_id UUID NOT NULL REFERENCES value_stream_definition(id) ON DELETE CASCADE,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    interest_id UUID REFERENCES stakeholder_interest(id) ON DELETE SET NULL,
    outcome_name VARCHAR(255) NOT NULL,
    outcome_description TEXT NOT NULL,
    measure_key VARCHAR(100),
    target_value NUMERIC,
    target_unit VARCHAR(50),
    current_value NUMERIC,
    current_unit VARCHAR(50),
    harm_if_missed TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'verified', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (party_id IS NOT NULL OR interest_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_vs_outcome_stream ON value_stream_stakeholder_outcome(value_stream_id, status);
CREATE INDEX IF NOT EXISTS idx_vs_outcome_party ON value_stream_stakeholder_outcome(party_id);

CREATE TABLE IF NOT EXISTS value_stream_feedback_source (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    value_stream_id UUID NOT NULL REFERENCES value_stream_definition(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,
    source_id UUID,
    description TEXT NOT NULL,
    consent_scope VARCHAR(50),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW v_stakeholder_capability_value_stream AS
SELECT 'capability' AS entity_type,
       bc.id AS entity_id,
       bc.name AS entity_name,
       cs.party_id,
       p.display_name AS party_name,
       cs.relationship_type,
       cs.desired_outcome,
       cs.demand_level,
       cs.criticality,
       cs.harm_exposure,
       cs.dependency_risk,
       bc.stakeholder_promise,
       bc.service_quality_target,
       bc.satisfaction_target,
       cs.status
FROM business_capability bc
JOIN capability_stakeholder cs ON cs.capability_id = bc.id
JOIN party p ON p.id = cs.party_id
UNION ALL
SELECT 'value_stream' AS entity_type,
       vs.id AS entity_id,
       vs.name AS entity_name,
       vso.party_id,
       p.display_name AS party_name,
       'beneficiary' AS relationship_type,
       vso.outcome_description AS desired_outcome,
       NULL AS demand_level,
       NULL AS criticality,
       NULL AS harm_exposure,
       NULL AS dependency_risk,
       vs.stakeholder_promise,
       NULL AS service_quality_target,
       NULL AS satisfaction_target,
       vso.status
FROM value_stream_definition vs
JOIN value_stream_stakeholder_outcome vso ON vso.value_stream_id = vs.id
LEFT JOIN party p ON p.id = vso.party_id;

COMMENT ON VIEW v_stakeholder_capability_value_stream IS 'Stakeholder beneficiary, outcome, barrier, harm, and dependency links across capability and value-stream architecture';
