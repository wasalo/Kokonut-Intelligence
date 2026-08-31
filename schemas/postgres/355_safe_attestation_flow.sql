-- ============================================================
-- 355_safe_attestation_flow.sql — SAFE-proposed attestations (KI-14 D2)
-- ============================================================
-- The signer service can propose EAS attestation calls to the Core Team
-- SAFE (Celo) instead of sending with the local private key. Track the
-- SAFE proposal so reconciliation can mark requests executed once humans
-- confirm on the SAFE.

ALTER TABLE attestation_request
    ADD COLUMN IF NOT EXISTS safe_tx_hash VARCHAR(66);
ALTER TABLE attestation_request
    ADD COLUMN IF NOT EXISTS proposal_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE attestation_request
    ADD COLUMN IF NOT EXISTS safe_chain VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_attestation_request_safe_tx
    ON attestation_request(safe_tx_hash);

ALTER TABLE attestation_request DROP CONSTRAINT IF EXISTS chk_attestation_request_proposal;
ALTER TABLE attestation_request ADD CONSTRAINT chk_attestation_request_proposal CHECK (
    proposal_status IN ('pending', 'proposed', 'confirmed', 'executed', 'failed', 'cancelled')
);

INSERT INTO schema_version (version, description, applied_by)
VALUES ('safe-attestation-flow-v1', 'SAFE-proposed attestation tracking columns (KI-14 D2)', 'schema 355')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
