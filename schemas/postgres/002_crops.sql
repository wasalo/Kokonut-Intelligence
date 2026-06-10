-- ============================================================
-- 002_crops.sql — Crops and crop cycles
-- ============================================================

-- Crop types
CREATE TABLE IF NOT EXISTS crop (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    scientific_name VARCHAR(255),
    variety VARCHAR(255),
    crop_category VARCHAR(100), -- grain, legume, vegetable, fruit, root, fiber, oil, spice, tree, other
    growing_season_days INTEGER,
    expected_yield_per_ha NUMERIC(12,4),
    expected_yield_unit VARCHAR(50),
    water_needs VARCHAR(50), -- low, medium, high
    climate_zone VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crop_cycle (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plot_id UUID NOT NULL REFERENCES plot(id) ON DELETE RESTRICT,
    crop_id UUID NOT NULL REFERENCES crop(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    cycle_name VARCHAR(255),
    season VARCHAR(50), -- dry, wet, spring, summer, fall, winter
    planting_date DATE,
    expected_harvest_date DATE,
    actual_harvest_date DATE,
    -- Yield tracking
    expected_yield NUMERIC(12,4),
    expected_yield_unit VARCHAR(50),
    actual_yield NUMERIC(12,4),
    actual_yield_unit VARCHAR(50),
    -- Revenue projections
    expected_price_per_unit NUMERIC(12,4),
    expected_revenue NUMERIC(15,2),
    actual_revenue NUMERIC(15,2),
    -- Planting details
    planting_density NUMERIC(10,2),
    planting_density_unit VARCHAR(50), -- plants_per_ha, seeds_per_ha
    area_planted NUMERIC(12,4),
    area_unit VARCHAR(20) DEFAULT 'hectares',
    -- Status
    status VARCHAR(50) DEFAULT 'planned', -- planned, active, flowering, harvesting, harvested, completed, failed
    failure_reason TEXT,
    metadata JSONB DEFAULT '{}',
    schema_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_crop_cycle_plot ON crop_cycle(plot_id);
CREATE INDEX IF NOT EXISTS idx_crop_cycle_crop ON crop_cycle(crop_id);
CREATE INDEX IF NOT EXISTS idx_crop_cycle_location ON crop_cycle(location_id);
CREATE INDEX IF NOT EXISTS idx_crop_cycle_status ON crop_cycle(status);
CREATE INDEX IF NOT EXISTS idx_crop_cycle_planting ON crop_cycle(planting_date);
