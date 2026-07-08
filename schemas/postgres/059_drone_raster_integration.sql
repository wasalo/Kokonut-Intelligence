-- 059_drone_raster_integration.sql
-- Drone & Raster Integration: MSAVI, Raster Metadata, Spatial Clustering, Pest Hotspots

BEGIN;

-- ============================================================================
-- ADD MSAVI TO REMOTE SENSING OBSERVATION
-- ============================================================================

ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS msavi NUMERIC(6,4);

COMMENT ON COLUMN remote_sensing_observation.msavi IS 'Modified Soil-Adjusted Vegetation Index (MSAVI) for understory health measurement';

-- ============================================================================
-- RASTER METADATA (for GeoTIFF and orthomosaic references)
-- ============================================================================

CREATE TABLE IF NOT EXISTS raster_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    raster_name VARCHAR(200) NOT NULL,
    raster_type VARCHAR(100) NOT NULL
        CHECK (raster_type IN (
            'orthomosaic', 'ndvi_raster', 'msavi_raster', 'elevation',
            'canopy_height', 'soil_moisture', 'thermal', 'other'
        )),
    file_url TEXT NOT NULL,
    file_format VARCHAR(20) NOT NULL DEFAULT 'geotiff'
        CHECK (file_format IN ('geotiff', 'tiff', 'jp2', 'png', 'other')),
    file_size_bytes BIGINT,
    crs VARCHAR(50) NOT NULL DEFAULT 'EPSG:4326',
    resolution_m NUMERIC(8,4),
    bbox_west NUMERIC(10,7),
    bbox_south NUMERIC(10,7),
    bbox_east NUMERIC(10,7),
    bbox_north NUMERIC(10,7),
    capture_date DATE,
    capture_method VARCHAR(100),
    sensor VARCHAR(100),
    processing_pipeline TEXT,
    processing_notes TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'processed'
        CHECK (status IN ('raw', 'processing', 'processed', 'archived', 'failed')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_raster_location ON raster_metadata(location_id);
CREATE INDEX IF NOT EXISTS idx_raster_type ON raster_metadata(raster_type);
CREATE INDEX IF NOT EXISTS idx_raster_status ON raster_metadata(status);

CREATE TRIGGER trg_raster_metadata_updated_at
    BEFORE UPDATE ON raster_metadata
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE raster_metadata IS 'Metadata for raster files (GeoTIFF, orthomosaic) — stores references, not binary data';

-- ============================================================================
-- SPATIAL CLUSTER (DBSCAN results)
-- ============================================================================

CREATE TABLE IF NOT EXISTS spatial_cluster (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    cluster_method VARCHAR(50) NOT NULL DEFAULT 'dbscan'
        CHECK (cluster_method IN ('dbscan', 'kmeans', 'hierarchical', 'manual')),
    cluster_name VARCHAR(200),
    cluster_type VARCHAR(100)
        CHECK (cluster_type IN ('tree_group', 'species_group', 'health_group', 'age_group', 'pest_cluster', 'gap_cluster', 'other')),
    tree_count INT NOT NULL DEFAULT 0,
    centroid_geometry GEOMETRY(POINT, 4326),
    hull_geometry GEOMETRY(POLYGON, 4326),
    avg_health_score NUMERIC(5,2),
    dominant_species VARCHAR(200),
    avg_height_m NUMERIC(6,2),
    compactness NUMERIC(5,4),
    eps_m NUMERIC(8,2),
    min_samples INT,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived', 'superseded')),
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

CREATE INDEX IF NOT EXISTS idx_spatial_cluster_location ON spatial_cluster(location_id);
CREATE INDEX IF NOT EXISTS idx_spatial_cluster_method ON spatial_cluster(cluster_method);
CREATE INDEX IF NOT EXISTS idx_spatial_cluster_centroid ON spatial_cluster USING GIST(centroid_geometry);
CREATE INDEX IF NOT EXISTS idx_spatial_cluster_hull ON spatial_cluster USING GIST(hull_geometry);

CREATE TRIGGER trg_spatial_cluster_updated_at
    BEFORE UPDATE ON spatial_cluster
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- PEST HOTSPOT (spatial pest/disease clustering)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pest_hotspot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    hotspot_name VARCHAR(200),
    pest_or_disease VARCHAR(200) NOT NULL,
    cluster_id UUID REFERENCES spatial_cluster(id) ON DELETE SET NULL,
    tree_count_affected INT NOT NULL DEFAULT 0,
    avg_severity NUMERIC(5,2),
    centroid_geometry GEOMETRY(POINT, 4326),
    radius_m NUMERIC(8,2),
    area_m2 NUMERIC(10,2),
    confidence_score NUMERIC(5,2)
        CHECK (confidence_score >= 0 AND confidence_score <= 100),
    detection_date DATE NOT NULL DEFAULT CURRENT_DATE,
    detection_method VARCHAR(100),
    recommended_action TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'treated', 'monitoring', 'resolved', 'escalated')),
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

CREATE INDEX IF NOT EXISTS idx_pest_hotspot_location ON pest_hotspot(location_id);
CREATE INDEX IF NOT EXISTS idx_pest_hotspot_pest ON pest_hotspot(pest_or_disease);
CREATE INDEX IF NOT EXISTS idx_pest_hotspot_status ON pest_hotspot(status);
CREATE INDEX IF NOT EXISTS idx_pest_hotspot_centroid ON pest_hotspot USING GIST(centroid_geometry);

CREATE TRIGGER trg_pest_hotspot_updated_at
    BEFORE UPDATE ON pest_hotspot
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE pest_hotspot IS 'Spatial pest/disease hotspot clusters identified from individual tree health data';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Public spatial clusters
CREATE OR REPLACE VIEW v_public_spatial_clusters AS
SELECT
    sc.id,
    sc.location_id,
    l.name AS location_name,
    sc.cluster_method,
    sc.cluster_name,
    sc.cluster_type,
    sc.tree_count,
    sc.avg_health_score,
    sc.dominant_species,
    sc.avg_height_m,
    sc.compactness,
    sc.eps_m,
    sc.min_samples,
    sc.status,
    ST_AsGeoJSON(sc.centroid_geometry, 6) AS centroid_geojson,
    ST_AsGeoJSON(sc.hull_geometry, 6) AS hull_geojson,
    sc.notes,
    sc.created_at
FROM spatial_cluster sc
JOIN location l ON sc.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND sc.status = 'active';

-- 2. Public pest hotspots
CREATE OR REPLACE VIEW v_public_pest_hotspots AS
SELECT
    ph.id,
    ph.location_id,
    l.name AS location_name,
    ph.hotspot_name,
    ph.pest_or_disease,
    ph.tree_count_affected,
    ph.avg_severity,
    ph.radius_m,
    ph.area_m2,
    ph.confidence_score,
    ph.detection_date,
    ph.detection_method,
    ph.recommended_action,
    ph.status,
    ST_AsGeoJSON(ph.centroid_geometry, 6) AS centroid_geojson,
    ph.notes,
    ph.created_at
FROM pest_hotspot ph
JOIN location l ON ph.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND ph.status IN ('active', 'treated', 'monitoring');

-- 3. Canopy coverage analysis (trees per zone with canopy overlap estimation)
CREATE OR REPLACE VIEW v_public_canopy_analysis AS
SELECT
    t.location_id,
    l.name AS location_name,
    t.zone_id,
    fz.zone_type,
    fz.name AS zone_name,
    fz.area_m2 AS zone_area_m2,
    COUNT(*) FILTER (WHERE t.status = 'alive') AS alive_trees,
    ROUND(AVG(t.canopy_diameter_m), 2) AS avg_canopy_diameter_m,
    ROUND(AVG(t.canopy_diameter_m) * AVG(t.canopy_diameter_m) * 3.14159 / 4, 2) AS avg_crown_area_m2,
    ROUND(
        COUNT(*) FILTER (WHERE t.status = 'alive') *
        AVG(t.canopy_diameter_m) * AVG(t.canopy_diameter_m) * 3.14159 / 4 /
        NULLIF(fz.area_m2, 0) * 100,
        2
    ) AS estimated_canopy_cover_pct
FROM tree_record t
JOIN location l ON t.location_id = l.id
LEFT JOIN farm_zone fz ON t.zone_id = fz.id
WHERE l.status IN ('active', 'verified', 'published')
  AND fz.area_m2 IS NOT NULL
GROUP BY t.location_id, l.name, t.zone_id, fz.zone_type, fz.name, fz.area_m2;

COMMIT;
