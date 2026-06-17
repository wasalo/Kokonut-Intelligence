-- Eagle View: NDVI Trend Over Time
-- NDVI vegetation index trajectory per plot for time-series visualization

SELECT
    rs.observation_date,
    p.name AS plot_name,
    l.name AS location_name,
    rs.ndvi,
    rs.ndre,
    rs.evi,
    rs.source AS sensor_source
FROM remote_sensing_observation rs
JOIN plot p ON rs.plot_id = p.id
JOIN location l ON rs.location_id = l.id
WHERE rs.ndvi IS NOT NULL
ORDER BY rs.observation_date ASC, p.name;
