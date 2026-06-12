-- Eagle View: Harvest & Loss Summary
-- Total harvest, loss rate, and top performing crops

SELECT
  c.name as crop,
  COUNT(DISTINCT h.id) as harvest_events,
  COALESCE(SUM(h.quantity), 0) as total_harvest_kg,
  COALESCE(AVG(h.quantity), 0) as avg_harvest_kg,
  COALESCE(SUM(le.quantity), 0) as total_loss_kg,
  CASE 
    WHEN SUM(h.quantity) > 0 
    THEN ROUND(SUM(COALESCE(le.quantity, 0)) / SUM(h.quantity) * 100::numeric, 2)
    ELSE 0 
  END as loss_rate_pct,
  COUNT(DISTINCT se.id) as sales_count,
  COALESCE(SUM(se.total_amount), 0) as total_sales_usd
FROM crop c
JOIN crop_cycle cc ON c.id = cc.crop_id
LEFT JOIN harvest_event h ON cc.id = h.crop_cycle_id AND h.status != 'rejected'
LEFT JOIN loss_event le ON cc.id = le.crop_cycle_id AND le.status != 'rejected'
LEFT JOIN sales_event se ON cc.id = se.crop_cycle_id AND se.status != 'rejected'
GROUP BY c.name
ORDER BY total_harvest_kg DESC;
