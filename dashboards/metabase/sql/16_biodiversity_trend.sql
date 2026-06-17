-- Eagle View: Biodiversity Over Time
-- Species count and diversity per observation date per plot

SELECT
    so.observation_date,
    p.name AS plot_name,
    l.name AS location_name,
    COUNT(DISTINCT so.species_name) AS species_count,
    COUNT(*) AS total_observations,
    COUNT(DISTINCT so.species_category) AS category_count
FROM species_observation so
JOIN plot p ON so.plot_id = p.id
JOIN location l ON so.location_id = l.id
GROUP BY so.observation_date, p.name, l.name
ORDER BY so.observation_date ASC, p.name;
