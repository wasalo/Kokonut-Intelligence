-- ============================================================
-- 278_strategy_kpi_refresh.sql
-- Live KPI refresh metadata and breach audit.
-- ============================================================

ALTER TABLE objective_kpi
    ADD COLUMN IF NOT EXISTS source_status VARCHAR(20) NOT NULL DEFAULT 'unrefreshed'
        CHECK (source_status IN ('unrefreshed', 'verified', 'missing', 'stale')),
    ADD COLUMN IF NOT EXISTS source_measured_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS source_metric_value_id UUID REFERENCES metric_value(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS variance_status VARCHAR(20) NOT NULL DEFAULT 'not_measurable'
        CHECK (variance_status IN ('on_track', 'at_risk', 'breach', 'not_measurable')),
    ADD COLUMN IF NOT EXISTS refreshed_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS strategy_kpi_refresh_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    objective_kpi_id UUID NOT NULL REFERENCES objective_kpi(id) ON DELETE CASCADE,
    metric_value_id UUID REFERENCES metric_value(id) ON DELETE SET NULL,
    previous_value NUMERIC,
    refreshed_value NUMERIC,
    variance_status VARCHAR(20) NOT NULL,
    source_status VARCHAR(20) NOT NULL,
    review_task_id UUID REFERENCES strategy_review_task(id) ON DELETE SET NULL,
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_kpi_refresh_kpi ON strategy_kpi_refresh_log(objective_kpi_id, refreshed_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_kpi_refresh_status ON strategy_kpi_refresh_log(variance_status, refreshed_at DESC);

COMMENT ON TABLE strategy_kpi_refresh_log IS 'Audit trail for live verified KPI refresh and strategy review triggers';
