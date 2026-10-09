-- ============================================================
-- 254_capacity_aware_planning.sql
-- Planning projections that surface work against operating gaps.
-- ============================================================

CREATE OR REPLACE VIEW v_capacity_aware_work_queue AS
SELECT
    wi.id AS work_item_id,
    wi.organization_id,
    wi.location_id,
    wi.title,
    wi.work_type,
    wi.status,
    wi.priority,
    wi.selection_mode,
    wi.autonomy_level,
    wi.estimated_effort_hours,
    wi.allocation_status,
    wi.due_at,
    wi.sla_at,
    CASE
        WHEN wi.location_id IS NOT NULL THEN 'adelphi'
        ELSE 'internal'
    END AS inferred_scope_type,
    COALESCE(g.coverage_status, 'unmodeled') AS capacity_status,
    COALESCE(g.net_hours, NULL) AS net_capacity_hours,
    g.period_start AS capacity_period_start,
    g.period_end AS capacity_period_end,
    g.priority_rank AS demand_priority_rank
FROM work_item wi
LEFT JOIN v_operating_capacity_gap g
    ON g.work_type = wi.work_type
   AND (g.scope_id = wi.organization_id OR g.scope_id = wi.location_id)
   AND (wi.due_at IS NULL OR wi.due_at::date BETWEEN g.period_start AND g.period_end)
WHERE wi.status NOT IN ('done', 'cancelled');

CREATE OR REPLACE VIEW v_operating_portfolio_health AS
SELECT
    scope_type,
    scope_id,
    COUNT(*) AS demand_signal_count,
    COUNT(*) FILTER (WHERE coverage_status = 'gap') AS gap_count,
    COUNT(*) FILTER (WHERE coverage_status = 'thin') AS thin_count,
    SUM(required_hours) AS required_hours,
    SUM(available_hours) AS available_hours,
    SUM(net_hours) AS net_hours,
    ROUND(100.0 * COUNT(*) FILTER (WHERE coverage_status = 'covered') / NULLIF(COUNT(*), 0), 1) AS covered_pct
FROM v_operating_capacity_gap
GROUP BY scope_type, scope_id;

COMMENT ON VIEW v_capacity_aware_work_queue IS 'Non-terminal work items annotated with modeled capacity coverage';
COMMENT ON VIEW v_operating_portfolio_health IS 'Dual-scope portfolio capacity health summary';
