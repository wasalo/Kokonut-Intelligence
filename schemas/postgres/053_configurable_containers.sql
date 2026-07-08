-- ============================================================
-- 053_configurable_containers.sql — Docker-like farm templates, specifications, needs, aspirations, objectives
-- ============================================================

-- Farm template: reusable configuration bundle (like a Docker image)
CREATE TABLE IF NOT EXISTS farm_template (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_name VARCHAR(255) NOT NULL,
    template_type VARCHAR(100) NOT NULL,
    description TEXT,
    version VARCHAR(50) DEFAULT '1.0',
    -- Zone configuration (default zones for this template)
    default_zones JSONB NOT NULL DEFAULT '[]',
    -- Governance configuration
    default_governance_mechanism VARCHAR(100),
    default_governance_config JSONB DEFAULT '{}',
    -- Token economics configuration
    default_token_allocation TEXT,
    default_public_goods_allocation_pct NUMERIC(6,3),
    default_redistribution_config JSONB DEFAULT '{}',
    -- Impact configuration
    default_impact_frameworks TEXT[] DEFAULT '{}',
    default_impact_dimensions JSONB DEFAULT '{}',
    -- Regeneration principles
    default_principles TEXT[] DEFAULT '{}',
    -- Farm type and characteristics
    suggested_farm_type VARCHAR(100),
    suggested_climate_zone VARCHAR(100),
    suggested_min_area_m2 NUMERIC(12,2),
    suggested_max_area_m2 NUMERIC(12,2),
    -- Metadata
    author VARCHAR(255),
    license VARCHAR(100),
    source_url TEXT,
    tags TEXT[] DEFAULT '{}',
    -- Governance
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'configurable-containers-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_farm_template_type ON farm_template(template_type);
CREATE INDEX IF NOT EXISTS idx_farm_template_status ON farm_template(status);
CREATE INDEX IF NOT EXISTS idx_farm_template_tags ON farm_template USING GIN(tags);

ALTER TABLE farm_template DROP CONSTRAINT IF EXISTS chk_farm_template_type;
ALTER TABLE farm_template ADD CONSTRAINT chk_farm_template_type CHECK (template_type IN (
    'syntropic', 'agroforestry', 'urban', 'regenerative', 'conventional',
    'research_pilot', 'community', 'commercial', 'hybrid', 'other'
));

ALTER TABLE farm_template DROP CONSTRAINT IF EXISTS chk_farm_template_status;
ALTER TABLE farm_template ADD CONSTRAINT chk_farm_template_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Farm specification: declarative farm configuration (like docker-compose.yml)
CREATE TABLE IF NOT EXISTS farm_specification (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    template_id UUID REFERENCES farm_template(id) ON DELETE SET NULL,
    spec_name VARCHAR(255) NOT NULL,
    version VARCHAR(50) DEFAULT '1.0',
    -- Declarative configuration (the "compose file")
    zones JSONB NOT NULL DEFAULT '[]',
    governance JSONB NOT NULL DEFAULT '{}',
    token_economics JSONB NOT NULL DEFAULT '{}',
    impact_config JSONB NOT NULL DEFAULT '{}',
    regeneration_principles JSONB DEFAULT '{}',
    -- Override fields (override template defaults)
    is_override BOOLEAN DEFAULT FALSE,
    override_reason TEXT,
    -- Validation
    validation_status VARCHAR(50) DEFAULT 'pending',
    validation_errors JSONB DEFAULT '[]',
    validated_at TIMESTAMPTZ,
    -- Lifecycle
    applied_at TIMESTAMPTZ,
    applied_by UUID,
    -- Governance
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'configurable-containers-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_farm_spec_location ON farm_specification(location_id);
CREATE INDEX IF NOT EXISTS idx_farm_spec_template ON farm_specification(template_id);
CREATE INDEX IF NOT EXISTS idx_farm_spec_status ON farm_specification(status);

ALTER TABLE farm_specification DROP CONSTRAINT IF EXISTS chk_farm_spec_validation;
ALTER TABLE farm_specification ADD CONSTRAINT chk_farm_spec_validation CHECK (validation_status IN (
    'pending', 'valid', 'invalid', 'warnings'
));

ALTER TABLE farm_specification DROP CONSTRAINT IF EXISTS chk_farm_spec_status;
ALTER TABLE farm_specification ADD CONSTRAINT chk_farm_spec_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Needs assessment: structured community/stakeholder needs tracking
CREATE TABLE IF NOT EXISTS needs_assessment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    need_category VARCHAR(100) NOT NULL,
    need_name VARCHAR(255) NOT NULL,
    description TEXT,
    severity VARCHAR(50),
    urgency VARCHAR(50),
    affected_stakeholder_groups TEXT[] DEFAULT '{}',
    affected_count INTEGER,
    current_state TEXT,
    desired_state TEXT,
    mitigation_plan TEXT,
    mitigation_status VARCHAR(50) DEFAULT 'identified',
    target_resolution_date DATE,
    assessor VARCHAR(255),
    assessment_date DATE NOT NULL,
    evidence_urls TEXT[],
    notes TEXT,
    -- Governance
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'configurable-containers-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_needs_location ON needs_assessment(location_id);
CREATE INDEX IF NOT EXISTS idx_needs_category ON needs_assessment(need_category);
CREATE INDEX IF NOT EXISTS idx_needs_severity ON needs_assessment(severity);
CREATE INDEX IF NOT EXISTS idx_needs_status ON needs_assessment(status);

ALTER TABLE needs_assessment DROP CONSTRAINT IF EXISTS chk_needs_category;
ALTER TABLE needs_assessment ADD CONSTRAINT chk_needs_category CHECK (need_category IN (
    'infrastructure', 'financial', 'technical', 'social', 'environmental',
    'governance', 'market', 'capacity_building', 'health', 'other'
));

ALTER TABLE needs_assessment DROP CONSTRAINT IF EXISTS chk_needs_severity;
ALTER TABLE needs_assessment ADD CONSTRAINT chk_needs_severity CHECK (
    severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical')
);

ALTER TABLE needs_assessment DROP CONSTRAINT IF EXISTS chk_needs_urgency;
ALTER TABLE needs_assessment ADD CONSTRAINT chk_needs_urgency CHECK (
    urgency IS NULL OR urgency IN ('low', 'medium', 'high', 'immediate')
);

ALTER TABLE needs_assessment DROP CONSTRAINT IF EXISTS chk_needs_mitigation;
ALTER TABLE needs_assessment ADD CONSTRAINT chk_needs_mitigation CHECK (mitigation_status IN (
    'identified', 'planned', 'in_progress', 'resolved', 'deferred', 'accepted'
));

ALTER TABLE needs_assessment DROP CONSTRAINT IF EXISTS chk_needs_status;
ALTER TABLE needs_assessment ADD CONSTRAINT chk_needs_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Stakeholder aspiration: formal tracking of wants and aspirations
CREATE TABLE IF NOT EXISTS stakeholder_aspiration (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    aspiration_name VARCHAR(255) NOT NULL,
    description TEXT,
    aspiration_category VARCHAR(100),
    priority VARCHAR(50),
    stakeholder_group VARCHAR(100),
    stakeholder_name VARCHAR(255),
    linked_objective_id UUID,
    desired_outcome TEXT,
    success_criteria TEXT,
    timeline_months INTEGER,
    resource_requirements TEXT,
    dependencies TEXT[],
    status VARCHAR(50) DEFAULT 'proposed',
    notes TEXT,
    -- Governance
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'configurable-containers-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_aspiration_location ON stakeholder_aspiration(location_id);
CREATE INDEX IF NOT EXISTS idx_aspiration_category ON stakeholder_aspiration(aspiration_category);
CREATE INDEX IF NOT EXISTS idx_aspiration_priority ON stakeholder_aspiration(priority);
CREATE INDEX IF NOT EXISTS idx_aspiration_status ON stakeholder_aspiration(status);

ALTER TABLE stakeholder_aspiration DROP CONSTRAINT IF EXISTS chk_aspiration_category;
ALTER TABLE stakeholder_aspiration ADD CONSTRAINT chk_aspiration_category CHECK (
    aspiration_category IS NULL OR aspiration_category IN (
        'ecological', 'financial', 'social', 'governance', 'capacity',
        'infrastructure', 'market', 'cultural', 'health', 'other'
    )
);

ALTER TABLE stakeholder_aspiration DROP CONSTRAINT IF EXISTS chk_aspiration_priority;
ALTER TABLE stakeholder_aspiration ADD CONSTRAINT chk_aspiration_priority CHECK (
    priority IS NULL OR priority IN ('low', 'medium', 'high', 'critical')
);

ALTER TABLE stakeholder_aspiration DROP CONSTRAINT IF EXISTS chk_aspiration_status;
ALTER TABLE stakeholder_aspiration ADD CONSTRAINT chk_aspiration_status CHECK (status IN (
    'proposed', 'discussed', 'approved', 'in_progress', 'achieved', 'deferred', 'rejected'
));

-- Objective: hierarchical goal tracking with progress
CREATE TABLE IF NOT EXISTS objective (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES objective(id) ON DELETE SET NULL,
    objective_name VARCHAR(255) NOT NULL,
    description TEXT,
    objective_type VARCHAR(100),
    category VARCHAR(100),
    target_value NUMERIC(15,4),
    current_value NUMERIC(15,4),
    unit VARCHAR(50),
    target_date DATE,
    start_date DATE,
    progress_pct NUMERIC(5,2) GENERATED ALWAYS AS (
        CASE WHEN target_value IS NOT NULL AND target_value > 0 AND current_value IS NOT NULL
        THEN LEAST(ROUND((current_value / target_value * 100)::numeric, 2), 100)
        ELSE NULL END
    ) STORED,
    owner VARCHAR(255),
    owner_role VARCHAR(100),
    success_criteria TEXT,
    dependencies TEXT[] DEFAULT '{}',
    priority VARCHAR(50),
    status VARCHAR(50) DEFAULT 'proposed',
    notes TEXT,
    -- Governance
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'configurable-containers-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_objective_location ON objective(location_id);
CREATE INDEX IF NOT EXISTS idx_objective_parent ON objective(parent_id);
CREATE INDEX IF NOT EXISTS idx_objective_type ON objective(objective_type);
CREATE INDEX IF NOT EXISTS idx_objective_category ON objective(category);
CREATE INDEX IF NOT EXISTS idx_objective_status ON objective(status);
CREATE INDEX IF NOT EXISTS idx_objective_target_date ON objective(target_date);

ALTER TABLE objective DROP CONSTRAINT IF EXISTS chk_objective_type;
ALTER TABLE objective ADD CONSTRAINT chk_objective_type CHECK (
    objective_type IS NULL OR objective_type IN (
        'strategic', 'operational', 'financial', 'ecological', 'social',
        'governance', 'capacity', 'research', 'other'
    )
);

ALTER TABLE objective DROP CONSTRAINT IF EXISTS chk_objective_priority;
ALTER TABLE objective ADD CONSTRAINT chk_objective_priority CHECK (
    priority IS NULL OR priority IN ('low', 'medium', 'high', 'critical')
);

ALTER TABLE objective DROP CONSTRAINT IF EXISTS chk_objective_status;
ALTER TABLE objective ADD CONSTRAINT chk_objective_status CHECK (status IN (
    'proposed', 'approved', 'in_progress', 'achieved', 'deferred', 'cancelled', 'rejected'
));

-- ============================================================
-- Public-safe views
-- ============================================================

CREATE OR REPLACE VIEW v_public_farm_templates AS
SELECT
    ft.id,
    ft.template_name,
    ft.template_type,
    ft.description,
    ft.version,
    ft.default_zones,
    ft.default_governance_mechanism,
    ft.default_token_allocation,
    ft.default_public_goods_allocation_pct,
    ft.default_impact_frameworks,
    ft.default_principles,
    ft.suggested_farm_type,
    ft.suggested_climate_zone,
    ft.suggested_min_area_m2,
    ft.suggested_max_area_m2,
    ft.tags,
    ft.status
FROM farm_template ft
WHERE ft.status IN ('verified', 'published');

CREATE OR REPLACE VIEW v_public_farm_specifications AS
SELECT
    fs.id,
    fs.location_id,
    l.name AS location_name,
    fs.template_id,
    ft.template_name,
    fs.spec_name,
    fs.version,
    fs.zones,
    fs.governance,
    fs.token_economics,
    fs.impact_config,
    fs.is_override,
    fs.validation_status,
    fs.applied_at,
    fs.status
FROM farm_specification fs
JOIN location l ON l.id = fs.location_id
LEFT JOIN farm_template ft ON ft.id = fs.template_id
WHERE l.status = 'active'
  AND fs.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_needs_assessment AS
SELECT
    na.id,
    na.location_id,
    l.name AS location_name,
    na.need_category,
    na.need_name,
    na.description,
    na.severity,
    na.urgency,
    na.affected_stakeholder_groups,
    na.affected_count,
    na.current_state,
    na.desired_state,
    na.mitigation_plan,
    na.mitigation_status,
    na.target_resolution_date,
    na.assessment_date,
    na.notes,
    na.status
FROM needs_assessment na
JOIN location l ON l.id = na.location_id
WHERE l.status = 'active'
  AND na.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_stakeholder_aspirations AS
SELECT
    sa.id,
    sa.location_id,
    l.name AS location_name,
    sa.aspiration_name,
    sa.description,
    sa.aspiration_category,
    sa.priority,
    sa.stakeholder_group,
    sa.desired_outcome,
    sa.success_criteria,
    sa.timeline_months,
    sa.status,
    sa.notes
FROM stakeholder_aspiration sa
JOIN location l ON l.id = sa.location_id
WHERE l.status = 'active'
  AND sa.status IN ('approved', 'in_progress', 'achieved')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_objectives AS
SELECT
    o.id,
    o.location_id,
    l.name AS location_name,
    o.parent_id,
    o.objective_name,
    o.description,
    o.objective_type,
    o.category,
    o.target_value,
    o.current_value,
    o.unit,
    o.target_date,
    o.start_date,
    o.progress_pct,
    o.owner,
    o.priority,
    o.status,
    o.notes
FROM objective o
JOIN location l ON l.id = o.location_id
WHERE l.status = 'active'
  AND o.status IN ('approved', 'in_progress', 'achieved')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('configurable-containers-v1', 'Farm templates, specifications, needs assessment, aspirations, objectives', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
