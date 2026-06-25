-- ============================================================
-- 028_carbon_framework.sql — Carbon & Regenerative Framework
-- ============================================================
-- Adds GHG inventory, tree carbon (allometric), underplanting,
-- carbon benchmarks, regenerative practice scoring, framework
-- phase tracking, climate-impact summaries, and operations
-- protocols for grant-reviewer-grade carbon evidence.

-- GHG emission factors (IPCC / local / configurable)
CREATE TABLE IF NOT EXISTS ghg_emission_factor (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    factor_key VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(100) NOT NULL, -- fuel, fertilizer, pesticide, transport, machinery, electricity
    subcategory VARCHAR(100), -- diesel, petrol, npk, urea, compost, truck, motorcycle
    emission_factor NUMERIC(12,6) NOT NULL, -- kg CO2e per unit
    unit VARCHAR(50) NOT NULL, -- litre, kg, km, kwh, hour
    source VARCHAR(255), -- IPCC 2006, local lab, estimate
    region VARCHAR(100), -- global, dominican_republic, east_africa
    valid_from DATE,
    valid_to DATE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emission_factor_category ON ghg_emission_factor(category);
CREATE INDEX IF NOT EXISTS idx_emission_factor_region ON ghg_emission_factor(region);

-- GHG emissions inventory (transport, machinery, inputs)
CREATE TABLE IF NOT EXISTS ghg_emissions_inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    reporting_date DATE NOT NULL,
    reporting_period VARCHAR(50), -- weekly, monthly, quarterly, annual
    category VARCHAR(100) NOT NULL, -- transport, machinery, input, land_use_change, waste
    activity_description TEXT,
    quantity NUMERIC(12,4),
    quantity_unit VARCHAR(50), -- litre, km, hour, kg
    emission_factor_id UUID REFERENCES ghg_emission_factor(id),
    co2e_kg NUMERIC(12,4), -- computed = quantity * emission_factor
    co2e_tonnes NUMERIC(12,6),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ghg_location ON ghg_emissions_inventory(location_id);
CREATE INDEX IF NOT EXISTS idx_ghg_category ON ghg_emissions_inventory(category);
CREATE INDEX IF NOT EXISTS idx_ghg_date ON ghg_emissions_inventory(reporting_date);
CREATE INDEX IF NOT EXISTS idx_ghg_status ON ghg_emissions_inventory(status);

-- Tree inventory for above-ground carbon via allometric model
CREATE TABLE IF NOT EXISTS tree_inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    zone_id UUID REFERENCES farm_zone(id),
    species_name VARCHAR(255) NOT NULL,
    tree_count INTEGER,
    avg_height_m NUMERIC(8,2),
    avg_dbh_cm NUMERIC(8,2), -- diameter at breast height
    avg_canopy_diameter_m NUMERIC(8,2),
    maturity_stage VARCHAR(50), -- seedling, juvenile, mature,老龄
    planting_date DATE,
    survey_date DATE NOT NULL,
    biomass_estimate_kg NUMERIC(12,2), -- from allometric equation
    carbon_estimate_tonnes NUMERIC(12,4), -- biomass * 0.47 (IPCC conversion)
    co2e_estimate_tonnes NUMERIC(12,4), -- carbon * 3.67
    allometric_source VARCHAR(255), -- equation reference
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tree_location ON tree_inventory(location_id);
CREATE INDEX IF NOT EXISTS idx_tree_species ON tree_inventory(species_name);
CREATE INDEX IF NOT EXISTS idx_tree_zone ON tree_inventory(zone_id);
CREATE INDEX IF NOT EXISTS idx_tree_survey ON tree_inventory(survey_date);

-- Underplanting / companion species events
CREATE TABLE IF NOT EXISTS underplanting_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES farm_zone(id),
    plot_id UUID REFERENCES plot(id),
    species_name VARCHAR(255) NOT NULL,
    species_role VARCHAR(100), -- nitrogen_fixer, living_cover, support_species, canopy, pollinator
    planting_date DATE NOT NULL,
    area_m2 NUMERIC(12,2),
    plant_count INTEGER,
    expected_benefit TEXT,
    survival_count INTEGER,
    survival_survey_date DATE,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_underplant_location ON underplanting_event(location_id);
CREATE INDEX IF NOT EXISTS idx_underplant_zone ON underplanting_event(zone_id);
CREATE INDEX IF NOT EXISTS idx_underplant_species ON underplanting_event(species_name);
CREATE INDEX IF NOT EXISTS idx_underplant_date ON underplanting_event(planting_date);

-- Carbon benchmarks for tree system comparison
CREATE TABLE IF NOT EXISTS carbon_benchmark (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    benchmark_key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    tree_system VARCHAR(100) NOT NULL, -- coconut, oil_palm, mango, cacao, mixed_agroforestry
    above_ground_carbon_tonnes_ha NUMERIC(10,4),
    below_ground_carbon_tonnes_ha NUMERIC(10,4),
    total_carbon_tonnes_ha NUMERIC(10,4),
    sequestration_rate_tonnes_co2e_ha_year NUMERIC(10,4),
    source VARCHAR(255), -- literature reference
    region VARCHAR(100),
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Regenerative practice checklist (scored 0-5 per principle)
CREATE TABLE IF NOT EXISTS regenerative_practice_checklist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    assessment_date DATE NOT NULL,
    principle_key VARCHAR(100) NOT NULL REFERENCES regeneration_principle(principle_key),
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 5),
    evidence_path TEXT,
    notes TEXT,
    assessed_by UUID,
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(location_id, principle_key, assessment_date)
);

CREATE INDEX IF NOT EXISTS idx_checklist_location ON regenerative_practice_checklist(location_id);
CREATE INDEX IF NOT EXISTS idx_checklist_principle ON regenerative_practice_checklist(principle_key);

-- Framework implementation phase tracking
CREATE TABLE IF NOT EXISTS framework_phase (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    framework_key VARCHAR(100) NOT NULL,
    phase VARCHAR(100) NOT NULL, -- baseline_establishment, monitoring, data_verification, methodology_review, verified, published
    phase_start_date DATE,
    phase_end_date DATE,
    phase_status VARCHAR(50) DEFAULT 'active', -- active, completed, superseded
    owner_wallet VARCHAR(42),
    review_cadence VARCHAR(50), -- weekly, monthly, quarterly, annual
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_framework_phase_location ON framework_phase(location_id);
CREATE INDEX IF NOT EXISTS idx_framework_phase_framework ON framework_phase(framework_key);
CREATE INDEX IF NOT EXISTS idx_framework_phase_status ON framework_phase(phase_status);

-- Annual climate-impact summary
CREATE TABLE IF NOT EXISTS climate_impact_summary (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    reporting_year INTEGER NOT NULL,
    -- Sequestration
    above_ground_carbon_tonnes NUMERIC(12,4),
    below_ground_carbon_tonnes NUMERIC(12,4),
    total_sequestration_tonnes_co2e NUMERIC(12,4),
    -- Emissions
    transport_emissions_tonnes_co2e NUMERIC(12,4),
    machinery_emissions_tonnes_co2e NUMERIC(12,4),
    input_emissions_tonnes_co2e NUMERIC(12,4),
    total_emissions_tonnes_co2e NUMERIC(12,4),
    -- Net
    net_climate_impact_tonnes_co2e NUMERIC(12,4),
    -- Biodiversity
    species_count INTEGER,
    shannon_index NUMERIC(8,4),
    -- Regenerative score
    regenerative_score_total INTEGER,
    -- Methodology
    methodology_version VARCHAR(50),
    data_quality_score NUMERIC(5,2),
    -- Status
    status VARCHAR(50) DEFAULT 'draft',
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    notes TEXT,
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(location_id, reporting_year)
);

CREATE INDEX IF NOT EXISTS idx_climate_summary_location ON climate_impact_summary(location_id);
CREATE INDEX IF NOT EXISTS idx_climate_summary_year ON climate_impact_summary(reporting_year);

-- Operations protocol (versioned handbook)
CREATE TABLE IF NOT EXISTS operations_protocol (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    protocol_key VARCHAR(100) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    section VARCHAR(100), -- soil_management, biodiversity, emissions_tracking, data_entry, reporting
    content TEXT NOT NULL,
    version VARCHAR(50) NOT NULL,
    effective_date DATE,
    owner_wallet VARCHAR(42),
    review_cadence VARCHAR(50),
    framework_key VARCHAR(100),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Views
-- ============================================================

-- Regenerative practice score summary per location
CREATE OR REPLACE VIEW v_regenerative_score_summary AS
SELECT
    rpc.location_id,
    l.name AS location_name,
    COUNT(DISTINCT rpc.principle_key) AS principles_assessed,
    COALESCE(SUM(rpc.score), 0) AS total_score,
    25 AS max_score,
    ROUND(COALESCE(SUM(rpc.score), 0) * 100.0 / 25, 1) AS score_pct,
    MAX(rpc.assessment_date) AS last_assessment_date,
    rpc.status
FROM regenerative_practice_checklist rpc
JOIN location l ON l.id = rpc.location_id
WHERE rpc.status IN ('verified', 'published')
GROUP BY rpc.location_id, l.name, rpc.status;

-- GHG emissions summary by category per location/period
CREATE OR REPLACE VIEW v_ghg_emissions_summary AS
SELECT
    gei.location_id,
    l.name AS location_name,
    gei.reporting_date,
    gei.reporting_period,
    gei.category,
    COUNT(*) AS record_count,
    COALESCE(SUM(gei.co2e_tonnes), 0) AS total_co2e_tonnes,
    COALESCE(SUM(gei.co2e_kg), 0) AS total_co2e_kg
FROM ghg_emissions_inventory gei
JOIN location l ON l.id = gei.location_id
WHERE gei.status IN ('verified', 'published')
GROUP BY gei.location_id, l.name, gei.reporting_date, gei.reporting_period, gei.category;

-- Carbon balance (sequestration vs emissions) per location/year
CREATE OR REPLACE VIEW v_carbon_balance AS
SELECT
    cis.location_id,
    l.name AS location_name,
    cis.reporting_year,
    COALESCE(cis.above_ground_carbon_tonnes, 0) AS above_ground_carbon_tonnes,
    COALESCE(cis.below_ground_carbon_tonnes, 0) AS below_ground_carbon_tonnes,
    COALESCE(cis.total_sequestration_tonnes_co2e, 0) AS total_sequestration_tonnes_co2e,
    COALESCE(cis.total_emissions_tonnes_co2e, 0) AS total_emissions_tonnes_co2e,
    COALESCE(cis.net_climate_impact_tonnes_co2e, 0) AS net_climate_impact_tonnes_co2e,
    CASE
        WHEN COALESCE(cis.net_climate_impact_tonnes_co2e, 0) > 0 THEN 'net_sequester'
        WHEN COALESCE(cis.net_climate_impact_tonnes_co2e, 0) < 0 THEN 'net_emitter'
        ELSE 'neutral'
    END AS carbon_position,
    cis.species_count,
    cis.shannon_index,
    cis.regenerative_score_total,
    cis.status
FROM climate_impact_summary cis
JOIN location l ON l.id = cis.location_id
WHERE cis.status IN ('verified', 'published');

-- Current framework phase per location
CREATE OR REPLACE VIEW v_framework_phase_status AS
SELECT DISTINCT ON (fp.location_id, fp.framework_key)
    fp.location_id,
    l.name AS location_name,
    fp.framework_key,
    fp.phase,
    fp.phase_status,
    fp.phase_start_date,
    fp.phase_end_date,
    fp.owner_wallet,
    fp.review_cadence
FROM framework_phase fp
JOIN location l ON l.id = fp.location_id
WHERE fp.phase_status = 'active'
ORDER BY fp.location_id, fp.framework_key, fp.phase_start_date DESC;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('carbon-framework-v1', 'GHG inventory, tree carbon, underplanting, benchmarks, regenerative scoring, framework phases, climate-impact summaries, operations protocols', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
