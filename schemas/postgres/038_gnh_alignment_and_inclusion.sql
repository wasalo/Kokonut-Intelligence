-- ============================================================
-- 038_gnh_alignment_and_inclusion.sql — GNH alignment, cultural preservation, renewable energy, access, and foundational well-being
-- ============================================================

CREATE TABLE IF NOT EXISTS gnh_alignment_assessment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    assessment_date DATE NOT NULL,
    gnh_domain VARCHAR(100) NOT NULL,
    principle_refs TEXT[] DEFAULT '{}',
    alignment_score NUMERIC(5,2),
    strengths TEXT[] DEFAULT '{}',
    gaps TEXT[] DEFAULT '{}',
    safeguards TEXT[] DEFAULT '{}',
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

CREATE INDEX IF NOT EXISTS idx_gnh_alignment_location ON gnh_alignment_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_gnh_alignment_domain ON gnh_alignment_assessment(gnh_domain);
CREATE INDEX IF NOT EXISTS idx_gnh_alignment_status ON gnh_alignment_assessment(status);

ALTER TABLE gnh_alignment_assessment DROP CONSTRAINT IF EXISTS chk_gnh_alignment_status;
ALTER TABLE gnh_alignment_assessment ADD CONSTRAINT chk_gnh_alignment_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE gnh_alignment_assessment DROP CONSTRAINT IF EXISTS chk_gnh_alignment_domain;
ALTER TABLE gnh_alignment_assessment ADD CONSTRAINT chk_gnh_alignment_domain CHECK (gnh_domain IN (
    'psychological_wellbeing', 'health', 'education', 'culture', 'time_use',
    'good_governance', 'community_vitality', 'ecological_diversity', 'living_standards', 'other'
));

ALTER TABLE gnh_alignment_assessment DROP CONSTRAINT IF EXISTS chk_gnh_alignment_score;
ALTER TABLE gnh_alignment_assessment ADD CONSTRAINT chk_gnh_alignment_score CHECK (
    alignment_score IS NULL OR alignment_score BETWEEN 0 AND 10
);

CREATE TABLE IF NOT EXISTS cultural_preservation_plan (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    cultural_context_record_id UUID REFERENCES cultural_context_record(id) ON DELETE SET NULL,
    plan_date DATE NOT NULL,
    cultural_element VARCHAR(255) NOT NULL,
    preservation_type VARCHAR(100) NOT NULL,
    local_language VARCHAR(50),
    traditional_practice_summary TEXT,
    digital_integration_strategy TEXT,
    consent_protocol TEXT,
    local_reviewer_role VARCHAR(100),
    implementation_status VARCHAR(50) DEFAULT 'planned',
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

CREATE INDEX IF NOT EXISTS idx_cultural_preservation_location ON cultural_preservation_plan(location_id);
CREATE INDEX IF NOT EXISTS idx_cultural_preservation_type ON cultural_preservation_plan(preservation_type);
CREATE INDEX IF NOT EXISTS idx_cultural_preservation_status ON cultural_preservation_plan(status, implementation_status);

ALTER TABLE cultural_preservation_plan DROP CONSTRAINT IF EXISTS chk_cultural_preservation_status;
ALTER TABLE cultural_preservation_plan ADD CONSTRAINT chk_cultural_preservation_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE cultural_preservation_plan DROP CONSTRAINT IF EXISTS chk_cultural_preservation_type;
ALTER TABLE cultural_preservation_plan ADD CONSTRAINT chk_cultural_preservation_type CHECK (preservation_type IN (
    'traditional_practice', 'local_language', 'heritage_species', 'storytelling',
    'cultural_review', 'visual_identity', 'education', 'other'
));

ALTER TABLE cultural_preservation_plan DROP CONSTRAINT IF EXISTS chk_cultural_preservation_state;
ALTER TABLE cultural_preservation_plan ADD CONSTRAINT chk_cultural_preservation_state CHECK (implementation_status IN (
    'planned', 'in_progress', 'implemented', 'blocked', 'deferred', 'cancelled'
));

CREATE TABLE IF NOT EXISTS renewable_energy_plan (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    plan_date DATE NOT NULL,
    energy_use_case VARCHAR(100) NOT NULL,
    renewable_source VARCHAR(100) NOT NULL,
    implementation_status VARCHAR(50) DEFAULT 'planned',
    current_energy_source VARCHAR(100),
    planned_capacity_kw NUMERIC(12,4),
    estimated_annual_kwh NUMERIC(18,4),
    renewable_share_pct NUMERIC(8,4),
    fossil_displacement_estimate_co2e_tonnes NUMERIC(14,6),
    infrastructure_dependencies TEXT[] DEFAULT '{}',
    maintenance_owner_role VARCHAR(100),
    plan_summary TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_renewable_energy_location ON renewable_energy_plan(location_id);
CREATE INDEX IF NOT EXISTS idx_renewable_energy_source ON renewable_energy_plan(renewable_source);
CREATE INDEX IF NOT EXISTS idx_renewable_energy_status ON renewable_energy_plan(status, implementation_status);

ALTER TABLE renewable_energy_plan DROP CONSTRAINT IF EXISTS chk_renewable_energy_status;
ALTER TABLE renewable_energy_plan ADD CONSTRAINT chk_renewable_energy_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE renewable_energy_plan DROP CONSTRAINT IF EXISTS chk_renewable_energy_source;
ALTER TABLE renewable_energy_plan ADD CONSTRAINT chk_renewable_energy_source CHECK (renewable_source IN (
    'solar', 'biogas', 'wind', 'micro_hydro', 'biomass', 'renewable_grid', 'hybrid', 'other'
));

ALTER TABLE renewable_energy_plan DROP CONSTRAINT IF EXISTS chk_renewable_energy_state;
ALTER TABLE renewable_energy_plan ADD CONSTRAINT chk_renewable_energy_state CHECK (implementation_status IN (
    'planned', 'in_progress', 'implemented', 'blocked', 'deferred', 'cancelled'
));

ALTER TABLE renewable_energy_plan DROP CONSTRAINT IF EXISTS chk_renewable_energy_values;
ALTER TABLE renewable_energy_plan ADD CONSTRAINT chk_renewable_energy_values CHECK (
    (planned_capacity_kw IS NULL OR planned_capacity_kw >= 0)
    AND (estimated_annual_kwh IS NULL OR estimated_annual_kwh >= 0)
    AND (renewable_share_pct IS NULL OR renewable_share_pct BETWEEN 0 AND 100)
    AND (fossil_displacement_estimate_co2e_tonnes IS NULL OR fossil_displacement_estimate_co2e_tonnes >= 0)
);

CREATE TABLE IF NOT EXISTS vulnerable_group_access_plan (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    plan_date DATE NOT NULL,
    access_scope VARCHAR(100) NOT NULL,
    vulnerable_groups TEXT[] DEFAULT '{}',
    access_barriers TEXT[] DEFAULT '{}',
    accommodations TEXT[] DEFAULT '{}',
    participation_pathways TEXT[] DEFAULT '{}',
    accountable_role VARCHAR(100),
    implementation_status VARCHAR(50) DEFAULT 'planned',
    access_coverage_pct NUMERIC(8,4),
    plan_summary TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_vulnerable_access_location ON vulnerable_group_access_plan(location_id);
CREATE INDEX IF NOT EXISTS idx_vulnerable_access_scope ON vulnerable_group_access_plan(access_scope);
CREATE INDEX IF NOT EXISTS idx_vulnerable_access_status ON vulnerable_group_access_plan(status, implementation_status);

ALTER TABLE vulnerable_group_access_plan DROP CONSTRAINT IF EXISTS chk_vulnerable_access_status;
ALTER TABLE vulnerable_group_access_plan ADD CONSTRAINT chk_vulnerable_access_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE vulnerable_group_access_plan DROP CONSTRAINT IF EXISTS chk_vulnerable_access_scope;
ALTER TABLE vulnerable_group_access_plan ADD CONSTRAINT chk_vulnerable_access_scope CHECK (access_scope IN (
    'farm_operations', 'governance', 'reporting', 'training', 'benefit_distribution', 'digital_access', 'other'
));

ALTER TABLE vulnerable_group_access_plan DROP CONSTRAINT IF EXISTS chk_vulnerable_access_state;
ALTER TABLE vulnerable_group_access_plan ADD CONSTRAINT chk_vulnerable_access_state CHECK (implementation_status IN (
    'planned', 'in_progress', 'implemented', 'blocked', 'deferred', 'cancelled'
));

ALTER TABLE vulnerable_group_access_plan DROP CONSTRAINT IF EXISTS chk_vulnerable_access_coverage;
ALTER TABLE vulnerable_group_access_plan ADD CONSTRAINT chk_vulnerable_access_coverage CHECK (
    access_coverage_pct IS NULL OR access_coverage_pct BETWEEN 0 AND 100
);

CREATE TABLE IF NOT EXISTS foundational_wellbeing_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    observation_date DATE NOT NULL,
    wellbeing_domain VARCHAR(100) NOT NULL,
    stakeholder_group VARCHAR(100),
    score_value NUMERIC(5,2),
    count_value INTEGER,
    qualitative_signal TEXT,
    source_tables TEXT[] DEFAULT '{}',
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

CREATE INDEX IF NOT EXISTS idx_foundational_wellbeing_location ON foundational_wellbeing_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_foundational_wellbeing_domain ON foundational_wellbeing_observation(wellbeing_domain);
CREATE INDEX IF NOT EXISTS idx_foundational_wellbeing_status ON foundational_wellbeing_observation(status);

ALTER TABLE foundational_wellbeing_observation DROP CONSTRAINT IF EXISTS chk_foundational_wellbeing_status;
ALTER TABLE foundational_wellbeing_observation ADD CONSTRAINT chk_foundational_wellbeing_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE foundational_wellbeing_observation DROP CONSTRAINT IF EXISTS chk_foundational_wellbeing_domain;
ALTER TABLE foundational_wellbeing_observation ADD CONSTRAINT chk_foundational_wellbeing_domain CHECK (wellbeing_domain IN (
    'happiness', 'peace', 'safety', 'food_security', 'basic_needs', 'dignity', 'belonging', 'other'
));

ALTER TABLE foundational_wellbeing_observation DROP CONSTRAINT IF EXISTS chk_foundational_wellbeing_values;
ALTER TABLE foundational_wellbeing_observation ADD CONSTRAINT chk_foundational_wellbeing_values CHECK (
    (score_value IS NULL OR score_value BETWEEN 0 AND 10)
    AND (count_value IS NULL OR count_value >= 0)
    AND (score_value IS NOT NULL OR count_value IS NOT NULL OR NULLIF(TRIM(COALESCE(qualitative_signal, '')), '') IS NOT NULL)
);

CREATE OR REPLACE VIEW v_public_gnh_alignment_summary AS
SELECT
    gaa.id,
    gaa.location_id,
    gaa.farm_id,
    gaa.assessment_date,
    gaa.gnh_domain,
    gaa.principle_refs,
    gaa.alignment_score,
    gaa.strengths,
    gaa.gaps,
    gaa.safeguards,
    gaa.public_summary,
    gaa.evidence_maturity,
    em.label AS evidence_maturity_label,
    gaa.metadata
FROM gnh_alignment_assessment gaa
LEFT JOIN evidence_maturity_level em ON em.level = gaa.evidence_maturity
WHERE gaa.status = 'published'
  AND gaa.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(gaa.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = gaa.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_cultural_preservation_summary AS
SELECT
    cpp.id,
    cpp.location_id,
    cpp.farm_id,
    cpp.cultural_context_record_id,
    cpp.plan_date,
    cpp.cultural_element,
    cpp.preservation_type,
    cpp.local_language,
    cpp.digital_integration_strategy,
    cpp.consent_protocol,
    cpp.local_reviewer_role,
    cpp.implementation_status,
    cpp.public_summary,
    cpp.evidence_maturity,
    em.label AS evidence_maturity_label,
    cpp.metadata
FROM cultural_preservation_plan cpp
LEFT JOIN evidence_maturity_level em ON em.level = cpp.evidence_maturity
WHERE cpp.status = 'published'
  AND cpp.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(cpp.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = cpp.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_renewable_energy_summary AS
SELECT
    rep.id,
    rep.location_id,
    rep.farm_id,
    rep.plan_date,
    rep.energy_use_case,
    rep.renewable_source,
    rep.implementation_status,
    rep.current_energy_source,
    rep.planned_capacity_kw,
    rep.estimated_annual_kwh,
    rep.renewable_share_pct,
    rep.fossil_displacement_estimate_co2e_tonnes,
    rep.infrastructure_dependencies,
    rep.maintenance_owner_role,
    rep.public_summary,
    rep.evidence_maturity,
    em.label AS evidence_maturity_label,
    rep.metadata
FROM renewable_energy_plan rep
LEFT JOIN evidence_maturity_level em ON em.level = rep.evidence_maturity
WHERE rep.status = 'published'
  AND rep.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(rep.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = rep.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_vulnerable_access_summary AS
SELECT
    vgap.id,
    vgap.location_id,
    vgap.farm_id,
    vgap.plan_date,
    vgap.access_scope,
    vgap.vulnerable_groups,
    vgap.access_barriers,
    vgap.accommodations,
    vgap.participation_pathways,
    vgap.accountable_role,
    vgap.implementation_status,
    vgap.access_coverage_pct,
    vgap.public_summary,
    vgap.evidence_maturity,
    em.label AS evidence_maturity_label,
    vgap.metadata
FROM vulnerable_group_access_plan vgap
LEFT JOIN evidence_maturity_level em ON em.level = vgap.evidence_maturity
WHERE vgap.status = 'published'
  AND vgap.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(vgap.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = vgap.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_foundational_wellbeing_summary AS
SELECT
    fwo.id,
    fwo.location_id,
    fwo.farm_id,
    fwo.observation_date,
    fwo.wellbeing_domain,
    fwo.stakeholder_group,
    fwo.score_value,
    fwo.count_value,
    fwo.public_summary,
    fwo.evidence_maturity,
    em.label AS evidence_maturity_label,
    fwo.metadata
FROM foundational_wellbeing_observation fwo
LEFT JOIN evidence_maturity_level em ON em.level = fwo.evidence_maturity
WHERE fwo.status = 'published'
  AND fwo.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(fwo.public_summary, '')), '') IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = fwo.location_id
        AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('gnh-alignment-inclusion-v1', 'GNH alignment, cultural preservation, renewable energy, vulnerable access, and foundational wellbeing evidence', 'schema 038')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
