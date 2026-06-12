-- Crop NOI Dashboard
-- Shows Net Operating Income by crop with revenue, costs, and margins

SELECT 
  c.name as crop,
  cc.season,
  cc.planting_date,
  cc.expected_harvest_date,
  COALESCE(SUM(se.total_amount), 0) as gross_revenue,
  COALESCE(SUM(se.return_amount + se.discount_amount), 0) as returns_discounts,
  COALESCE(SUM(se.total_amount) - SUM(se.return_amount + se.discount_amount), 0) as net_revenue,
  COALESCE(SUM(ee.amount), 0) as direct_costs,
  CASE 
    WHEN SUM(se.total_amount) - SUM(se.return_amount + se.discount_amount) > 0 
    THEN ROUND(
      (SUM(se.total_amount) - SUM(se.return_amount + se.discount_amount) - SUM(ee.amount)) / 
      NULLIF(SUM(se.total_amount) - SUM(se.return_amount + se.discount_amount), 0) * 100::numeric, 
      2
    )
    ELSE 0 
  END as operating_margin_pct,
  COUNT(DISTINCT h.id) as harvest_count,
  COALESCE(SUM(h.quantity), 0) as total_harvest_kg
FROM crop_cycle cc
JOIN crop c ON cc.crop_id = c.id
LEFT JOIN sales_event se ON cc.id = se.crop_cycle_id
LEFT JOIN expense_event ee ON cc.id = ee.crop_cycle_id
LEFT JOIN harvest_event h ON cc.id = h.crop_cycle_id
WHERE cc.status = 'active'
GROUP BY c.name, cc.season, cc.planting_date, cc.expected_harvest_date
ORDER BY operating_margin_pct DESC;
