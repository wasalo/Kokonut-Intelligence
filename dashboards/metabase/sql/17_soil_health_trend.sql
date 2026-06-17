-- Eagle View: Soil Health Trend
-- Soil pH, organic matter, and nutrient levels over time per plot

SELECT
    ss.sample_date,
    p.name AS plot_name,
    l.name AS location_name,
    ss.ph,
    ss.organic_matter_pct,
    ss.nitrogen_ppm,
    ss.phosphorus_ppm,
    ss.potassium_ppm,
    ss.moisture_pct
FROM soil_sample ss
JOIN plot p ON ss.plot_id = p.id
JOIN location l ON ss.location_id = l.id
ORDER BY ss.sample_date ASC, p.name;
