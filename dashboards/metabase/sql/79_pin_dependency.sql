-- Pin dependencies: governed records blocked by unverified upstream data.
SELECT 'metric_value' AS entity_type, mv.id AS entity_id, mv.location_id,
  l.name AS location, 'unverified' AS blocker, mv.created_at
FROM metric_value mv
JOIN location l ON l.id = mv.location_id
WHERE mv.verified = FALSE

UNION ALL

SELECT 'farm_registry_record' AS entity_type, frr.id AS entity_id, frr.location_id,
  l.name AS location, frr.status AS blocker, frr.created_at
FROM farm_registry_record frr
JOIN location l ON l.id = frr.location_id
WHERE frr.status NOT IN ('verified', 'published')

UNION ALL

SELECT 'climate_impact_summary' AS entity_type, cis.id AS entity_id, cis.location_id,
  l.name AS location, cis.status AS blocker, cis.created_at
FROM climate_impact_summary cis
JOIN location l ON l.id = cis.location_id
WHERE cis.status NOT IN ('verified', 'published')

ORDER BY created_at DESC;
