-- Durable status for multi-report generation runs.

CREATE TABLE IF NOT EXISTS report_generation_run (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_scope TEXT,
    requested_by TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    total_reports INTEGER NOT NULL DEFAULT 0,
    succeeded_reports INTEGER NOT NULL DEFAULT 0,
    failed_reports INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    CONSTRAINT report_generation_run_status CHECK (status IN ('running', 'succeeded', 'partial', 'failed'))
);

CREATE TABLE IF NOT EXISTS report_generation_run_item (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES report_generation_run(id) ON DELETE CASCADE,
    report_type VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    snapshot_id UUID,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT report_generation_run_item_status CHECK (status IN ('running', 'succeeded', 'failed', 'empty')),
    UNIQUE (run_id, report_type)
);

CREATE INDEX IF NOT EXISTS idx_report_generation_run_status
    ON report_generation_run (status, started_at DESC);
