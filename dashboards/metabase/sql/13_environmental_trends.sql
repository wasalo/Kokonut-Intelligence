-- Environmental Trends — NDVI, Soil Carbon, Biodiversity over time
-- Used by Metabase Eagle View dashboard

SELECT
    l.name AS location_name,
    p.name AS plot_name,
    rs.observation_date,
    rs.ndvi,
    rs.ndre,
    rs.evi,
    rs.canopy_cover_pct,
    rs.source AS sensor_source
FROM remote_sensing_observation rs
JOIN plot p ON rs.plot_id = p.id
JOIN location l ON rs.location_id = l.id
WHERE rs.ndvi IS NOT NULL
ORDER BY rs.observation_date ASC, p.name;
