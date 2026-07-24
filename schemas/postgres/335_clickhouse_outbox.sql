-- Durable PostgreSQL-to-ClickHouse delivery and reconciliation state.

CREATE TABLE IF NOT EXISTS clickhouse_outbox (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_key VARCHAR(255) NOT NULL UNIQUE,
    source_table VARCHAR(100) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    target_table VARCHAR(100) NOT NULL,
    columns JSONB NOT NULL,
    rows JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_owner VARCHAR(100),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT clickhouse_outbox_status CHECK (
        status IN ('pending', 'processing', 'succeeded', 'retryable', 'dead_letter', 'resolved', 'discarded')
    ),
    CONSTRAINT clickhouse_outbox_columns_array CHECK (jsonb_typeof(columns) = 'array'),
    CONSTRAINT clickhouse_outbox_rows_array CHECK (jsonb_typeof(rows) = 'array'),
    CONSTRAINT clickhouse_outbox_attempts_nonnegative CHECK (attempt_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_clickhouse_outbox_claim
    ON clickhouse_outbox (available_at, created_at)
    WHERE status IN ('pending', 'retryable');
CREATE INDEX IF NOT EXISTS idx_clickhouse_outbox_lease
    ON clickhouse_outbox (lease_expires_at)
    WHERE status = 'processing';
CREATE INDEX IF NOT EXISTS idx_clickhouse_outbox_source
    ON clickhouse_outbox (source_table, source_id);

CREATE TABLE IF NOT EXISTS clickhouse_reconciliation_run (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_table VARCHAR(100) NOT NULL,
    target_table VARCHAR(100) NOT NULL,
    cursor_key VARCHAR(255),
    rows_scanned INTEGER NOT NULL DEFAULT 0,
    missing_rows INTEGER NOT NULL DEFAULT 0,
    mismatched_rows INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT clickhouse_reconciliation_status CHECK (status IN ('running', 'completed', 'failed'))
);
