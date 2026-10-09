-- ============================================================
-- Attestation request anchor fields
-- Keeps the governed anchor queue aligned with its signer service.
-- ============================================================

ALTER TABLE attestation_request
    ADD COLUMN IF NOT EXISTS schema_name VARCHAR(100);

ALTER TABLE attestation_request
    ADD COLUMN IF NOT EXISTS block_number BIGINT;

CREATE INDEX IF NOT EXISTS idx_attestation_request_schema_name
    ON attestation_request (schema_name);
