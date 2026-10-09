-- Tranche 2: durable remote-sensing attempts, leases, and telemetry correctness.
ALTER TABLE remote_sensing_job
    ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS lease_owner VARCHAR(150),
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_error_class VARCHAR(30),
    ADD COLUMN IF NOT EXISTS last_error TEXT;

CREATE INDEX IF NOT EXISTS idx_rs_job_claimable
    ON remote_sensing_job (status, next_run_at, lease_expires_at);

CREATE TABLE IF NOT EXISTS remote_sensing_provider_attempt (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES remote_sensing_job(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    outcome VARCHAR(30) NOT NULL CHECK (outcome IN ('success', 'no_data', 'retryable', 'non_retryable')),
    retryable BOOLEAN,
    observations INTEGER NOT NULL DEFAULT 0 CHECK (observations >= 0),
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS idx_rs_attempt_job ON remote_sensing_provider_attempt (job_id, created_at);

ALTER TABLE data_freshness_config
    DROP CONSTRAINT IF EXISTS chk_freshness_thresholds;
ALTER TABLE data_freshness_config
    ADD CONSTRAINT chk_freshness_thresholds CHECK (
        expected_interval_minutes > 0
        AND stale_threshold_minutes > 0
        AND critical_threshold_minutes >= stale_threshold_minutes
    );
