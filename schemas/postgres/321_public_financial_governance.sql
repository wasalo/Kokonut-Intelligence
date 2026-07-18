-- ============================================================
-- 321_public_financial_governance.sql
-- Keep public financial aggregates limited to governed records.
-- ============================================================

CREATE OR REPLACE VIEW v_public_cross_farm_portfolio AS
SELECT
    cfp.portfolio_name,
    cfp.last_computed_at,
    (
        SELECT COUNT(DISTINCT f.id)::INTEGER
        FROM farm f
        JOIN farm_registry_record fr ON fr.location_id = f.location_id
        WHERE f.status = 'active'
          AND fr.status IN ('verified', 'published')
    ) AS active_farms,
    (
        SELECT COALESCE(SUM(re.amount_usd), 0)
        FROM revenue_event re
        JOIN farm_registry_record fr ON fr.location_id = re.location_id
        WHERE re.status IN ('verified', 'published')
          AND fr.status IN ('verified', 'published')
    ) AS total_network_revenue
FROM cross_farm_portfolio cfp
WHERE EXISTS (
    SELECT 1
    FROM farm_registry_record fr
    WHERE fr.status IN ('verified', 'published')
)
ORDER BY cfp.last_computed_at DESC
LIMIT 1;

COMMENT ON VIEW v_public_cross_farm_portfolio IS
    'Public portfolio summary using only verified or published registry and revenue records.';
