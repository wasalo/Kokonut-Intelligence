-- ============================================================
-- 026_ground_analytics.sql — Recurring field intelligence
-- ============================================================

CREATE TABLE IF NOT EXISTS plant_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id) ON DELETE RESTRICT,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE RESTRICT,
    analysis_date DATE NOT NULL,
    analysis_type VARCHAR(100) NOT NULL, -- scouting, growth_stage, foliar, yield_estimate, harvest_quality
    crop_stage VARCHAR(100),
    sample_size INTEGER,
    plant_count INTEGER,
    plant_height_cm NUMERIC(8,2),
    canopy_cover_pct NUMERIC(6,2),
    health_score NUMERIC(5,2), -- 0-100
    vigor_score NUMERIC(5,2), -- 0-100
    pest_pressure VARCHAR(50), -- none, low, medium, high, critical
    disease_pressure VARCHAR(50), -- none, low, medium, high, critical
    nutrient_status JSONB DEFAULT '{}',
    recommendations TEXT,
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'ground-analytics-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE plant_analysis ALTER COLUMN schema_version TYPE VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_plant_analysis_location ON plant_analysis(location_id);
CREATE INDEX IF NOT EXISTS idx_plant_analysis_plot ON plant_analysis(plot_id);
CREATE INDEX IF NOT EXISTS idx_plant_analysis_crop_cycle ON plant_analysis(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_plant_analysis_date ON plant_analysis(analysis_date);
CREATE INDEX IF NOT EXISTS idx_plant_analysis_status ON plant_analysis(status);

CREATE TABLE IF NOT EXISTS water_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    water_access_id UUID REFERENCES water_access(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id) ON DELETE RESTRICT,
    sample_date DATE NOT NULL,
    sample_id VARCHAR(100),
    analysis_type VARCHAR(100) DEFAULT 'water_quality', -- water_quality, irrigation_suitability, potability, salinity
    ph NUMERIC(5,2),
    electrical_conductivity_ms_cm NUMERIC(8,3),
    total_dissolved_solids_ppm NUMERIC(10,3),
    salinity_ppt NUMERIC(8,3),
    nitrate_ppm NUMERIC(8,3),
    phosphorus_ppm NUMERIC(8,3),
    potassium_ppm NUMERIC(8,3),
    sodium_ppm NUMERIC(8,3),
    chloride_ppm NUMERIC(8,3),
    dissolved_oxygen_mg_l NUMERIC(8,3),
    turbidity_ntu NUMERIC(8,3),
    coliform_present BOOLEAN,
    quality_score NUMERIC(5,2), -- 0-100
    lab_name VARCHAR(255),
    lab_report_url TEXT,
    evidence_hash VARCHAR(255),
    recommendations TEXT,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'ground-analytics-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE water_analysis ALTER COLUMN schema_version TYPE VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_water_analysis_location ON water_analysis(location_id);
CREATE INDEX IF NOT EXISTS idx_water_analysis_access ON water_analysis(water_access_id);
CREATE INDEX IF NOT EXISTS idx_water_analysis_plot ON water_analysis(plot_id);
CREATE INDEX IF NOT EXISTS idx_water_analysis_date ON water_analysis(sample_date);
CREATE INDEX IF NOT EXISTS idx_water_analysis_status ON water_analysis(status);

CREATE TABLE IF NOT EXISTS disease_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id) ON DELETE RESTRICT,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE RESTRICT,
    loss_event_id UUID REFERENCES loss_event(id) ON DELETE SET NULL,
    observation_date DATE NOT NULL,
    disease_name VARCHAR(255) NOT NULL,
    pathogen_type VARCHAR(100), -- fungal, bacterial, viral, nematode, unknown, other
    symptoms TEXT,
    affected_area_pct NUMERIC(6,2),
    incidence_pct NUMERIC(6,2),
    severity VARCHAR(50), -- low, medium, high, critical
    spread_risk VARCHAR(50), -- low, medium, high, critical
    treatment_applied TEXT,
    follow_up_date DATE,
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'ground-analytics-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE disease_observation ALTER COLUMN schema_version TYPE VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_disease_observation_location ON disease_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_disease_observation_plot ON disease_observation(plot_id);
CREATE INDEX IF NOT EXISTS idx_disease_observation_crop_cycle ON disease_observation(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_disease_observation_date ON disease_observation(observation_date);
CREATE INDEX IF NOT EXISTS idx_disease_observation_status ON disease_observation(status);

CREATE TABLE IF NOT EXISTS irrigation_program (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id) ON DELETE RESTRICT,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE RESTRICT,
    water_access_id UUID REFERENCES water_access(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    irrigation_method VARCHAR(100) NOT NULL, -- drip, sprinkler, furrow, flood, manual, rainfed_supplemental
    program_state VARCHAR(50) DEFAULT 'planned', -- planned, active, paused, completed, cancelled
    start_date DATE,
    end_date DATE,
    frequency VARCHAR(100), -- daily, weekly, twice_weekly, threshold_based, as_needed
    target_mm_per_week NUMERIC(8,2),
    target_liters_per_event NUMERIC(12,2),
    trigger_rule TEXT,
    monitoring_method VARCHAR(100), -- manual, sensor, weather_forecast, soil_probe, mixed
    expected_monthly_cost_usd NUMERIC(12,2),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'ground-analytics-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE irrigation_program ALTER COLUMN schema_version TYPE VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_irrigation_program_location ON irrigation_program(location_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_program_plot ON irrigation_program(plot_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_program_crop_cycle ON irrigation_program(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_program_water_access ON irrigation_program(water_access_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_program_state ON irrigation_program(program_state);
CREATE INDEX IF NOT EXISTS idx_irrigation_program_status ON irrigation_program(status);

INSERT INTO schema_version (version, description, applied_by)
VALUES ('ground-analytics-v1', 'Normalized plant, water, disease, and irrigation field intelligence', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
