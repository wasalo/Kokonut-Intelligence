-- ============================================================
-- 260_strategy_execution_snapshots.sql
-- Strategic execution rollups and immutable review snapshots.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_review_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    captured_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    summary JSONB NOT NULL,
    review_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_snapshot_plan
    ON strategy_review_snapshot(strategy_plan_id, captured_at DESC);

CREATE OR REPLACE VIEW v_strategy_kernel_execution AS
SELECT
    sp.id AS strategy_plan_id,
    sp.scope_type,
    sp.scope_id,
    sp.name,
    sp.version,
    sp.status AS plan_status,
    sp.visibility,
    COUNT(DISTINCT sm.id) AS objective_count,
    COUNT(DISTINCT sm.id) FILTER (WHERE sm.accountable_party_id IS NOT NULL) AS accountable_objective_count,
    COUNT(DISTINCT sm.id) FILTER (WHERE EXISTS (SELECT 1 FROM objective_kpi ok WHERE ok.objective_id = sm.objective_id)) AS measured_objective_count,
    COUNT(DISTINCT si.id) AS initiative_count,
    COUNT(DISTINCT si.id) FILTER (WHERE si.status = 'completed') AS completed_initiative_count,
    COALESCE(ROUND(AVG(si.completion_pct), 1), 0) AS average_initiative_completion_pct,
    COUNT(DISTINCT sic.id) AS investment_case_count,
    COUNT(DISTINCT sic.id) FILTER (WHERE sic.status IN ('recommended', 'approved')) AS recommended_investment_count,
    COALESCE(ROUND(AVG(sic.composite_score), 2), 0) AS average_investment_score,
    COALESCE(sc.open_finding_count, 0) AS open_coherence_finding_count,
    COALESCE(sc.critical_count, 0) AS critical_coherence_finding_count,
    MAX(GREATEST(sm.updated_at, si.updated_at, sic.updated_at)) AS latest_execution_update
FROM strategy_plan sp
LEFT JOIN strategy_map sm ON sm.strategy_plan_id = sp.id
LEFT JOIN strategy_initiative si ON si.strategy_map_id = sm.id
LEFT JOIN strategy_investment_case sic ON sic.strategy_plan_id = sp.id
LEFT JOIN v_strategy_coherence_summary sc ON sc.strategy_plan_id = sp.id
GROUP BY sp.id, sp.scope_type, sp.scope_id, sp.name, sp.version, sp.status,
         sp.visibility, sc.open_finding_count, sc.critical_count;

COMMENT ON VIEW v_strategy_kernel_execution IS 'Integrated strategy plan execution rollup across objectives, initiatives, investments, and coherence';
COMMENT ON TABLE strategy_review_snapshot IS 'Immutable historical strategy execution state for intended-versus-realized analysis';
