-- ============================================================
-- 224_nature_future_generations.sql - Nature and future generations
-- ============================================================

CREATE TABLE IF NOT EXISTS stewardship_proxy_authority (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proxy_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    steward_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    authority_type VARCHAR(30) NOT NULL CHECK (authority_type IN ('represent', 'monitor', 'escalate', 'approve_plan', 'verify_evidence')),
    basis TEXT NOT NULL,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network' CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    scope_id UUID,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'active', 'suspended', 'expired', 'revoked')),
    starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    CHECK (proxy_party_id <> steward_party_id),
    CHECK (expires_at IS NULL OR expires_at >= starts_at)
);

CREATE INDEX IF NOT EXISTS idx_proxy_authority_proxy ON stewardship_proxy_authority(proxy_party_id, status);
CREATE INDEX IF NOT EXISTS idx_proxy_authority_steward ON stewardship_proxy_authority(steward_party_id, status);

CREATE TABLE IF NOT EXISTS ecological_threshold (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proxy_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    threshold_key VARCHAR(100) NOT NULL,
    subject_type VARCHAR(40) NOT NULL CHECK (subject_type IN ('ecosystem', 'species', 'watershed', 'soil', 'biodiversity', 'carbon', 'water', 'landscape', 'other')),
    metric_key VARCHAR(100) NOT NULL,
    operator VARCHAR(10) NOT NULL CHECK (operator IN ('lt', 'lte', 'gt', 'gte', 'eq', 'neq', 'between')),
    threshold_value NUMERIC,
    threshold_min NUMERIC,
    threshold_max NUMERIC,
    unit VARCHAR(50),
    severity VARCHAR(20) NOT NULL DEFAULT 'high' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    rationale TEXT NOT NULL,
    source_type VARCHAR(50),
    source_id UUID,
    evidence_maturity INTEGER REFERENCES evidence_maturity_level(level),
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'superseded', 'retired')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (operator <> 'between' OR (threshold_min IS NOT NULL AND threshold_max IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_ecological_threshold_location ON ecological_threshold(location_id, status);
CREATE INDEX IF NOT EXISTS idx_ecological_threshold_metric ON ecological_threshold(metric_key, status);

CREATE TABLE IF NOT EXISTS nature_stewardship_obligation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proxy_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    interest_id UUID REFERENCES stakeholder_interest(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    obligation_type VARCHAR(30) NOT NULL CHECK (obligation_type IN ('protect', 'restore', 'avoid_harm', 'monitor', 'disclose', 'repair', 'intergenerational')),
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network',
    scope_id UUID,
    metric_key VARCHAR(100),
    target_value NUMERIC,
    target_unit VARCHAR(50),
    target_date DATE,
    threshold_id UUID REFERENCES ecological_threshold(id) ON DELETE SET NULL,
    principle_source VARCHAR(100),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'approved', 'in_progress', 'met', 'breached', 'retired')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stewardship_obligation_proxy ON nature_stewardship_obligation(proxy_party_id, status);
CREATE INDEX IF NOT EXISTS idx_stewardship_obligation_metric ON nature_stewardship_obligation(metric_key, status);

CREATE TABLE IF NOT EXISTS future_generation_principle (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proxy_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    principle TEXT NOT NULL,
    target_metric VARCHAR(100),
    target_value NUMERIC,
    target_unit VARCHAR(50),
    review_cadence_days INTEGER NOT NULL DEFAULT 365 CHECK (review_cadence_days > 0),
    review_due_at DATE,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'approved', 'active', 'retired')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nature_decision_impact (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES stakeholder_decision(id) ON DELETE CASCADE,
    proxy_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    impact_type VARCHAR(20) NOT NULL CHECK (impact_type IN ('benefit', 'harm', 'risk', 'threshold_exposure', 'restoration')),
    magnitude NUMERIC,
    unit VARCHAR(50),
    threshold_id UUID REFERENCES ecological_threshold(id) ON DELETE SET NULL,
    threshold_status VARCHAR(20) CHECK (threshold_status IN ('not_assessed', 'within', 'approaching', 'breached')),
    ecological_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    mitigation TEXT,
    review_required BOOLEAN NOT NULL DEFAULT TRUE,
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW v_nature_stewardship_status AS
SELECT o.id AS obligation_id, o.proxy_party_id, p.display_name AS proxy_name, p.party_type,
       o.title, o.obligation_type, o.scope_type, o.scope_id, o.metric_key,
       o.target_value, o.target_unit, o.target_date, o.status,
       t.threshold_key, t.severity AS threshold_severity,
       CASE WHEN o.status = 'breached' THEN TRUE ELSE FALSE END AS ecological_harm_flag
FROM nature_stewardship_obligation o
JOIN party p ON p.id = o.proxy_party_id
LEFT JOIN ecological_threshold t ON t.id = o.threshold_id;

CREATE OR REPLACE VIEW v_public_ecological_stewardship AS
SELECT o.id AS obligation_id, o.proxy_party_id, p.display_name AS proxy_name,
       o.title, o.obligation_type, o.metric_key, o.target_value, o.target_unit,
       o.target_date, o.status, o.evidence,
       'Proxy interests are documented ecological obligations; no consent or vote is claimed.' AS limitation
FROM nature_stewardship_obligation o
JOIN party p ON p.id = o.proxy_party_id
WHERE o.status IN ('approved', 'in_progress', 'met')
  AND p.privacy_level = 'public';

COMMENT ON VIEW v_public_ecological_stewardship IS 'Public-safe nature stewardship projection with explicit proxy limitation';
