-- ============================================================
-- 284_competitive_advantage_integrity.sql
-- Correct current-state competitive reporting and advantage evidence gates.
-- ============================================================

ALTER TABLE strategy_advantage
    ADD COLUMN IF NOT EXISTS assessment_methodology_version VARCHAR(40),
    ADD COLUMN IF NOT EXISTS assessment_confidence VARCHAR(20)
        CHECK (assessment_confidence IS NULL OR assessment_confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    ADD COLUMN IF NOT EXISTS reassessment_due_at DATE;

ALTER TABLE strategy_advantage
    DROP CONSTRAINT IF EXISTS strategy_advantage_verified_evidence_check;
ALTER TABLE strategy_advantage
    ADD CONSTRAINT strategy_advantage_verified_evidence_check CHECK (
        status <> 'verified'
        OR (assessed_at IS NOT NULL AND assessed_by_party_id IS NOT NULL AND evidence <> '[]'::jsonb)
    ) NOT VALID;

CREATE OR REPLACE VIEW v_strategy_competitive_health AS
WITH ranked_landscapes AS (
    SELECT cl.*, ROW_NUMBER() OVER (
        PARTITION BY cl.strategy_plan_id
        ORDER BY cl.period_end DESC, cl.updated_at DESC, cl.id DESC
    ) AS recency_rank
    FROM competitive_landscape cl
    WHERE cl.status IN ('verified', 'published')
), current_landscapes AS (
    SELECT * FROM ranked_landscapes WHERE recency_rank = 1
)
SELECT sp.id AS strategy_plan_id,
       sp.scope_type,
       sp.scope_id,
       COUNT(DISTINCT cl.id) AS landscape_count,
       COUNT(DISTINCT cl.id) AS verified_landscape_count,
       COALESCE((SELECT AVG(cfo.pressure_score)
                 FROM competitive_force_observation cfo
                 WHERE cfo.landscape_id = cl.id), 0) AS average_force_pressure_score,
       COALESCE((SELECT COUNT(*)
                 FROM competitive_signal cs
                 WHERE cs.landscape_id = cl.id
                   AND cs.materiality IN ('high', 'critical')
                   AND cs.reviewed_at IS NULL), 0) AS unreviewed_material_signal_count,
       COALESCE((SELECT COUNT(*) FROM strategy_position position
                 WHERE position.strategy_plan_id = sp.id AND position.status = 'approved'), 0) AS approved_position_count,
       COALESCE((SELECT COUNT(*) FROM strategy_advantage advantage
                 WHERE advantage.strategy_plan_id = sp.id AND advantage.status = 'verified'), 0) AS verified_advantage_count,
       COALESCE((SELECT COUNT(*) FROM v_strategy_advantage_fit fit
                 WHERE fit.strategy_plan_id = sp.id AND fit.fit_status = 'unlinked'), 0) AS unlinked_advantage_count,
       COALESCE((SELECT COUNT(*) FROM v_strategy_advantage_fit fit
                 WHERE fit.strategy_plan_id = sp.id AND fit.fit_status = 'partial'), 0) AS partial_advantage_count,
       COALESCE((SELECT COUNT(*) FROM strategy_review_task srt
                 WHERE srt.strategy_plan_id = sp.id AND srt.review_type = 'competitive_change'
                   AND srt.status IN ('pending', 'in_progress', 'overdue')), 0) AS open_competitive_review_count
FROM strategy_plan sp
LEFT JOIN current_landscapes cl ON cl.strategy_plan_id = sp.id
GROUP BY sp.id, sp.scope_type, sp.scope_id, cl.id;

COMMENT ON VIEW v_strategy_competitive_health IS 'Current verified competitive landscape health for the strategy cockpit';
