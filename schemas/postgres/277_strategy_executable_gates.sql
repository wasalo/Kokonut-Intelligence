-- ============================================================
-- 277_strategy_executable_gates.sql
-- Coherence findings for executable and measurable strategy plans.
-- ============================================================

CREATE OR REPLACE VIEW v_strategy_gate_status AS
SELECT sp.id AS strategy_plan_id,
       COUNT(DISTINCT scf.id) FILTER (WHERE scf.status = 'open' AND scf.severity IN ('critical', 'high')) AS blocking_finding_count,
       COUNT(DISTINCT sm.id) AS objective_count,
       COUNT(DISTINCT si.id) AS initiative_count,
       COUNT(DISTINCT sm.id) FILTER (WHERE sm.accountable_party_id IS NOT NULL) AS accountable_objective_count,
       COUNT(DISTINCT sm.id) FILTER (WHERE sm.objective_id IS NOT NULL AND EXISTS (SELECT 1 FROM objective_kpi ok WHERE ok.objective_id = sm.objective_id)) AS measured_objective_count,
       CASE WHEN COUNT(DISTINCT scf.id) FILTER (WHERE scf.status = 'open' AND scf.severity IN ('critical', 'high')) = 0
             AND COUNT(DISTINCT sm.id) > 0 AND COUNT(DISTINCT si.id) > 0
             AND COUNT(DISTINCT sm.id) FILTER (WHERE sm.accountable_party_id IS NOT NULL) = COUNT(DISTINCT sm.id)
            THEN 'ready' ELSE 'blocked' END AS gate_status
FROM strategy_plan sp
LEFT JOIN strategy_map sm ON sm.strategy_plan_id = sp.id
LEFT JOIN strategy_initiative si ON si.strategy_map_id = sm.id
LEFT JOIN strategy_coherence_finding scf ON scf.strategy_plan_id = sp.id
GROUP BY sp.id;

COMMENT ON VIEW v_strategy_gate_status IS 'Executable strategy approval gate status across coherence, objectives, owners, and initiatives';
