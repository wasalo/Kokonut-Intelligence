-- ============================================================
-- 293_sequential_gate_integrity.sql
-- Typed scale thresholds and enforceable solution gate evaluations.
-- ============================================================

ALTER TABLE solution_scale_gate
    ADD COLUMN IF NOT EXISTS metric_key VARCHAR(120),
    ADD COLUMN IF NOT EXISTS comparison_operator VARCHAR(10)
        CHECK (comparison_operator IS NULL OR comparison_operator IN ('lt', 'lte', 'eq', 'gte', 'gt')),
    ADD COLUMN IF NOT EXISTS threshold_numeric NUMERIC,
    ADD COLUMN IF NOT EXISTS unit VARCHAR(50),
    ADD COLUMN IF NOT EXISTS minimum_sample INTEGER
        CHECK (minimum_sample IS NULL OR minimum_sample > 0);

ALTER TABLE solution_stage_gate
    ADD COLUMN IF NOT EXISTS minimum_evaluation_count INTEGER NOT NULL DEFAULT 1
        CHECK (minimum_evaluation_count > 0);

COMMENT ON COLUMN solution_scale_gate.threshold IS 'Human-readable threshold explanation; typed comparisons use metric_key, comparison_operator, threshold_numeric, and unit';
COMMENT ON COLUMN solution_scale_gate.threshold_numeric IS 'Machine-comparable threshold for a scale gate';
