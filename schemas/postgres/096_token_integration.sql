-- ============================================================
-- 096_token_integration.sql — Token/Staking Integration
-- ============================================================
-- Supports both external contract address AND internal contract
-- source/ABI for flexibility with partner tokens.

-- 1. Governance token registry
CREATE TABLE IF NOT EXISTS governance_token (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain VARCHAR(50) NOT NULL,
    contract_address VARCHAR(42) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    decimals INTEGER DEFAULT 18,
    deployment_mode VARCHAR(50) NOT NULL DEFAULT 'external',
    contract_source_code TEXT,
    abi JSONB,
    deployment_date DATE,
    deployer_address VARCHAR(42),
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(chain, contract_address)
);

CREATE INDEX IF NOT EXISTS gt_chain ON governance_token(chain);
CREATE INDEX IF NOT EXISTS gt_symbol ON governance_token(symbol);
CREATE INDEX IF NOT EXISTS gt_status ON governance_token(status);

ALTER TABLE governance_token DROP CONSTRAINT IF EXISTS chk_gt_deployment;
ALTER TABLE governance_token ADD CONSTRAINT chk_gt_deployment CHECK (deployment_mode IN ('external', 'internal'));

ALTER TABLE governance_token DROP CONSTRAINT IF EXISTS chk_gt_status;
ALTER TABLE governance_token ADD CONSTRAINT chk_gt_status CHECK (status IN ('active', 'deprecated', 'paused'));

-- 2. Tree-token binding (1:1 mapping)
CREATE TABLE IF NOT EXISTS tree_token_binding (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tree_record_id UUID NOT NULL REFERENCES tree_record(id) ON DELETE RESTRICT,
    token_id UUID NOT NULL REFERENCES governance_token(id) ON DELETE RESTRICT,
    token_id_onchain VARCHAR(100) NOT NULL,
    wallet_address VARCHAR(42) NOT NULL,
    binding_date DATE NOT NULL DEFAULT CURRENT_DATE,
    binding_tx_hash VARCHAR(66),
    unbinding_date DATE,
    unbinding_tx_hash VARCHAR(66),
    status VARCHAR(50) DEFAULT 'bound',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ttb_tree ON tree_token_binding(tree_record_id);
CREATE INDEX IF NOT EXISTS ttb_token ON tree_token_binding(token_id);
CREATE INDEX IF NOT EXISTS ttb_wallet ON tree_token_binding(wallet_address);
CREATE INDEX IF NOT EXISTS ttb_status ON tree_token_binding(status);

ALTER TABLE tree_token_binding DROP CONSTRAINT IF EXISTS chk_ttb_status;
ALTER TABLE tree_token_binding ADD CONSTRAINT chk_ttb_status CHECK (status IN ('bound', 'unbound', 'pending'));

-- 3. Staking position
CREATE TABLE IF NOT EXISTS staking_position (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_address VARCHAR(42) NOT NULL,
    token_id UUID NOT NULL REFERENCES governance_token(id) ON DELETE RESTRICT,
    token_amount NUMERIC(18,8) NOT NULL,
    lock_period_days INTEGER NOT NULL DEFAULT 90,
    lock_start DATE NOT NULL DEFAULT CURRENT_DATE,
    lock_end DATE,
    accumulated_rewards NUMERIC(18,8) DEFAULT 0,
    last_reward_date DATE,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sp_wallet ON staking_position(wallet_address);
CREATE INDEX IF NOT EXISTS sp_token ON staking_position(token_id);
CREATE INDEX IF NOT EXISTS sp_status ON staking_position(status);
CREATE INDEX IF NOT EXISTS sp_lock_end ON staking_position(lock_end);

ALTER TABLE staking_position DROP CONSTRAINT IF EXISTS chk_sp_status;
ALTER TABLE staking_position ADD CONSTRAINT chk_sp_status CHECK (status IN ('active', 'locked', 'unlocked', 'withdrawn'));

-- 4. Yield distribution
CREATE TABLE IF NOT EXISTS yield_distribution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    epoch VARCHAR(50) NOT NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    total_yield_usd NUMERIC(15,2) NOT NULL,
    total_staked_tokens NUMERIC(18,8) NOT NULL,
    distribution_per_token NUMERIC(18,8) NOT NULL,
    distribution_date DATE NOT NULL,
    distribution_tx_hash VARCHAR(66),
    chain VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS yd_epoch ON yield_distribution(epoch);
CREATE INDEX IF NOT EXISTS yd_location ON yield_distribution(location_id);
CREATE INDEX IF NOT EXISTS yd_status ON yield_distribution(status);

ALTER TABLE yield_distribution DROP CONSTRAINT IF EXISTS chk_yd_status;
ALTER TABLE yield_distribution ADD CONSTRAINT chk_yd_status CHECK (status IN ('pending', 'distributed', 'failed'));

-- 5. Token balance snapshot
CREATE TABLE IF NOT EXISTS token_balance_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_address VARCHAR(42) NOT NULL,
    token_id UUID NOT NULL REFERENCES governance_token(id) ON DELETE RESTRICT,
    balance NUMERIC(18,8) NOT NULL,
    staked_amount NUMERIC(18,8) DEFAULT 0,
    voting_power NUMERIC(18,8) DEFAULT 0,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    chain VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS tbs_wallet ON token_balance_snapshot(wallet_address);
CREATE INDEX IF NOT EXISTS tbs_token ON token_balance_snapshot(token_id);
CREATE INDEX IF NOT EXISTS tbs_date ON token_balance_snapshot(snapshot_date);

-- 6. Public view
CREATE OR REPLACE VIEW v_public_tree_token_inventory AS
SELECT
    l.name AS location_name,
    tr.species_name,
    tr.height_m,
    tr.dbh_cm,
    tr.health_score,
    gt.symbol AS token_symbol,
    gt.chain AS token_chain,
    ttb.token_id_onchain,
    ttb.wallet_address,
    ttb.binding_date,
    ttb.status AS binding_status
FROM tree_token_binding ttb
JOIN tree_record tr ON tr.id = ttb.tree_record_id
JOIN governance_token gt ON gt.id = ttb.token_id
JOIN location l ON l.id = tr.location_id
WHERE ttb.status = 'bound';
