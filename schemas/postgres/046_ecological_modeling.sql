-- ============================================================
-- 046_ecological_modeling.sql — Ecological modeling, trophic interactions, and energy flow
-- ============================================================

-- Trophic classification extensions for existing tables
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS trophic_level VARCHAR(50);
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS population_density_per_m2 NUMERIC(10,4);

ALTER TABLE species_observation DROP CONSTRAINT IF EXISTS chk_species_trophic_level;
ALTER TABLE species_observation ADD CONSTRAINT chk_species_trophic_level CHECK (
    trophic_level IS NULL OR trophic_level IN (
        'producer', 'primary_consumer', 'secondary_consumer', 'decomposer', 'omnivore'
    )
);

ALTER TABLE farm_zone ADD COLUMN IF NOT EXISTS strata_layer VARCHAR(50);

ALTER TABLE farm_zone DROP CONSTRAINT IF EXISTS chk_farm_zone_strata;
ALTER TABLE farm_zone ADD CONSTRAINT chk_farm_zone_strata CHECK (
    strata_layer IS NULL OR strata_layer IN (
        'emergent', 'canopy', 'sub_canopy', 'shrub', 'herbaceous', 'ground_cover', 'root', 'decomposer'
    )
);

-- Trophic interaction network: species-species relationships
CREATE TABLE IF NOT EXISTS ecological_interaction (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    species_a_name VARCHAR(255) NOT NULL,
    species_a_common VARCHAR(255),
    species_a_trophic VARCHAR(50) NOT NULL,
    species_b_name VARCHAR(255) NOT NULL,
    species_b_common VARCHAR(255),
    species_b_trophic VARCHAR(50) NOT NULL,
    interaction_type VARCHAR(50) NOT NULL,
    interaction_strength NUMERIC(4,3) CHECK (interaction_strength >= 0 AND interaction_strength <= 1),
    description TEXT,
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'ecological-modeling-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_eco_interaction_location ON ecological_interaction(location_id);
CREATE INDEX IF NOT EXISTS idx_eco_interaction_zone ON ecological_interaction(zone_id);
CREATE INDEX IF NOT EXISTS idx_eco_interaction_species_a ON ecological_interaction(species_a_name);
CREATE INDEX IF NOT EXISTS idx_eco_interaction_species_b ON ecological_interaction(species_b_name);
CREATE INDEX IF NOT EXISTS idx_eco_interaction_type ON ecological_interaction(interaction_type);
CREATE INDEX IF NOT EXISTS idx_eco_interaction_status ON ecological_interaction(status);

ALTER TABLE ecological_interaction DROP CONSTRAINT IF EXISTS chk_eco_interaction_type;
ALTER TABLE ecological_interaction ADD CONSTRAINT chk_eco_interaction_type CHECK (interaction_type IN (
    'mutualism', 'competition', 'predation', 'parasitism', 'commensalism', 'facilitation', 'other'
));

ALTER TABLE ecological_interaction DROP CONSTRAINT IF EXISTS chk_eco_interaction_trophic;
ALTER TABLE ecological_interaction ADD CONSTRAINT chk_eco_interaction_trophic CHECK (
    species_a_trophic IN ('producer', 'primary_consumer', 'secondary_consumer', 'decomposer', 'omnivore')
    AND species_b_trophic IN ('producer', 'primary_consumer', 'secondary_consumer', 'decomposer', 'omnivore')
);

ALTER TABLE ecological_interaction DROP CONSTRAINT IF EXISTS chk_eco_interaction_status;
ALTER TABLE ecological_interaction ADD CONSTRAINT chk_eco_interaction_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Ecological model runs: simulation inputs and outputs
CREATE TABLE IF NOT EXISTS ecological_model_run (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    model_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(100) NOT NULL,
    run_date DATE NOT NULL,
    input_parameters JSONB NOT NULL DEFAULT '{}',
    output_predictions JSONB NOT NULL DEFAULT '{}',
    confidence_level NUMERIC(5,2) CHECK (confidence_level >= 0 AND confidence_level <= 100),
    calculation_version VARCHAR(50),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'ecological-modeling-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_eco_model_location ON ecological_model_run(location_id);
CREATE INDEX IF NOT EXISTS idx_eco_model_zone ON ecological_model_run(zone_id);
CREATE INDEX IF NOT EXISTS idx_eco_model_type ON ecological_model_run(model_type);
CREATE INDEX IF NOT EXISTS idx_eco_model_status ON ecological_model_run(status);
CREATE INDEX IF NOT EXISTS idx_eco_model_run_date ON ecological_model_run(run_date);

ALTER TABLE ecological_model_run DROP CONSTRAINT IF EXISTS chk_eco_model_type;
ALTER TABLE ecological_model_run ADD CONSTRAINT chk_eco_model_type CHECK (model_type IN (
    'nutrient_cycling', 'pest_dynamics', 'yield_prediction', 'carbon_projection',
    'population_dynamics', 'energy_flow', 'water_balance', 'other'
));

ALTER TABLE ecological_model_run DROP CONSTRAINT IF EXISTS chk_eco_model_status;
ALTER TABLE ecological_model_run ADD CONSTRAINT chk_eco_model_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Energy flow measurements: biomass transfer between trophic levels
CREATE TABLE IF NOT EXISTS energy_flow_measurement (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    measurement_date DATE NOT NULL,
    from_trophic_level VARCHAR(50) NOT NULL,
    to_trophic_level VARCHAR(50) NOT NULL,
    biomass_transferred_kg NUMERIC(12,4) NOT NULL,
    biomass_source_kg NUMERIC(12,4),
    conversion_efficiency_pct NUMERIC(6,2) CHECK (conversion_efficiency_pct >= 0 AND conversion_efficiency_pct <= 100),
    measurement_method VARCHAR(100),
    period_start DATE,
    period_end DATE,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    schema_version VARCHAR(50) DEFAULT 'ecological-modeling-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_energy_flow_location ON energy_flow_measurement(location_id);
CREATE INDEX IF NOT EXISTS idx_energy_flow_zone ON energy_flow_measurement(zone_id);
CREATE INDEX IF NOT EXISTS idx_energy_flow_from ON energy_flow_measurement(from_trophic_level);
CREATE INDEX IF NOT EXISTS idx_energy_flow_to ON energy_flow_measurement(to_trophic_level);
CREATE INDEX IF NOT EXISTS idx_energy_flow_date ON energy_flow_measurement(measurement_date);

ALTER TABLE energy_flow_measurement DROP CONSTRAINT IF EXISTS chk_energy_flow_trophic;
ALTER TABLE energy_flow_measurement ADD CONSTRAINT chk_energy_flow_trophic CHECK (
    from_trophic_level IN ('producer', 'primary_consumer', 'secondary_consumer', 'decomposer', 'omnivore')
    AND to_trophic_level IN ('producer', 'primary_consumer', 'secondary_consumer', 'decomposer', 'omnivore')
);

ALTER TABLE energy_flow_measurement DROP CONSTRAINT IF EXISTS chk_energy_flow_status;
ALTER TABLE energy_flow_measurement ADD CONSTRAINT chk_energy_flow_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Population dynamics records: species population tracking over time
CREATE TABLE IF NOT EXISTS population_dynamics_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    species_name VARCHAR(255) NOT NULL,
    species_common_name VARCHAR(255),
    trophic_level VARCHAR(50) NOT NULL,
    record_date DATE NOT NULL,
    population_count INTEGER,
    population_density_per_m2 NUMERIC(10,4),
    carrying_capacity_estimate INTEGER,
    growth_rate_estimate NUMERIC(8,4),
    method VARCHAR(100),
    observer VARCHAR(255),
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    schema_version VARCHAR(50) DEFAULT 'ecological-modeling-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_pop_dynamics_location ON population_dynamics_record(location_id);
CREATE INDEX IF NOT EXISTS idx_pop_dynamics_plot ON population_dynamics_record(plot_id);
CREATE INDEX IF NOT EXISTS idx_pop_dynamics_zone ON population_dynamics_record(zone_id);
CREATE INDEX IF NOT EXISTS idx_pop_dynamics_species ON population_dynamics_record(species_name);
CREATE INDEX IF NOT EXISTS idx_pop_dynamics_trophic ON population_dynamics_record(trophic_level);
CREATE INDEX IF NOT EXISTS idx_pop_dynamics_date ON population_dynamics_record(record_date);

ALTER TABLE population_dynamics_record DROP CONSTRAINT IF EXISTS chk_pop_dynamics_trophic;
ALTER TABLE population_dynamics_record ADD CONSTRAINT chk_pop_dynamics_trophic CHECK (trophic_level IN (
    'producer', 'primary_consumer', 'secondary_consumer', 'decomposer', 'omnivore'
));

ALTER TABLE population_dynamics_record DROP CONSTRAINT IF EXISTS chk_pop_dynamics_status;
ALTER TABLE population_dynamics_record ADD CONSTRAINT chk_pop_dynamics_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- ============================================================
-- Public-safe views
-- ============================================================

CREATE OR REPLACE VIEW v_public_ecological_interaction_summary AS
SELECT
    ei.id,
    ei.location_id,
    l.name AS location_name,
    ei.zone_id,
    fz.name AS zone_name,
    ei.species_a_name,
    ei.species_a_common,
    ei.species_a_trophic,
    ei.species_b_name,
    ei.species_b_common,
    ei.species_b_trophic,
    ei.interaction_type,
    ei.interaction_strength,
    ei.description,
    ei.notes,
    ei.evidence_maturity >= 3 AS evidence_adequate,
    ei.status
FROM ecological_interaction ei
JOIN location l ON l.id = ei.location_id
LEFT JOIN farm_zone fz ON fz.id = ei.zone_id
WHERE l.status = 'active'
  AND ei.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_energy_flow_summary AS
SELECT
    efm.id,
    efm.location_id,
    l.name AS location_name,
    efm.zone_id,
    fz.name AS zone_name,
    efm.measurement_date,
    efm.from_trophic_level,
    efm.to_trophic_level,
    efm.biomass_transferred_kg,
    efm.conversion_efficiency_pct,
    efm.measurement_method,
    efm.period_start,
    efm.period_end,
    efm.notes,
    efm.status
FROM energy_flow_measurement efm
JOIN location l ON l.id = efm.location_id
LEFT JOIN farm_zone fz ON fz.id = efm.zone_id
WHERE l.status = 'active'
  AND efm.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_population_dynamics_summary AS
SELECT
    pdr.id,
    pdr.location_id,
    l.name AS location_name,
    pdr.plot_id,
    p.name AS plot_name,
    pdr.species_name,
    pdr.species_common_name,
    pdr.trophic_level,
    pdr.record_date,
    pdr.population_count,
    pdr.population_density_per_m2,
    pdr.growth_rate_estimate,
    pdr.method,
    pdr.notes,
    pdr.status
FROM population_dynamics_record pdr
JOIN location l ON l.id = pdr.location_id
LEFT JOIN plot p ON p.id = pdr.plot_id
WHERE l.status = 'active'
  AND pdr.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_ecological_model_summary AS
SELECT
    emr.id,
    emr.location_id,
    l.name AS location_name,
    emr.zone_id,
    fz.name AS zone_name,
    emr.model_name,
    emr.model_type,
    emr.run_date,
    emr.confidence_level,
    emr.input_parameters,
    emr.output_predictions,
    emr.notes,
    emr.status
FROM ecological_model_run emr
JOIN location l ON l.id = emr.location_id
LEFT JOIN farm_zone fz ON fz.id = emr.zone_id
WHERE l.status = 'active'
  AND emr.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

-- Trophic balance view: aggregated interaction counts by type
CREATE OR REPLACE VIEW v_trophic_balance AS
SELECT
    ei.location_id,
    l.name AS location_name,
    ei.species_a_trophic AS from_level,
    ei.species_b_trophic AS to_level,
    ei.interaction_type,
    COUNT(*) AS interaction_count,
    AVG(ei.interaction_strength) AS avg_interaction_strength
FROM ecological_interaction ei
JOIN location l ON l.id = ei.location_id
WHERE ei.status IN ('verified', 'published')
GROUP BY ei.location_id, l.name, ei.species_a_trophic, ei.species_b_trophic, ei.interaction_type;

-- Energy flow efficiency view: aggregated by trophic transfer
CREATE OR REPLACE VIEW v_energy_flow_efficiency AS
SELECT
    efm.location_id,
    l.name AS location_name,
    efm.from_trophic_level,
    efm.to_trophic_level,
    SUM(efm.biomass_transferred_kg) AS total_biomass_kg,
    AVG(efm.conversion_efficiency_pct) AS avg_efficiency_pct,
    COUNT(*) AS measurement_count
FROM energy_flow_measurement efm
JOIN location l ON l.id = efm.location_id
WHERE efm.status IN ('verified', 'published')
GROUP BY efm.location_id, l.name, efm.from_trophic_level, efm.to_trophic_level;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('ecological-modeling-v1', 'Ecological modeling tables, trophic interactions, energy flow, population dynamics, and public views', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
