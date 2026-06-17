-- Location Overview Dashboard
-- Per-location KPIs: baselines vs actuals, crop cycles, revenue, losses

SELECT
  l.name as location,
  l.country,
  l.region,
  l.baseline_revenue,
  l.baseline_cost,
  l.baseline_cash_flow,
  COUNT(DISTINCT f.id) as farms,
  COUNT(DISTINCT p.id) as plots,
  COUNT(DISTINCT cc.id) as total_crop_cycles,
  COUNT(DISTINCT CASE WHEN cc.status = 'active' THEN cc.id END) as active_cycles,
  COUNT(DISTINCT CASE WHEN cc.status = 'completed' THEN cc.id END) as completed_cycles,
  COALESCE(SUM(CASE WHEN se.status IN ('verified','published') THEN se.net_amount END), 0) as actual_revenue,
  CASE WHEN l.baseline_revenue > 0
    THEN ROUND((COALESCE(SUM(CASE WHEN se.status IN ('verified','published') THEN se.net_amount END), 0) / l.baseline_revenue * 100), 1)
    ELSE NULL END as revenue_vs_baseline_pct,
  (SELECT COUNT(DISTINCT he.id) FROM harvest_event he
   JOIN crop_cycle cc2 ON he.crop_cycle_id = cc2.id
   WHERE cc2.location_id = l.id) as total_harvests,
  (SELECT COUNT(DISTINCT le.id) FROM loss_event le
   WHERE le.location_id = l.id) as total_losses,
  (SELECT COALESCE(SUM(ee.amount), 0) FROM expense_event ee
   WHERE ee.location_id = l.id AND ee.status != 'rejected') as total_expenses
FROM location l
LEFT JOIN farm f ON f.location_id = l.id
LEFT JOIN plot p ON f.id = p.farm_id
LEFT JOIN crop_cycle cc ON p.id = cc.plot_id
LEFT JOIN sales_event se ON cc.id = se.crop_cycle_id
WHERE l.status = 'active'
GROUP BY l.id, l.name, l.country, l.region,
         l.baseline_revenue, l.baseline_cost, l.baseline_cash_flow
ORDER BY actual_revenue DESC;
