-- Eagle View: Rainfall Trend
-- Precipitation and temperature over time per location

SELECT
    wo.observation_date,
    l.name AS location_name,
    SUM(wo.rainfall_mm) AS total_rainfall_mm,
    AVG(wo.temperature_c) AS avg_temperature_c,
    AVG(wo.humidity_pct) AS avg_humidity_pct,
    COUNT(*) AS reading_count
FROM weather_observation wo
JOIN location l ON wo.location_id = l.id
GROUP BY wo.observation_date, l.name
ORDER BY wo.observation_date ASC;
