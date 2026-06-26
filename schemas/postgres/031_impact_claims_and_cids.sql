-- ============================================================
-- 031_impact_claims_and_cids.sql — Impact claims and CIDS Essential Tier
-- ============================================================

CREATE TABLE IF NOT EXISTS stakeholder_outcome (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE RESTRICT,
    outcome_name VARCHAR(255) NOT NULL,
    outcome_description TEXT,
    stakeholder_group VARCHAR(100) NOT NULL,
    stakeholder_description TEXT,
    importance VARCHAR(20),
    importance_perspective VARCHAR(255),
    is_underserved BOOLEAN DEFAULT FALSE,
    framework_key VARCHAR(100),
    dimension_key VARCHAR(100),
    sdg_number INTEGER REFERENCES sdg(sdg_number),
    capital_key VARCHAR(100) REFERENCES form_of_capital(capital_key),
    pillar_key VARCHAR(100) REFERENCES pillar_of_value(pillar_key),
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_stakeholder_outcome_location ON stakeholder_outcome(location_id);
CREATE INDEX IF NOT EXISTS idx_stakeholder_outcome_group ON stakeholder_outcome(stakeholder_group);
CREATE INDEX IF NOT EXISTS idx_stakeholder_outcome_status ON stakeholder_outcome(status);
CREATE INDEX IF NOT EXISTS idx_stakeholder_outcome_sdg ON stakeholder_outcome(sdg_number);

ALTER TABLE stakeholder_outcome DROP CONSTRAINT IF EXISTS chk_stakeholder_outcome_lifecycle;
ALTER TABLE stakeholder_outcome ADD CONSTRAINT chk_stakeholder_outcome_lifecycle CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE stakeholder_outcome DROP CONSTRAINT IF EXISTS chk_stakeholder_outcome_importance;
ALTER TABLE stakeholder_outcome ADD CONSTRAINT chk_stakeholder_outcome_importance CHECK (
    importance IS NULL OR importance IN ('high', 'moderate', 'low', 'neutral', 'unimportant', 'unknown')
);

CREATE TABLE IF NOT EXISTS impact_claim (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE RESTRICT,
    stakeholder_outcome_id UUID REFERENCES stakeholder_outcome(id) ON DELETE SET NULL,
    metric_id UUID REFERENCES metric_definition(id) ON DELETE SET NULL,
    claim_type VARCHAR(50) NOT NULL,
    claim_category VARCHAR(50) NOT NULL,
    claim_date DATE NOT NULL,
    period_start DATE,
    period_end DATE,
    claim_text TEXT NOT NULL,
    claim_value NUMERIC(15,4),
    claim_unit VARCHAR(100),
    source_record_ids UUID[],
    evidence_cid TEXT,
    evidence_hash VARCHAR(64),
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    attestation_uid VARCHAR(255),
    public_claim BOOLEAN DEFAULT FALSE,
    confidence_level VARCHAR(20),
    confidence_notes TEXT,
    methodology_ref TEXT,
    external_verifier TEXT,
    reviewer_id UUID REFERENCES staff(id) ON DELETE SET NULL,
    review_date DATE,
    review_notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    parent_claim_id UUID REFERENCES impact_claim(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_impact_claim_location ON impact_claim(location_id);
CREATE INDEX IF NOT EXISTS idx_impact_claim_type ON impact_claim(claim_type);
CREATE INDEX IF NOT EXISTS idx_impact_claim_category ON impact_claim(claim_category);
CREATE INDEX IF NOT EXISTS idx_impact_claim_status ON impact_claim(status);
CREATE INDEX IF NOT EXISTS idx_impact_claim_evidence_maturity ON impact_claim(evidence_maturity);
CREATE INDEX IF NOT EXISTS idx_impact_claim_public ON impact_claim(public_claim, status);

ALTER TABLE impact_claim DROP CONSTRAINT IF EXISTS chk_impact_claim_lifecycle;
ALTER TABLE impact_claim ADD CONSTRAINT chk_impact_claim_lifecycle CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE impact_claim DROP CONSTRAINT IF EXISTS chk_impact_claim_type;
ALTER TABLE impact_claim ADD CONSTRAINT chk_impact_claim_type CHECK (claim_type IN (
    'raw_observation', 'submitted_record', 'verified_record', 'published_record',
    'internal_estimate', 'public_claim', 'forecast', 'assumption', 'scenario',
    'third_party_verified_claim', 'rejected_claim', 'revised_claim'
));

ALTER TABLE impact_claim DROP CONSTRAINT IF EXISTS chk_impact_claim_category;
ALTER TABLE impact_claim ADD CONSTRAINT chk_impact_claim_category CHECK (claim_category IN (
    'social', 'ecological', 'financial', 'governance', 'carbon', 'biodiversity', 'operational', 'other'
));

ALTER TABLE impact_claim DROP CONSTRAINT IF EXISTS chk_impact_claim_confidence;
ALTER TABLE impact_claim ADD CONSTRAINT chk_impact_claim_confidence CHECK (
    confidence_level IS NULL OR confidence_level IN ('high', 'medium', 'low', 'unknown')
);

-- Public carbon claims require external verification (Level 6).
ALTER TABLE impact_claim DROP CONSTRAINT IF EXISTS chk_impact_public_carbon_level6;
ALTER TABLE impact_claim ADD CONSTRAINT chk_impact_public_carbon_level6 CHECK (
    NOT (public_claim = TRUE AND claim_category = 'carbon')
    OR (
        evidence_maturity = 6
        AND claim_type = 'third_party_verified_claim'
        AND NULLIF(TRIM(COALESCE(external_verifier, '')), '') IS NOT NULL
        AND NULLIF(TRIM(COALESCE(methodology_ref, '')), '') IS NOT NULL
        AND status = 'published'
    )
);

CREATE TABLE IF NOT EXISTS metric_proposal (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE RESTRICT,
    proposed_by VARCHAR(255) NOT NULL,
    proposed_by_role VARCHAR(100) NOT NULL,
    proposal_date DATE NOT NULL,
    metric_name VARCHAR(255) NOT NULL,
    metric_description TEXT NOT NULL,
    unit_of_measure VARCHAR(100),
    category VARCHAR(100),
    rationale TEXT,
    data_source VARCHAR(255),
    collection_method VARCHAR(255),
    frequency VARCHAR(50),
    stakeholder_groups TEXT[] DEFAULT '{}',
    discussion_notes JSONB DEFAULT '[]',
    status VARCHAR(50) DEFAULT 'proposed',
    reviewed_by UUID REFERENCES staff(id) ON DELETE SET NULL,
    review_date DATE,
    implementation_date DATE,
    metric_definition_id UUID REFERENCES metric_definition(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metric_proposal_location ON metric_proposal(location_id);
CREATE INDEX IF NOT EXISTS idx_metric_proposal_status ON metric_proposal(status);
CREATE INDEX IF NOT EXISTS idx_metric_proposal_role ON metric_proposal(proposed_by_role);

ALTER TABLE metric_proposal DROP CONSTRAINT IF EXISTS chk_metric_proposal_status;
ALTER TABLE metric_proposal ADD CONSTRAINT chk_metric_proposal_status CHECK (status IN (
    'proposed', 'discussed', 'approved', 'implemented', 'deprecated', 'rejected'
));

CREATE OR REPLACE VIEW v_public_impact_claim_summary AS
SELECT
    ic.id,
    ic.location_id,
    ic.claim_type,
    ic.claim_category,
    ic.claim_date,
    ic.period_start,
    ic.period_end,
    ic.claim_text,
    ic.claim_value,
    ic.claim_unit,
    ic.evidence_maturity,
    em.label AS evidence_maturity_label,
    ic.confidence_level,
    ic.methodology_ref,
    ic.external_verifier,
    ic.attestation_uid
FROM impact_claim ic
LEFT JOIN evidence_maturity_level em ON em.level = ic.evidence_maturity
WHERE ic.public_claim = TRUE
  AND ic.status = 'published'
  AND EXISTS (
      SELECT 1 FROM evidence_maturity_level level
      WHERE level.level = ic.evidence_maturity
        AND level.public_claim_allowed = TRUE
  )
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = ic.location_id
        AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('impact-claims-cids-v1', 'Impact claims, stakeholder outcomes, and participatory metric proposal foundations', 'schema 031')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
