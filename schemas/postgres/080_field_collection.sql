-- ============================================================
-- 080_field_collection.sql — Field Data Collection
-- ============================================================
-- Water sampling table and governed lifecycle additions
-- for soil and biodiversity tables.
-- ============================================================

-- 1. Water sample (field collection → feeds into water_analysis)
CREATE TABLE IF NOT EXISTS water_sample (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    water_access_id UUID REFERENCES water_access(id) ON DELETE SET NULL,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,

    -- Sampling details
    sample_date DATE NOT NULL,
    sample_time TIME,
    sample_id VARCHAR(100),
    sample_type VARCHAR(50) NOT NULL,
    collection_method VARCHAR(100),
    depth_m NUMERIC(6,2),
    container_type VARCHAR(50),
    preservative VARCHAR(100),
    sample_volume_ml INTEGER,

    -- Location
    gps_latitude NUMERIC(10,7),
    gps_longitude NUMERIC(10,7),

    -- Field measurements
    air_temperature_c NUMERIC(5,2),
    water_temperature_c NUMERIC(5,2),
    weather_conditions VARCHAR(100),

    -- Collection chain
    collector_name VARCHAR(255),
    collector_id UUID REFERENCES staff(id) ON DELETE SET NULL,
    chain_of_custody TEXT,

    -- Lab linkage
    water_analysis_id UUID REFERENCES water_analysis(id) ON DELETE SET NULL,
    lab_submission_date DATE,
    lab_name VARCHAR(255),
    lab_reference_id VARCHAR(100),

    -- Evidence
    photo_urls TEXT[],
    notes TEXT,
    evidence_hash VARCHAR(255),

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'draft',
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    schema_version VARCHAR(50),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_water_sample_location ON water_sample(location_id);
CREATE INDEX IF NOT EXISTS idx_water_sample_access ON water_sample(water_access_id);
CREATE INDEX IF NOT EXISTS idx_water_sample_plot ON water_sample(plot_id);
CREATE INDEX IF NOT EXISTS idx_water_sample_date ON water_sample(sample_date);
CREATE INDEX IF NOT EXISTS idx_water_sample_status ON water_sample(status);
CREATE INDEX IF NOT EXISTS idx_water_sample_analysis ON water_sample(water_analysis_id);

ALTER TABLE water_sample DROP CONSTRAINT IF EXISTS chk_water_sample_type;
ALTER TABLE water_sample ADD CONSTRAINT chk_water_sample_type CHECK (
    sample_type IN ('surface', 'groundwater', 'irrigation', 'runoff', 'rainwater', 'other')
);

ALTER TABLE water_sample DROP CONSTRAINT IF EXISTS chk_water_sample_lifecycle;
ALTER TABLE water_sample ADD CONSTRAINT chk_water_sample_lifecycle CHECK (
    status IN ('draft', 'submitted', 'verified', 'published', 'rejected')
);

-- 2. Add governed lifecycle to soil_sample
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'draft';
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS verified_by UUID;
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level);

ALTER TABLE soil_sample DROP CONSTRAINT IF EXISTS chk_soil_sample_lifecycle;
ALTER TABLE soil_sample ADD CONSTRAINT chk_soil_sample_lifecycle CHECK (
    status IN ('draft', 'submitted', 'verified', 'published', 'rejected')
);

CREATE INDEX IF NOT EXISTS idx_soil_sample_status ON soil_sample(status);

-- 3. Add governed lifecycle to soil_carbon_measurement
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'draft';
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS verified_by UUID;
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level);

ALTER TABLE soil_carbon_measurement DROP CONSTRAINT IF EXISTS chk_soil_carbon_lifecycle;
ALTER TABLE soil_carbon_measurement ADD CONSTRAINT chk_soil_carbon_lifecycle CHECK (
    status IN ('draft', 'submitted', 'verified', 'published', 'rejected')
);

CREATE INDEX IF NOT EXISTS idx_soil_carbon_status ON soil_carbon_measurement(status);

-- 4. Add governed lifecycle to species_observation
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'draft';
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS verified_by UUID;
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level);

ALTER TABLE species_observation DROP CONSTRAINT IF EXISTS chk_species_obs_lifecycle;
ALTER TABLE species_observation ADD CONSTRAINT chk_species_obs_lifecycle CHECK (
    status IN ('draft', 'submitted', 'verified', 'published', 'rejected')
);

CREATE INDEX IF NOT EXISTS idx_species_obs_status ON species_observation(status);

-- 5. Public water sample view
CREATE OR REPLACE VIEW v_public_water_sample_summary AS
SELECT
    ws.id,
    ws.sample_date,
    ws.sample_type,
    ws.collection_method,
    ws.depth_m,
    ws.gps_latitude,
    ws.gps_longitude,
    ws.water_temperature_c,
    ws.collector_name,
    ws.lab_name,
    ws.status,
    l.name AS location_name,
    wa.source_type AS water_source_type,
    wa.source_name AS water_source_name
FROM water_sample ws
JOIN location l ON l.id = ws.location_id
LEFT JOIN water_access wa ON wa.id = ws.water_access_id
WHERE ws.status = 'published'
AND ws.evidence_maturity >= 4
AND EXISTS (
    SELECT 1 FROM farm_registry_record fr
    WHERE fr.location_id = ws.location_id
    AND fr.status IN ('verified', 'published')
);
