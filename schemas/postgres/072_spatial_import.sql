-- 072_spatial_import.sql
-- Spatial Import: KML/GeoJSON upload and parsing into farm_zone geometry

BEGIN;

-- ============================================================================
-- SPATIAL IMPORT LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS spatial_import_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    import_format VARCHAR(20) NOT NULL CHECK (import_format IN ('geojson', 'kml')),
    original_filename TEXT,
    raw_content_hash TEXT,
    feature_count INT DEFAULT 0,
    zones_created INT DEFAULT 0,
    zones_updated INT DEFAULT 0,
    zones_skipped INT DEFAULT 0,
    errors JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'success'
        CHECK (status IN ('success', 'partial', 'failed')),
    imported_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_spatial_import_location ON spatial_import_log(location_id);
CREATE INDEX IF NOT EXISTS idx_spatial_import_format ON spatial_import_log(import_format);

COMMENT ON TABLE spatial_import_log IS 'Audit log for KML/GeoJSON spatial imports into farm_zone geometry';

COMMIT;
