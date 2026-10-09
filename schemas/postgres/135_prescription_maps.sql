-- 135_prescription_maps.sql
-- Variable Rate Technology (VRT) prescription maps and application zones
-- Precision Agriculture Phase 2: Prescription Maps / VRT

BEGIN;

-- ============================================================
-- PRESCRIPTION MAPS
-- ============================================================

CREATE TABLE IF NOT EXISTS prescription_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    input_type VARCHAR(100) NOT NULL,
    basis_metric VARCHAR(100) NOT NULL,
    basis_source VARCHAR(100) DEFAULT 'kriging',
    unit VARCHAR(50) NOT NULL,
    total_area_ha NUMERIC(12,4),
    avg_rate NUMERIC(10,4),
    min_rate NUMERIC(10,4),
    max_rate NUMERIC(10,4),
    total_volume NUMERIC(12,4),
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'applied', 'archived')),
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prescription_map_location ON prescription_map(location_id, status);
CREATE INDEX IF NOT EXISTS idx_prescription_map_plot ON prescription_map(plot_id);

-- ============================================================
-- PRESCRIPTION ZONES
-- ============================================================

CREATE TABLE IF NOT EXISTS prescription_zone (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prescription_map_id UUID NOT NULL REFERENCES prescription_map(id) ON DELETE CASCADE,
    zone_name VARCHAR(100),
    zone_class VARCHAR(50),
    geometry GEOMETRY(POLYGON, 4326),
    area_m2 NUMERIC(15,4),
    application_rate NUMERIC(10,4) NOT NULL,
    application_unit VARCHAR(50) NOT NULL,
    basis_value NUMERIC(12,4),
    confidence NUMERIC(5,2),
    material_cost_usd NUMERIC(10,2),
    notes TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_prescription_zone_geom ON prescription_zone USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_prescription_zone_map ON prescription_zone(prescription_map_id);

-- ============================================================
-- MATERIAL COST REFERENCE
-- ============================================================

CREATE TABLE IF NOT EXISTS material_cost (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    input_type VARCHAR(100) NOT NULL,
    input_name VARCHAR(255),
    unit VARCHAR(50) NOT NULL,
    cost_per_unit NUMERIC(10,2) NOT NULL,
    supplier VARCHAR(255),
    effective_date DATE DEFAULT CURRENT_DATE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_material_cost_unique
    ON material_cost(location_id, input_type, unit, effective_date);

-- ============================================================
-- VIEWS
-- ============================================================

CREATE OR REPLACE VIEW v_public_prescription_maps AS
SELECT
    pm.id,
    pm.location_id,
    pm.plot_id,
    pm.input_type,
    pm.basis_metric,
    pm.unit,
    pm.total_area_ha,
    pm.avg_rate,
    pm.min_rate,
    pm.max_rate,
    pm.total_volume,
    pm.status,
    pm.generated_at,
    pm.approved_at,
    l.name AS location_name,
    p.name AS plot_name
FROM prescription_map pm
JOIN location l ON l.id = pm.location_id
LEFT JOIN plot p ON p.id = pm.plot_id
WHERE pm.status IN ('approved', 'applied')
  AND l.status = 'active';

CREATE OR REPLACE VIEW v_prescription_summary AS
SELECT
    pm.id AS prescription_id,
    pm.location_id,
    pm.input_type,
    pm.basis_metric,
    pm.unit,
    pm.status,
    pm.total_area_ha,
    pm.avg_rate,
    pm.total_volume,
    COUNT(pz.id) AS zone_count,
    MIN(pz.application_rate) AS zone_min_rate,
    MAX(pz.application_rate) AS zone_max_rate,
    SUM(COALESCE(pz.material_cost_usd, 0)) AS total_estimated_cost,
    pm.generated_at
FROM prescription_map pm
LEFT JOIN prescription_zone pz ON pz.prescription_map_id = pm.id
GROUP BY pm.id, pm.location_id, pm.input_type, pm.basis_metric,
         pm.unit, pm.status, pm.total_area_ha, pm.avg_rate,
         pm.total_volume, pm.generated_at;

-- Rate distribution view: shows how zones are distributed across rate classes
CREATE OR REPLACE VIEW v_prescription_rate_distribution AS
SELECT
    pz.prescription_map_id,
    pz.zone_class,
    pz.application_rate,
    COUNT(*) AS zone_count,
    SUM(pz.area_m2) AS total_area_m2,
    SUM(pz.area_m2) / 10000.0 AS total_area_ha,
    AVG(pz.basis_value) AS avg_basis_value
FROM prescription_zone pz
GROUP BY pz.prescription_map_id, pz.zone_class, pz.application_rate
ORDER BY pz.prescription_map_id, pz.application_rate;

COMMIT;
