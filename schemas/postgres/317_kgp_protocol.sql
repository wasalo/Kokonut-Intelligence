-- ============================================================
-- 317_kgp_protocol.sql
-- Canonical PostgreSQL ledger and durable projection state for KGP.
-- ============================================================

CREATE TABLE IF NOT EXISTS kgp_protocol_deployment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_key VARCHAR(100) NOT NULL UNIQUE,
    chain_id INTEGER NOT NULL CHECK (chain_id IN (100, 10200)),
    network_name VARCHAR(50) NOT NULL,
    proxy_address VARCHAR(42) NOT NULL,
    implementation_address VARCHAR(42) NOT NULL,
    contract_version VARCHAR(50) NOT NULL,
    deployment_tx_hash VARCHAR(66),
    deployment_block_number BIGINT,
    upgrade_authority VARCHAR(42),
    status VARCHAR(50) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'active', 'paused', 'deprecated')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (proxy_address ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (implementation_address ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (upgrade_authority IS NULL OR upgrade_authority ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (deployment_tx_hash IS NULL OR deployment_tx_hash ~ '^0x[0-9a-fA-F]{64}$')
);

CREATE INDEX IF NOT EXISTS idx_kgp_deployment_chain
    ON kgp_protocol_deployment(chain_id, status);

CREATE TABLE IF NOT EXISTS guild_reputation_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id UUID NOT NULL REFERENCES kokonut_guild(id),
    contributor_id UUID REFERENCES guild_contributor(id),
    contributor_wallet VARCHAR(42) NOT NULL,
    domain_id BIGINT NOT NULL CHECK (domain_id >= 0),
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('award', 'reversal')),
    settlement_method VARCHAR(20) NOT NULL DEFAULT 'automatic'
        CHECK (settlement_method IN ('automatic', 'claim')),
    settlement_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (settlement_status IN ('pending', 'submitted', 'settled', 'reconciled', 'failed', 'reversed')),
    review_status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft', 'submitted', 'verified', 'published', 'rejected')),
    amount NUMERIC(30, 6) NOT NULL CHECK (amount > 0),
    epoch BIGINT NOT NULL CHECK (epoch >= 0),
    evidence_hash VARCHAR(66),
    evidence_cid TEXT,
    ledger_record_hash VARCHAR(66) NOT NULL,
    calculation_version VARCHAR(100) NOT NULL,
    award_id VARCHAR(66),
    reversal_id VARCHAR(66),
    reversal_of_id UUID REFERENCES guild_reputation_event(id),
    reason_hash VARCHAR(66),
    contract_deployment_id UUID REFERENCES kgp_protocol_deployment(id),
    transaction_hash VARCHAR(66),
    block_number BIGINT,
    log_index INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    settled_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (contributor_wallet ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (evidence_hash IS NULL OR evidence_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (ledger_record_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (award_id IS NULL OR award_id ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (reversal_id IS NULL OR reversal_id ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (reason_hash IS NULL OR reason_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (transaction_hash IS NULL OR transaction_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (event_type = 'award' OR reversal_of_id IS NOT NULL),
    CHECK (event_type = 'reversal' OR reversal_of_id IS NULL),
    CHECK (event_type = 'reversal' OR reason_hash IS NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_guild_reputation_event_award_id
    ON guild_reputation_event(award_id)
    WHERE award_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_guild_reputation_event_reversal_id
    ON guild_reputation_event(reversal_id)
    WHERE reversal_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_guild_reputation_event_chain_log
    ON guild_reputation_event(contract_deployment_id, transaction_hash, log_index)
    WHERE contract_deployment_id IS NOT NULL
      AND transaction_hash IS NOT NULL
      AND log_index IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_guild_reputation_event_balance
    ON guild_reputation_event(guild_id, domain_id, contributor_wallet, review_status);
CREATE INDEX IF NOT EXISTS idx_guild_reputation_event_settlement
    ON guild_reputation_event(settlement_status, created_at);
CREATE INDEX IF NOT EXISTS idx_guild_reputation_event_reversal
    ON guild_reputation_event(reversal_of_id);

CREATE TABLE IF NOT EXISTS kgp_claim (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reputation_event_id UUID NOT NULL UNIQUE REFERENCES guild_reputation_event(id),
    award_id VARCHAR(66) NOT NULL UNIQUE,
    contributor_wallet VARCHAR(42) NOT NULL,
    voucher_hash VARCHAR(66) NOT NULL UNIQUE,
    nonce NUMERIC(78, 0) NOT NULL CHECK (nonce >= 0),
    deadline TIMESTAMPTZ NOT NULL,
    claim_status VARCHAR(30) NOT NULL DEFAULT 'issued'
        CHECK (claim_status IN ('issued', 'submitted', 'claimed', 'expired', 'rejected')),
    signer_wallet VARCHAR(42) NOT NULL,
    transaction_hash VARCHAR(66),
    block_number BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (award_id ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (contributor_wallet ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (voucher_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (signer_wallet ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (transaction_hash IS NULL OR transaction_hash ~ '^0x[0-9a-fA-F]{64}$')
);

CREATE INDEX IF NOT EXISTS idx_kgp_claim_status
    ON kgp_claim(claim_status, deadline);

CREATE TABLE IF NOT EXISTS kgp_chain_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_id UUID NOT NULL REFERENCES kgp_protocol_deployment(id),
    chain_id INTEGER NOT NULL,
    block_number BIGINT NOT NULL CHECK (block_number >= 0),
    block_hash VARCHAR(66),
    transaction_hash VARCHAR(66) NOT NULL,
    log_index INTEGER NOT NULL CHECK (log_index >= 0),
    contract_address VARCHAR(42) NOT NULL,
    event_signature VARCHAR(66) NOT NULL,
    event_name VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    processing_status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processed', 'rejected', 'dead_letter')),
    processing_error TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    UNIQUE(deployment_id, transaction_hash, log_index),
    CHECK (block_hash IS NULL OR block_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (transaction_hash ~ '^0x[0-9a-fA-F]{64}$'),
    CHECK (contract_address ~ '^0x[0-9a-fA-F]{40}$'),
    CHECK (event_signature ~ '^0x[0-9a-fA-F]{64}$')
);

CREATE INDEX IF NOT EXISTS idx_kgp_chain_event_processing
    ON kgp_chain_event(deployment_id, processing_status, block_number, log_index);

CREATE TABLE IF NOT EXISTS kgp_indexer_cursor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_id UUID NOT NULL UNIQUE REFERENCES kgp_protocol_deployment(id),
    next_block BIGINT NOT NULL DEFAULT 0 CHECK (next_block >= 0),
    confirmed_block BIGINT NOT NULL DEFAULT 0 CHECK (confirmed_block >= 0),
    last_block_hash VARCHAR(66),
    status VARCHAR(30) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'reorg', 'failed')),
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (confirmed_block <= next_block),
    CHECK (last_block_hash IS NULL OR last_block_hash ~ '^0x[0-9a-fA-F]{64}$')
);

CREATE OR REPLACE VIEW v_kgp_canonical_balance AS
SELECT
    event.guild_id,
    event.domain_id,
    event.contributor_id,
    event.contributor_wallet,
    SUM(CASE WHEN event.event_type = 'award' THEN event.amount ELSE -event.amount END) AS kgp_balance,
    COUNT(*) AS event_count,
    MAX(event.updated_at) AS last_event_at
FROM guild_reputation_event event
WHERE event.review_status IN ('verified', 'published')
  AND event.settlement_status IN ('pending', 'submitted', 'settled', 'reconciled', 'reversed')
GROUP BY event.guild_id, event.domain_id, event.contributor_id, event.contributor_wallet;

COMMENT ON TABLE guild_reputation_event IS
    'Canonical append-only KGP award and reversal ledger; the contract is an auditable projection.';
COMMENT ON TABLE kgp_claim IS
    'EIP-712 claim vouchers and settlement status for canonical KGP reputation events.';
COMMENT ON VIEW v_kgp_canonical_balance IS
    'Canonical PostgreSQL KGP balance derived from governed award and reversal events.';
