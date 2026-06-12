-- Eagle View: Environmental Health
-- Soil carbon, biodiversity, and remote sensing across all plots

SELECT
  l.name as location,
  f.name as farm,
  p.name as plot,
  COALESCE(sc.carbon_tonnes_per_ha, 0) as soil_carbon,
  COALESCE(so.species_count, 0) as species_count,
  COALESCE(so.shannon_index, 0) as shannon_diversity_index,
  COALESCE(rs.ndvi, 0) as latest_ndvi,
  rs.observation_date as latest_ndvi_date
FROM plot p
JOIN farm f ON p.farm_id = f.id
JOIN location l ON f.location_id = l.id
LEFT JOIN LATERAL (
  SELECT carbon_tonnes_per_ha 
  FROM soil_carbon_measurement 
  WHERE plot_id = p.id 
  ORDER BY measurement_date DESC 
  LIMIT 1
) sc ON true
LEFT JOIN LATERAL (
  SELECT 
    COUNT(DISTINCT species_name) as species_count,
    CASE 
      WHEN COUNT(DISTINCT species_name) > 0 
      THEN -1 * SUM(
        CASE WHEN COUNT(*) > 0 
        THEN (COUNT(*)::float / (SELECT COUNT(*) FROM species_observation WHERE plot_id = p.id)) * 
             ln(COUNT(*)::float / (SELECT COUNT(*) FROM species_observation WHERE plot_id = p.id))
        ELSE 0 END
      )
      ELSE 0 
    END as shannon_index
  FROM species_observation 
  WHERE plot_id = p.id
) so ON true
LEFT JOIN LATERAL (
  SELECT ndvi, observation_date 
  FROM remote_sensing_observation 
  WHERE plot_id = p.id 
  ORDER BY observation_date DESC 
  LIMIT 1
) rs ON true
ORDER BY l.name, f.name, p.name;
