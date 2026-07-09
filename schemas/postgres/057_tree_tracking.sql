-- 057_tree_tracking.sql
-- Individual Tree Tracking with GPS Coordinates
-- Enables Silvi integration, spatial mapping, and growth rate tracking

BEGIN;

-- ============================================================================
-- TREE RECORD (Individual Trees)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tree_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID NOT NULL REFERENCES plot(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    tree_inventory_id UUID REFERENCES tree_inventory(id) ON DELETE SET NULL,
    species_name VARCHAR(200) NOT NULL,
    species_common_name VARCHAR(200),
    tree_tag VARCHAR(50) NOT NULL,
    latitude NUMERIC(10,7) NOT NULL,
    longitude NUMERIC(10,7) NOT NULL,
    point_geometry GEOMETRY(POINT, 4326),
    planting_date DATE,
    height_m NUMERIC(6,2),
    dbh_cm NUMERIC(6,2),
    canopy_diameter_m NUMERIC(6,2),
    health_score NUMERIC(5,2) DEFAULT 100
        CHECK (health_score >= 0 AND health_score <= 100),
    maturity_stage VARCHAR(50) NOT NULL DEFAULT 'seedling'
        CHECK (maturity_stage IN ('seedling', 'juvenile', 'mature', 'mature-elder')),
    status VARCHAR(50) NOT NULL DEFAULT 'alive'
        CHECK (status IN ('alive', 'dead', 'removal', 'surviving')),
    last_survey_date DATE,
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

-- Auto-compute point_geometry from lat/lon
CREATE OR REPLACE FUNCTION fn_tree_record_compute_geometry()
RETURNS TRIGGER AS $$
BEGIN
    NEW.point_geometry = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tree_record_compute_geometry
    BEFORE INSERT OR UPDATE ON tree_record
    FOR EACH ROW EXECUTE FUNCTION fn_tree_record_compute_geometry();

CREATE TRIGGER trg_tree_record_updated_at
    BEFORE UPDATE ON tree_record
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS idx_tree_record_location ON tree_record(location_id);
CREATE INDEX IF NOT EXISTS idx_tree_record_plot ON tree_record(plot_id);
CREATE INDEX IF NOT EXISTS idx_tree_record_zone ON tree_record(zone_id);
CREATE INDEX IF NOT EXISTS idx_tree_record_species ON tree_record(species_name);
CREATE INDEX IF NOT EXISTS idx_tree_record_status ON tree_record(status);
CREATE INDEX IF NOT EXISTS idx_tree_record_inventory ON tree_record(tree_inventory_id);
CREATE INDEX IF NOT EXISTS idx_tree_record_geometry ON tree_record USING GIST(point_geometry);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tree_record_tag_per_plot ON tree_record(plot_id, tree_tag);

COMMENT ON TABLE tree_record IS 'Individual tree records with GPS coordinates for spatial mapping, Silvi integration, and growth tracking';

-- ============================================================================
-- TREE MEASUREMENT (Time-Series Growth Tracking)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tree_measurement (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tree_record_id UUID NOT NULL REFERENCES tree_record(id) ON DELETE CASCADE,
    measurement_date DATE NOT NULL DEFAULT CURRENT_DATE,
    height_m NUMERIC(6,2),
    dbh_cm NUMERIC(6,2),
    canopy_diameter_m NUMERIC(6,2),
    health_score NUMERIC(5,2)
        CHECK (health_score >= 0 AND health_score <= 100),
    notes TEXT,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tree_measurement_record ON tree_measurement(tree_record_id);
CREATE INDEX IF NOT EXISTS idx_tree_measurement_date ON tree_measurement(measurement_date);

COMMENT ON TABLE tree_measurement IS 'Time-series measurements for individual tree growth rate tracking';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Public tree records (gated: registry + GPS stripped for poaching prevention)
CREATE OR REPLACE VIEW v_public_tree_records AS
SELECT
    t.id,
    t.location_id,
    l.name AS location_name,
    t.plot_id,
    p.name AS plot_name,
    t.zone_id,
    fz.zone_type,
    t.species_name,
    t.species_common_name,
    t.planting_date,
    t.height_m,
    t.dbh_cm,
    t.canopy_diameter_m,
    t.health_score,
    t.maturity_stage,
    t.status,
    t.last_survey_date,
    t.created_at
FROM tree_record t
JOIN location l ON t.location_id = l.id
JOIN plot p ON t.plot_id = p.id
LEFT JOIN farm_zone fz ON t.zone_id = fz.id
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND t.status = 'alive'
  AND (fr.id IS NULL OR fr.status IN ('verified', 'published'));

-- 2. Public tree density map
CREATE OR REPLACE VIEW v_public_tree_density_map AS
SELECT
    t.location_id,
    l.name AS location_name,
    t.plot_id,
    p.name AS plot_name,
    t.zone_id,
    fz.zone_type,
    t.species_name,
    COUNT(*) AS tree_count,
    COUNT(*) FILTER (WHERE t.status = 'alive') AS alive_count,
    COUNT(*) FILTER (WHERE t.status = 'dead') AS dead_count,
    ROUND(COUNT(*) FILTER (WHERE t.status = 'alive')::numeric / NULLIF(p.area_ha, 0), 2) AS trees_per_ha,
    ROUND(AVG(t.height_m), 2) AS avg_height_m,
    ROUND(AVG(t.canopy_diameter_m), 2) AS avg_canopy_diameter_m,
    ROUND(AVG(t.health_score), 1) AS avg_health_score,
    ST_Centroid(ST_Collect(t.point_geometry)) AS centroid_geometry
FROM tree_record t
JOIN location l ON t.location_id = l.id
JOIN plot p ON t.plot_id = p.id
LEFT JOIN farm_zone fz ON t.zone_id = fz.id
WHERE l.status IN ('active', 'verified', 'published')
GROUP BY t.location_id, l.name, t.plot_id, p.name, p.area_ha, t.zone_id, fz.zone_type, t.species_name;

COMMIT;
