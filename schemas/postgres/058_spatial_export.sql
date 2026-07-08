-- 058_spatial_export.sql
-- Spatial Export: farm_zone geometry, GeoJSON/KML views, XML export support

BEGIN;

-- ============================================================================
-- ADD GEOMETRY COLUMN TO FARM_ZONE
-- ============================================================================

ALTER TABLE farm_zone ADD COLUMN IF NOT EXISTS geometry GEOMETRY(POLYGON, 4326);

CREATE INDEX IF NOT EXISTS idx_farm_zone_geometry ON farm_zone USING GIST(geometry);

COMMENT ON COLUMN farm_zone.geometry IS 'PostGIS polygon geometry for spatial mapping and export (SRID 4326)';

-- ============================================================================
-- VIEWS FOR SPATIAL EXPORT
-- ============================================================================

-- 1. Farm zone GeoJSON-ready view (all zones with geometry as GeoJSON text)
CREATE OR REPLACE VIEW v_spatial_zone_geojson AS
SELECT
    fz.id,
    fz.location_id,
    l.name AS location_name,
    l.latitude AS location_latitude,
    l.longitude AS location_longitude,
    fz.plot_id,
    p.name AS plot_name,
    fz.zone_key,
    fz.name AS zone_name,
    fz.zone_type,
    fz.area_m2,
    fz.description,
    fz.status,
    ST_AsGeoJSON(fz.geometry, 6) AS geometry_geojson,
    fz.geometry,
    fz.metadata
FROM farm_zone fz
JOIN location l ON fz.location_id = l.id
LEFT JOIN plot p ON fz.plot_id = p.id
WHERE l.status IN ('active', 'verified', 'published')
  AND fz.geometry IS NOT NULL;

-- 2. Tree records GeoJSON-ready view (all trees with point geometry)
CREATE OR REPLACE VIEW v_spatial_tree_geojson AS
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
    t.tree_tag,
    t.latitude,
    t.longitude,
    t.height_m,
    t.dbh_cm,
    t.canopy_diameter_m,
    t.health_score,
    t.maturity_stage,
    t.status,
    ST_AsGeoJSON(t.point_geometry, 6) AS geometry_geojson,
    t.point_geometry AS geometry,
    t.planting_date,
    t.last_survey_date,
    t.metadata
FROM tree_record t
JOIN location l ON t.location_id = l.id
JOIN plot p ON t.plot_id = p.id
LEFT JOIN farm_zone fz ON t.zone_id = fz.id
WHERE l.status IN ('active', 'verified', 'published')
  AND t.point_geometry IS NOT NULL;

-- 3. Location boundary GeoJSON-ready view
CREATE OR REPLACE VIEW v_spatial_location_geojson AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    l.latitude,
    l.longitude,
    l.boundary,
    ST_AsGeoJSON(l.boundary, 6) AS boundary_geojson,
    l.center,
    ST_AsGeoJSON(l.center, 6) AS center_geojson,
    l.status,
    fr.id AS farm_registry_id,
    fr.farm_name
FROM location l
LEFT JOIN farm_registry_record fr ON fr.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND l.boundary IS NOT NULL;

-- 4. Plot boundary GeoJSON-ready view
CREATE OR REPLACE VIEW v_spatial_plot_geojson AS
SELECT
    p.id AS plot_id,
    p.name AS plot_name,
    p.farm_id,
    f.name AS farm_name,
    p.location_id,
    l.name AS location_name,
    p.area_ha,
    p.boundary,
    ST_AsGeoJSON(p.boundary, 6) AS boundary_geojson,
    p.center,
    ST_AsGeoJSON(p.center, 6) AS center_geojson,
    p.status
FROM plot p
JOIN farm f ON p.farm_id = f.id
JOIN location l ON p.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND p.boundary IS NOT NULL;

-- 5. Buffer zone GeoJSON-ready view
CREATE OR REPLACE VIEW v_spatial_buffer_geojson AS
SELECT
    b.id,
    b.location_id,
    l.name AS location_name,
    b.buffer_name,
    b.buffer_type,
    b.width_m,
    b.length_m,
    b.area_m2,
    b.adjacent_use,
    b.condition_status,
    b.boundary_geometry,
    ST_AsGeoJSON(b.boundary_geometry, 6) AS geometry_geojson,
    b.establishment_date,
    b.status
FROM buffer_zone b
JOIN location l ON b.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND b.boundary_geometry IS NOT NULL;

-- 6. Comprehensive spatial summary view (for API endpoint)
CREATE OR REPLACE VIEW v_spatial_project_summary AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    l.latitude,
    l.longitude,
    l.boundary,
    ST_AsGeoJSON(l.boundary, 6) AS boundary_geojson,
    (SELECT COUNT(*) FROM tree_record t WHERE t.location_id = l.id AND t.status = 'alive') AS tree_count,
    (SELECT COUNT(DISTINCT t.species_name) FROM tree_record t WHERE t.location_id = l.id AND t.status = 'alive') AS species_count,
    (SELECT COUNT(*) FROM farm_zone fz WHERE fz.location_id = l.id AND fz.geometry IS NOT NULL) AS zone_count,
    (SELECT json_agg(DISTINCT fz.zone_type) FROM farm_zone fz WHERE fz.location_id = l.id) AS zone_types,
    (SELECT COUNT(*) FROM buffer_zone b WHERE b.location_id = l.id AND b.condition_status = 'adequate') AS buffer_count,
    l.status
FROM location l
WHERE l.status IN ('active', 'verified', 'published');

COMMIT;
