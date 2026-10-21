-- Keep every crop-cycle NOI input verified/published and location-consistent.
-- Migration 353 owns the view's output shape; this forward migration narrows its
-- inputs so lifecycle-ineligible or cross-location rows cannot affect governed
-- NOI results.

BEGIN;

CREATE OR REPLACE VIEW v_crop_cycle_noi AS
WITH sales AS (
    SELECT sales.crop_cycle_id,
           SUM(sales.total_amount) AS gross_revenue,
           SUM(sales.return_amount + sales.discount_amount) AS returns_discounts
    FROM sales_event AS sales
    JOIN crop_cycle AS cc
      ON cc.id = sales.crop_cycle_id
     AND cc.location_id = sales.location_id
    WHERE sales.status IN ('verified', 'published')
    GROUP BY sales.crop_cycle_id
),
direct_costs AS (
    SELECT expense.crop_cycle_id, SUM(expense.amount) AS total
    FROM expense_event AS expense
    JOIN crop_cycle AS cc
      ON cc.id = expense.crop_cycle_id
     AND cc.location_id = expense.location_id
    WHERE expense.status IN ('verified', 'published')
    GROUP BY expense.crop_cycle_id
),
shared_costs AS (
    SELECT ca.crop_cycle_id, SUM(ca.allocated_amount) AS total
    FROM crop_cost_allocation AS ca
    JOIN expense_event AS ee ON ee.id = ca.expense_id
    JOIN crop_cycle AS cc
      ON cc.id = ca.crop_cycle_id
     AND cc.location_id = ee.location_id
    WHERE ee.status IN ('verified', 'published')
    GROUP BY ca.crop_cycle_id
),
harvest AS (
    SELECT event.crop_cycle_id,
           SUM(event.quantity) AS total_harvest,
           SUM(event.loss_amount) AS total_loss
    FROM harvest_event AS event
    JOIN crop_cycle AS cc
      ON cc.id = event.crop_cycle_id
     AND cc.location_id = event.location_id
    WHERE event.status IN ('verified', 'published')
    GROUP BY event.crop_cycle_id
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
FROM crop_cycle AS cc
LEFT JOIN sales AS s ON s.crop_cycle_id = cc.id
LEFT JOIN direct_costs AS d ON d.crop_cycle_id = cc.id
LEFT JOIN shared_costs AS sh ON sh.crop_cycle_id = cc.id
LEFT JOIN harvest AS h ON h.crop_cycle_id = cc.id;

COMMIT;
