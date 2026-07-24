-- ============================================================
-- EAS Data-Stream Anchor Enhancements
-- Adds signing tracking to attestation_request and content_hash
-- dedup to data_stream_post for the governed anchor pipeline.
-- ============================================================

-- Tracking columns for the signer service
ALTER TABLE attestation_request
    ADD COLUMN IF NOT EXISTS signing_attempts INT DEFAULT 0;

ALTER TABLE attestation_request
    ADD COLUMN IF NOT EXISTS last_signing_at TIMESTAMPTZ;

ALTER TABLE attestation_request
    ADD COLUMN IF NOT EXISTS error_message TEXT;

-- Content hash for dedup on data_stream_post
ALTER TABLE data_stream_post
    ADD COLUMN IF NOT EXISTS content_hash VARCHAR(66);

-- Index for signer service polling
CREATE INDEX IF NOT EXISTS idx_ar_pending_chain
    ON attestation_request (chain, created_at)
    WHERE execution_status = 'pending';
