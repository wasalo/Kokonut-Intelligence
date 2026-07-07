-- Ecological Interactions Dashboard
SELECT
    ei.species_a_name,
    ei.species_a_common,
    ei.species_a_trophic,
    ei.species_b_name,
    ei.species_b_common,
    ei.species_b_trophic,
    ei.interaction_type,
    ei.interaction_strength,
    ei.description,
    fz.name AS zone_name,
    l.name AS location_name
FROM ecological_interaction ei
JOIN location l ON l.id = ei.location_id
LEFT JOIN farm_zone fz ON fz.id = ei.zone_id
WHERE ei.status IN ('verified', 'published')
  AND l.status = 'active'
ORDER BY ei.interaction_strength DESC;
