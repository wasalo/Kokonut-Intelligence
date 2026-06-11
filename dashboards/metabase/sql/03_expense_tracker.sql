-- Expense Tracker Dashboard
-- Shows expenses by category with direct vs shared cost breakdown

SELECT 
  ec.name as category,
  ec.is_direct,
  COUNT(ee.id) as transaction_count,
  SUM(ee.amount) as total_amount,
  AVG(ee.amount) as avg_transaction,
  MAX(ee.expense_date) as last_expense_date,
  MIN(ee.expense_date) as first_expense_date,
  CASE 
    WHEN ec.is_direct = true 
    THEN 'Direct Cost' 
    ELSE 'Shared Cost' 
  END as cost_type
FROM expense_event ee
JOIN expense_category ec ON ee.category = ec.name
WHERE ee.status != 'rejected'
GROUP BY ec.name, ec.is_direct
ORDER BY total_amount DESC;
