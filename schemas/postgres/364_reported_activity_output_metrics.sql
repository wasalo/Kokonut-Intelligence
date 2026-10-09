-- ============================================================
-- 364_reported_activity_output_metrics.sql
-- Preserve source-reported output indicators without conflating them with
-- governed metric definitions or calculator-produced metric values.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS farm_activity_reported_metric (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    indicator_label TEXT NOT NULL CHECK (BTRIM(indicator_label) <> ''),
    reported_value NUMERIC(15,4) NOT NULL,
    reported_unit TEXT,
    period_start DATE,
    period_end DATE,
    reported_description TEXT,
    source_system TEXT NOT NULL CHECK (BTRIM(source_system) <> ''),
    source_database_id BIGINT NOT NULL,
    source_table_id BIGINT NOT NULL,
    source_row_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_farm_activity_reported_metric_source_identity UNIQUE (
        source_system, source_database_id, source_table_id, source_row_id
    ),
    CONSTRAINT chk_farm_activity_reported_metric_period CHECK (
        period_start IS NULL OR period_end IS NULL OR period_end >= period_start
    )
);

CREATE INDEX IF NOT EXISTS idx_farm_activity_reported_metric_indicator
    ON farm_activity_reported_metric(indicator_label);

CREATE TABLE IF NOT EXISTS farm_activity_reported_metric_output (
    reported_metric_id UUID NOT NULL
        REFERENCES farm_activity_reported_metric(id) ON DELETE CASCADE,
    output_id UUID NOT NULL
        REFERENCES farm_activity_output(id) ON DELETE RESTRICT,
    source_system TEXT NOT NULL CHECK (BTRIM(source_system) <> ''),
    source_database_id BIGINT NOT NULL,
    source_table_id BIGINT NOT NULL,
    source_field_id BIGINT NOT NULL,
    source_row_id BIGINT NOT NULL,
    source_related_table_id BIGINT NOT NULL,
    source_related_row_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (reported_metric_id, output_id),
    CONSTRAINT uq_farm_activity_reported_metric_output_source_edge UNIQUE (
        source_system, source_database_id, source_table_id, source_field_id,
        source_row_id, source_related_table_id, source_related_row_id
    )
);

CREATE INDEX IF NOT EXISTS idx_farm_activity_reported_metric_output_output
    ON farm_activity_reported_metric_output(output_id);

COMMENT ON TABLE farm_activity_reported_metric IS
    'Unverified source-reported activity-output indicators; not governed metric definitions or metric values and not eligible for verified/public metric views.';
COMMENT ON COLUMN farm_activity_reported_metric.indicator_label IS
    'Source-reported indicator label, not a canonical metric_definition key.';
COMMENT ON COLUMN farm_activity_reported_metric.reported_value IS
    'Numeric value as reported by the source; not computed or verified.';
COMMENT ON COLUMN farm_activity_reported_metric.reported_unit IS
    'Reported unit when source-backed; NULL means unspecified, never an inferred default.';
COMMENT ON COLUMN farm_activity_reported_metric.period_start IS
    'Measurement period start when source-backed; NULL means unspecified.';
COMMENT ON COLUMN farm_activity_reported_metric.period_end IS
    'Measurement period end when source-backed; NULL means unspecified.';
COMMENT ON COLUMN farm_activity_reported_metric.reported_description IS
    'Source-reported description; does not establish proof or formal impact evidence.';
COMMENT ON TABLE farm_activity_reported_metric_output IS
    'Typed many-to-many link from unverified reported metrics to activity outputs, with source-edge identity for idempotent reconciliation.';

COMMIT;
