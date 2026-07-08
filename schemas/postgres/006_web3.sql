-- ============================================================
-- 006_web3.sql — Web3 and engagement facts
-- ============================================================

-- Wallet profiles
CREATE TABLE IF NOT EXISTS wallet_profile (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    address VARCHAR(42) NOT NULL CHECK (address ~ '^0x[0-9a-fA-F]{40}$'),
    chain VARCHAR(50) NOT NULL, -- ethereum, optimism, base, arbitrum
    chain_id INTEGER,
    role VARCHAR(100), -- treasury, operations, rewards, deployer, user, team, community
    owner_type VARCHAR(100), -- farm, location, protocol, user, dao, team
    owner_id UUID,
    label VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    first_seen_date DATE,
    last_active_date DATE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wallet_address_chain ON wallet_profile(address, chain);
CREATE INDEX IF NOT EXISTS idx_wallet_role ON wallet_profile(role);
CREATE INDEX IF NOT EXISTS idx_wallet_owner ON wallet_profile(owner_type, owner_id);

-- Protocols / Digital Legos
CREATE TABLE IF NOT EXISTS protocol (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    chain VARCHAR(50) NOT NULL,
    contract_address VARCHAR(42),
    protocol_type VARCHAR(100), -- defi, nft, dao, attestation, identity, storage, oracle, other
    category VARCHAR(100), -- lending, dex, staking, governance, nft_marketplace, other
    website VARCHAR(500),
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Wallet activity events
CREATE TABLE IF NOT EXISTS wallet_activity_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_id UUID NOT NULL REFERENCES wallet_profile(id) ON DELETE RESTRICT,
    chain VARCHAR(50) NOT NULL,
    tx_hash VARCHAR(66) NOT NULL,
    block_number BIGINT,
    block_timestamp TIMESTAMPTZ,
    activity_type VARCHAR(100), -- transfer, swap, stake, unstake, deposit, withdraw, vote, attest, mint, burn, other
    from_address VARCHAR(42),
    to_address VARCHAR(42),
    contract_address VARCHAR(42),
    value NUMERIC(18,8),
    token VARCHAR(50),
    token_amount NUMERIC(18,8),
    gas_used NUMERIC(18,8),
    gas_price NUMERIC(18,8),
    status VARCHAR(20), -- success, failed, pending
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wallet_activity_wallet ON wallet_activity_event(wallet_id);
CREATE INDEX IF NOT EXISTS idx_wallet_activity_chain ON wallet_activity_event(chain);
CREATE INDEX IF NOT EXISTS idx_wallet_activity_tx ON wallet_activity_event(tx_hash);
CREATE INDEX IF NOT EXISTS idx_wallet_activity_type ON wallet_activity_event(activity_type);
CREATE INDEX IF NOT EXISTS idx_wallet_activity_block ON wallet_activity_event(block_number);

-- dApp sessions
CREATE TABLE IF NOT EXISTS dapp_session (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_id UUID NOT NULL REFERENCES wallet_profile(id) ON DELETE RESTRICT,
    protocol_id UUID REFERENCES protocol(id),
    session_start TIMESTAMPTZ NOT NULL,
    session_end TIMESTAMPTZ,
    duration_seconds INTEGER,
    actions_count INTEGER DEFAULT 0,
    chain VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Digital Lego usage (protocol/tool usage linked to location or user)
CREATE TABLE IF NOT EXISTS digital_lego_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_id UUID REFERENCES wallet_profile(id),
    protocol_id UUID NOT NULL REFERENCES protocol(id),
    location_id UUID REFERENCES location(id),
    usage_date DATE NOT NULL,
    action_type VARCHAR(100), -- swap, stake, lend, borrow, attest, vote, transfer, provide_liquidity, other
    amount NUMERIC(18,8),
    token VARCHAR(50),
    token_amount NUMERIC(18,8),
    tx_hash VARCHAR(66),
    chain VARCHAR(50),
    block_number BIGINT,
    -- Value attribution
    value_attributed NUMERIC(15,2),
    attribution_method VARCHAR(100),
    evidence_urls TEXT[],
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dlego_wallet ON digital_lego_usage(wallet_id);
CREATE INDEX IF NOT EXISTS idx_dlego_protocol ON digital_lego_usage(protocol_id);
CREATE INDEX IF NOT EXISTS idx_dlego_location ON digital_lego_usage(location_id);
CREATE INDEX IF NOT EXISTS idx_dlego_date ON digital_lego_usage(usage_date);

-- Governance events
CREATE TABLE IF NOT EXISTS governance_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_id UUID REFERENCES wallet_profile(id),
    protocol_id UUID REFERENCES protocol(id),
    chain VARCHAR(50) NOT NULL,
    event_type VARCHAR(100), -- proposal_created, vote_cast, delegate_changed, ragequit, tribute, signal
    proposal_id VARCHAR(255),
    proposal_title TEXT,
    vote_choice VARCHAR(50),
    amount NUMERIC(18,8),
    token VARCHAR(50),
    tx_hash VARCHAR(66),
    block_number BIGINT,
    block_timestamp TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Treasury events
CREATE TABLE IF NOT EXISTS treasury_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id),
    wallet_id UUID REFERENCES wallet_profile(id),
    chain VARCHAR(50) NOT NULL,
    event_date DATE NOT NULL,
    flow_direction VARCHAR(10) NOT NULL, -- inflow, outflow
    amount NUMERIC(18,8) NOT NULL,
    token VARCHAR(50) NOT NULL,
    token_amount NUMERIC(18,8),
    usd_value NUMERIC(15,2),
    source VARCHAR(255), -- dao_grant, revenue, sponsorship, purchase, swap, other
    purpose VARCHAR(255),
    tx_hash VARCHAR(66),
    block_number BIGINT,
    -- Verification
    verified BOOLEAN DEFAULT FALSE,
    attestation_uid VARCHAR(66),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_treasury_location ON treasury_event(location_id);
CREATE INDEX IF NOT EXISTS idx_treasury_date ON treasury_event(event_date);
CREATE INDEX IF NOT EXISTS idx_treasury_flow ON treasury_event(flow_direction);

-- Attestation schemas (EAS)
CREATE TABLE IF NOT EXISTS attestation_schema (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schema_uid VARCHAR(66) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    schema_text TEXT,
    chain VARCHAR(50) NOT NULL,
    resolver_address VARCHAR(42),
    version INTEGER DEFAULT 1,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Attestation records
CREATE TABLE IF NOT EXISTS attestation_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attestation_uid VARCHAR(66),
    schema_id UUID NOT NULL REFERENCES attestation_schema(id),
    claim_type VARCHAR(100), -- mrv, financial, operational, impact, identity, other
    subject_id UUID,
    subject_type VARCHAR(100), -- location, plot, crop_cycle, harvest_event, expense_event, etc.
    claim_data JSONB NOT NULL,
    -- Evidence
    evidence_hash VARCHAR(255),
    evidence_cids TEXT[],
    evidence_urls TEXT[],
    -- Workflow
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    reviewer_id UUID,
    review_notes TEXT,
    reviewed_at TIMESTAMPTZ,
    -- On-chain
    chain VARCHAR(50),
    tx_hash VARCHAR(66),
    attested_at TIMESTAMPTZ,
    expiration_date DATE,
    revocation_date DATE,
    -- Metadata
    schema_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_attest_schema ON attestation_record(schema_id);
CREATE INDEX IF NOT EXISTS idx_attest_subject ON attestation_record(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_attest_status ON attestation_record(status);
CREATE INDEX IF NOT EXISTS idx_attest_uid ON attestation_record(attestation_uid);

-- Chain indexer status
CREATE TABLE IF NOT EXISTS chain_indexer_status (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain VARCHAR(50) NOT NULL,
    indexer_type VARCHAR(50) NOT NULL, -- rpc, subgraph, eas
    last_synced_block BIGINT,
    last_synced_at TIMESTAMPTZ,
    status VARCHAR(50), -- syncing, healthy, error, paused
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_indexer_chain_type ON chain_indexer_status(chain, indexer_type);
