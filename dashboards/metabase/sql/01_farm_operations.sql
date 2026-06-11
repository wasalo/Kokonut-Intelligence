-- Farm Operations Dashboard
-- Shows farm overview with harvest volumes and activity counts

SELECT 
  l.name as location,
  f.name as farm,
  COUNT(DISTINCT p.id) as plot_count,
  COUNT(DISTINCT cc.id) as active_crop_cycles,
  COALESCE(SUM(h.quantity), 0) as total_harvest_kg,
  COUNT(DISTINCT fa.id) as total_activities,
  COALESCE(SUM(CASE WHEN cc.status = 'active' THEN 1 ELSE 0 END), 0) as active_cycles
FROM farm f
JOIN location l ON f.location_id = l.id
LEFT JOIN plot p ON f.id = p.farm_id
LEFT JOIN crop_cycle cc ON p.id = cc.plot_id
LEFT JOIN harvest_event h ON cc.id = h.crop_cycle_id
LEFT JOIN farm_activity fa ON cc.id = fa.crop_cycle_id
WHERE f.status = 'active'
GROUP BY l.name, f.name
ORDER BY total_harvest_kg DESC;
