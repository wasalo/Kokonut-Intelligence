-- Comprehensive status: composite per-location view across all governed dimensions.
SELECT
  l.name AS location,
  l.status AS location_status,
  (SELECT COUNT(*) FROM farm_registry_record frr WHERE frr.location_id = l.id AND frr.status = 'verified') AS verified_registries,
  (SELECT COUNT(*) FROM metric_value mv WHERE mv.location_id = l.id AND mv.verified = TRUE) AS verified_metrics,
  (SELECT COUNT(*) FROM carbon_credit cc WHERE cc.location_id = l.id AND cc.status = 'published') AS published_credits,
  (SELECT COUNT(*) FROM stakeholder_outcome so WHERE so.location_id = l.id AND so.status = 'verified') AS verified_outcomes,
  (SELECT COUNT(*) FROM tree_inventory ti WHERE ti.location_id = l.id) AS tree_count,
  (SELECT COALESCE(SUM(hv.quantity_kg), 0) FROM harvest_event hv WHERE hv.location_id = l.id) AS total_harvest_kg
FROM location l
WHERE l.status = 'active'
ORDER BY l.name;
