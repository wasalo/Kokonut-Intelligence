-- Re-scan every tracked recipient once. The previous chain-wide timestamp
-- may be ahead of a slower recipient and cannot safely seed its cursor.
-- Existing attestations are protected by UID uniqueness and outbox idempotency.
-- Forward-only recovery: a rollback must retain zero cursors; restoring the
-- legacy maximum can reintroduce the skipped-history gap.
BEGIN;

UPDATE eas_indexer_cursor
   SET last_attestation_time = 0,
       updated_at = NOW()
 WHERE last_attestation_time <> 0;

COMMENT ON TABLE eas_indexer_cursor IS
    'Per-recipient EAS timestamp cursors. Migration 422 establishes a zero-watermark rescan so legacy chain-wide state cannot skip recipient history; successful record/outbox writes and cursor advances commit atomically.';

COMMIT;
