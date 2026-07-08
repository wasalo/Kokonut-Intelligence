-- ============================================================
-- 051_gap_closures.sql — Q1, Q3, Q4, Q5, Q11 gap closures
-- ============================================================

-- Q5: Add irrigation_mm_used to resource_consumption for rainfall-vs-irrigation comparison
ALTER TABLE resource_consumption ADD COLUMN IF NOT EXISTS irrigation_mm_used NUMERIC(8,2);
ALTER TABLE resource_consumption ADD COLUMN IF NOT EXISTS rainfall_mm_during_period NUMERIC(8,2);

-- Q5: Public view joining rainfall with irrigation
CREATE OR REPLACE VIEW v_public_rainfall_vs_irrigation AS
SELECT
    rc.id,
    rc.location_id,
    l.name AS location_name,
    rc.period_start,
    rc.period_end,
    rc.irrigation_mm_used,
    rc.rainfall_mm_during_period,
    CASE
        WHEN rc.irrigation_mm_used IS NOT NULL AND rc.rainfall_mm_during_period IS NOT NULL
        THEN rc.rainfall_mm_during_period - rc.irrigation_mm_used
        ELSE NULL
    END AS rainfall_irrigation_delta_mm,
    CASE
        WHEN rc.irrigation_mm_used IS NOT NULL AND rc.irrigation_mm_used > 0
        THEN ROUND((rc.rainfall_mm_during_period / rc.irrigation_mm_used)::numeric, 2)
        ELSE NULL
    END AS rainfall_to_irrigation_ratio,
    rc.notes,
    rc.status
FROM resource_consumption rc
JOIN location l ON l.id = rc.location_id
WHERE l.status = 'active'
  AND rc.status IN ('verified', 'published')
  AND rc.irrigation_mm_used IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

-- Q11: Public view for species richness per hectare
CREATE OR REPLACE VIEW v_public_species_richness_per_ha AS
SELECT
    so.location_id,
    l.name AS location_name,
    so.plot_id,
    p.name AS plot_name,
    p.area AS plot_area_ha,
    COUNT(DISTINCT so.species_name) AS unique_species_count,
    CASE
        WHEN p.area IS NOT NULL AND p.area > 0
        THEN ROUND((COUNT(DISTINCT so.species_name) / p.area)::numeric, 2)
        ELSE NULL
    END AS species_per_hectare,
    COUNT(*) AS total_observations,
    MAX(so.observation_date) AS last_observation_date
FROM species_observation so
JOIN location l ON l.id = so.location_id
LEFT JOIN plot p ON p.id = so.plot_id
WHERE l.status = 'active'
  AND so.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  )
GROUP BY so.location_id, l.name, so.plot_id, p.name, p.area;

-- Q11: Location-level species richness per hectare
CREATE OR REPLACE VIEW v_public_location_species_richness AS
SELECT
    so.location_id,
    l.name AS location_name,
    COALESCE(SUM(p.area), 0) AS total_area_ha,
    COUNT(DISTINCT so.species_name) AS unique_species_count,
    CASE
        WHEN COALESCE(SUM(p.area), 0) > 0
        THEN ROUND((COUNT(DISTINCT so.species_name) / SUM(p.area))::numeric, 2)
        ELSE NULL
    END AS species_per_hectare,
    COUNT(*) AS total_observations
FROM species_observation so
JOIN location l ON l.id = so.location_id
LEFT JOIN plot p ON p.id = so.plot_id
WHERE l.status = 'active'
  AND so.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  )
GROUP BY so.location_id, l.name;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('gap-closures-v1', 'Rainfall vs irrigation view, species richness per hectare views, resource consumption extensions', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
