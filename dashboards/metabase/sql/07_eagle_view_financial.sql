-- Eagle View: Financial Summary
-- Revenue, expenses, NOI, and operating margin across all farms

SELECT
  COALESCE(SUM(se.total_amount), 0) as gross_revenue,
  COALESCE(SUM(se.return_amount + se.discount_amount), 0) as returns_discounts,
  COALESCE(SUM(se.total_amount) - SUM(se.return_amount + se.discount_amount), 0) as net_revenue,
  COALESCE(SUM(ee.amount), 0) as total_expenses,
  COALESCE(SUM(se.total_amount) - SUM(se.return_amount + se.discount_amount), 0) 
    - COALESCE(SUM(ee.amount), 0) as noi,
  CASE 
    WHEN SUM(se.total_amount) - SUM(se.return_amount + se.discount_amount) > 0 
    THEN ROUND(
      (SUM(se.total_amount) - SUM(se.return_amount + se.discount_amount) - SUM(ee.amount)) / 
      NULLIF(SUM(se.total_amount) - SUM(se.return_amount + se.discount_amount), 0) * 100::numeric, 
      2
    )
    ELSE 0 
  END as operating_margin_pct,
  (SELECT COUNT(*) FROM sales_event WHERE status != 'rejected') as total_sales,
  (SELECT COUNT(*) FROM expense_event WHERE status != 'rejected') as total_expense_records
FROM sales_event se
LEFT JOIN expense_event ee ON se.crop_cycle_id = ee.crop_cycle_id
WHERE se.status != 'rejected';
