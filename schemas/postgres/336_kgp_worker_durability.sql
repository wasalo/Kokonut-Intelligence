-- Durable KGP worker ownership, retries, and operator dispositions.

ALTER TABLE kgp_indexer_cursor
    ADD COLUMN IF NOT EXISTS lease_owner VARCHAR(100),
    ADD COLUMN IF NOT EXISTS lease_token UUID,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS max_retries INTEGER NOT NULL DEFAULT 8;

ALTER TABLE kgp_chain_event
    ADD COLUMN IF NOT EXISTS processing_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dead_lettered_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS disposition VARCHAR(20),
    ADD COLUMN IF NOT EXISTS disposition_reason TEXT;

ALTER TABLE kgp_chain_event
    DROP CONSTRAINT IF EXISTS kgp_chain_event_disposition_check,
    ADD CONSTRAINT kgp_chain_event_disposition_check
        CHECK (disposition IS NULL OR disposition IN ('resolved', 'discarded'));

CREATE INDEX IF NOT EXISTS idx_kgp_chain_event_retry
    ON kgp_chain_event (deployment_id, next_retry_at)
    WHERE processing_status = 'dead_letter';
