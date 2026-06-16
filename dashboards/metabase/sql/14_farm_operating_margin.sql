-- Farm-Level Operating Margin — aggregates NOI across all crops per farm
-- FR4: Operating margin by farm

SELECT
    f.id AS farm_id,
    f.name AS farm_name,
    l.name AS location_name,
    COALESCE(SUM(ns.gross_revenue), 0) AS total_revenue,
    COALESCE(SUM(ns.total_costs), 0) AS total_costs,
    COALESCE(SUM(ns.noi), 0) AS total_noi,
    CASE
        WHEN COALESCE(SUM(ns.gross_revenue), 0) > 0
        THEN ROUND((SUM(ns.noi) / SUM(ns.gross_revenue) * 100)::numeric, 2)
        ELSE 0
    END AS operating_margin_pct,
    COUNT(DISTINCT ns.crop_cycle_id) AS crop_cycles
FROM farm f
JOIN location l ON f.location_id = l.id
LEFT JOIN noi_snapshot ns ON ns.location_id = l.id
GROUP BY f.id, f.name, l.name
ORDER BY total_noi DESC;
