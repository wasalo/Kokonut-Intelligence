-- Eagle View: Soil Carbon Trajectory
-- Soil organic carbon measurements over time per plot

SELECT
    scm.measurement_date,
    p.name AS plot_name,
    l.name AS location_name,
    scm.carbon_tonnes_per_ha,
    scm.carbon_pct,
    scm.measurement_method,
    scm.is_baseline
FROM soil_carbon_measurement scm
JOIN plot p ON scm.plot_id = p.id
JOIN location l ON scm.location_id = l.id
ORDER BY scm.measurement_date ASC, p.name;
