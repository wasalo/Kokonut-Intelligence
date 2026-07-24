-- ============================================================
-- Selective Disclosure
-- Tracks Merkle disclosure roots for EAS attestations.
-- ============================================================

CREATE TABLE IF NOT EXISTS disclosure_proof (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attestation_uid VARCHAR(66) NOT NULL,
    root_hash VARCHAR(66) NOT NULL,
    leaf_count INT NOT NULL,
    disclosed_fields JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(attestation_uid)
);

CREATE INDEX IF NOT EXISTS idx_dp_attestation ON disclosure_proof(attestation_uid);
