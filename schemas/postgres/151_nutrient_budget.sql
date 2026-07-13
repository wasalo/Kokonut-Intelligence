-- 151_nutrient_budget.sql
-- Nutrient Budget Tracking: field-level nutrient balance,
-- input/removal events, soil-test recommendations, and crop removal factors.

BEGIN;

-- ============================================================
-- NUTRIENT BUDGET (per field/plot/season)
-- ============================================================

CREATE TABLE IF NOT EXISTS nutrient_budget (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    season VARCHAR(100) NOT NULL,
    crop_name VARCHAR(100),
    area_ha NUMERIC(8,2),

    -- Inputs (kg per season)
    nitrogen_input_kg NUMERIC(10,2) DEFAULT 0,
    phosphorus_input_kg NUMERIC(10,2) DEFAULT 0,
    potassium_input_kg NUMERIC(10,2) DEFAULT 0,

    -- Removals (kg per season)
    nitrogen_removal_kg NUMERIC(10,2) DEFAULT 0,
    phosphorus_removal_kg NUMERIC(10,2) DEFAULT 0,
    potassium_removal_kg NUMERIC(10,2) DEFAULT 0,

    -- Surplus / deficit (computed)
    nitrogen_surplus_kg NUMERIC(10,2)
        GENERATED ALWAYS AS (nitrogen_input_kg - nitrogen_removal_kg) STORED,
    phosphorus_surplus_kg NUMERIC(10,2)
        GENERATED ALWAYS AS (phosphorus_input_kg - phosphorus_removal_kg) STORED,
    potassium_surplus_kg NUMERIC(10,2)
        GENERATED ALWAYS AS (potassium_input_kg - potassium_removal_kg) STORED,

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_nutrient_budget_status CHECK (
        status IN ('draft', 'submitted', 'verified', 'published', 'rejected')
    )
);

CREATE INDEX IF NOT EXISTS idx_nutrient_budget_location ON nutrient_budget(location_id, status);
CREATE INDEX IF NOT EXISTS idx_nutrient_budget_plot ON nutrient_budget(plot_id);
CREATE INDEX IF NOT EXISTS idx_nutrient_budget_season ON nutrient_budget(season, crop_name);
CREATE INDEX IF NOT EXISTS idx_nutrient_budget_status ON nutrient_budget(status);

-- ============================================================
-- NUTRIENT INPUT EVENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS nutrient_input (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id UUID NOT NULL REFERENCES nutrient_budget(id) ON DELETE CASCADE,
    input_date DATE NOT NULL,
    input_type VARCHAR(100) NOT NULL,
    product_name VARCHAR(200),

    -- Nutrient content (kg)
    nitrogen_kg NUMERIC(10,2) DEFAULT 0,
    phosphorus_kg NUMERIC(10,2) DEFAULT 0,
    potassium_kg NUMERIC(10,2) DEFAULT 0,

    -- Application details
    application_rate NUMERIC(10,2),
    rate_unit VARCHAR(50),
    cost NUMERIC(10,2),

    notes TEXT,

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'recorded',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_nutrient_input_type CHECK (
        input_type IN (
            'fertilizer', 'manure', 'compost', 'biochar',
            'green_manure', 'rainfall', 'irrigation', 'seed', 'other'
        )
    ),
    CONSTRAINT chk_nutrient_input_status CHECK (
        status IN ('draft', 'recorded', 'submitted', 'verified', 'rejected')
    )
);

CREATE INDEX IF NOT EXISTS idx_nutrient_input_budget ON nutrient_input(budget_id, input_date);
CREATE INDEX IF NOT EXISTS idx_nutrient_input_date ON nutrient_input(input_date);
CREATE INDEX IF NOT EXISTS idx_nutrient_input_type ON nutrient_input(input_type);

-- ============================================================
-- NUTRIENT REMOVAL AT HARVEST
-- ============================================================

CREATE TABLE IF NOT EXISTS nutrient_removal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id UUID NOT NULL REFERENCES nutrient_budget(id) ON DELETE CASCADE,
    harvest_date DATE NOT NULL,
    crop_name VARCHAR(100),

    -- Yield
    yield_amount NUMERIC(10,2),
    yield_unit VARCHAR(50),

    -- Nutrient removed (kg)
    nitrogen_kg NUMERIC(10,2) DEFAULT 0,
    phosphorus_kg NUMERIC(10,2) DEFAULT 0,
    potassium_kg NUMERIC(10,2) DEFAULT 0,

    -- Reference for removal factors
    removal_factor_source VARCHAR(200),

    notes TEXT,

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'recorded',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_nutrient_removal_status CHECK (
        status IN ('draft', 'recorded', 'submitted', 'verified', 'rejected')
    )
);

CREATE INDEX IF NOT EXISTS idx_nutrient_removal_budget ON nutrient_removal(budget_id, harvest_date);
CREATE INDEX IF NOT EXISTS idx_nutrient_removal_date ON nutrient_removal(harvest_date);
CREATE INDEX IF NOT EXISTS idx_nutrient_removal_crop ON nutrient_removal(crop_name);

-- ============================================================
-- SOIL TEST RECOMMENDATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS soil_test_recommendation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    test_date DATE NOT NULL,

    -- Soil test results
    soil_ph NUMERIC(4,2),
    organic_matter_pct NUMERIC(5,2),
    nitrogen_ppm NUMERIC(8,2),
    phosphorus_ppm NUMERIC(8,2),
    potassium_ppm NUMERIC(8,2),
    cec NUMERIC(6,2),

    -- Recommended application rates (kg/ha)
    recommended_n_kg_ha NUMERIC(8,2),
    recommended_p_kg_ha NUMERIC(8,2),
    recommended_k_kg_ha NUMERIC(8,2),

    notes TEXT,

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'recorded',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_soil_test_status CHECK (
        status IN ('draft', 'recorded', 'submitted', 'verified', 'rejected')
    )
);

CREATE INDEX IF NOT EXISTS idx_soil_test_location ON soil_test_recommendation(location_id, test_date DESC);
CREATE INDEX IF NOT EXISTS idx_soil_test_plot ON soil_test_recommendation(plot_id);
CREATE INDEX IF NOT EXISTS idx_soil_test_date ON soil_test_recommendation(test_date DESC);

-- ============================================================
-- VIEWS
-- ============================================================

-- Current nutrient surplus/deficit per plot (latest budget per plot)
CREATE OR REPLACE VIEW v_nutrient_balance AS
SELECT DISTINCT ON (nb.plot_id, nb.season)
    nb.id AS budget_id,
    nb.location_id,
    l.name AS location_name,
    nb.plot_id,
    nb.season,
    nb.crop_name,
    nb.area_ha,
    nb.nitrogen_input_kg,
    nb.nitrogen_removal_kg,
    nb.nitrogen_surplus_kg,
    nb.phosphorus_input_kg,
    nb.phosphorus_removal_kg,
    nb.phosphorus_surplus_kg,
    nb.potassium_input_kg,
    nb.potassium_removal_kg,
    nb.potassium_surplus_kg,
    CASE
        WHEN nb.nitrogen_surplus_kg > 0 THEN 'surplus'
        WHEN nb.nitrogen_surplus_kg < 0 THEN 'deficit'
        ELSE 'balanced'
    END AS nitrogen_balance_status,
    CASE
        WHEN nb.phosphorus_surplus_kg > 0 THEN 'surplus'
        WHEN nb.phosphorus_surplus_kg < 0 THEN 'deficit'
        ELSE 'balanced'
    END AS phosphorus_balance_status,
    CASE
        WHEN nb.potassium_surplus_kg > 0 THEN 'surplus'
        WHEN nb.potassium_surplus_kg < 0 THEN 'deficit'
        ELSE 'balanced'
    END AS potassium_balance_status,
    nb.status,
    nb.updated_at
FROM nutrient_budget nb
JOIN location l ON l.id = nb.location_id
WHERE nb.status IN ('verified', 'published')
ORDER BY nb.plot_id, nb.season, nb.updated_at DESC;

-- Input totals by type and nutrient per budget
CREATE OR REPLACE VIEW v_nutrient_input_summary AS
SELECT
    ni.budget_id,
    nb.location_id,
    nb.season,
    nb.crop_name,
    ni.input_type,
    COUNT(*) AS event_count,
    SUM(ni.nitrogen_kg) AS total_nitrogen_kg,
    SUM(ni.phosphorus_kg) AS total_phosphorus_kg,
    SUM(ni.potassium_kg) AS total_potassium_kg,
    SUM(ni.cost) AS total_cost,
    AVG(ni.application_rate) AS avg_application_rate,
    ni.rate_unit
FROM nutrient_input ni
JOIN nutrient_budget nb ON nb.id = ni.budget_id
WHERE ni.status IN ('recorded', 'verified')
GROUP BY ni.budget_id, nb.location_id, nb.season, nb.crop_name,
         ni.input_type, ni.rate_unit
ORDER BY nb.season, ni.input_type;

-- Soil test results over time per location/plot
CREATE OR REPLACE VIEW v_soil_test_history AS
SELECT
    str.id AS test_id,
    str.location_id,
    l.name AS location_name,
    str.plot_id,
    str.test_date,
    str.soil_ph,
    str.organic_matter_pct,
    str.nitrogen_ppm,
    str.phosphorus_ppm,
    str.potassium_ppm,
    str.cec,
    str.recommended_n_kg_ha,
    str.recommended_p_kg_ha,
    str.recommended_k_kg_ha,
    str.notes,
    str.status,
    LAG(str.test_date) OVER (
        PARTITION BY str.location_id, str.plot_id ORDER BY str.test_date
    ) AS previous_test_date,
    str.nitrogen_ppm - LAG(str.nitrogen_ppm) OVER (
        PARTITION BY str.location_id, str.plot_id ORDER BY str.test_date
    ) AS nitrogen_ppm_change,
    str.phosphorus_ppm - LAG(str.phosphorus_ppm) OVER (
        PARTITION BY str.location_id, str.plot_id ORDER BY str.test_date
    ) AS phosphorus_ppm_change,
    str.potassium_ppm - LAG(str.potassium_ppm) OVER (
        PARTITION BY str.location_id, str.plot_id ORDER BY str.test_date
    ) AS potassium_ppm_change
FROM soil_test_recommendation str
JOIN location l ON l.id = str.location_id
ORDER BY str.location_id, str.plot_id, str.test_date;

COMMIT;

-- ============================================================
-- SEED: Nutrient removal factors for common crops
-- Values in kg nutrient removed per tonne of harvested product
-- Sources: FAO 2006, IFA/IPNI nutrient guidelines, CIAT
-- ============================================================

-- Reference table for crop nutrient removal factors
CREATE TABLE IF NOT EXISTS crop_nutrient_removal_factor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_name VARCHAR(100) NOT NULL,
    nutrient VARCHAR(20) NOT NULL,
    removal_kg_per_tonne NUMERIC(8,2) NOT NULL,
    yield_part VARCHAR(100),
    source VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(crop_name, nutrient)
);

INSERT INTO crop_nutrient_removal_factor (crop_name, nutrient, removal_kg_per_tonne, yield_part, source)
VALUES
    -- Maize (grain)
    ('maize', 'nitrogen', 24.8, 'grain', 'FAO 2006, IPNI'),
    ('maize', 'phosphorus', 8.6, 'grain', 'FAO 2006, IPNI'),
    ('maize', 'potassium', 18.2, 'grain', 'FAO 2006, IPNI'),

    -- Beans (grain)
    ('beans', 'nitrogen', 42.0, 'grain', 'FAO 2006, IPNI'),
    ('beans', 'phosphorus', 11.5, 'grain', 'FAO 2006, IPNI'),
    ('beans', 'potassium', 30.0, 'grain', 'FAO 2006, IPNI'),

    -- Cassava (tuber)
    ('cassava', 'nitrogen', 7.5, 'tuber', 'CIAT, IPNI'),
    ('cassava', 'phosphorus', 2.0, 'tuber', 'CIAT, IPNI'),
    ('cassava', 'potassium', 12.0, 'tuber', 'CIAT, IPNI'),

    -- Sweet Potato (tuber)
    ('sweet_potato', 'nitrogen', 8.2, 'tuber', 'CIP, IPNI'),
    ('sweet_potato', 'phosphorus', 2.5, 'tuber', 'CIP, IPNI'),
    ('sweet_potato', 'potassium', 15.0, 'tuber', 'CIP, IPNI'),

    -- Coffee (green bean)
    ('coffee', 'nitrogen', 45.0, 'green_bean', 'ICO, IPNI'),
    ('coffee', 'phosphorus', 5.0, 'green_bean', 'ICO, IPNI'),
    ('coffee', 'potassium', 55.0, 'green_bean', 'ICO, IPNI'),

    -- Tomato (fruit)
    ('tomato', 'nitrogen', 6.2, 'fruit', 'FAO 2006, IPNI'),
    ('tomato', 'phosphorus', 1.8, 'fruit', 'FAO 2006, IPNI'),
    ('tomato', 'potassium', 12.0, 'fruit', 'FAO 2006, IPNI'),

    -- Banana (fruit bunch)
    ('banana', 'nitrogen', 5.5, 'fruit_bunch', 'FAO, IPNI'),
    ('banana', 'phosphorus', 1.2, 'fruit_bunch', 'FAO, IPNI'),
    ('banana', 'potassium', 18.0, 'fruit_bunch', 'FAO, IPNI')
ON CONFLICT (crop_name, nutrient) DO UPDATE SET
    removal_kg_per_tonne = EXCLUDED.removal_kg_per_tonne,
    yield_part = EXCLUDED.yield_part,
    source = EXCLUDED.source;
