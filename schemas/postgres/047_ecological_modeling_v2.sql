-- ============================================================
-- 047_ecological_modeling_v2.sql — Soil input tracking, pest management, biocontrol, resource consumption
-- ============================================================

-- Conservation status extension for species_observation
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS conservation_status VARCHAR(50);

ALTER TABLE species_observation DROP CONSTRAINT IF EXISTS chk_species_conservation_status;
ALTER TABLE species_observation ADD CONSTRAINT chk_species_conservation_status CHECK (
    conservation_status IS NULL OR conservation_status IN (
        'critically_endangered', 'endangered', 'vulnerable',
        'near_threatened', 'least_concern', 'data_deficient', 'not_evaluated'
    )
);

-- Soil input application: tracks organic inputs (biochar, leaf litter, compost) applied to plots
CREATE TABLE IF NOT EXISTS soil_input_application (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID NOT NULL REFERENCES plot(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE SET NULL,
    application_date DATE NOT NULL,
    input_type VARCHAR(100) NOT NULL,
    input_name VARCHAR(255) NOT NULL,
    quantity_kg NUMERIC(12,4) NOT NULL,
    application_method VARCHAR(100),
    depth_cm NUMERIC(6,2),
    area_m2 NUMERIC(12,2),
    decomposition_status VARCHAR(50) DEFAULT 'fresh',
    residual_pct NUMERIC(5,2),
    residual_measurement_date DATE,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'ecological-modeling-v2',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_soil_input_location ON soil_input_application(location_id);
CREATE INDEX IF NOT EXISTS idx_soil_input_plot ON soil_input_application(plot_id);
CREATE INDEX IF NOT EXISTS idx_soil_input_zone ON soil_input_application(zone_id);
CREATE INDEX IF NOT EXISTS idx_soil_input_type ON soil_input_application(input_type);
CREATE INDEX IF NOT EXISTS idx_soil_input_date ON soil_input_application(application_date);
CREATE INDEX IF NOT EXISTS idx_soil_input_status ON soil_input_application(status);

ALTER TABLE soil_input_application DROP CONSTRAINT IF EXISTS chk_soil_input_type;
ALTER TABLE soil_input_application ADD CONSTRAINT chk_soil_input_type CHECK (input_type IN (
    'biochar', 'leaf_litter', 'compost', 'vermicompost', 'manure',
    'green_manure', 'mulch', 'biofertilizer', 'other'
));

ALTER TABLE soil_input_application DROP CONSTRAINT IF EXISTS chk_soil_input_decomposition;
ALTER TABLE soil_input_application ADD CONSTRAINT chk_soil_input_decomposition CHECK (
    decomposition_status IN ('fresh', 'partially_decomposed', 'fully_decomposed', 'incorporated')
);

ALTER TABLE soil_input_application DROP CONSTRAINT IF EXISTS chk_soil_input_status;
ALTER TABLE soil_input_application ADD CONSTRAINT chk_soil_input_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Pest observation: structured monthly pest tracking per plot
CREATE TABLE IF NOT EXISTS pest_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID NOT NULL REFERENCES plot(id) ON DELETE CASCADE,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE SET NULL,
    observation_date DATE NOT NULL,
    pest_species VARCHAR(255),
    pest_common_name VARCHAR(255),
    pest_category VARCHAR(100),
    incidence_count INTEGER,
    severity VARCHAR(50),
    affected_area_pct NUMERIC(5,2),
    damage_description TEXT,
    weather_conditions JSONB,
    temperature_c NUMERIC(5,2),
    humidity_pct NUMERIC(5,2),
    rainfall_mm NUMERIC(8,2),
    predator_count INTEGER,
    natural_enemy_present BOOLEAN DEFAULT FALSE,
    outbreak_probability_pct NUMERIC(5,2),
    control_action TEXT,
    method VARCHAR(100),
    observer VARCHAR(255),
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'ecological-modeling-v2',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_pest_location ON pest_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_pest_plot ON pest_observation(plot_id);
CREATE INDEX IF NOT EXISTS idx_pest_crop_cycle ON pest_observation(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_pest_date ON pest_observation(observation_date);
CREATE INDEX IF NOT EXISTS idx_pest_species ON pest_observation(pest_species);
CREATE INDEX IF NOT EXISTS idx_pest_status ON pest_observation(status);

ALTER TABLE pest_observation DROP CONSTRAINT IF EXISTS chk_pest_severity;
ALTER TABLE pest_observation ADD CONSTRAINT chk_pest_severity CHECK (
    severity IS NULL OR severity IN ('none', 'low', 'medium', 'high', 'critical')
);

ALTER TABLE pest_observation DROP CONSTRAINT IF EXISTS chk_pest_category;
ALTER TABLE pest_observation ADD CONSTRAINT chk_pest_category CHECK (
    pest_category IS NULL OR pest_category IN (
        'insect', 'mite', 'nematode', 'fungal', 'bacterial', 'viral',
        'weed', 'rodent', 'bird', 'other'
    )
);

ALTER TABLE pest_observation DROP CONSTRAINT IF EXISTS chk_pest_status;
ALTER TABLE pest_observation ADD CONSTRAINT chk_pest_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Biocontrol release: records deliberate predator/biocontrol introductions
CREATE TABLE IF NOT EXISTS biocontrol_release (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID NOT NULL REFERENCES plot(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE SET NULL,
    release_date DATE NOT NULL,
    predator_species VARCHAR(255) NOT NULL,
    predator_common_name VARCHAR(255),
    predator_category VARCHAR(100),
    release_count INTEGER NOT NULL,
    target_pest VARCHAR(255),
    release_method VARCHAR(100),
    release_density_per_m2 NUMERIC(8,4),
    follow_up_date DATE,
    follow_up_count INTEGER,
    effectiveness_pct NUMERIC(5,2),
    pest_reduction_pct NUMERIC(5,2),
    notes TEXT,
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'ecological-modeling-v2',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_bioctrl_location ON biocontrol_release(location_id);
CREATE INDEX IF NOT EXISTS idx_bioctrl_plot ON biocontrol_release(plot_id);
CREATE INDEX IF NOT EXISTS idx_bioctrl_date ON biocontrol_release(release_date);
CREATE INDEX IF NOT EXISTS idx_bioctrl_predator ON biocontrol_release(predator_species);
CREATE INDEX IF NOT EXISTS idx_bioctrl_target ON biocontrol_release(target_pest);
CREATE INDEX IF NOT EXISTS idx_bioctrl_status ON biocontrol_release(status);

ALTER TABLE biocontrol_release DROP CONSTRAINT IF EXISTS chk_bioctrl_category;
ALTER TABLE biocontrol_release ADD CONSTRAINT chk_bioctrl_category CHECK (
    predator_category IS NULL OR predator_category IN (
        'predator', 'parasitoid', 'pathogen', 'microbial', 'other'
    )
);

ALTER TABLE biocontrol_release DROP CONSTRAINT IF EXISTS chk_bioctrl_status;
ALTER TABLE biocontrol_release ADD CONSTRAINT chk_bioctrl_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Resource consumption: actual metered resource use (energy, water, labor)
CREATE TABLE IF NOT EXISTS resource_consumption (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE SET NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    quantity NUMERIC(15,4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    component VARCHAR(100),
    meter_id VARCHAR(100),
    is_estimated BOOLEAN DEFAULT FALSE,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'ecological-modeling-v2',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_resource_location ON resource_consumption(location_id);
CREATE INDEX IF NOT EXISTS idx_resource_plot ON resource_consumption(plot_id);
CREATE INDEX IF NOT EXISTS idx_resource_crop_cycle ON resource_consumption(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_resource_type ON resource_consumption(resource_type);
CREATE INDEX IF NOT EXISTS idx_resource_period ON resource_consumption(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_resource_status ON resource_consumption(status);

ALTER TABLE resource_consumption DROP CONSTRAINT IF EXISTS chk_resource_type;
ALTER TABLE resource_consumption ADD CONSTRAINT chk_resource_type CHECK (resource_type IN (
    'energy_kwh', 'water_liters', 'labor_hours', 'fuel_liters', 'other'
));

ALTER TABLE resource_consumption DROP CONSTRAINT IF EXISTS chk_resource_status;
ALTER TABLE resource_consumption ADD CONSTRAINT chk_resource_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- ============================================================
-- Public-safe views
-- ============================================================

CREATE OR REPLACE VIEW v_public_pest_trends AS
SELECT
    po.id,
    po.location_id,
    l.name AS location_name,
    po.plot_id,
    p.name AS plot_name,
    po.observation_date,
    DATE_TRUNC('month', po.observation_date) AS observation_month,
    po.pest_species,
    po.pest_common_name,
    po.pest_category,
    po.severity,
    po.incidence_count,
    po.affected_area_pct,
    po.predator_count,
    po.natural_enemy_present,
    po.outbreak_probability_pct,
    po.temperature_c,
    po.humidity_pct,
    po.notes,
    po.status
FROM pest_observation po
JOIN location l ON l.id = po.location_id
LEFT JOIN plot p ON p.id = po.plot_id
WHERE l.status = 'active'
  AND po.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_biocontrol_effectiveness AS
SELECT
    bc.id,
    bc.location_id,
    l.name AS location_name,
    bc.plot_id,
    p.name AS plot_name,
    bc.release_date,
    bc.predator_species,
    bc.predator_common_name,
    bc.release_count,
    bc.target_pest,
    bc.follow_up_date,
    bc.follow_up_count,
    bc.effectiveness_pct,
    bc.pest_reduction_pct,
    bc.notes,
    bc.status
FROM biocontrol_release bc
JOIN location l ON l.id = bc.location_id
LEFT JOIN plot p ON p.id = bc.plot_id
WHERE l.status = 'active'
  AND bc.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_resource_efficiency AS
SELECT
    rc.id,
    rc.location_id,
    l.name AS location_name,
    rc.plot_id,
    p.name AS plot_name,
    rc.crop_cycle_id,
    cc.cycle_name,
    rc.period_start,
    rc.period_end,
    rc.resource_type,
    rc.quantity,
    rc.unit,
    rc.component,
    rc.is_estimated,
    rc.notes,
    rc.status
FROM resource_consumption rc
JOIN location l ON l.id = rc.location_id
LEFT JOIN plot p ON p.id = rc.plot_id
LEFT JOIN crop_cycle cc ON cc.id = rc.crop_cycle_id
WHERE l.status = 'active'
  AND rc.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_soil_input_retention AS
SELECT
    sia.id,
    sia.location_id,
    l.name AS location_name,
    sia.plot_id,
    p.name AS plot_name,
    sia.application_date,
    sia.input_type,
    sia.input_name,
    sia.quantity_kg,
    sia.application_method,
    sia.depth_cm,
    sia.decomposition_status,
    sia.residual_pct,
    sia.residual_measurement_date,
    sia.notes,
    sia.status
FROM soil_input_application sia
JOIN location l ON l.id = sia.location_id
LEFT JOIN plot p ON p.id = sia.plot_id
WHERE l.status = 'active'
  AND sia.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('ecological-modeling-v2', 'Soil input tracking, pest observation, biocontrol release, resource consumption, conservation status', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
