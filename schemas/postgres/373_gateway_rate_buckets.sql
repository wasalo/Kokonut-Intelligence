-- Shared gateway token buckets; operational state, never authorization evidence.
CREATE TABLE gateway_rate_bucket (
    caller_hash TEXT PRIMARY KEY CHECK (length(caller_hash) = 64),
    tokens DOUBLE PRECISION NOT NULL CHECK (tokens >= 0 AND tokens <= 100),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX gateway_rate_bucket_updated_idx ON gateway_rate_bucket (updated_at);
