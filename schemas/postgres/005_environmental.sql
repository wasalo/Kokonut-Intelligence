-- ============================================================
-- 005_environmental.sql — Environmental and MRV facts
-- ============================================================

-- Soil samples
CREATE TABLE IF NOT EXISTS soil_sample (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plot_id UUID NOT NULL REFERENCES plot(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    sample_date DATE NOT NULL,
    sample_id VARCHAR(100), -- lab reference ID
    depth_cm NUMERIC(6,2),
    depth_layer VARCHAR(50), -- topsoil, subsoil, root_zone
    -- Soil properties
    ph NUMERIC(5,2),
    organic_matter_pct NUMERIC(6,3),
    organic_carbon_pct NUMERIC(6,3),
    nitrogen_ppm NUMERIC(8,3),
    phosphorus_ppm NUMERIC(8,3),
    potassium_ppm NUMERIC(8,3),
    calcium_ppm NUMERIC(8,3),
    magnesium_ppm NUMERIC(8,3),
    sulfur_ppm NUMERIC(8,3),
    cec NUMERIC(6,3), -- cation exchange capacity
    texture VARCHAR(50), -- sandy, loamy, clay, silty
    moisture_pct NUMERIC(5,2),
    -- Lab info
    lab_name VARCHAR(255),
    lab_report_url TEXT,
    evidence_hash VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_soil_plot ON soil_sample(plot_id);
CREATE INDEX IF NOT EXISTS idx_soil_location ON soil_sample(location_id);
CREATE INDEX IF NOT EXISTS idx_soil_date ON soil_sample(sample_date);

-- Soil carbon measurements (before/after)
CREATE TABLE IF NOT EXISTS soil_carbon_measurement (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plot_id UUID NOT NULL REFERENCES plot(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    measurement_date DATE NOT NULL,
    carbon_pct NUMERIC(6,3),
    carbon_tonnes_per_ha NUMERIC(10,4),
    organic_carbon_stock NUMERIC(10,4), -- tonnes C per hectare
    measurement_method VARCHAR(100), -- lab_analysis, remote_sensing, model_estimate
    depth_cm NUMERIC(6,2),
    is_baseline BOOLEAN DEFAULT FALSE,
    baseline_id UUID REFERENCES soil_carbon_measurement(id),
    evidence_urls TEXT[],
    evidence_hash VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_carbon_plot ON soil_carbon_measurement(plot_id);
CREATE INDEX IF NOT EXISTS idx_carbon_baseline ON soil_carbon_measurement(is_baseline);

-- Species observations (biodiversity)
CREATE TABLE IF NOT EXISTS species_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    observation_date DATE NOT NULL,
    -- Species info
    species_name VARCHAR(255), -- scientific name
    species_common_name VARCHAR(255),
    species_category VARCHAR(100), -- bird, insect, plant, mammal, amphibian, reptile, fish, fungi, other
    taxonomic_family VARCHAR(255),
    -- Count
    count INTEGER,
    abundance VARCHAR(50), -- rare, occasional, frequent, common, abundant
    -- Observation details
    observer VARCHAR(255),
    observer_id UUID REFERENCES staff(id),
    method VARCHAR(100), -- visual, acoustic, camera_trap, transect, quadrat, pitfall, other
    habitat_type VARCHAR(100),
    -- Evidence
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_species_location ON species_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_species_plot ON species_observation(plot_id);
CREATE INDEX IF NOT EXISTS idx_species_date ON species_observation(observation_date);
CREATE INDEX IF NOT EXISTS idx_species_category ON species_observation(species_category);

-- Remote sensing observations
CREATE TABLE IF NOT EXISTS remote_sensing_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plot_id UUID NOT NULL REFERENCES plot(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    observation_date DATE NOT NULL,
    source VARCHAR(100), -- sentinel2, landsat8, landsat9, drone, planet
    -- Vegetation indices
    ndvi NUMERIC(6,4),
    ndre NUMERIC(6,4),
    evi NUMERIC(6,4), -- enhanced vegetation index
    savi NUMERIC(6,4), -- soil-adjusted vegetation index
    -- Canopy
    canopy_cover_pct NUMERIC(6,2),
    canopy_height_m NUMERIC(6,2),
    -- Water
    ndwi NUMERIC(6,4), -- normalized difference water index
    -- Spatial
    bbox GEOMETRY(POLYGON, 4326),
    centroid GEOMETRY(POINT, 4326),
    cloud_cover_pct NUMERIC(5,2),
    -- Assets
    image_url TEXT,
    thumbnail_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rs_plot ON remote_sensing_observation(plot_id);
CREATE INDEX IF NOT EXISTS idx_rs_date ON remote_sensing_observation(observation_date);
CREATE INDEX IF NOT EXISTS idx_rs_source ON remote_sensing_observation(source);

-- Weather observations
CREATE TABLE IF NOT EXISTS weather_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    observation_date DATE NOT NULL,
    observation_time TIME,
    source VARCHAR(100), -- openweathermap, weatherapi, manual, station
    -- Temperature
    temperature_c NUMERIC(5,2),
    temp_min_c NUMERIC(5,2),
    temp_max_c NUMERIC(5,2),
    -- Precipitation
    precipitation_mm NUMERIC(8,2),
    rainfall_mm NUMERIC(8,2),
    -- Humidity
    humidity_pct NUMERIC(5,2),
    -- Wind
    wind_speed_kmh NUMERIC(6,2),
    wind_direction_deg NUMERIC(5,2),
    -- Solar
    solar_radiation_wm2 NUMERIC(8,2),
    sunshine_hours NUMERIC(5,2),
    -- Other
    cloud_cover_pct NUMERIC(5,2),
    pressure_hpa NUMERIC(8,2),
    visibility_km NUMERIC(6,2),
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weather_location ON weather_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_observation(observation_date);

-- Sensor readings
CREATE TABLE IF NOT EXISTS sensor_reading (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    sensor_id UUID NOT NULL,
    sensor_type VARCHAR(100), -- soil_moisture, soil_temperature, air_temperature, humidity, light, rainfall, water_level
    reading_date DATE NOT NULL,
    reading_time TIME,
    value NUMERIC(12,4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    quality VARCHAR(20), -- good, estimated, suspect, bad
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sensor_location ON sensor_reading(location_id);
CREATE INDEX IF NOT EXISTS idx_sensor_plot ON sensor_reading(plot_id);
CREATE INDEX IF NOT EXISTS idx_sensor_date ON sensor_reading(reading_date);
CREATE INDEX IF NOT EXISTS idx_sensor_type ON sensor_reading(sensor_type);

-- Environmental baseline
CREATE TABLE IF NOT EXISTS environmental_baseline (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    metric_name VARCHAR(100) NOT NULL, -- soil_carbon, species_count, ndvi_avg, canopy_cover, water_availability
    baseline_value NUMERIC(12,4),
    unit VARCHAR(50),
    measurement_date DATE,
    measurement_method VARCHAR(100),
    source VARCHAR(255),
    evidence_urls TEXT[],
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_env_baseline_location ON environmental_baseline(location_id);
CREATE INDEX IF NOT EXISTS idx_env_baseline_metric ON environmental_baseline(metric_name);

-- MRV claims (structured claims awaiting review/proof)
CREATE TABLE IF NOT EXISTS mrv_claim (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    claim_type VARCHAR(100) NOT NULL, -- soil_carbon_change, biodiversity_change, vegetation_change, water_resilience, practice_verification
    claim_date DATE NOT NULL,
    claim_data JSONB NOT NULL,
    -- Supporting evidence
    source_record_ids UUID[],
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    -- Review workflow
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    reviewer_id UUID,
    review_notes TEXT,
    reviewed_at TIMESTAMPTZ,
    -- Attestation
    attestation_uid VARCHAR(66),
    attested_at TIMESTAMPTZ,
    schema_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_mrv_location ON mrv_claim(location_id);
CREATE INDEX IF NOT EXISTS idx_mrv_type ON mrv_claim(claim_type);
CREATE INDEX IF NOT EXISTS idx_mrv_status ON mrv_claim(status);

-- Verification reviews
CREATE TABLE IF NOT EXISTS verification_review (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    claim_id UUID NOT NULL REFERENCES mrv_claim(id) ON DELETE RESTRICT,
    reviewer_id UUID NOT NULL,
    review_date DATE NOT NULL,
    method VARCHAR(100), -- document_check, field_visit, remote_sensing, lab_verification, peer_review
    result VARCHAR(50) NOT NULL, -- approved, rejected, needs_info
    notes TEXT,
    evidence_urls TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);
