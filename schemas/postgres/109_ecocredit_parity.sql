-- Ecocredit Module Parity: Credit Type, Issuers, Allowlist, Basket, Marketplace
-- Closes remaining gaps with Regen Network's Ecocredit module

-- ============================================================
-- credit_type (Credit Type with abbreviation, unit, precision)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_type (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    abbreviation VARCHAR(3) NOT NULL UNIQUE,
    unit VARCHAR(50) NOT NULL,
    precision INTEGER DEFAULT 2,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO credit_type (name, abbreviation, unit, precision, description) VALUES
('carbon', 'C', 'tonneCO2e', 2, 'Carbon dioxide equivalent sequestered or avoided'),
('biodiversity', 'B', 'species_ha', 2, 'Biodiversity impact per hectare'),
('water', 'W', 'm3', 2, 'Water quality or quantity improvement'),
('soil', 'S', 'tonne', 2, 'Soil organic matter or health improvement'),
('mixed', 'M', 'unit', 2, 'Mixed ecosystem service credits')
ON CONFLICT (name) DO UPDATE SET
    abbreviation = EXCLUDED.abbreviation,
    unit = EXCLUDED.unit,
    precision = EXCLUDED.precision,
    description = EXCLUDED.description;

-- ============================================================
-- credit_class_issuer (list of addresses authorized to issue batches)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_class_issuer (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_class_id UUID NOT NULL REFERENCES credit_class(id) ON DELETE CASCADE,
    issuer_address VARCHAR(42) NOT NULL,
    issuer_name VARCHAR(255),
    added_by VARCHAR(42),
    added_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    UNIQUE(credit_class_id, issuer_address)
);

CREATE INDEX idx_cci_class ON credit_class_issuer(credit_class_id);
CREATE INDEX idx_cci_address ON credit_class_issuer(issuer_address);

-- ============================================================
-- credit_class_creator_allowlist
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_class_creator_allowlist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    address VARCHAR(42) NOT NULL UNIQUE,
    entity_name VARCHAR(255),
    added_by VARCHAR(42),
    is_active BOOLEAN DEFAULT TRUE,
    added_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ccca_address ON credit_class_creator_allowlist(address);
CREATE INDEX idx_ccca_active ON credit_class_creator_allowlist(is_active) WHERE is_active = TRUE;

-- ============================================================
-- credit_basket (Basket submodule)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_basket (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    credit_type_id UUID REFERENCES credit_type(id),
    credit_class_ids UUID[],
    min_start_date DATE,
    max_start_date DATE,
    min_start_year INTEGER,
    token_denom VARCHAR(50) NOT NULL,
    chain VARCHAR(50) DEFAULT 'celo',
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_basket_status CHECK (status IN ('active', 'paused', 'deprecated'))
);

CREATE INDEX idx_cb_type ON credit_basket(credit_type_id);
CREATE INDEX idx_cb_denom ON credit_basket(token_denom);

-- ============================================================
-- credit_basket_deposit (deposits into basket)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_basket_deposit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    basket_id UUID NOT NULL REFERENCES credit_basket(id) ON DELETE RESTRICT,
    credit_batch_id UUID NOT NULL REFERENCES credit_batch(id) ON DELETE RESTRICT,
    depositor_address VARCHAR(42) NOT NULL,
    quantity NUMERIC(14,4) NOT NULL CHECK (quantity > 0),
    token_amount NUMERIC(18,8) NOT NULL CHECK (token_amount > 0),
    deposit_tx_hash VARCHAR(66),
    chain VARCHAR(50) DEFAULT 'celo',
    deposited_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'deposited',
    CONSTRAINT chk_basket_deposit_status CHECK (status IN ('deposited', 'withdrawn', 'cancelled'))
);

CREATE INDEX idx_cbd_basket ON credit_basket_deposit(basket_id);
CREATE INDEX idx_cbd_batch ON credit_basket_deposit(credit_batch_id);
CREATE INDEX idx_cbd_depositor ON credit_basket_deposit(depositor_address);

-- ============================================================
-- credit_basket_token (token balances per basket)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_basket_token (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    basket_id UUID NOT NULL REFERENCES credit_basket(id) ON DELETE RESTRICT,
    holder_address VARCHAR(42) NOT NULL,
    token_amount NUMERIC(18,8) NOT NULL DEFAULT 0,
    last_updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(basket_id, holder_address)
);

CREATE INDEX idx_cbt_basket ON credit_basket_token(basket_id);
CREATE INDEX idx_cbt_holder ON credit_basket_token(holder_address);

-- ============================================================
-- credit_sell_order (Marketplace submodule)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_sell_order (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_batch_id UUID NOT NULL REFERENCES credit_batch(id) ON DELETE RESTRICT,
    seller_address VARCHAR(42) NOT NULL,
    quantity NUMERIC(14,4) NOT NULL CHECK (quantity > 0),
    ask_price NUMERIC(18,8) NOT NULL CHECK (ask_price > 0),
    ask_denom VARCHAR(50) NOT NULL,
    auto_retire BOOLEAN DEFAULT FALSE,
    allow_partial_fills BOOLEAN DEFAULT TRUE,
    escrow_quantity NUMERIC(14,4) NOT NULL CHECK (escrow_quantity >= 0),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_sell_order_status CHECK (status IN ('active', 'filled', 'cancelled', 'expired'))
);

CREATE INDEX idx_cso_batch ON credit_sell_order(credit_batch_id);
CREATE INDEX idx_cso_seller ON credit_sell_order(seller_address);
CREATE INDEX idx_cso_status ON credit_sell_order(status);
CREATE INDEX idx_cso_denom ON credit_sell_order(ask_denom);

-- ============================================================
-- credit_buy_order (Marketplace submodule)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_buy_order (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sell_order_id UUID NOT NULL REFERENCES credit_sell_order(id) ON DELETE RESTRICT,
    buyer_address VARCHAR(42) NOT NULL,
    quantity NUMERIC(14,4) NOT NULL CHECK (quantity > 0),
    total_price NUMERIC(18,8) NOT NULL CHECK (total_price > 0),
    price_denom VARCHAR(50) NOT NULL,
    auto_retire BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT chk_buy_order_status CHECK (status IN ('pending', 'completed', 'cancelled', 'failed'))
);

CREATE INDEX idx_cbo_sell ON credit_buy_order(sell_order_id);
CREATE INDEX idx_cbo_buyer ON credit_buy_order(buyer_address);
CREATE INDEX idx_cbo_status ON credit_buy_order(status);

-- ============================================================
-- credit_allowed_denom (approved denominations for marketplace)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_allowed_denom (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    denom VARCHAR(50) NOT NULL UNIQUE,
    chain VARCHAR(50) DEFAULT 'celo',
    contract_address VARCHAR(42),
    is_active BOOLEAN DEFAULT TRUE,
    added_by VARCHAR(42),
    added_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cad_denom ON credit_allowed_denom(denom);
CREATE INDEX idx_cad_active ON credit_allowed_denom(is_active) WHERE is_active = TRUE;

-- Seed default allowed denominations
INSERT INTO credit_allowed_denom (denom, chain, is_active) VALUES
('uusd', 'celo', TRUE),
('cusd', 'celo', TRUE),
('ceur', 'celo', TRUE)
ON CONFLICT (denom) DO NOTHING;

-- ============================================================
-- credit_balance (per-account balance tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_balance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_batch_id UUID NOT NULL REFERENCES credit_batch(id) ON DELETE RESTRICT,
    account_address VARCHAR(42) NOT NULL,
    tradable_amount NUMERIC(14,4) DEFAULT 0 CHECK (tradable_amount >= 0),
    retired_amount NUMERIC(14,4) DEFAULT 0 CHECK (retired_amount >= 0),
    escrowed_amount NUMERIC(14,4) DEFAULT 0 CHECK (escrowed_amount >= 0),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(credit_batch_id, account_address)
);

CREATE INDEX idx_cb_batch ON credit_balance(credit_batch_id);
CREATE INDEX idx_cb_account ON credit_balance(account_address);

-- ============================================================
-- ecocredit_params (module parameters)
-- ============================================================
CREATE TABLE IF NOT EXISTS ecocredit_params (
    param_key VARCHAR(100) PRIMARY KEY,
    param_value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default parameters
INSERT INTO ecocredit_params (param_key, param_value, description) VALUES
('class_fee', '{"denom": "cusd", "amount": 0}', 'Credit class creation fee'),
('basket_fee', '{"denom": "cusd", "amount": 0}', 'Basket creation fee'),
('allowed_bridge_chains', '["celo", "gnosis"]', 'Chains allowed for bridge operations')
ON CONFLICT (param_key) DO NOTHING;
