-- ============================================================
-- 052_final_gaps.sql — Q6 weather-growth correlation, Q12 endangered species survival
-- ============================================================

-- Q6: Weather-growth correlation view
-- Joins weather observations with harvest events by month
CREATE OR REPLACE VIEW v_public_weather_growth_correlation AS
SELECT
    he.location_id,
    l.name AS location_name,
    DATE_TRUNC('month', he.harvest_date) AS harvest_month,
    c.name AS crop_name,
    SUM(he.quantity) AS total_harvest_kg,
    he.unit AS harvest_unit,
    COUNT(he.id) AS harvest_event_count,
    AVG(wo.temperature_c) AS avg_temperature_c,
    AVG(wo.humidity_pct) AS avg_humidity_pct,
    SUM(wo.rainfall_mm) AS total_rainfall_mm,
    AVG(wo.solar_radiation_wm2) AS avg_solar_radiation,
    CASE
        WHEN AVG(wo.temperature_c) IS NOT NULL AND AVG(wo.humidity_pct) IS NOT NULL
             AND AVG(wo.temperature_c) > 0 AND AVG(wo.humidity_pct) > 0
        THEN ROUND((SUM(he.quantity) / (AVG(wo.temperature_c) * AVG(wo.humidity_pct)))::numeric, 4)
        ELSE NULL
    END AS yield_per_temp_humidity_unit
FROM harvest_event he
JOIN location l ON l.id = he.location_id
JOIN crop_cycle cc ON cc.id = he.crop_cycle_id
JOIN crop c ON c.id = cc.crop_id
LEFT JOIN weather_observation wo ON wo.location_id = he.location_id
    AND wo.observation_date BETWEEN (he.harvest_date - INTERVAL '30 days') AND he.harvest_date
WHERE he.status IN ('verified', 'published')
  AND l.status = 'active'
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  )
GROUP BY he.location_id, l.name, DATE_TRUNC('month', he.harvest_date), c.name, he.unit;

-- Q12: Endangered species survival view
-- Joins underplanting_event with species_observation.conservation_status
CREATE OR REPLACE VIEW v_public_endangered_species_survival AS
SELECT
    ue.id,
    ue.location_id,
    l.name AS location_name,
    ue.species_name,
    so.conservation_status,
    ue.planting_date,
    ue.plant_count,
    ue.survival_count,
    ue.survival_survey_date,
    CASE
        WHEN ue.plant_count IS NOT NULL AND ue.plant_count > 0
             AND ue.survival_count IS NOT NULL
        THEN ROUND((ue.survival_count::numeric / ue.plant_count * 100), 2)
        ELSE NULL
    END AS survival_pct,
    ue.area_m2,
    ue.species_role,
    ue.notes,
    ue.status
FROM underplanting_event ue
JOIN location l ON l.id = ue.location_id
LEFT JOIN species_observation so ON so.species_name = ue.species_name
    AND so.location_id = ue.location_id
    AND so.status IN ('verified', 'published')
WHERE l.status = 'active'
  AND ue.status IN ('verified', 'published')
  AND (
      so.conservation_status IN ('critically_endangered', 'endangered', 'vulnerable', 'near_threatened')
      OR so.conservation_status IS NULL
  )
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('final-gaps-v1', 'Weather-growth correlation view, endangered species survival view', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
