-- ============================================================
-- 354_safe_treasury_accounts.sql — SAFE smart account registry (KI-12)
-- ============================================================
-- Tracks SAFE accounts used by Kokonut: the Core Team SAFE, the DAO
-- Treasury SAFE, and per-farm sidecar SAFEs provisioned via the official
-- SAFE Factory (Phase C). Chain-agnostic: each account names its chain.
--
-- safe_account rows are created in 'draft' by agents (proposal), moved to
-- 'verified' by human approval, and 'published' once the SAFE is confirmed
-- on-chain. The governed lifecycle mirrors every other KI record.
--
-- safe_transaction indexes observed SAFE multisig transactions for
-- reporting/evidence (read from the SAFE Transaction Service API).

CREATE TABLE IF NOT EXISTS safe_account (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    address VARCHAR(64) NOT NULL,                 -- SAFE address (lowercase)
    chain VARCHAR(50) NOT NULL DEFAULT 'gnosis',  -- gnosis, celo, mainnet, ...
    account_role VARCHAR(50) NOT NULL,            -- core_team, dao_treasury, farm, other
    location_id UUID REFERENCES location(id) ON DELETE SET NULL, -- farm SAFEs
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    name VARCHAR(255),
    threshold INTEGER NOT NULL DEFAULT 1,
    owners TEXT[] NOT NULL DEFAULT '{}',
    modules TEXT[] NOT NULL DEFAULT '{}',
    guard VARCHAR(64),
    version VARCHAR(50),
    nonce BIGINT DEFAULT 0,
    provisioning_status VARCHAR(50) DEFAULT 'registered', -- proposed, approved, deployed, active, archived
    status VARCHAR(50) DEFAULT 'draft',           -- draft, submitted, verified, published, rejected
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100) DEFAULT 'safe_transaction_service',
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    CONSTRAINT uq_safe_account_address_chain UNIQUE (address, chain)
);

CREATE INDEX IF NOT EXISTS idx_safe_account_address ON safe_account(address);
CREATE INDEX IF NOT EXISTS idx_safe_account_chain ON safe_account(chain);
CREATE INDEX IF NOT EXISTS idx_safe_account_role ON safe_account(account_role);
CREATE INDEX IF NOT EXISTS idx_safe_account_location ON safe_account(location_id);
CREATE INDEX IF NOT EXISTS idx_safe_account_status ON safe_account(status);

ALTER TABLE safe_account DROP CONSTRAINT IF EXISTS chk_safe_account_status;
ALTER TABLE safe_account ADD CONSTRAINT chk_safe_account_status CHECK (
    status IN ('draft', 'submitted', 'verified', 'published', 'rejected')
);

ALTER TABLE safe_account DROP CONSTRAINT IF EXISTS chk_safe_account_role;
ALTER TABLE safe_account ADD CONSTRAINT chk_safe_account_role CHECK (
    account_role IN ('core_team', 'dao_treasury', 'farm', 'other')
);

ALTER TABLE safe_account DROP CONSTRAINT IF EXISTS chk_safe_account_provisioning;
ALTER TABLE safe_account ADD CONSTRAINT chk_safe_account_provisioning CHECK (
    provisioning_status IN ('proposed', 'approved', 'deployed', 'active', 'archived')
);

ALTER TABLE safe_account DROP CONSTRAINT IF EXISTS chk_safe_account_values;
ALTER TABLE safe_account ADD CONSTRAINT chk_safe_account_values CHECK (
    threshold >= 1
    AND cardinality(owners) >= threshold
);

CREATE TABLE IF NOT EXISTS safe_transaction (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    safe_account_id UUID NOT NULL REFERENCES safe_account(id) ON DELETE RESTRICT,
    safe_tx_hash VARCHAR(128) NOT NULL,
    nonce BIGINT DEFAULT 0,
    to_address VARCHAR(64),
    value TEXT DEFAULT '0',
    data TEXT,
    proposer VARCHAR(64),
    confirmations INTEGER DEFAULT 0,
    confirmations_required INTEGER,
    executed BOOLEAN DEFAULT FALSE,
    submission_date TIMESTAMPTZ,
    execution_date TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'draft',           -- draft, submitted, verified, published, rejected
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100) DEFAULT 'safe_transaction_service',
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    CONSTRAINT uq_safe_tx_hash UNIQUE (safe_tx_hash)
);

CREATE INDEX IF NOT EXISTS idx_safe_tx_account ON safe_transaction(safe_account_id);
CREATE INDEX IF NOT EXISTS idx_safe_tx_hash ON safe_transaction(safe_tx_hash);
CREATE INDEX IF NOT EXISTS idx_safe_tx_nonce ON safe_transaction(nonce);
CREATE INDEX IF NOT EXISTS idx_safe_tx_status ON safe_transaction(status);
CREATE INDEX IF NOT EXISTS idx_safe_tx_executed ON safe_transaction(executed);

ALTER TABLE safe_transaction DROP CONSTRAINT IF EXISTS chk_safe_tx_status;
ALTER TABLE safe_transaction ADD CONSTRAINT chk_safe_tx_status CHECK (
    status IN ('draft', 'submitted', 'verified', 'published', 'rejected')
);

-- Seed the two canonical Kokonut SAFEs (Gnosis, verified 2026-08-29).
-- Idempotent: ON CONFLICT on (address, chain) does nothing on re-run.
INSERT INTO safe_account (address, chain, account_role, name, threshold, owners, version, nonce, provisioning_status, status)
VALUES
    ('0x03779b674cbcbfc0b801c4cac9dfac8aacbbd5c5', 'gnosis', 'core_team',
     'Kokonut Core Team SAFE', 2,
     ARRAY[
        '0xf7e75e58dfa8ce8f278444523d8564992f5e5322',
        '0x535d64eb74a24883944c9a44c02a2733f929bfff',
        '0x0ea26051f7657d59418da186137141cea90d0652'
     ],
     '1.4.1+L2', 7, 'active', 'published'),
    ('0xeb55b75328a8dffd45bbf34b7e7efc431a179085', 'gnosis', 'dao_treasury',
     'Kokonut DAO Treasury SAFE (Baal-owned)', 1,
     ARRAY['0x8977c56e979f0d8b76afb5ad85549acd2e96422d'],
     '1.3.0', 0, 'active', 'published')
ON CONFLICT (address, chain) DO NOTHING;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('safe-treasury-accounts-v1', 'SAFE smart account registry + transaction index (KI-12)', 'schema 354')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
