-- ARKIV Parity: Time-scoped data, batch contract tracking, marketplace fees

-- ============================================================
-- Time-scoped data: expires_at on governed records
-- ============================================================
ALTER TABLE data_stream_post ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE impact_claim ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE attestation_record ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE report_snapshot ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE carbon_credit ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE credit_retirement ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- Index for efficient expiration queries
CREATE INDEX IF NOT EXISTS idx_dsp_expires ON data_stream_post(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ic_expires ON impact_claim(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ar_expires ON attestation_record(expires_at) WHERE expires_at IS NOT NULL;

-- ============================================================
-- Batch contract tracking (prevents double-minting)
-- ============================================================
-- credit_batch_contract already exists in 111_ecocredit_enhancements.sql
-- Add origin_tx_index for double-mint prevention
CREATE TABLE IF NOT EXISTS origin_tx_index (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_class_id UUID NOT NULL REFERENCES credit_class(id),
    origin_tx_id VARCHAR(255) NOT NULL,
    origin_tx_source VARCHAR(100) NOT NULL,
    credit_batch_id UUID REFERENCES credit_batch(id),
    indexed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(credit_class_id, origin_tx_id, origin_tx_source)
);

CREATE INDEX idx_oti_class ON origin_tx_index(credit_class_id);
CREATE INDEX idx_oti_tx ON origin_tx_index(origin_tx_id);

-- ============================================================
-- Marketplace fee tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS marketplace_fee (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_type VARCHAR(50) NOT NULL,
    transaction_id UUID NOT NULL,
    buyer_fee NUMERIC(18,8) DEFAULT 0,
    seller_fee NUMERIC(18,8) DEFAULT 0,
    total_fee NUMERIC(18,8) DEFAULT 0,
    fee_denom VARCHAR(50) NOT NULL,
    fee_pool_address VARCHAR(42),
    status VARCHAR(50) DEFAULT 'pending',
    distributed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mf_transaction ON marketplace_fee(transaction_type, transaction_id);
CREATE INDEX idx_mf_status ON marketplace_fee(status);

-- Fee distribution log
CREATE TABLE IF NOT EXISTS marketplace_fee_distribution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fee_id UUID NOT NULL REFERENCES marketplace_fee(id) ON DELETE CASCADE,
    recipient_address VARCHAR(42) NOT NULL,
    amount NUMERIC(18,8) NOT NULL,
    denom VARCHAR(50) NOT NULL,
    tx_hash VARCHAR(66),
    distributed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mfd_fee ON marketplace_fee_distribution(fee_id);
