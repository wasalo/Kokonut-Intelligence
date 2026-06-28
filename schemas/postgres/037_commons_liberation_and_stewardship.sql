-- ============================================================
-- 037_commons_liberation_and_stewardship.sql — Time liberation, aligned capital, inclusive governance, and land stewardship
-- ============================================================

CREATE TABLE IF NOT EXISTS time_liberation_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    observation_date DATE NOT NULL,
    workflow_area VARCHAR(100) NOT NULL,
    baseline_hours NUMERIC(12,4),
    observed_hours NUMERIC(12,4),
    hours_reclaimed NUMERIC(12,4),
    burden_reduction_pct NUMERIC(8,4),
    automation_or_agent_used BOOLEAN DEFAULT FALSE,
    automation_type VARCHAR(100),
    beneficiary_group VARCHAR(100),
    liberation_summary TEXT NOT NULL,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_time_liberation_location ON time_liberation_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_time_liberation_workflow ON time_liberation_observation(workflow_area);
CREATE INDEX IF NOT EXISTS idx_time_liberation_status ON time_liberation_observation(status);

ALTER TABLE time_liberation_observation DROP CONSTRAINT IF EXISTS chk_time_liberation_status;
ALTER TABLE time_liberation_observation ADD CONSTRAINT chk_time_liberation_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE time_liberation_observation DROP CONSTRAINT IF EXISTS chk_time_liberation_values;
ALTER TABLE time_liberation_observation ADD CONSTRAINT chk_time_liberation_values CHECK (
    (baseline_hours IS NULL OR baseline_hours >= 0)
    AND (observed_hours IS NULL OR observed_hours >= 0)
    AND (hours_reclaimed IS NULL OR hours_reclaimed >= 0)
    AND (burden_reduction_pct IS NULL OR burden_reduction_pct BETWEEN -100 AND 100)
);

CREATE TABLE IF NOT EXISTS capital_alignment_assessment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    capital_source_id UUID REFERENCES capital_source(id) ON DELETE SET NULL,
    assessment_date DATE NOT NULL,
    provider_name VARCHAR(255),
    provider_type VARCHAR(100) NOT NULL,
    alignment_status VARCHAR(50) NOT NULL DEFAULT 'under_review',
    extractive_risk_level VARCHAR(50),
    community_control_terms TEXT,
    exit_pressure_risk TEXT,
    profit_extraction_limits TEXT,
    commons_reinvestment_commitment_pct NUMERIC(7,4),
    assessment_summary TEXT NOT NULL,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_capital_alignment_location ON capital_alignment_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_capital_alignment_provider ON capital_alignment_assessment(provider_type);
CREATE INDEX IF NOT EXISTS idx_capital_alignment_status ON capital_alignment_assessment(status, alignment_status);

ALTER TABLE capital_alignment_assessment DROP CONSTRAINT IF EXISTS chk_capital_alignment_status;
ALTER TABLE capital_alignment_assessment ADD CONSTRAINT chk_capital_alignment_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE capital_alignment_assessment DROP CONSTRAINT IF EXISTS chk_capital_alignment_state;
ALTER TABLE capital_alignment_assessment ADD CONSTRAINT chk_capital_alignment_state CHECK (alignment_status IN (
    'aligned', 'conditionally_aligned', 'under_review', 'misaligned', 'rejected'
));

ALTER TABLE capital_alignment_assessment DROP CONSTRAINT IF EXISTS chk_capital_alignment_provider;
ALTER TABLE capital_alignment_assessment ADD CONSTRAINT chk_capital_alignment_provider CHECK (provider_type IN (
    'dao_treasury', 'grantmaker', 'public_goods_funder', 'sponsor', 'buyer_partner',
    'impact_investor', 'debt_provider', 'equity_provider', 'other'
));

ALTER TABLE capital_alignment_assessment DROP CONSTRAINT IF EXISTS chk_capital_alignment_risk;
ALTER TABLE capital_alignment_assessment ADD CONSTRAINT chk_capital_alignment_risk CHECK (
    extractive_risk_level IS NULL OR extractive_risk_level IN ('low', 'medium', 'high', 'critical', 'unknown')
);

ALTER TABLE capital_alignment_assessment DROP CONSTRAINT IF EXISTS chk_capital_alignment_reinvestment;
ALTER TABLE capital_alignment_assessment ADD CONSTRAINT chk_capital_alignment_reinvestment CHECK (
    commons_reinvestment_commitment_pct IS NULL OR commons_reinvestment_commitment_pct BETWEEN 0 AND 100
);

CREATE TABLE IF NOT EXISTS governance_inclusion_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    dao_proposal_id UUID REFERENCES dao_proposal(id) ON DELETE SET NULL,
    observation_date DATE NOT NULL,
    governance_body VARCHAR(255) NOT NULL,
    inclusion_scope VARCHAR(100) NOT NULL,
    represented_groups TEXT[] DEFAULT '{}',
    missing_groups TEXT[] DEFAULT '{}',
    pseudonymous_participation_enabled BOOLEAN DEFAULT FALSE,
    marginalized_voice_count INTEGER,
    total_participant_count INTEGER,
    representation_coverage_pct NUMERIC(8,4),
    inclusion_summary TEXT NOT NULL,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_governance_inclusion_location ON governance_inclusion_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_governance_inclusion_scope ON governance_inclusion_observation(inclusion_scope);
CREATE INDEX IF NOT EXISTS idx_governance_inclusion_status ON governance_inclusion_observation(status);

ALTER TABLE governance_inclusion_observation DROP CONSTRAINT IF EXISTS chk_governance_inclusion_status;
ALTER TABLE governance_inclusion_observation ADD CONSTRAINT chk_governance_inclusion_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE governance_inclusion_observation DROP CONSTRAINT IF EXISTS chk_governance_inclusion_scope;
ALTER TABLE governance_inclusion_observation ADD CONSTRAINT chk_governance_inclusion_scope CHECK (inclusion_scope IN (
    'dao_committee', 'guild', 'farm_operator_group', 'stakeholder_review', 'metric_review', 'publication_review', 'other'
));

ALTER TABLE governance_inclusion_observation DROP CONSTRAINT IF EXISTS chk_governance_inclusion_values;
ALTER TABLE governance_inclusion_observation ADD CONSTRAINT chk_governance_inclusion_values CHECK (
    (marginalized_voice_count IS NULL OR marginalized_voice_count >= 0)
    AND (total_participant_count IS NULL OR total_participant_count >= 0)
    AND (representation_coverage_pct IS NULL OR representation_coverage_pct BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS land_stewardship_commitment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    tenure_rights_assessment_id UUID REFERENCES tenure_rights_assessment(id) ON DELETE SET NULL,
    commitment_date DATE NOT NULL,
    stewardship_model VARCHAR(100) NOT NULL,
    landlord_dependency_risk VARCHAR(50),
    anti_speculation_terms TEXT,
    community_benefit_rights TEXT,
    commons_transition_path TEXT,
    land_access_summary TEXT NOT NULL,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_land_stewardship_location ON land_stewardship_commitment(location_id);
CREATE INDEX IF NOT EXISTS idx_land_stewardship_model ON land_stewardship_commitment(stewardship_model);
CREATE INDEX IF NOT EXISTS idx_land_stewardship_status ON land_stewardship_commitment(status);

ALTER TABLE land_stewardship_commitment DROP CONSTRAINT IF EXISTS chk_land_stewardship_status;
ALTER TABLE land_stewardship_commitment ADD CONSTRAINT chk_land_stewardship_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE land_stewardship_commitment DROP CONSTRAINT IF EXISTS chk_land_stewardship_model;
ALTER TABLE land_stewardship_commitment ADD CONSTRAINT chk_land_stewardship_model CHECK (stewardship_model IN (
    'community_stewardship', 'cooperative_use', 'family_stewardship_with_public_goods',
    'commons_trust_pathway', 'lease_to_stewardship', 'customary_commons', 'other'
));

ALTER TABLE land_stewardship_commitment DROP CONSTRAINT IF EXISTS chk_land_stewardship_risk;
ALTER TABLE land_stewardship_commitment ADD CONSTRAINT chk_land_stewardship_risk CHECK (
    landlord_dependency_risk IS NULL OR landlord_dependency_risk IN ('low', 'medium', 'high', 'critical', 'unknown')
);

CREATE OR REPLACE VIEW v_public_time_liberation_summary AS
SELECT
    tlo.id,
    tlo.location_id,
    tlo.farm_id,
    tlo.observation_date,
    tlo.workflow_area,
    tlo.baseline_hours,
    tlo.observed_hours,
    tlo.hours_reclaimed,
    tlo.burden_reduction_pct,
    tlo.automation_or_agent_used,
    tlo.automation_type,
    tlo.beneficiary_group,
    tlo.public_summary,
    tlo.evidence_maturity,
    em.label AS evidence_maturity_label,
    tlo.metadata
FROM time_liberation_observation tlo
LEFT JOIN evidence_maturity_level em ON em.level = tlo.evidence_maturity
WHERE tlo.status = 'published'
  AND tlo.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(tlo.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = tlo.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_capital_alignment_summary AS
SELECT
    caa.id,
    caa.location_id,
    caa.farm_id,
    caa.capital_source_id,
    caa.assessment_date,
    caa.provider_name,
    caa.provider_type,
    caa.alignment_status,
    caa.extractive_risk_level,
    caa.community_control_terms,
    caa.exit_pressure_risk,
    caa.profit_extraction_limits,
    caa.commons_reinvestment_commitment_pct,
    caa.public_summary,
    caa.evidence_maturity,
    em.label AS evidence_maturity_label,
    caa.metadata
FROM capital_alignment_assessment caa
LEFT JOIN evidence_maturity_level em ON em.level = caa.evidence_maturity
WHERE caa.status = 'published'
  AND caa.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(caa.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = caa.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_governance_inclusion_summary AS
SELECT
    gio.id,
    gio.location_id,
    gio.dao_proposal_id,
    gio.observation_date,
    gio.governance_body,
    gio.inclusion_scope,
    gio.represented_groups,
    gio.missing_groups,
    gio.pseudonymous_participation_enabled,
    gio.marginalized_voice_count,
    gio.total_participant_count,
    gio.representation_coverage_pct,
    gio.public_summary,
    gio.evidence_maturity,
    em.label AS evidence_maturity_label,
    gio.metadata
FROM governance_inclusion_observation gio
LEFT JOIN evidence_maturity_level em ON em.level = gio.evidence_maturity
WHERE gio.status = 'published'
  AND gio.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(gio.public_summary, '')), '') IS NOT NULL
  AND (
      gio.location_id IS NULL OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = gio.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

CREATE OR REPLACE VIEW v_public_land_stewardship_summary AS
SELECT
    lsc.id,
    lsc.location_id,
    lsc.farm_id,
    lsc.tenure_rights_assessment_id,
    lsc.commitment_date,
    lsc.stewardship_model,
    lsc.landlord_dependency_risk,
    lsc.anti_speculation_terms,
    lsc.community_benefit_rights,
    lsc.commons_transition_path,
    lsc.public_summary,
    lsc.evidence_maturity,
    em.label AS evidence_maturity_label,
    lsc.metadata
FROM land_stewardship_commitment lsc
LEFT JOIN evidence_maturity_level em ON em.level = lsc.evidence_maturity
WHERE lsc.status = 'published'
  AND lsc.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(lsc.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = lsc.location_id
        AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('commons-liberation-stewardship-v1', 'Time liberation, aligned capital, inclusive governance, and land stewardship evidence', 'schema 037')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
