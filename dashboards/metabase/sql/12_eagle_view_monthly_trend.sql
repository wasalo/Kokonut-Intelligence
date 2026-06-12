-- Eagle View: Monthly Revenue Trend
-- Monthly net revenue and expense trend for the last 12 months

WITH monthly_revenue AS (
  SELECT
    DATE_TRUNC('month', sale_date) as month,
    COUNT(DISTINCT id) as sales_count,
    COALESCE(SUM(total_amount), 0) as gross_revenue,
    COALESCE(SUM(return_amount + discount_amount), 0) as returns_discounts,
    COALESCE(SUM(total_amount) - SUM(return_amount + discount_amount), 0) as net_revenue
  FROM sales_event
  WHERE status != 'rejected'
    AND sale_date >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY DATE_TRUNC('month', sale_date)
),
monthly_expenses AS (
  SELECT
    DATE_TRUNC('month', expense_date) as month,
    COALESCE(SUM(amount), 0) as period_expenses
  FROM expense_event
  WHERE status != 'rejected'
    AND expense_date >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY DATE_TRUNC('month', expense_date)
)
SELECT
  COALESCE(r.month, e.month) as month,
  COALESCE(r.sales_count, 0) as sales_count,
  COALESCE(r.gross_revenue, 0) as gross_revenue,
  COALESCE(r.returns_discounts, 0) as returns_discounts,
  COALESCE(r.net_revenue, 0) as net_revenue,
  COALESCE(e.period_expenses, 0) as period_expenses,
  COALESCE(r.net_revenue, 0) - COALESCE(e.period_expenses, 0) as period_noi
FROM monthly_revenue r
FULL JOIN monthly_expenses e ON r.month = e.month
ORDER BY month DESC;
