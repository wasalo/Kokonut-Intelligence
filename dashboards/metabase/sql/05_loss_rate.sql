-- Loss Rate Dashboard
-- Shows loss rates by crop and loss type with financial impact

SELECT 
  c.name as crop,
  le.loss_type,
  COUNT(le.id) as loss_events,
  SUM(le.quantity) as total_loss_kg,
  SUM(h.quantity) as total_harvest_kg,
  CASE 
    WHEN SUM(h.quantity) > 0 
    THEN ROUND(SUM(le.quantity) / SUM(h.quantity) * 100::numeric, 2)
    ELSE 0 
  END as loss_rate_pct,
  SUM(le.estimated_value) as loss_value,
  COUNT(DISTINCT le.crop_cycle_id) as affected_cycles
FROM loss_event le
JOIN crop_cycle cc ON le.crop_cycle_id = cc.id
JOIN crop c ON cc.crop_id = c.id
JOIN harvest_event h ON cc.id = h.crop_cycle_id
WHERE le.status != 'rejected'
GROUP BY c.name, le.loss_type
ORDER BY loss_rate_pct DESC;
