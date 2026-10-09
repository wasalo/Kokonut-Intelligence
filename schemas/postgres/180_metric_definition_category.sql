-- ============================================================
-- 180_metric_definition_category.sql - Flow taxonomy for metrics (VSM)
-- ============================================================
-- Adds a `category` column to metric_definition so flow / lead-time /
-- throughput / quality metrics can be grouped and surfaced distinctly
-- from financial or ecological metrics. Nullable + indexed; existing
-- rows are left uncategorized (retained as-is).

ALTER TABLE metric_definition ADD COLUMN IF NOT EXISTS category VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_metric_definition_category ON metric_definition(category);
