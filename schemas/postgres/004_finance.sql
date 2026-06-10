-- ============================================================
-- 004_finance.sql — Financial facts
-- ============================================================

-- Expense categories (governed taxonomy)
CREATE TABLE IF NOT EXISTS expense_category (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    code VARCHAR(50) UNIQUE,
    parent_id UUID REFERENCES expense_category(id),
    description TEXT,
    is_direct BOOLEAN DEFAULT TRUE, -- TRUE = direct crop cost, FALSE = shared operating cost
    allocation_default VARCHAR(50), -- direct, proportional, equal, area_based
    sort_order INTEGER,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Capital sources
CREATE TABLE IF NOT EXISTS capital_source (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(100) NOT NULL, -- dao, grant, partner, revenue, debt, equity, sponsorship, other
    description TEXT,
    amount NUMERIC(15,2),
    currency VARCHAR(10) DEFAULT 'USD',
    terms TEXT,
    start_date DATE,
    end_date DATE,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Financial transactions
CREATE TABLE IF NOT EXISTS financial_transaction (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    capital_source_id UUID REFERENCES capital_source(id),
    transaction_date DATE NOT NULL,
    transaction_type VARCHAR(50) NOT NULL, -- revenue, expense, transfer, capital_inflow, capital_outflow
    category VARCHAR(100),
    subcategory VARCHAR(100),
    amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    exchange_rate NUMERIC(12,6) DEFAULT 1,
    amount_usd NUMERIC(15,2),
    description TEXT,
    reference VARCHAR(255),
    counterparty VARCHAR(255),
    payment_method VARCHAR(100), -- cash, bank_transfer, mobile_money, crypto, check, other
    -- Reconciliation
    reconciled BOOLEAN DEFAULT FALSE,
    reconciled_at TIMESTAMPTZ,
    bank_reference VARCHAR(255),
    -- Evidence
    evidence_urls TEXT[],
    notes TEXT,
    -- Source lineage
    schema_version VARCHAR(20),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_financial_location ON financial_transaction(location_id);
CREATE INDEX IF NOT EXISTS idx_financial_date ON financial_transaction(transaction_date);
CREATE INDEX IF NOT EXISTS idx_financial_type ON financial_transaction(transaction_type);
CREATE INDEX IF NOT EXISTS idx_financial_category ON financial_transaction(category);

-- Crop cost allocation
CREATE TABLE IF NOT EXISTS crop_cost_allocation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_cycle_id UUID NOT NULL REFERENCES crop_cycle(id) ON DELETE RESTRICT,
    expense_id UUID NOT NULL REFERENCES expense_event(id) ON DELETE RESTRICT,
    allocation_method VARCHAR(50) NOT NULL,
    allocated_amount NUMERIC(15,2) NOT NULL,
    allocation_ratio NUMERIC(8,6),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alloc_crop_cycle ON crop_cost_allocation(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_alloc_expense ON crop_cost_allocation(expense_id);

-- Value flow events (governed value-flow tracking)
CREATE TABLE IF NOT EXISTS value_flow_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id),
    flow_date DATE NOT NULL,
    flow_type VARCHAR(100) NOT NULL, -- revenue, cost, allocation, public_goods, reinvestment, withdrawal, transfer
    from_entity VARCHAR(255),
    to_entity VARCHAR(255),
    amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    token VARCHAR(50),
    chain VARCHAR(50),
    tx_hash VARCHAR(66),
    description TEXT,
    -- Verification
    verified BOOLEAN DEFAULT FALSE,
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    attestation_uid VARCHAR(66),
    -- Exclusions
    is_excluded BOOLEAN DEFAULT FALSE,
    exclusion_reason TEXT,
    -- Source
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

-- Excluded value events (failed rounds, returned funds, excluded fees)
CREATE TABLE IF NOT EXISTS excluded_value_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    value_flow_id UUID REFERENCES value_flow_event(id),
    exclusion_type VARCHAR(100) NOT NULL, -- failed_round, returned_fund, excluded_fee, double_count, other
    amount NUMERIC(15,2),
    currency VARCHAR(10) DEFAULT 'USD',
    reason TEXT NOT NULL,
    excluded_by UUID,
    excluded_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- NOI snapshot (computed from crop cycles + expenses + sales)
CREATE TABLE IF NOT EXISTS noi_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_cycle_id UUID NOT NULL REFERENCES crop_cycle(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    -- Revenue
    gross_revenue NUMERIC(15,2),
    returns_and_discounts NUMERIC(15,2) DEFAULT 0,
    net_revenue NUMERIC(15,2),
    -- Costs
    direct_crop_costs NUMERIC(15,2),
    allocated_shared_costs NUMERIC(15,2),
    total_costs NUMERIC(15,2),
    -- Output
    noi NUMERIC(15,2),
    operating_margin_pct NUMERIC(8,4),
    loss_rate_pct NUMERIC(8,4),
    -- Metadata
    calculation_version VARCHAR(20),
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    inputs JSONB, -- snapshot of all inputs used in calculation
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_noi_crop_cycle ON noi_snapshot(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_noi_location ON noi_snapshot(location_id);
CREATE INDEX IF NOT EXISTS idx_noi_period ON noi_snapshot(period_start, period_end);

-- Cash flow snapshot
CREATE TABLE IF NOT EXISTS cash_flow_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    -- Inflows
    total_revenue NUMERIC(15,2),
    capital_inflows NUMERIC(15,2),
    grants_received NUMERIC(15,2),
    total_inflows NUMERIC(15,2),
    -- Outflows
    total_operating_expenses NUMERIC(15,2),
    total_capex NUMERIC(15,2),
    loan_repayments NUMERIC(15,2),
    public_goods_allocation NUMERIC(15,2),
    total_outflows NUMERIC(15,2),
    -- Net
    net_cash_flow NUMERIC(15,2),
    running_balance NUMERIC(15,2),
    -- Metadata
    calculation_version VARCHAR(20),
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    inputs JSONB,
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_cf_location ON cash_flow_snapshot(location_id);
CREATE INDEX IF NOT EXISTS idx_cf_period ON cash_flow_snapshot(period_start, period_end);
