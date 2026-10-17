-- Migration 423: record canonical Gnosis event-log identities in the same
-- transaction as their PostgreSQL projections, outbox rows, and block cursor.
-- Existing rows are intentionally not backfilled: legacy tables do not retain
-- log_index/block_hash, so historical replay still requires reconciliation.
BEGIN;

CREATE TABLE IF NOT EXISTS public.gnosis_event_log_receipt (
    chain VARCHAR(50) NOT NULL,
    transaction_hash VARCHAR(66) NOT NULL
        CHECK (transaction_hash ~ '^0x[0-9a-f]{64}$'),
    log_index BIGINT NOT NULL CHECK (log_index >= 0),
    block_number BIGINT NOT NULL CHECK (block_number >= 0),
    block_hash VARCHAR(66) NOT NULL
        CHECK (block_hash ~ '^0x[0-9a-f]{64}$'),
    event_name VARCHAR(100) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chain, transaction_hash, log_index)
);

CREATE INDEX IF NOT EXISTS idx_gnosis_event_log_receipt_block
    ON public.gnosis_event_log_receipt (chain, block_number);

COMMENT ON TABLE public.gnosis_event_log_receipt IS
    'Idempotency receipts for Gnosis DAO event logs first processed with migration 423. Receipt, event projections, outbox intents, and block checkpoint must commit together. A reused log identity with a different block hash fails closed; it does not perform automatic reorg rollback. Historical events are not backfilled because prior projections do not retain log_index or block_hash.';

COMMIT;
