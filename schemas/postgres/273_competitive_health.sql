-- ============================================================
-- 273_competitive_health.sql
-- External-position health projection for strategic cockpit use.
-- ============================================================

CREATE OR REPLACE VIEW v_strategy_competitive_health AS
SELECT sp.id AS strategy_plan_id,
       sp.scope_type,
       sp.scope_id,
       COUNT(DISTINCT cl.id) AS landscape_count,
       COUNT(DISTINCT cl.id) FILTER (WHERE cl.status IN ('verified', 'published')) AS verified_landscape_count,
       COALESCE((SELECT AVG(cfo.pressure_score) FROM competitive_force_observation cfo JOIN competitive_landscape cl2 ON cl2.id = cfo.landscape_id WHERE cl2.strategy_plan_id = sp.id AND cl2.status IN ('verified', 'published')), 0) AS average_force_pressure_score,
       COALESCE((SELECT COUNT(*) FROM competitive_signal cs JOIN competitive_landscape cl3 ON cl3.id = cs.landscape_id WHERE cl3.strategy_plan_id = sp.id AND cs.materiality IN ('high', 'critical') AND cs.reviewed_at IS NULL), 0) AS unreviewed_material_signal_count,
       COALESCE((SELECT COUNT(*) FROM strategy_position position WHERE position.strategy_plan_id = sp.id AND position.status = 'approved'), 0) AS approved_position_count,
       COALESCE((SELECT COUNT(*) FROM strategy_advantage advantage WHERE advantage.strategy_plan_id = sp.id AND advantage.status = 'verified'), 0) AS verified_advantage_count,
       COALESCE((SELECT COUNT(*) FROM v_strategy_advantage_fit fit WHERE fit.strategy_plan_id = sp.id AND fit.fit_status = 'unlinked'), 0) AS unlinked_advantage_count,
       COALESCE((SELECT COUNT(*) FROM v_strategy_advantage_fit fit WHERE fit.strategy_plan_id = sp.id AND fit.fit_status = 'partial'), 0) AS partial_advantage_count,
       COALESCE((SELECT COUNT(*) FROM strategy_review_task srt WHERE srt.strategy_plan_id = sp.id AND srt.review_type = 'competitive_change' AND srt.status IN ('pending', 'in_progress', 'overdue')), 0) AS open_competitive_review_count
FROM strategy_plan sp
LEFT JOIN competitive_landscape cl ON cl.strategy_plan_id = sp.id
GROUP BY sp.id, sp.scope_type, sp.scope_id;

COMMENT ON VIEW v_strategy_competitive_health IS 'External-position health for the strategy cockpit, separate from internal execution health';
