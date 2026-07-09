-- ============================================================
-- 078_carbon_credits.sql — Tokenized Carbon Credits
-- with Auto-Adjustment
-- ============================================================
-- Credit tracking, lifecycle management, and auto-adjustment
-- when new measurements arrive.  Credits are representations
-- of verified sequestration, not independent financial instruments.
-- ============================================================

-- 1. Carbon credit core record
CREATE TABLE IF NOT EXISTS carbon_credit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,

    -- Credit identity
    credit_code VARCHAR(50) NOT NULL UNIQUE,
    vintage_year INTEGER NOT NULL,
    methodology VARCHAR(255) NOT NULL,
    methodology_version VARCHAR(50),

    -- Carbon quantities (tonnes CO2e)
    initial_sequestration_tonnes NUMERIC(12,4) NOT NULL,
    current_sequestration_tonnes NUMERIC(12,4) NOT NULL,
    adjustment_margin_pct NUMERIC(5,2) DEFAULT 10.00,
    buffer_pool_pct NUMERIC(5,2) DEFAULT 20.00,
    issuable_tonnes NUMERIC(12,4) NOT NULL,
    retired_tonnes NUMERIC(12,4) DEFAULT 0,
    available_tonnes NUMERIC(12,4) GENERATED ALWAYS AS (issuable_tonnes - retired_tonnes) STORED,

    -- Pricing (configurable, market-adjusted)
    price_per_tonne_usd NUMERIC(10,2) DEFAULT 25.00,
    market_price_per_tonne_usd NUMERIC(10,2),
    effective_price_per_tonne_usd NUMERIC(10,2) GENERATED ALWAYS AS (
        COALESCE(market_price_per_tonne_usd, price_per_tonne_usd)
    ) STORED,
    total_value_usd NUMERIC(15,2) GENERATED ALWAYS AS (
        available_tonnes * COALESCE(market_price_per_tonne_usd, price_per_tonne_usd)
    ) STORED,

    -- Evidence chain
    climate_impact_summary_id UUID REFERENCES climate_impact_summary(id) ON DELETE SET NULL,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    external_verifier TEXT,
    methodology_ref TEXT,

    -- Attestation linkage
    attestation_uid VARCHAR(66),
    attestation_schema_id UUID REFERENCES attestation_schema(id),
    attested_at TIMESTAMPTZ,

    -- On-chain token pointer (optional)
    token_chain VARCHAR(50),
    token_contract VARCHAR(42),
    token_id VARCHAR(100),
    token_minted_at TIMESTAMPTZ,

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'draft',
    reviewer_id UUID,
    review_date DATE,
    review_notes TEXT,
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_carbon_credit_location ON carbon_credit(location_id);
CREATE INDEX IF NOT EXISTS idx_carbon_credit_farm ON carbon_credit(farm_id);
CREATE INDEX IF NOT EXISTS idx_carbon_credit_vintage ON carbon_credit(vintage_year);
CREATE INDEX IF NOT EXISTS idx_carbon_credit_status ON carbon_credit(status);
CREATE INDEX IF NOT EXISTS idx_carbon_credit_methodology ON carbon_credit(methodology);
CREATE INDEX IF NOT EXISTS idx_carbon_credit_code ON carbon_credit(credit_code);
CREATE INDEX IF NOT EXISTS idx_carbon_credit_attestation ON carbon_credit(attestation_uid);

ALTER TABLE carbon_credit DROP CONSTRAINT IF EXISTS chk_carbon_credit_lifecycle;
ALTER TABLE carbon_credit ADD CONSTRAINT chk_carbon_credit_lifecycle
    CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'retired', 'revoked', 'rejected'));

ALTER TABLE carbon_credit DROP CONSTRAINT IF EXISTS chk_carbon_credit_vintage;
ALTER TABLE carbon_credit ADD CONSTRAINT chk_carbon_credit_vintage
    CHECK (vintage_year >= 2020 AND vintage_year <= 2100);

ALTER TABLE carbon_credit DROP CONSTRAINT IF EXISTS chk_carbon_credit_margin;
ALTER TABLE carbon_credit ADD CONSTRAINT chk_carbon_credit_margin
    CHECK (adjustment_margin_pct >= 0 AND adjustment_margin_pct <= 50);

ALTER TABLE carbon_credit DROP CONSTRAINT IF EXISTS chk_carbon_credit_buffer;
ALTER TABLE carbon_credit ADD CONSTRAINT chk_carbon_credit_buffer
    CHECK (buffer_pool_pct >= 0 AND buffer_pool_pct <= 50);

ALTER TABLE carbon_credit DROP CONSTRAINT IF EXISTS chk_carbon_credit_quantities;
ALTER TABLE carbon_credit ADD CONSTRAINT chk_carbon_credit_quantities
    CHECK (
        initial_sequestration_tonnes >= 0
        AND current_sequestration_tonnes >= 0
        AND issuable_tonnes >= 0
        AND retired_tonnes >= 0
        AND retired_tonnes <= issuable_tonnes
    );

ALTER TABLE carbon_credit DROP CONSTRAINT IF EXISTS chk_carbon_credit_public_level6;
ALTER TABLE carbon_credit ADD CONSTRAINT chk_carbon_credit_public_level6 CHECK (
    status != 'published'
    OR (
        evidence_maturity = 6
        AND NULLIF(TRIM(COALESCE(external_verifier, '')), '') IS NOT NULL
        AND NULLIF(TRIM(COALESCE(methodology_ref, '')), '') IS NOT NULL
    )
);

-- 2. Credit adjustment audit trail
CREATE TABLE IF NOT EXISTS credit_adjustment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_id UUID NOT NULL REFERENCES carbon_credit(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,

    adjustment_type VARCHAR(50) NOT NULL,
    previous_sequestration_tonnes NUMERIC(12,4) NOT NULL,
    new_sequestration_tonnes NUMERIC(12,4) NOT NULL,
    delta_tonnes NUMERIC(12,4) NOT NULL,
    delta_pct NUMERIC(7,4) NOT NULL,

    trigger_source VARCHAR(100) NOT NULL,
    trigger_record_id UUID,
    trigger_snapshot JSONB,

    within_margin BOOLEAN NOT NULL,
    requires_review BOOLEAN NOT NULL,

    reviewer_id UUID,
    review_date DATE,
    review_result VARCHAR(50),
    review_notes TEXT,

    adjustment_attestation_uid VARCHAR(66),
    adjustment_attested_at TIMESTAMPTZ,

    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_credit_adj_credit ON credit_adjustment(credit_id);
CREATE INDEX IF NOT EXISTS idx_credit_adj_location ON credit_adjustment(location_id);
CREATE INDEX IF NOT EXISTS idx_credit_adj_type ON credit_adjustment(adjustment_type);
CREATE INDEX IF NOT EXISTS idx_credit_adj_trigger ON credit_adjustment(trigger_source);
CREATE INDEX IF NOT EXISTS idx_credit_adj_status ON credit_adjustment(status);

ALTER TABLE credit_adjustment DROP CONSTRAINT IF EXISTS chk_credit_adj_lifecycle;
ALTER TABLE credit_adjustment ADD CONSTRAINT chk_credit_adj_lifecycle
    CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE credit_adjustment DROP CONSTRAINT IF EXISTS chk_credit_adj_type;
ALTER TABLE credit_adjustment ADD CONSTRAINT chk_credit_adj_type
    CHECK (adjustment_type IN ('measurement_update', 'methodology_change', 'reversal', 'correction'));

ALTER TABLE credit_adjustment DROP CONSTRAINT IF EXISTS chk_credit_adj_trigger;
ALTER TABLE credit_adjustment ADD CONSTRAINT chk_credit_adj_trigger
    CHECK (trigger_source IN (
        'tree_inventory', 'soil_carbon_measurement', 'ghg_emissions_inventory',
        'climate_impact_summary', 'remote_sensing', 'manual_override'
    ));

-- 3. Credit retirement ledger
CREATE TABLE IF NOT EXISTS credit_retirement (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_id UUID NOT NULL REFERENCES carbon_credit(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,

    retirement_reason VARCHAR(100) NOT NULL,
    retired_tonnes NUMERIC(12,4) NOT NULL CHECK (retired_tonnes > 0),
    retirement_value_usd NUMERIC(15,2),

    beneficiary_name VARCHAR(255),
    beneficiary_wallet VARCHAR(42),
    retirement_statement TEXT,

    evidence_cid TEXT,
    evidence_hash VARCHAR(64),

    retirement_attestation_uid VARCHAR(66),
    retired_onchain_at TIMESTAMPTZ,
    retirement_tx_hash VARCHAR(66),

    status VARCHAR(50) DEFAULT 'draft',
    reviewer_id UUID,
    review_date DATE,
    review_notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_credit_retire_credit ON credit_retirement(credit_id);
CREATE INDEX IF NOT EXISTS idx_credit_retire_location ON credit_retirement(location_id);
CREATE INDEX IF NOT EXISTS idx_credit_retire_reason ON credit_retirement(retirement_reason);
CREATE INDEX IF NOT EXISTS idx_credit_retire_status ON credit_retirement(status);

ALTER TABLE credit_retirement DROP CONSTRAINT IF EXISTS chk_credit_retire_lifecycle;
ALTER TABLE credit_retirement ADD CONSTRAINT chk_credit_retire_lifecycle
    CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

-- 4. Credit transfer ledger
CREATE TABLE IF NOT EXISTS credit_transfer (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_id UUID NOT NULL REFERENCES carbon_credit(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,

    transfer_type VARCHAR(50) NOT NULL,
    transferred_tonnes NUMERIC(12,4) NOT NULL CHECK (transferred_tonnes > 0),
    transfer_value_usd NUMERIC(15,2),
    price_per_tonne_usd NUMERIC(10,2),

    from_wallet VARCHAR(42),
    to_wallet VARCHAR(42),
    from_entity VARCHAR(255),
    to_entity VARCHAR(255),

    revenue_event_id UUID REFERENCES revenue_event(id) ON DELETE SET NULL,
    treasury_event_id UUID REFERENCES treasury_event(id) ON DELETE SET NULL,

    evidence_cid TEXT,
    evidence_hash VARCHAR(64),
    tx_hash VARCHAR(66),
    chain VARCHAR(50),

    status VARCHAR(50) DEFAULT 'draft',
    reviewer_id UUID,
    review_date DATE,
    review_notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_credit_xfer_credit ON credit_transfer(credit_id);
CREATE INDEX IF NOT EXISTS idx_credit_xfer_location ON credit_transfer(location_id);
CREATE INDEX IF NOT EXISTS idx_credit_xfer_type ON credit_transfer(transfer_type);
CREATE INDEX IF NOT EXISTS idx_credit_xfer_status ON credit_transfer(status);

ALTER TABLE credit_transfer DROP CONSTRAINT IF EXISTS chk_credit_xfer_lifecycle;
ALTER TABLE credit_transfer ADD CONSTRAINT chk_credit_xfer_lifecycle
    CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE credit_transfer DROP CONSTRAINT IF EXISTS chk_credit_xfer_type;
ALTER TABLE credit_transfer ADD CONSTRAINT chk_credit_xfer_type
    CHECK (transfer_type IN ('allocation', 'sale', 'grant', 'internal_rebalance'));

-- 5. Public views
CREATE OR REPLACE VIEW v_public_carbon_credit_inventory AS
SELECT
    cc.id,
    cc.credit_code,
    cc.location_id,
    l.name AS location_name,
    cc.vintage_year,
    cc.methodology,
    cc.current_sequestration_tonnes,
    cc.issuable_tonnes,
    cc.retired_tonnes,
    cc.available_tonnes,
    cc.effective_price_per_tonne_usd,
    cc.total_value_usd,
    cc.buffer_pool_pct,
    cc.evidence_maturity,
    em.label AS evidence_maturity_label,
    cc.external_verifier,
    cc.methodology_ref,
    cc.attestation_uid,
    cc.attested_at,
    cc.status
FROM carbon_credit cc
JOIN location l ON l.id = cc.location_id
LEFT JOIN evidence_maturity_level em ON em.level = cc.evidence_maturity
WHERE cc.status = 'published'
  AND cc.evidence_maturity = 6
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = cc.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_carbon_credit_balance AS
SELECT
    cc.location_id,
    l.name AS location_name,
    COUNT(*) AS total_credits,
    SUM(cc.issuable_tonnes) AS total_issuable_tonnes,
    SUM(cc.retired_tonnes) AS total_retired_tonnes,
    SUM(cc.available_tonnes) AS total_available_tonnes,
    SUM(cc.total_value_usd) AS total_value_usd,
    COUNT(*) FILTER (WHERE cc.status = 'published') AS published_count,
    COUNT(*) FILTER (WHERE cc.status = 'retired') AS retired_count,
    MAX(cc.vintage_year) AS latest_vintage
FROM carbon_credit cc
JOIN location l ON l.id = cc.location_id
WHERE cc.status IN ('published', 'retired')
GROUP BY cc.location_id, l.name;

CREATE OR REPLACE VIEW v_credit_adjustment_history AS
SELECT
    ca.credit_id,
    cc.credit_code,
    ca.adjustment_type,
    ca.previous_sequestration_tonnes,
    ca.new_sequestration_tonnes,
    ca.delta_tonnes,
    ca.delta_pct,
    ca.within_margin,
    ca.requires_review,
    ca.trigger_source,
    ca.review_result,
    ca.created_at
FROM credit_adjustment ca
JOIN carbon_credit cc ON cc.id = ca.credit_id
WHERE ca.status IN ('verified', 'published')
ORDER BY ca.created_at DESC;
