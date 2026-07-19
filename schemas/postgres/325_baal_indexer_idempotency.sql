-- Idempotent re-indexing for Baal governance_event rows.
-- The baal_indexer (services/ingestion/baal_indexer.py) can be re-run over the
-- same block range (e.g. after a partial failure or a backfill replay). Without
-- a uniqueness guard, repeated scans insert duplicate rows. Each Baal event is
-- emitted in exactly one transaction, so (chain, event_type, tx_hash) uniquely
-- identifies a row for this indexer. tx_hash is always populated for Baal
-- events, so the index is unconditional.

CREATE UNIQUE INDEX IF NOT EXISTS uq_governance_event_baal_source
    ON governance_event (chain, event_type, tx_hash);

