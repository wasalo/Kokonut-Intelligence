-- ============================================================
-- Crop cycle NOI view
-- Single source of truth for the crop-cycle NOI formula, previously
-- duplicated in Python (services/metrics/calculators/crop_noi.py —
-- location-level aggregate) and TypeScript
-- (extensions/kokonut-hooks/src/metrics-calculator.ts — per crop cycle).
--
-- NOI = Net Revenue - Direct Crop Costs - Allocated Shared Costs
-- Net Revenue = Gross Sales - Returns - Discounts
-- ============================================================

CREATE OR REPLACE VIEW v_crop_cycle_noi AS
WITH sales AS (
    SELECT crop_cycle_id,
           SUM(total_amount) AS gross_revenue,
           SUM(return_amount + discount_amount) AS returns_discounts
    FROM sales_event
    WHERE status IN ('verified', 'published')
    GROUP BY crop_cycle_id
),
direct_costs AS (
    SELECT crop_cycle_id, SUM(amount) AS total
    FROM expense_event
    WHERE status IN ('verified', 'published')
    GROUP BY crop_cycle_id
),
shared_costs AS (
    SELECT crop_cycle_id, SUM(allocated_amount) AS total
    FROM crop_cost_allocation
    GROUP BY crop_cycle_id
),
harvest AS (
    SELECT crop_cycle_id,
           SUM(quantity) AS total_harvest,
           SUM(loss_amount) AS total_loss
    FROM harvest_event
    WHERE status IN ('verified', 'published')
    GROUP BY crop_cycle_id
)
SELECT
    cc.id AS crop_cycle_id,
    cc.location_id,
    cc.planting_date AS period_start,
    COALESCE(cc.actual_harvest_date, cc.expected_harvest_date) AS period_end,
    COALESCE(s.gross_revenue, 0) AS gross_revenue,
    COALESCE(s.returns_discounts, 0) AS returns_discounts,
    COALESCE(s.gross_revenue, 0) - COALESCE(s.returns_discounts, 0) AS net_revenue,
    COALESCE(d.total, 0) AS direct_crop_costs,
    COALESCE(sh.total, 0) AS allocated_shared_costs,
    COALESCE(d.total, 0) + COALESCE(sh.total, 0) AS total_costs,
    (COALESCE(s.gross_revenue, 0) - COALESCE(s.returns_discounts, 0))
        - (COALESCE(d.total, 0) + COALESCE(sh.total, 0)) AS noi,
    CASE
        WHEN COALESCE(s.gross_revenue, 0) - COALESCE(s.returns_discounts, 0) > 0
        THEN ((COALESCE(s.gross_revenue, 0) - COALESCE(s.returns_discounts, 0))
              - (COALESCE(d.total, 0) + COALESCE(sh.total, 0)))
             / (COALESCE(s.gross_revenue, 0) - COALESCE(s.returns_discounts, 0)) * 100
        ELSE 0
    END AS operating_margin_pct,
    CASE
        WHEN COALESCE(h.total_harvest, 0) > 0
        THEN COALESCE(h.total_loss, 0) / h.total_harvest * 100
        ELSE 0
    END AS loss_rate_pct
FROM crop_cycle cc
LEFT JOIN sales s ON s.crop_cycle_id = cc.id
LEFT JOIN direct_costs d ON d.crop_cycle_id = cc.id
LEFT JOIN shared_costs sh ON sh.crop_cycle_id = cc.id
LEFT JOIN harvest h ON h.crop_cycle_id = cc.id;

CREATE INDEX IF NOT EXISTS idx_sales_crop_cycle_status
    ON sales_event (crop_cycle_id) WHERE status IN ('verified', 'published');

CREATE INDEX IF NOT EXISTS idx_expense_crop_cycle_status
    ON expense_event (crop_cycle_id) WHERE status IN ('verified', 'published');
