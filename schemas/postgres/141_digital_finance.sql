-- ============================================================
-- 141_digital_finance.sql — Digital Financial Services
-- Savings, credit, insurance, and lending built on top of
-- farm data, CRISP risk scores, and digital twin predictions.
-- ============================================================

BEGIN;

-- ============================================================
-- Reference Data
-- ============================================================

-- Currency types
CREATE TABLE IF NOT EXISTS dfs_currency (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(10) NOT NULL UNIQUE,
    name            VARCHAR(100) NOT NULL,
    symbol          VARCHAR(10),
    decimal_places  INTEGER DEFAULT 2,
    is_active       BOOLEAN DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO dfs_currency (code, name, symbol, decimal_places) VALUES
    ('KES', 'Kenyan Shilling', 'KSh', 2),
    ('USD', 'United States Dollar', '$', 2),
    ('CNG', 'Celo NGN Stablecoin', 'cNGN', 18),
    ('CUSD', 'Celo Dollar', 'cUSD', 18),
    ('EUR', 'Euro', 'E', 2),
    ('GBP', 'British Pound', 'GBP', 2)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    symbol = EXCLUDED.symbol,
    decimal_places = EXCLUDED.decimal_places;

-- Insurance product types
CREATE TABLE IF NOT EXISTS dfs_insurance_product_type (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(50) NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    coverage_type   VARCHAR(100) NOT NULL,
    risk_dimensions TEXT[] DEFAULT '{}',
    is_active       BOOLEAN DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO dfs_insurance_product_type (code, name, description, coverage_type, risk_dimensions) VALUES
    ('weather_index', 'Weather Index Insurance', 'Payout triggered by weather parameters (rainfall, temperature)', 'weather_index', '{climate}'),
    ('yield_guarantee', 'Yield Guarantee Insurance', 'Covers yield shortfalls below guaranteed threshold', 'yield_guarantee', '{carbon_yield,implementation}'),
    ('revenue_protection', 'Revenue Protection Insurance', 'Protects against revenue loss from price or yield drops', 'revenue_protection', '{financial,carbon_yield,climate}'),
    ('multi_peril', 'Multi-Peril Crop Insurance', 'Comprehensive coverage across weather, pest, and disease', 'multi_peril', '{climate,carbon_yield,implementation,policy}'),
    ('drought_cover', 'Drought Coverage', 'Index-based drought trigger using satellite NDVI and rainfall', 'weather_index', '{climate}'),
    ('flood_cover', 'Flood Coverage', 'Excess rainfall / flood trigger using gauge and satellite data', 'weather_index', '{climate}')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    coverage_type = EXCLUDED.coverage_type,
    risk_dimensions = EXCLUDED.risk_dimensions;

-- ============================================================
-- 1. Farm Financial Account
-- ============================================================

CREATE TABLE IF NOT EXISTS farm_financial_account (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    account_name    VARCHAR(300) NOT NULL,
    account_type    VARCHAR(50) NOT NULL,
    currency_code   VARCHAR(10) NOT NULL DEFAULT 'KES' REFERENCES dfs_currency(code),
    provider        VARCHAR(200),
    account_number  VARCHAR(200),
    balance         NUMERIC(18,4) DEFAULT 0,
    available_credit NUMERIC(18,4) DEFAULT 0,
    credit_limit    NUMERIC(18,4) DEFAULT 0,
    interest_rate_pct NUMERIC(6,4),
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    kyc_verified    BOOLEAN DEFAULT FALSE,
    kyc_verified_at TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(200),
    updated_by      VARCHAR(200)
);

ALTER TABLE farm_financial_account DROP CONSTRAINT IF EXISTS chk_dfs_account_type;
ALTER TABLE farm_financial_account ADD CONSTRAINT chk_dfs_account_type CHECK (
    account_type IN ('savings', 'credit', 'insurance_wallet', 'mobile_money', 'bank', 'crypto')
);

ALTER TABLE farm_financial_account DROP CONSTRAINT IF EXISTS chk_dfs_account_status;
ALTER TABLE farm_financial_account ADD CONSTRAINT chk_dfs_account_status CHECK (
    status IN ('active', 'frozen', 'closed', 'pending_verification')
);

CREATE INDEX IF NOT EXISTS idx_dfs_account_location ON farm_financial_account (location_id);
CREATE INDEX IF NOT EXISTS idx_dfs_account_type ON farm_financial_account (account_type);
CREATE INDEX IF NOT EXISTS idx_dfs_account_status ON farm_financial_account (status);
CREATE INDEX IF NOT EXISTS idx_dfs_account_currency ON farm_financial_account (currency_code);

-- ============================================================
-- 2. Financial Transaction
-- ============================================================

CREATE TABLE IF NOT EXISTS dfs_financial_transaction (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES farm_financial_account(id) ON DELETE RESTRICT,
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    transaction_type VARCHAR(50) NOT NULL,
    amount          NUMERIC(18,4) NOT NULL,
    currency_code   VARCHAR(10) NOT NULL DEFAULT 'KES' REFERENCES dfs_currency(code),
    exchange_rate   NUMERIC(12,6) DEFAULT 1,
    amount_usd      NUMERIC(18,4),
    direction       VARCHAR(10) NOT NULL,

    reference_id    UUID,
    reference_type  VARCHAR(50),
    external_ref    VARCHAR(300),

    status          VARCHAR(50) NOT NULL DEFAULT 'completed',
    completed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    fee_amount      NUMERIC(18,4) DEFAULT 0,
    fee_currency    VARCHAR(10),

    reconciled      BOOLEAN DEFAULT FALSE,
    reconciled_at   TIMESTAMPTZ,

    source_system   VARCHAR(100),
    source_id       VARCHAR(255),
    source_raw      JSONB,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(200)
);

ALTER TABLE dfs_financial_transaction DROP CONSTRAINT IF EXISTS chk_dfs_tx_type;
ALTER TABLE dfs_financial_transaction ADD CONSTRAINT chk_dfs_tx_type CHECK (
    transaction_type IN (
        'deposit', 'withdrawal', 'loan_disbursement', 'loan_repayment',
        'insurance_premium', 'claim_payout', 'transfer', 'fee', 'interest',
        'collateral_deposit', 'collateral_release'
    )
);

ALTER TABLE dfs_financial_transaction DROP CONSTRAINT IF EXISTS chk_dfs_tx_direction;
ALTER TABLE dfs_financial_transaction ADD CONSTRAINT chk_dfs_tx_direction CHECK (
    direction IN ('inflow', 'outflow')
);

ALTER TABLE dfs_financial_transaction DROP CONSTRAINT IF EXISTS chk_dfs_tx_status;
ALTER TABLE dfs_financial_transaction ADD CONSTRAINT chk_dfs_tx_status CHECK (
    status IN ('pending', 'completed', 'failed', 'reversed', 'cancelled')
);

CREATE INDEX IF NOT EXISTS idx_dfs_tx_account ON dfs_financial_transaction (account_id);
CREATE INDEX IF NOT EXISTS idx_dfs_tx_location ON dfs_financial_transaction (location_id);
CREATE INDEX IF NOT EXISTS idx_dfs_tx_type ON dfs_financial_transaction (transaction_type);
CREATE INDEX IF NOT EXISTS idx_dfs_tx_status ON dfs_financial_transaction (status);
CREATE INDEX IF NOT EXISTS idx_dfs_tx_date ON dfs_financial_transaction (completed_at);
CREATE INDEX IF NOT EXISTS idx_dfs_tx_reference ON dfs_financial_transaction (reference_id, reference_type);

-- ============================================================
-- 3. Crop Insurance Policy
-- ============================================================

CREATE TABLE IF NOT EXISTS crop_insurance_policy (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    product_type_id UUID NOT NULL REFERENCES dfs_insurance_product_type(id),
    account_id      UUID REFERENCES farm_financial_account(id),

    policy_number   VARCHAR(100) NOT NULL UNIQUE,
    policy_name     VARCHAR(300),
    crop_type       VARCHAR(100),
    area_hectares   NUMERIC(10,4),
    sum_insured     NUMERIC(18,4) NOT NULL,
    premium_amount  NUMERIC(18,4) NOT NULL,
    premium_frequency VARCHAR(50) DEFAULT 'seasonal',
    deductible_pct  NUMERIC(5,2) DEFAULT 0,

    crisp_assessment_id UUID REFERENCES crisp_risk_assessment(id),
    risk_rating     VARCHAR(5),
    risk_score      NUMERIC(5,2),

    twin_id         UUID REFERENCES digital_twin(id),
    predicted_yield NUMERIC(12,4),
    yield_unit      VARCHAR(50) DEFAULT 'kg/ha',
    yield_source    VARCHAR(100),

    trigger_type    VARCHAR(100),
    trigger_param   VARCHAR(200),
    trigger_value   NUMERIC(12,4),
    payout_max_pct  NUMERIC(5,2) DEFAULT 100,

    coverage_start  DATE NOT NULL,
    coverage_end    DATE NOT NULL,

    underwriter     VARCHAR(200),
    underwriter_ref VARCHAR(200),
    premium_paid    BOOLEAN DEFAULT FALSE,
    premium_paid_at TIMESTAMPTZ,

    status          VARCHAR(50) NOT NULL DEFAULT 'draft',
    issued_at       TIMESTAMPTZ,
    activated_at    TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    cancellation_reason TEXT,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(200),
    updated_by      VARCHAR(200)
);

ALTER TABLE crop_insurance_policy DROP CONSTRAINT IF EXISTS chk_dfs_policy_status;
ALTER TABLE crop_insurance_policy ADD CONSTRAINT chk_dfs_policy_status CHECK (
    status IN ('draft', 'submitted', 'quoted', 'issued', 'active', 'expired', 'cancelled', 'claimed', 'rejected')
);

ALTER TABLE crop_insurance_policy DROP CONSTRAINT IF EXISTS chk_dfs_policy_premium_freq;
ALTER TABLE crop_insurance_policy ADD CONSTRAINT chk_dfs_policy_premium_freq CHECK (
    premium_frequency IN ('monthly', 'quarterly', 'seasonal', 'annual', 'one_time')
);

ALTER TABLE crop_insurance_policy DROP CONSTRAINT IF EXISTS chk_dfs_policy_yield_source;
ALTER TABLE crop_insurance_policy ADD CONSTRAINT chk_dfs_policy_yield_source CHECK (
    yield_source IS NULL OR yield_source IN ('digital_twin', 'historical_average', 'satellite', 'manual', 'hybrid')
);

ALTER TABLE crop_insurance_policy DROP CONSTRAINT IF EXISTS chk_dfs_policy_coverage_dates;
ALTER TABLE crop_insurance_policy ADD CONSTRAINT chk_dfs_policy_coverage_dates CHECK (
    coverage_start <= coverage_end
);

CREATE INDEX IF NOT EXISTS idx_dfs_policy_location ON crop_insurance_policy (location_id);
CREATE INDEX IF NOT EXISTS idx_dfs_policy_product ON crop_insurance_policy (product_type_id);
CREATE INDEX IF NOT EXISTS idx_dfs_policy_status ON crop_insurance_policy (status);
CREATE INDEX IF NOT EXISTS idx_dfs_policy_crisp ON crop_insurance_policy (crisp_assessment_id);
CREATE INDEX IF NOT EXISTS idx_dfs_policy_coverage ON crop_insurance_policy (coverage_start, coverage_end);
CREATE INDEX IF NOT EXISTS idx_dfs_policy_account ON crop_insurance_policy (account_id);

-- ============================================================
-- 4. Insurance Claim
-- ============================================================

CREATE TABLE IF NOT EXISTS insurance_claim (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id       UUID NOT NULL REFERENCES crop_insurance_policy(id) ON DELETE RESTRICT,
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    account_id      UUID REFERENCES farm_financial_account(id),

    claim_number    VARCHAR(100) NOT NULL UNIQUE,
    claim_date      DATE NOT NULL,
    event_date      DATE NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    event_description TEXT,

    trigger_actual_value NUMERIC(12,4),
    trigger_threshold    NUMERIC(12,4),
    evidence_data   JSONB DEFAULT '{}',

    claim_amount    NUMERIC(18,4) NOT NULL,
    payout_amount   NUMERIC(18,4),
    payout_status   VARCHAR(50) DEFAULT 'pending',

    crisp_score_at_event NUMERIC(5,2),
    twin_predicted_yield NUMERIC(12,4),
    actual_yield    NUMERIC(12,4),
    yield_gap_pct   NUMERIC(8,4),

    status          VARCHAR(50) NOT NULL DEFAULT 'filed',
    filed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at     TIMESTAMPTZ,
    approved_at     TIMESTAMPTZ,
    paid_at         TIMESTAMPTZ,
    rejected_at     TIMESTAMPTZ,
    rejection_reason TEXT,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(200),
    updated_by      VARCHAR(200)
);

ALTER TABLE insurance_claim DROP CONSTRAINT IF EXISTS chk_dfs_claim_status;
ALTER TABLE insurance_claim ADD CONSTRAINT chk_dfs_claim_status CHECK (
    status IN ('filed', 'under_review', 'approved', 'rejected', 'paid', 'closed', 'disputed')
);

ALTER TABLE insurance_claim DROP CONSTRAINT IF EXISTS chk_dfs_claim_payout_status;
ALTER TABLE insurance_claim ADD CONSTRAINT chk_dfs_claim_payout_status CHECK (
    payout_status IN ('pending', 'processing', 'completed', 'failed', 'reversed')
);

ALTER TABLE insurance_claim DROP CONSTRAINT IF EXISTS chk_dfs_claim_event_type;
ALTER TABLE insurance_claim ADD CONSTRAINT chk_dfs_claim_event_type CHECK (
    event_type IN ('drought', 'flood', 'pest', 'disease', 'frost', 'heat_stress', 'hailstorm', 'wildfire', 'other')
);

CREATE INDEX IF NOT EXISTS idx_dfs_claim_policy ON insurance_claim (policy_id);
CREATE INDEX IF NOT EXISTS idx_dfs_claim_location ON insurance_claim (location_id);
CREATE INDEX IF NOT EXISTS idx_dfs_claim_status ON insurance_claim (status);
CREATE INDEX IF NOT EXISTS idx_dfs_claim_date ON insurance_claim (claim_date);
CREATE INDEX IF NOT EXISTS idx_dfs_claim_event ON insurance_claim (event_type);

-- ============================================================
-- 5. Digital Lending
-- ============================================================

CREATE TABLE IF NOT EXISTS digital_lending (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    account_id      UUID NOT NULL REFERENCES farm_financial_account(id) ON DELETE RESTRICT,

    loan_number     VARCHAR(100) NOT NULL UNIQUE,
    loan_type       VARCHAR(50) NOT NULL,
    principal       NUMERIC(18,4) NOT NULL,
    currency_code   VARCHAR(10) NOT NULL DEFAULT 'KES' REFERENCES dfs_currency(code),
    interest_rate_pct NUMERIC(6,4) NOT NULL,
    interest_type   VARCHAR(20) DEFAULT 'simple',
    term_months     INTEGER NOT NULL,
    disbursement_date DATE,
    maturity_date   DATE,

    eligibility_score NUMERIC(5,2),
    eligibility_factors JSONB DEFAULT '{}',
    crisp_assessment_id UUID REFERENCES crisp_risk_assessment(id),
    auto_approved   BOOLEAN DEFAULT FALSE,
    approved_by     VARCHAR(200),
    approved_at     TIMESTAMPTZ,
    approval_limit  NUMERIC(18,4),

    disbursed_amount NUMERIC(18,4),
    disbursement_method VARCHAR(100),
    disbursement_ref VARCHAR(200),

    collateral_required NUMERIC(18,4),
    collateral_value   NUMERIC(18,4),

    status          VARCHAR(50) NOT NULL DEFAULT 'draft',
    disbursed       BOOLEAN DEFAULT FALSE,
    closed_at       TIMESTAMPTZ,
    defaulted_at    TIMESTAMPTZ,
    default_reason  TEXT,

    penalty_rate_pct NUMERIC(6,4) DEFAULT 0,
    penalty_accrued  NUMERIC(18,4) DEFAULT 0,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(200),
    updated_by      VARCHAR(200)
);

ALTER TABLE digital_lending DROP CONSTRAINT IF EXISTS chk_dfs_lending_type;
ALTER TABLE digital_lending ADD CONSTRAINT chk_dfs_lending_type CHECK (
    loan_type IN ('working_capital', 'equipment', 'input_advance', 'post_harvest', 'emergency', 'expansion')
);

ALTER TABLE digital_lending DROP CONSTRAINT IF EXISTS chk_dfs_lending_status;
ALTER TABLE digital_lending ADD CONSTRAINT chk_dfs_lending_status CHECK (
    status IN ('draft', 'submitted', 'under_review', 'approved', 'disbursed', 'repaying', 'completed', 'defaulted', 'written_off', 'rejected')
);

ALTER TABLE digital_lending DROP CONSTRAINT IF EXISTS chk_dfs_lending_interest_type;
ALTER TABLE digital_lending ADD CONSTRAINT chk_dfs_lending_interest_type CHECK (
    interest_type IN ('simple', 'reducing_balance', 'flat')
);

CREATE INDEX IF NOT EXISTS idx_dfs_lending_location ON digital_lending (location_id);
CREATE INDEX IF NOT EXISTS idx_dfs_lending_account ON digital_lending (account_id);
CREATE INDEX IF NOT EXISTS idx_dfs_lending_status ON digital_lending (status);
CREATE INDEX IF NOT EXISTS idx_dfs_lending_type ON digital_lending (loan_type);
CREATE INDEX IF NOT EXISTS idx_dfs_lending_maturity ON digital_lending (maturity_date);

-- ============================================================
-- 6. Repayment Schedule
-- ============================================================

CREATE TABLE IF NOT EXISTS repayment_schedule (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id         UUID NOT NULL REFERENCES digital_lending(id) ON DELETE CASCADE,
    installment_no  INTEGER NOT NULL,

    principal_due   NUMERIC(18,4) NOT NULL,
    interest_due    NUMERIC(18,4) NOT NULL,
    total_due       NUMERIC(18,4) NOT NULL,
    principal_paid  NUMERIC(18,4) DEFAULT 0,
    interest_paid   NUMERIC(18,4) DEFAULT 0,
    total_paid      NUMERIC(18,4) DEFAULT 0,
    balance_after   NUMERIC(18,4),

    due_date        DATE NOT NULL,
    paid_date       DATE,

    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    days_overdue    INTEGER DEFAULT 0,
    penalty_amount  NUMERIC(18,4) DEFAULT 0,

    transaction_id  UUID REFERENCES dfs_financial_transaction(id),

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_repayment_installment UNIQUE (loan_id, installment_no)
);

ALTER TABLE repayment_schedule DROP CONSTRAINT IF EXISTS chk_dfs_repayment_status;
ALTER TABLE repayment_schedule ADD CONSTRAINT chk_dfs_repayment_status CHECK (
    status IN ('pending', 'partial', 'paid', 'overdue', 'waived', 'written_off')
);

CREATE INDEX IF NOT EXISTS idx_dfs_repayment_loan ON repayment_schedule (loan_id);
CREATE INDEX IF NOT EXISTS idx_dfs_repayment_status ON repayment_schedule (status);
CREATE INDEX IF NOT EXISTS idx_dfs_repayment_due ON repayment_schedule (due_date);
CREATE INDEX IF NOT EXISTS idx_dfs_repayment_overdue ON repayment_schedule (days_overdue) WHERE days_overdue > 0;

-- ============================================================
-- 7. Collateral Asset
-- ============================================================

CREATE TABLE IF NOT EXISTS collateral_asset (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    asset_name      VARCHAR(300) NOT NULL,
    asset_type      VARCHAR(100) NOT NULL,
    asset_class     VARCHAR(50) DEFAULT 'tangible',

    registration_id VARCHAR(200),
    description     TEXT,
    location_detail TEXT,

    estimated_value NUMERIC(18,4) NOT NULL,
    currency_code   VARCHAR(10) NOT NULL DEFAULT 'KES' REFERENCES dfs_currency(code),
    valuation_date  DATE NOT NULL,
    valuation_method VARCHAR(100),
    valuation_source VARCHAR(200),
    confidence_pct  NUMERIC(5,2),

    tree_count      INTEGER,
    land_area_ha    NUMERIC(10,4),
    crop_cycle_id   UUID,
    sensor_asset_id UUID,
    digital_twin_id UUID REFERENCES digital_twin(id),

    verified        BOOLEAN DEFAULT FALSE,
    verified_by     VARCHAR(200),
    verified_at     TIMESTAMPTZ,
    attestation_uid VARCHAR(66),

    pledged         BOOLEAN DEFAULT FALSE,
    pledged_to_loan UUID REFERENCES digital_lending(id),
    pledge_date     DATE,
    release_date    DATE,

    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(200),
    updated_by      VARCHAR(200)
);

ALTER TABLE collateral_asset DROP CONSTRAINT IF EXISTS chk_dfs_collateral_type;
ALTER TABLE collateral_asset ADD CONSTRAINT chk_dfs_collateral_type CHECK (
    asset_type IN ('land', 'tree_inventory', 'equipment', 'livestock', 'crop_stock', 'building', 'vehicle', 'other')
);

ALTER TABLE collateral_asset DROP CONSTRAINT IF EXISTS chk_dfs_collateral_class;
ALTER TABLE collateral_asset ADD CONSTRAINT chk_dfs_collateral_class CHECK (
    asset_class IN ('tangible', 'intangible', 'digital')
);

ALTER TABLE collateral_asset DROP CONSTRAINT IF EXISTS chk_dfs_collateral_status;
ALTER TABLE collateral_asset ADD CONSTRAINT chk_dfs_collateral_status CHECK (
    status IN ('active', 'depreciated', 'disposed', 'pledged', 'released', 'revalued')
);

ALTER TABLE collateral_asset DROP CONSTRAINT IF EXISTS chk_dfs_collateral_valuation_method;
ALTER TABLE collateral_asset ADD CONSTRAINT chk_dfs_collateral_valuation_method CHECK (
    valuation_method IS NULL OR valuation_method IN ('market_value', 'replacement_cost', 'depreciated_value', 'oracle', 'appraisal', 'auto')
);

CREATE INDEX IF NOT EXISTS idx_dfs_collateral_location ON collateral_asset (location_id);
CREATE INDEX IF NOT EXISTS idx_dfs_collateral_type ON collateral_asset (asset_type);
CREATE INDEX IF NOT EXISTS idx_dfs_collateral_status ON collateral_asset (status);
CREATE INDEX IF NOT EXISTS idx_dfs_collateral_pledged ON collateral_asset (pledged_to_loan) WHERE pledged = TRUE;

-- ============================================================
-- Views
-- ============================================================

-- Account balances and transaction counts
CREATE OR REPLACE VIEW v_finance_account_summary AS
SELECT
    a.id                AS account_id,
    a.location_id,
    l.name              AS location_name,
    a.account_name,
    a.account_type,
    a.currency_code,
    dc.symbol           AS currency_symbol,
    a.balance,
    a.available_credit,
    a.credit_limit,
    a.status,
    a.kyc_verified,
    (SELECT COUNT(*)
     FROM dfs_financial_transaction t
     WHERE t.account_id = a.id AND t.status = 'completed'
    )                   AS total_transactions,
    (SELECT COALESCE(SUM(t.amount), 0)
     FROM dfs_financial_transaction t
     WHERE t.account_id = a.id AND t.direction = 'inflow' AND t.status = 'completed'
    )                   AS total_inflow,
    (SELECT COALESCE(SUM(t.amount), 0)
     FROM dfs_financial_transaction t
     WHERE t.account_id = a.id AND t.direction = 'outflow' AND t.status = 'completed'
    )                   AS total_outflow,
    (SELECT MAX(t.completed_at)
     FROM dfs_financial_transaction t
     WHERE t.account_id = a.id AND t.status = 'completed'
    )                   AS last_transaction_at,
    a.created_at
FROM farm_financial_account a
LEFT JOIN location l ON l.id = a.location_id
LEFT JOIN dfs_currency dc ON dc.code = a.currency_code
WHERE a.status = 'active'
ORDER BY a.created_at DESC;

-- Active insurance policies with risk scores and coverage
CREATE OR REPLACE VIEW v_insurance_portfolio AS
SELECT
    p.id                AS policy_id,
    p.policy_number,
    p.location_id,
    l.name              AS location_name,
    pt.code             AS product_code,
    pt.name             AS product_name,
    pt.coverage_type,
    p.crop_type,
    p.area_hectares,
    p.sum_insured,
    p.premium_amount,
    p.premium_frequency,
    p.deductible_pct,
    p.risk_rating,
    p.risk_score,
    p.predicted_yield,
    p.yield_unit,
    p.yield_source,
    p.trigger_type,
    p.trigger_param,
    p.trigger_value,
    p.coverage_start,
    p.coverage_end,
    p.status,
    p.premium_paid,
    p.premium_paid_at,
    (SELECT COUNT(*)
     FROM insurance_claim c
     WHERE c.policy_id = p.id
    )                   AS claims_filed,
    (SELECT COALESCE(SUM(c.payout_amount), 0)
     FROM insurance_claim c
     WHERE c.policy_id = p.id AND c.status = 'paid'
    )                   AS total_payouts,
    p.created_at
FROM crop_insurance_policy p
LEFT JOIN location l ON l.id = p.location_id
LEFT JOIN dfs_insurance_product_type pt ON pt.id = p.product_type_id
WHERE p.status IN ('issued', 'active')
ORDER BY p.created_at DESC;

-- Active loans with repayment status
CREATE OR REPLACE VIEW v_lending_portfolio AS
SELECT
    dl.id               AS loan_id,
    dl.loan_number,
    dl.location_id,
    l.name              AS location_name,
    dl.loan_type,
    dl.principal,
    dl.currency_code,
    dl.interest_rate_pct,
    dl.interest_type,
    dl.term_months,
    dl.disbursement_date,
    dl.maturity_date,
    dl.eligibility_score,
    dl.disbursed_amount,
    dl.status,
    dl.penalty_accrued,
    (SELECT COUNT(*)
     FROM repayment_schedule rs
     WHERE rs.loan_id = dl.id
    )                   AS total_installments,
    (SELECT COUNT(*)
     FROM repayment_schedule rs
     WHERE rs.loan_id = dl.id AND rs.status = 'paid'
    )                   AS paid_installments,
    (SELECT COALESCE(SUM(rs.total_paid), 0)
     FROM repayment_schedule rs
     WHERE rs.loan_id = dl.id
    )                   AS total_repaid,
    (SELECT COALESCE(SUM(rs.total_due), 0)
     FROM repayment_schedule rs
     WHERE rs.loan_id = dl.id AND rs.status = 'paid'
    )                   AS principal_repaid,
    (SELECT COALESCE(SUM(rs.total_due - rs.total_paid), 0)
     FROM repayment_schedule rs
     WHERE rs.loan_id = dl.id AND rs.status != 'paid'
    )                   AS outstanding_balance,
    (SELECT MIN(rs.due_date)
     FROM repayment_schedule rs
     WHERE rs.loan_id = dl.id AND rs.status != 'paid'
    )                   AS next_payment_due,
    (SELECT COUNT(*)
     FROM repayment_schedule rs
     WHERE rs.loan_id = dl.id AND rs.status = 'overdue'
    )                   AS overdue_installments,
    dl.created_at
FROM digital_lending dl
LEFT JOIN location l ON l.id = dl.location_id
WHERE dl.status NOT IN ('draft', 'rejected', 'written_off')
ORDER BY dl.created_at DESC;

-- ============================================================
-- Schema version
-- ============================================================

INSERT INTO schema_version (version, description, applied_by)
VALUES ('digital-finance-v1', 'Digital Financial Services: accounts, transactions, insurance, lending, collateral', 'schema 141')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;

COMMIT;
