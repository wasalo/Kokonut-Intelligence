-- 324_baal_governance.sql — Configurable Governance Framework + Baal (Moloch v3) support
--
-- Introduces a pluggable governance_framework registry and Baal-specific
-- columns/table so Kokonut Intelligence is governance-framework-aware. The
-- Kokonut DAO is a Moloch v3 (Baal) deployment on Gnosis Chain; the legacy
-- Moloch v2 indexer (services/ingestion/gnosis_indexer.py) is preserved for
-- historical data.

-- 1. Governance framework registry: one row per configured DAO framework.
CREATE TABLE IF NOT EXISTS governance_framework (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    framework_key VARCHAR(100) NOT NULL UNIQUE,   -- moloch_v3_baal, governor, aragon, colony
    name VARCHAR(255) NOT NULL,
    chain VARCHAR(50) NOT NULL,
    contract_address VARCHAR(66),
    abi_ref VARCHAR(255),                          -- pointer to contracts/abis/*.json
    is_active BOOLEAN DEFAULT TRUE,
    config_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gov_framework_chain ON governance_framework(chain);
CREATE INDEX IF NOT EXISTS idx_gov_framework_active ON governance_framework(is_active);

-- 2. Extend dao_proposal with a framework discriminator + Baal proposal id.
ALTER TABLE dao_proposal
    ADD COLUMN IF NOT EXISTS framework VARCHAR(100) DEFAULT 'moloch_v2';  -- moloch_v2, moloch_v3_baal, governor, aragon, colony
ALTER TABLE dao_proposal
    ADD COLUMN IF NOT EXISTS baal_proposal_id VARCHAR(255);
ALTER TABLE dao_proposal
    ADD COLUMN IF NOT EXISTS lifecycle_detail JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_dao_proposal_framework ON dao_proposal(framework);
CREATE INDEX IF NOT EXISTS idx_dao_proposal_baal ON dao_proposal(baal_proposal_id);

-- 3. Cached snapshot of Baal governance config (populated by baal_indexer).
CREATE TABLE IF NOT EXISTS baal_governance_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    framework_id UUID REFERENCES governance_framework(id) ON DELETE CASCADE,
    chain VARCHAR(50) NOT NULL,
    voting_period INTEGER,
    grace_period INTEGER,
    proposal_offering NUMERIC(36,0),
    quorum_percent INTEGER,
    sponsor_threshold NUMERIC(36,0),
    min_retention_percent INTEGER,
    baal_version VARCHAR(50),
    observed_at_block BIGINT,
    captured_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_baal_config_framework ON baal_governance_config(framework_id);

-- 4. Registered Baal shamans (permission registry: 0 none,1 admin,2 manager,
--    4 governor, additive combos 3/5/6/7). Populated by baal_indexer.
CREATE TABLE IF NOT EXISTS baal_shaman (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    framework_id UUID REFERENCES governance_framework(id) ON DELETE CASCADE,
    shaman_address VARCHAR(66) NOT NULL,
    permission INTEGER NOT NULL DEFAULT 0,
    observed_at_block BIGINT,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (framework_id, shaman_address)
);

CREATE INDEX IF NOT EXISTS idx_baal_shaman_framework ON baal_shaman(framework_id);
