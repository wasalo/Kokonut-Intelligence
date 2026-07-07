-- Trophic Pyramid Dashboard
SELECT
    ei.species_a_trophic AS from_trophic_level,
    ei.species_b_trophic AS to_trophic_level,
    ei.interaction_type,
    COUNT(*) AS interaction_count,
    AVG(ei.interaction_strength) AS avg_strength,
    l.name AS location_name
FROM ecological_interaction ei
JOIN location l ON l.id = ei.location_id
WHERE ei.status IN ('verified', 'published')
  AND l.status = 'active'
GROUP BY ei.species_a_trophic, ei.species_b_trophic, ei.interaction_type, l.name
ORDER BY ei.species_a_trophic, ei.species_b_trophic;
