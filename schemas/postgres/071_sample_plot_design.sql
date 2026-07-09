-- 071_sample_plot_design.sql
-- Sample Plot Generation: statistically valid plot designs for forest monitoring
-- Inspired by Open Forest Protocol's MRV standard

BEGIN;

-- ============================================================================
-- SAMPLE PLOT DESIGN (one design per zone per method)
-- ============================================================================

CREATE TABLE IF NOT EXISTS sample_plot_design (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    zone_id UUID NOT NULL REFERENCES farm_zone(id) ON DELETE CASCADE,
    design_name VARCHAR(200),
    sampling_method VARCHAR(50) NOT NULL DEFAULT 'stratified_random'
        CHECK (sampling_method IN ('simple_random', 'stratified_random', 'systematic_grid')),
    target_plot_count INT NOT NULL CHECK (target_plot_count > 0),
    target_plot_area_m2 NUMERIC(10,2) CHECK (target_plot_area_m2 > 0),
    min_distance_between_plots_m NUMERIC(8,2) DEFAULT 10.0,
    zone_area_m2 NUMERIC(15,4),
    zone_area_ha NUMERIC(8,4),
    confidence_level NUMERIC(5,2) DEFAULT 95.0,
    generated_plot_count INT DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'superseded')),
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

CREATE INDEX IF NOT EXISTS idx_sample_plot_design_location ON sample_plot_design(location_id);
CREATE INDEX IF NOT EXISTS idx_sample_plot_design_zone ON sample_plot_design(zone_id);
CREATE INDEX IF NOT EXISTS idx_sample_plot_design_status ON sample_plot_design(status);

CREATE TRIGGER trg_sample_plot_design_updated_at
    BEFORE UPDATE ON sample_plot_design
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE sample_plot_design IS 'Statistical plot design for forest monitoring — mirrors OFP sample plot generation';

-- ============================================================================
-- SAMPLE PLOT (individual plots generated from a design)
-- ============================================================================

CREATE TABLE IF NOT EXISTS sample_plot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    design_id UUID NOT NULL REFERENCES sample_plot_design(id) ON DELETE CASCADE,
    zone_id UUID NOT NULL REFERENCES farm_zone(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_number INT NOT NULL,
    plot_label VARCHAR(50),
    center_latitude NUMERIC(10,7) NOT NULL,
    center_longitude NUMERIC(10,7) NOT NULL,
    center_geometry GEOMETRY(POINT, 4326),
    plot_area_m2 NUMERIC(10,2),
    radius_m NUMERIC(8,2),
    stratum VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sample_plot_design ON sample_plot(design_id);
CREATE INDEX IF NOT EXISTS idx_sample_plot_zone ON sample_plot(zone_id);
CREATE INDEX IF NOT EXISTS idx_sample_plot_location ON sample_plot(location_id);
CREATE INDEX IF NOT EXISTS idx_sample_plot_geometry ON sample_plot USING GIST(center_geometry);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sample_plot_number_per_design ON sample_plot(design_id, plot_number);

COMMENT ON TABLE sample_plot IS 'Individual sample plots generated from a plot design — used for field agent measurement';

-- Auto-compute center_geometry from lat/lon
CREATE OR REPLACE FUNCTION fn_sample_plot_compute_geometry()
RETURNS TRIGGER AS $$
BEGIN
    NEW.center_geometry = ST_SetSRID(ST_MakePoint(NEW.center_longitude, NEW.center_latitude), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sample_plot_compute_geometry
    BEFORE INSERT OR UPDATE ON sample_plot
    FOR EACH ROW EXECUTE FUNCTION fn_sample_plot_compute_geometry();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Public sample plot summary per design
CREATE OR REPLACE VIEW v_public_sample_plot_designs AS
SELECT
    spd.id AS design_id,
    spd.location_id,
    l.name AS location_name,
    spd.zone_id,
    fz.zone_key,
    fz.name AS zone_name,
    fz.zone_type,
    spd.design_name,
    spd.sampling_method,
    spd.target_plot_count,
    spd.generated_plot_count,
    spd.target_plot_area_m2,
    spd.zone_area_m2,
    spd.zone_area_ha,
    spd.confidence_level,
    spd.status,
    spd.created_at
FROM sample_plot_design spd
JOIN location l ON spd.location_id = l.id
JOIN farm_zone fz ON spd.zone_id = fz.id
WHERE l.status IN ('active', 'verified', 'published');

-- 2. Public sample plots with geometry
CREATE OR REPLACE VIEW v_public_sample_plots AS
SELECT
    sp.id AS plot_id,
    sp.design_id,
    sp.location_id,
    l.name AS location_name,
    sp.zone_id,
    fz.zone_key,
    fz.name AS zone_name,
    sp.plot_number,
    sp.plot_label,
    sp.center_latitude,
    sp.center_longitude,
    ST_AsGeoJSON(sp.center_geometry, 6) AS geometry_geojson,
    sp.plot_area_m2,
    sp.radius_m,
    sp.stratum,
    spd.sampling_method,
    sp.created_at
FROM sample_plot sp
JOIN location l ON sp.location_id = l.id
JOIN farm_zone fz ON sp.zone_id = fz.id
JOIN sample_plot_design spd ON sp.design_id = spd.id
WHERE l.status IN ('active', 'verified', 'published');

-- 3. Overdue measurements (zones with no recent sample plot visits)
CREATE OR REPLACE VIEW v_sample_plot_measurement_status AS
SELECT
    sp.id AS plot_id,
    sp.plot_label,
    sp.zone_id,
    fz.name AS zone_name,
    fz.zone_type,
    sp.location_id,
    l.name AS location_name,
    sp.center_latitude,
    sp.center_longitude,
    sp.stratum,
    (SELECT MAX(tm.measurement_date)
     FROM tree_measurement tm
     JOIN tree_record tr ON tm.tree_record_id = tr.id
     WHERE tr.zone_id = sp.zone_id
    ) AS last_tree_measurement_date,
    sp.created_at AS plot_created_at
FROM sample_plot sp
JOIN location l ON sp.location_id = l.id
JOIN farm_zone fz ON sp.zone_id = fz.id
WHERE l.status IN ('active', 'verified', 'published');

COMMIT;
