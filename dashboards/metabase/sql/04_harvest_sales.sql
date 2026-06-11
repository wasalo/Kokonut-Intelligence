-- Harvest & Sales Dashboard
-- Shows monthly harvest volumes and sales revenue by crop

SELECT 
  DATE_TRUNC('month', h.harvest_date) as month,
  c.name as crop,
  COUNT(h.id) as harvest_count,
  SUM(h.quantity) as total_harvest_kg,
  COUNT(DISTINCT se.id) as sales_count,
  SUM(se.total_amount) as total_sales,
  AVG(se.price_per_unit) as avg_price_per_kg,
  SUM(h.quantity) * AVG(se.price_per_unit) as potential_revenue
FROM harvest_event h
JOIN crop_cycle cc ON h.crop_cycle_id = cc.id
JOIN crop c ON cc.crop_id = c.id
LEFT JOIN sales_event se ON cc.id = se.crop_cycle_id 
  AND se.sale_date >= h.harvest_date
WHERE h.status != 'rejected'
GROUP BY DATE_TRUNC('month', h.harvest_date), c.name
ORDER BY month DESC, total_harvest_kg DESC;
