-- Phase 5 source-of-truth cleanup.
-- raster_metadata is owned by 059_drone_raster_integration.sql. Migration 115
-- remains a compatibility no-op for installations that already have the table.

DO $$
DECLARE
    required_column TEXT;
BEGIN
    FOREACH required_column IN ARRAY ARRAY[
        'location_id', 'plot_id', 'raster_name', 'raster_type', 'file_url',
        'file_format', 'resolution_m', 'capture_date', 'capture_method',
        'sensor', 'processing_pipeline', 'status', 'source_system',
        'source_id', 'source_raw'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'raster_metadata'
              AND column_name = required_column
        ) THEN
            RAISE EXCEPTION
                'raster_metadata is not the canonical 059 shape; missing column %',
                required_column;
        END IF;
    END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_raster_metadata_source_identity
    ON raster_metadata (source_system, source_id)
    WHERE source_system IS NOT NULL AND source_id IS NOT NULL;

-- Public spatial projections must use the same registry gate as other public
-- projections. CREATE OR REPLACE preserves the established compatibility API.
CREATE OR REPLACE VIEW v_public_spatial_clusters AS
SELECT
    sc.id, sc.location_id, l.name AS location_name, sc.cluster_method,
    sc.cluster_name, sc.cluster_type, sc.tree_count, sc.avg_health_score,
    sc.dominant_species, sc.avg_height_m, sc.compactness, sc.eps_m,
    sc.min_samples, sc.status,
    ST_AsGeoJSON(sc.centroid_geometry, 6) AS centroid_geojson,
    ST_AsGeoJSON(sc.hull_geometry, 6) AS hull_geojson, sc.notes, sc.created_at
FROM spatial_cluster sc
JOIN location l ON l.id = sc.location_id
WHERE l.status IN ('active', 'verified', 'published')
  AND sc.status = 'active'
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = sc.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_pest_hotspots AS
SELECT
    ph.id, ph.location_id, l.name AS location_name, ph.hotspot_name,
    ph.pest_or_disease, ph.tree_count_affected, ph.avg_severity, ph.radius_m,
    ph.area_m2, ph.confidence_score, ph.detection_date, ph.detection_method,
    ph.recommended_action, ph.status,
    ST_AsGeoJSON(ph.centroid_geometry, 6) AS centroid_geojson, ph.notes,
    ph.created_at
FROM pest_hotspot ph
JOIN location l ON l.id = ph.location_id
WHERE l.status IN ('active', 'verified', 'published')
  AND ph.status IN ('active', 'treated', 'monitoring')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = ph.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_canopy_analysis AS
SELECT
    t.location_id, l.name AS location_name, t.zone_id, fz.zone_type,
    fz.name AS zone_name, fz.area_m2 AS zone_area_m2,
    COUNT(*) FILTER (WHERE t.status = 'alive') AS alive_trees,
    ROUND(AVG(t.canopy_diameter_m), 2) AS avg_canopy_diameter_m,
    ROUND(AVG(t.canopy_diameter_m) * AVG(t.canopy_diameter_m) * 3.14159 / 4, 2)
        AS avg_crown_area_m2,
    ROUND(
        COUNT(*) FILTER (WHERE t.status = 'alive')
        * AVG(t.canopy_diameter_m) * AVG(t.canopy_diameter_m) * 3.14159 / 4
        / NULLIF(fz.area_m2, 0) * 100, 2
    ) AS estimated_canopy_cover_pct
FROM tree_record t
JOIN location l ON l.id = t.location_id
LEFT JOIN farm_zone fz ON fz.id = t.zone_id
WHERE l.status IN ('active', 'verified', 'published')
  AND fz.area_m2 IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = t.location_id
        AND fr.status IN ('verified', 'published')
  )
GROUP BY t.location_id, l.name, t.zone_id, fz.zone_type, fz.name, fz.area_m2;

-- Directus metadata repair is intentionally guarded for deployments without
-- Directus. Permission field lists are normalized only to real DB columns.
DO $$
DECLARE
    permission_row RECORD;
    valid_fields TEXT;
BEGIN
    IF to_regclass('public.directus_fields') IS NULL
       OR to_regclass('public.directus_permissions') IS NULL THEN
        RETURN;
    END IF;

    DELETE FROM directus_fields df
    WHERE EXISTS (
        SELECT 1 FROM information_schema.tables t
        WHERE t.table_schema = 'public' AND t.table_name = df.collection
    )
      AND COALESCE(df.special, '') NOT LIKE '%alias%'
      AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.table_name = df.collection
          AND c.column_name = df.field
    );

    FOR permission_row IN
        SELECT id, collection, fields
        FROM directus_permissions
        WHERE fields IS NOT NULL AND fields <> '*'
    LOOP
        SELECT string_agg(trim(field_name), ',' ORDER BY ordinality)
        INTO valid_fields
        FROM unnest(string_to_array(permission_row.fields, ','))
             WITH ORDINALITY AS fields(field_name, ordinality)
        WHERE EXISTS (
            SELECT 1 FROM information_schema.columns c
            WHERE c.table_schema = 'public'
              AND c.table_name = permission_row.collection
              AND c.column_name = trim(field_name)
        );

        IF valid_fields IS NULL THEN
            DELETE FROM directus_permissions WHERE id = permission_row.id;
        ELSE
            UPDATE directus_permissions
            SET fields = valid_fields
            WHERE id = permission_row.id;
        END IF;
    END LOOP;
END $$;
