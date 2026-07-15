-- ============================================================
-- 213_stakeholder_vocabulary.sql - Canonical stakeholder foundation
-- ============================================================
-- Additive identity and relationship layer. Existing domain records remain
-- canonical for their domains and link here through party_identifier.

CREATE TABLE IF NOT EXISTS party (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_type VARCHAR(30) NOT NULL CHECK (party_type IN (
        'person', 'organization', 'community', 'cooperative',
        'public_institution', 'ecosystem', 'species', 'future_generation'
    )),
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('draft', 'active', 'suspended', 'retired')),
    privacy_level VARCHAR(20) NOT NULL DEFAULT 'private'
        CHECK (privacy_level IN ('private', 'limited', 'public')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_party_type ON party(party_type);
CREATE INDEX IF NOT EXISTS idx_party_status ON party(status);
CREATE INDEX IF NOT EXISTS idx_party_name ON party(display_name);

DROP TRIGGER IF EXISTS trg_party_updated_at ON party;
CREATE TRIGGER trg_party_updated_at
    BEFORE UPDATE ON party
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS party_identifier (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    identifier_type VARCHAR(50) NOT NULL,
    identifier_value TEXT NOT NULL,
    source_system VARCHAR(100) NOT NULL,
    source_id VARCHAR(255),
    verification_status VARCHAR(20) NOT NULL DEFAULT 'unreviewed'
        CHECK (verification_status IN ('unreviewed', 'candidate', 'verified', 'rejected')),
    confidence NUMERIC(5,4) CHECK (confidence >= 0 AND confidence <= 1),
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (identifier_type, identifier_value, source_system)
);

CREATE INDEX IF NOT EXISTS idx_party_identifier_party ON party_identifier(party_id);
CREATE INDEX IF NOT EXISTS idx_party_identifier_source ON party_identifier(source_system, source_id);
CREATE INDEX IF NOT EXISTS idx_party_identifier_status ON party_identifier(verification_status);

CREATE TABLE IF NOT EXISTS party_relationship (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    to_party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    scope_id UUID,
    legitimacy VARCHAR(20) NOT NULL DEFAULT 'derivative'
        CHECK (legitimacy IN ('normative', 'derivative', 'proxy', 'unknown')),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'active', 'suspended', 'ended', 'rejected')),
    confidence NUMERIC(5,4) CHECK (confidence >= 0 AND confidence <= 1),
    valid_from DATE,
    valid_until DATE,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (from_party_id <> to_party_id),
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from)
);

CREATE INDEX IF NOT EXISTS idx_party_relationship_from ON party_relationship(from_party_id, status);
CREATE INDEX IF NOT EXISTS idx_party_relationship_to ON party_relationship(to_party_id, status);
CREATE INDEX IF NOT EXISTS idx_party_relationship_scope ON party_relationship(scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_party_relationship_type ON party_relationship(relationship_type);

CREATE TABLE IF NOT EXISTS stakeholder_interest (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    interest_type VARCHAR(30) NOT NULL CHECK (interest_type IN (
        'need', 'claim', 'obligation', 'dependency', 'benefit', 'harm', 'stewardship'
    )),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    legitimacy VARCHAR(20) NOT NULL DEFAULT 'normative'
        CHECK (legitimacy IN ('normative', 'derivative', 'proxy', 'unknown')),
    priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    scope_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'validated', 'in_progress', 'met', 'deferred', 'retired')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stakeholder_interest_party ON stakeholder_interest(party_id, status);
CREATE INDEX IF NOT EXISTS idx_stakeholder_interest_scope ON stakeholder_interest(scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_stakeholder_interest_type ON stakeholder_interest(interest_type);

CREATE TABLE IF NOT EXISTS stakeholder_salience_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    interest_id UUID REFERENCES stakeholder_interest(id) ON DELETE CASCADE,
    power_score NUMERIC(4,2) NOT NULL DEFAULT 0 CHECK (power_score BETWEEN 0 AND 10),
    legitimacy_score NUMERIC(4,2) NOT NULL DEFAULT 0 CHECK (legitimacy_score BETWEEN 0 AND 10),
    urgency_score NUMERIC(4,2) NOT NULL DEFAULT 0 CHECK (urgency_score BETWEEN 0 AND 10),
    vulnerability_score NUMERIC(4,2) NOT NULL DEFAULT 0 CHECK (vulnerability_score BETWEEN 0 AND 10),
    harm_exposure_score NUMERIC(4,2) NOT NULL DEFAULT 0 CHECK (harm_exposure_score BETWEEN 0 AND 10),
    representation_score NUMERIC(4,2) NOT NULL DEFAULT 0 CHECK (representation_score BETWEEN 0 AND 10),
    advisory_score NUMERIC(6,3) GENERATED ALWAYS AS (
        (power_score * 0.15) + (legitimacy_score * 0.25) + (urgency_score * 0.20)
        + (vulnerability_score * 0.15) + (harm_exposure_score * 0.15)
        + ((10 - representation_score) * 0.10)
    ) STORED,
    rationale TEXT NOT NULL,
    assessed_by UUID,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    review_status VARCHAR(20) NOT NULL DEFAULT 'advisory'
        CHECK (review_status IN ('advisory', 'reviewed', 'superseded')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_salience_party ON stakeholder_salience_assessment(party_id, assessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_salience_interest ON stakeholder_salience_assessment(interest_id);
CREATE INDEX IF NOT EXISTS idx_salience_score ON stakeholder_salience_assessment(advisory_score DESC);

CREATE OR REPLACE VIEW v_stakeholder_landscape AS
SELECT
    p.id AS party_id,
    p.party_type,
    p.display_name,
    p.status AS party_status,
    p.privacy_level,
    COUNT(DISTINCT pi.id) AS identifier_count,
    COUNT(DISTINCT CASE WHEN pr.status = 'active' THEN pr.id END) AS active_relationship_count,
    COUNT(DISTINCT si.id) FILTER (WHERE si.status NOT IN ('retired', 'met')) AS open_interest_count,
    latest.advisory_score,
    latest.review_status AS salience_review_status,
    GREATEST(p.updated_at, COALESCE(latest.assessed_at, p.updated_at)) AS last_updated_at
FROM party p
LEFT JOIN party_identifier pi ON pi.party_id = p.id
LEFT JOIN party_relationship pr ON pr.from_party_id = p.id OR pr.to_party_id = p.id
LEFT JOIN stakeholder_interest si ON si.party_id = p.id
LEFT JOIN LATERAL (
    SELECT advisory_score, review_status, assessed_at
    FROM stakeholder_salience_assessment ssa
    WHERE ssa.party_id = p.id
    ORDER BY assessed_at DESC
    LIMIT 1
) latest ON TRUE
GROUP BY p.id, p.party_type, p.display_name, p.status, p.privacy_level,
         latest.advisory_score, latest.review_status, latest.assessed_at;

CREATE OR REPLACE VIEW v_stakeholder_identity_links AS
SELECT
    pi.id AS identifier_id,
    pi.party_id,
    p.party_type,
    p.display_name,
    pi.identifier_type,
    pi.identifier_value,
    pi.source_system,
    pi.source_id,
    pi.verification_status,
    pi.confidence,
    pi.reviewed_at
FROM party_identifier pi
JOIN party p ON p.id = pi.party_id;

COMMENT ON TABLE party IS 'Canonical stakeholder party registry; domain tables link through party_identifier';
COMMENT ON TABLE party_relationship IS 'Scoped, evidence-backed relationships between parties';
COMMENT ON TABLE stakeholder_interest IS 'Needs, claims, obligations, benefits, harms, and stewardship interests';
COMMENT ON TABLE stakeholder_salience_assessment IS 'Advisory power, legitimacy, urgency, vulnerability, harm, and representation assessment';
COMMENT ON VIEW v_stakeholder_landscape IS 'Internal stakeholder landscape summary with latest advisory salience';
