-- Dashboard SQL: 66_livestock_feed_intake
-- Daily feed intake trends, conversion ratio, and per-animal consumption

SELECT
    fir.location_id,
    l.name AS location_name,
    fir.livestock_group_id,
    lg.group_name,
    lg.species AS livestock_species,
    lg.breed AS livestock_breed,
    lg.animal_count,
    fir.record_date,
    fir.feed_type,
    fir.feed_name,
    fir.quantity_kg,
    fir.per_animal_kg,
    fir.method,
    fir.temperature_c,
    fir.notes,
    fir.status
FROM feed_intake_record fir
JOIN location l ON l.id = fir.location_id
JOIN livestock_group lg ON lg.id = fir.livestock_group_id
WHERE fir.status IN ('verified', 'published')
  AND l.status = 'active'
ORDER BY fir.record_date DESC, lg.group_name;
