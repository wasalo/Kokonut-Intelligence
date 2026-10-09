-- ============================================================
-- 184_process_control.sql - SPC / process-control KPIs (BPM Optimize)
-- ============================================================
-- Stores time-series process KPI snapshots (for control charts) and
-- Critical-To-Quality (CTQ) definitions. process_control.py computes
-- control limits and flags out-of-control points. process_ctq is
-- org-authored; no rows are seeded here (targets are governance-owned).

CREATE TABLE IF NOT EXISTS process_kpi_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    metric VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    period VARCHAR(40) DEFAULT 'all',
    source_ref VARCHAR(200),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pks_entity_metric ON process_kpi_snapshot(entity_type, metric, captured_at);

CREATE TABLE IF NOT EXISTS process_ctq (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    process VARCHAR(100) NOT NULL,
    ctq_name VARCHAR(100) NOT NULL,
    target DOUBLE PRECISION,
    unit VARCHAR(40),
    upper_spec DOUBLE PRECISION,
    lower_spec DOUBLE PRECISION,
    source_ref VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (process, ctq_name)
);
