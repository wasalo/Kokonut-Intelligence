-- Dashboard SQL: 64_pest_management
-- Monthly pest incidence trends, outbreak probability, and biocontrol effectiveness

SELECT
    po.location_id,
    l.name AS location_name,
    po.plot_id,
    p.name AS plot_name,
    DATE_TRUNC('month', po.observation_date) AS observation_month,
    po.pest_species,
    po.pest_common_name,
    po.pest_category,
    COUNT(*) AS observation_count,
    AVG(po.outbreak_probability_pct) AS avg_outbreak_probability_pct,
    AVG(po.affected_area_pct) AS avg_affected_area_pct,
    SUM(CASE WHEN po.severity IN ('high', 'critical') THEN 1 ELSE 0 END) AS severe_count,
    AVG(po.incidence_count) AS avg_incidence,
    SUM(COALESCE(po.predator_count, 0)) AS total_predators,
    SUM(CASE WHEN po.natural_enemy_present THEN 1 ELSE 0 END) AS natural_enemy_observations,
    AVG(po.temperature_c) AS avg_temperature_c,
    AVG(po.humidity_pct) AS avg_humidity_pct
FROM pest_observation po
JOIN location l ON l.id = po.location_id
LEFT JOIN plot p ON p.id = po.plot_id
WHERE po.status IN ('verified', 'published')
  AND l.status = 'active'
GROUP BY
    po.location_id, l.name, po.plot_id, p.name,
    DATE_TRUNC('month', po.observation_date),
    po.pest_species, po.pest_common_name, po.pest_category
ORDER BY observation_month DESC, avg_outbreak_probability_pct DESC;
