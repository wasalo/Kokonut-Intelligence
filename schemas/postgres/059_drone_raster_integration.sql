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

-- 4. Zone adjacency matrix (pairwise distances between all zones)
CREATE OR REPLACE VIEW v_zone_adjacency AS
SELECT
    a.id AS zone_a_id,
    a.zone_key AS zone_a_key,
    a.name AS zone_a_name,
    a.zone_type AS zone_a_type,
    a.area_m2 AS zone_a_area_m2,
    b.id AS zone_b_id,
    b.zone_key AS zone_b_key,
    b.name AS zone_b_name,
    b.zone_type AS zone_b_type,
    b.area_m2 AS zone_b_area_m2,
    a.location_id,
    ROUND(ST_Distance(a.geometry::geography, b.geometry::geography)::numeric, 2) AS distance_m,
    CASE
        WHEN ST_DWithin(a.geometry::geography, b.geometry::geography, 10) THEN 'adjacent'
        WHEN ST_DWithin(a.geometry::geography, b.geometry::geography, 50) THEN 'nearby'
        ELSE 'separated'
    END AS proximity_status,
    CASE
        WHEN a.zone_type IN ('agroforestry', 'syntropic_plot') AND b.zone_type IN ('agroforestry', 'syntropic_plot') THEN 'habitat_to_habitat'
        WHEN a.zone_type IN ('agroforestry', 'syntropic_plot') OR b.zone_type IN ('agroforestry', 'syntropic_plot') THEN 'habitat_to_non_habitat'
        ELSE 'non_habitat_to_non_habitat'
    END AS connectivity_type
FROM farm_zone a
JOIN farm_zone b ON a.id < b.id
WHERE a.location_id = b.location_id
  AND a.geometry IS NOT NULL
  AND b.geometry IS NOT NULL;

-- 5. Habitat connectivity summary (per-location connectivity score)
CREATE OR REPLACE VIEW v_habitat_connectivity_summary AS
WITH habitat_zones AS (
    SELECT id, location_id, zone_key, name, zone_type, area_m2, geometry
    FROM farm_zone
    WHERE geometry IS NOT NULL
      AND zone_type IN ('agroforestry', 'syntropic_plot')
),
zone_pairs AS (
    SELECT
        a.id AS zone_a_id,
        a.name AS zone_a_name,
        a.zone_type AS zone_a_type,
        a.area_m2 AS zone_a_area_m2,
        b.id AS zone_b_id,
        b.name AS zone_b_name,
        b.zone_type AS zone_b_type,
        b.area_m2 AS zone_b_area_m2,
        a.location_id,
        ROUND(ST_Distance(a.geometry::geography, b.geometry::geography)::numeric, 2) AS distance_m
    FROM habitat_zones a
    JOIN habitat_zones b ON a.id < b.id
    WHERE a.location_id = b.location_id
),
nearest_neighbor AS (
    SELECT DISTINCT ON (zone_a_id)
        zone_a_id, zone_a_name, zone_a_type, zone_a_area_m2,
        zone_b_id, zone_b_name, zone_b_type,
        distance_m AS nearest_distance_m
    FROM zone_pairs
    ORDER BY zone_a_id, distance_m
)
SELECT
    h.location_id,
    l.name AS location_name,
    COUNT(DISTINCT h.id) AS habitat_zone_count,
    ROUND(SUM(h.area_m2)::numeric, 2) AS total_habitat_area_m2,
    ROUND(SUM(h.area_m2) / 10000, 4) AS total_habitat_area_ha,
    COUNT(DISTINCT h.zone_type) AS habitat_type_count,
    ROUND(AVG(nn.nearest_distance_m), 2) AS avg_nearest_neighbor_m,
    ROUND(MIN(nn.nearest_distance_m), 2) AS min_nearest_neighbor_m,
    ROUND(MAX(nn.nearest_distance_m), 2) AS max_nearest_neighbor_m,
    CASE
        WHEN AVG(nn.nearest_distance_m) <= 10 THEN 'highly_connected'
        WHEN AVG(nn.nearest_distance_m) <= 50 THEN 'connected'
        WHEN AVG(nn.nearest_distance_m) <= 200 THEN 'moderately_connected'
        ELSE 'fragmented'
    END AS connectivity_status
FROM habitat_zones h
JOIN location l ON h.location_id = l.id
LEFT JOIN nearest_neighbor nn ON h.id = nn.zone_a_id
WHERE l.status IN ('active', 'verified', 'published')
GROUP BY h.location_id, l.name;

COMMIT;
