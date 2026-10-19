-- Normalize plot areas before reporting trees per hectare.
-- Keep this as a forward migration; 057_tree_tracking.sql may already be applied.

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
    ROUND(
        COUNT(*) FILTER (WHERE t.status = 'alive')::numeric
        / NULLIF(
            CASE
                WHEN p.area IS NULL OR p.area <= 0 THEN NULL
                ELSE CASE LOWER(BTRIM(COALESCE(p.area_unit, '')))
                    WHEN 'hectare' THEN p.area
                    WHEN 'hectares' THEN p.area
                    WHEN 'ha' THEN p.area
                    WHEN 'square_meter' THEN p.area / 10000.0
                    WHEN 'square_meters' THEN p.area / 10000.0
                    WHEN 'm2' THEN p.area / 10000.0
                    WHEN 'sqm' THEN p.area / 10000.0
                    WHEN 'acre' THEN p.area * 0.40468564224
                    WHEN 'acres' THEN p.area * 0.40468564224
                    ELSE NULL
                END
            END,
            0
        ),
        2
    ) AS trees_per_ha,
    ROUND(AVG(t.height_m), 2) AS avg_height_m,
    ROUND(AVG(t.canopy_diameter_m), 2) AS avg_canopy_diameter_m,
    ROUND(AVG(t.health_score), 1) AS avg_health_score,
    ST_Centroid(ST_Collect(t.point_geometry)) AS centroid_geometry
FROM tree_record t
JOIN location l ON t.location_id = l.id
JOIN plot p ON t.plot_id = p.id
LEFT JOIN farm_zone fz ON t.zone_id = fz.id
WHERE l.status IN ('active', 'verified', 'published')
GROUP BY t.location_id, l.name, t.plot_id, p.name, p.area, p.area_unit,
         t.zone_id, fz.zone_type, t.species_name;
