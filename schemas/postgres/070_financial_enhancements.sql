-- 070_financial_enhancements.sql
-- Financial Statement Formatter, IRR/NPV, Investment Analysis

BEGIN;

-- ============================================================================
-- ADD IRR/NPV COLUMNS TO EXISTING TABLES
-- ============================================================================

ALTER TABLE farm_launch_unit_economics ADD COLUMN IF NOT EXISTS irr_pct NUMERIC(10,4);
ALTER TABLE farm_launch_unit_economics ADD COLUMN IF NOT EXISTS npv_usd NUMERIC(18,2);
ALTER TABLE farm_launch_unit_economics ADD COLUMN IF NOT EXISTS discount_rate_pct NUMERIC(8,4) DEFAULT 8.0;
ALTER TABLE farm_launch_unit_economics ADD COLUMN IF NOT EXISTS mirr_pct NUMERIC(10,4);
ALTER TABLE farm_launch_unit_economics ADD COLUMN IF NOT EXISTS cash_flow_series JSONB;

ALTER TABLE capital_efficiency_scenario ADD COLUMN IF NOT EXISTS irr_pct NUMERIC(10,4);
ALTER TABLE capital_efficiency_scenario ADD COLUMN IF NOT EXISTS npv_usd NUMERIC(18,2);
ALTER TABLE capital_efficiency_scenario ADD COLUMN IF NOT EXISTS discount_rate_pct NUMERIC(8,4) DEFAULT 8.0;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- 1. Income Statement by period
CREATE OR REPLACE VIEW v_income_statement_period AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    COALESCE(SUM(re.amount_usd), 0) AS revenue_usd,
    COALESCE(SUM(CASE WHEN ee.is_direct = TRUE THEN ee.amount ELSE 0 END), 0) AS cost_of_goods_sold_usd,
    COALESCE(SUM(re.amount_usd), 0) - COALESCE(SUM(CASE WHEN ee.is_direct = TRUE THEN ee.amount ELSE 0 END), 0) AS gross_profit_usd,
    COALESCE(SUM(CASE WHEN ee.is_direct = FALSE THEN ee.amount ELSE 0 END), 0) AS operating_expenses_usd,
    COALESCE(SUM(re.amount_usd), 0) - COALESCE(SUM(ee.amount), 0) AS net_income_usd,
    CASE WHEN COALESCE(SUM(re.amount_usd), 0) > 0
        THEN ROUND((COALESCE(SUM(re.amount_usd), 0) - COALESCE(SUM(ee.amount), 0)) / SUM(re.amount_usd) * 100, 2)
        ELSE 0
    END AS operating_margin_pct
FROM location l
LEFT JOIN revenue_event re ON re.location_id = l.id AND re.status IN ('verified', 'published')
LEFT JOIN expense_event ee ON ee.location_id = l.id AND ee.status IN ('verified', 'published')
WHERE l.status IN ('active', 'verified', 'published')
GROUP BY l.id, l.name;

-- 2. Balance Sheet snapshot
CREATE OR REPLACE VIEW v_balance_sheet_snapshot AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    COALESCE(SUM(CASE WHEN te.flow_direction = 'inflow' THEN te.usd_value ELSE 0 END), 0) AS total_assets_usd,
    COALESCE(SUM(CASE WHEN ee.is_capex = TRUE THEN ee.amount ELSE 0 END), 0) AS fixed_assets_usd,
    COALESCE(SUM(CASE WHEN te.flow_direction = 'outflow' THEN te.usd_value ELSE 0 END), 0) AS total_liabilities_usd,
    COALESCE(SUM(re.amount_usd), 0) - COALESCE(SUM(ee.amount), 0) AS equity_usd
FROM location l
LEFT JOIN treasury_event te ON te.location_id = l.id
LEFT JOIN expense_event ee ON ee.location_id = l.id AND ee.status IN ('verified', 'published')
LEFT JOIN revenue_event re ON re.location_id = l.id AND re.status IN ('verified', 'published')
WHERE l.status IN ('active', 'verified', 'published')
GROUP BY l.id, l.name;

-- 3. Cash Flow Statement by period
CREATE OR REPLACE VIEW v_cash_flow_statement_period AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    COALESCE(SUM(re.amount_usd), 0) AS operating_revenue_usd,
    COALESCE(SUM(ee.amount), 0) AS operating_expenses_usd,
    COALESCE(SUM(re.amount_usd), 0) - COALESCE(SUM(ee.amount), 0) AS operating_cash_flow_usd,
    COALESCE(SUM(CASE WHEN ee.is_capex = TRUE THEN ee.amount ELSE 0 END), 0) AS investing_cash_flow_usd,
    COALESCE(SUM(CASE WHEN te.flow_direction = 'inflow' THEN te.usd_value ELSE 0 END), 0) AS financing_cash_flow_usd,
    COALESCE(SUM(re.amount_usd), 0) - COALESCE(SUM(ee.amount), 0)
        - COALESCE(SUM(CASE WHEN ee.is_capex = TRUE THEN ee.amount ELSE 0 END), 0)
        AS net_cash_flow_usd
FROM location l
LEFT JOIN revenue_event re ON re.location_id = l.id AND re.status IN ('verified', 'published')
LEFT JOIN expense_event ee ON ee.location_id = l.id AND ee.status IN ('verified', 'published')
LEFT JOIN treasury_event te ON te.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
GROUP BY l.id, l.name;

COMMIT;
