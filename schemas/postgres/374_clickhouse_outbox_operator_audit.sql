-- Operator transitions are recorded atomically with durable outbox changes.
CREATE TABLE IF NOT EXISTS clickhouse_outbox_operator_audit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    outbox_id UUID NOT NULL REFERENCES clickhouse_outbox(id),
    event_key VARCHAR(255) NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('replayed', 'resolved', 'discarded')),
    actor VARCHAR(255) NOT NULL CHECK (length(btrim(actor)) > 0),
    reason TEXT NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 2000),
    prior_attempt_count INTEGER NOT NULL CHECK (prior_attempt_count >= 0),
    payload_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_clickhouse_outbox_operator_history
    ON clickhouse_outbox_operator_audit (outbox_id, created_at);
