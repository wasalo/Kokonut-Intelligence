-- Credit Class / Batch Hierarchy
-- Three-tier model: credit_class (methodology) -> credit_batch (issuance) -> carbon_credit (identity)
-- Aligned with Regen Network Framework Working Group CreditClassInfo schema

-- ============================================================
-- credit_class
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_class (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    url TEXT,
    methodology VARCHAR(255) NOT NULL,
    methodology_version VARCHAR(50),
    methodology_ref TEXT,
    credit_type VARCHAR(50) NOT NULL,
    ecosystem_types TEXT[],
    eligible_activities TEXT[],
    crediting_period_years INTEGER DEFAULT 10,
    registry_slug VARCHAR(100) UNIQUE,
    issuer_wallet VARCHAR(42),
    governance_mechanism VARCHAR(100),
    approval_required BOOLEAN DEFAULT TRUE,
    primary_impact_type VARCHAR(50),
    primary_impact_name VARCHAR(255),
    primary_impact_sdgs INTEGER[],
    attestation_uid VARCHAR(66),
    chain VARCHAR(50) DEFAULT 'celo',
    status VARCHAR(50) DEFAULT 'draft',
    admin_address VARCHAR(42),
    credit_type_id UUID REFERENCES credit_type(id),
    allowlist_required BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    CONSTRAINT chk_credit_class_type CHECK (credit_type IN ('carbon', 'biodiversity', 'water', 'soil', 'mixed')),
    CONSTRAINT chk_credit_class_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'deprecated'))
);

CREATE INDEX idx_cc_type ON credit_class(credit_type);
CREATE INDEX idx_cc_status ON credit_class(status);
CREATE INDEX idx_cc_methodology ON credit_class(methodology);

-- ============================================================
-- credit_class_cobenefit (hasCoBenefits)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_class_cobenefit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_class_id UUID NOT NULL REFERENCES credit_class(id) ON DELETE CASCADE,
    impact_name VARCHAR(255) NOT NULL,
    impact_type VARCHAR(50),
    sdg_numbers INTEGER[],
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ccc_class ON credit_class_cobenefit(credit_class_id);

-- ============================================================
-- credit_class_registry (hasSourceRegistry)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_class_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_class_id UUID NOT NULL REFERENCES credit_class(id) ON DELETE CASCADE,
    registry_name VARCHAR(255) NOT NULL,
    registry_url TEXT,
    is_source BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ccr_class ON credit_class_registry(credit_class_id);

-- ============================================================
-- crediting_program (managedUnderProgram)
-- ============================================================
CREATE TABLE IF NOT EXISTS crediting_program (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_class_id UUID NOT NULL REFERENCES credit_class(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    url TEXT,
    version VARCHAR(50),
    identifier VARCHAR(100),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cp_class ON crediting_program(credit_class_id);

-- ============================================================
-- credit_protocol (hasCreditProtocol)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_protocol (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_class_id UUID NOT NULL REFERENCES credit_class(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    url TEXT,
    version VARCHAR(50),
    identifier VARCHAR(100),
    description TEXT,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cpr_class ON credit_protocol(credit_class_id);

-- ============================================================
-- credit_class_methodology (hasApprovedMethodologies)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_class_methodology (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_class_id UUID NOT NULL REFERENCES credit_class(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    url TEXT,
    version VARCHAR(50),
    identifier VARCHAR(100),
    description TEXT,
    is_approved BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ccm_class ON credit_class_methodology(credit_class_id);

-- ============================================================
-- buffer_pool_account (hasBufferPoolAccounts)
-- ============================================================
CREATE TABLE IF NOT EXISTS buffer_pool_account (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_class_id UUID NOT NULL REFERENCES credit_class(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    wallet_address VARCHAR(42),
    pool_allocation VARCHAR(100),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_bpa_class ON buffer_pool_account(credit_class_id);

-- ============================================================
-- credit_batch
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_batch (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    credit_class_id UUID NOT NULL REFERENCES credit_class(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    batch_code VARCHAR(50) NOT NULL UNIQUE,
    vintage_year INTEGER NOT NULL,
    total_quantity NUMERIC(14,4) NOT NULL,
    issued_quantity NUMERIC(14,4) DEFAULT 0,
    retired_quantity NUMERIC(14,4) DEFAULT 0,
    cancelled_quantity NUMERIC(14,4) DEFAULT 0,
    available_quantity NUMERIC(14,4) GENERATED ALWAYS AS (
        issued_quantity - retired_quantity - cancelled_quantity
    ) STORED,
    unit VARCHAR(50) DEFAULT 'tonneCO2e',
    monitoring_report_cid TEXT,
    verification_report_cid TEXT,
    evidence_maturity INTEGER DEFAULT 1,
    attestation_uid VARCHAR(66),
    chain VARCHAR(50) DEFAULT 'celo',
    minted_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    CONSTRAINT chk_batch_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'retired', 'cancelled'))
);

CREATE INDEX idx_cb_class ON credit_batch(credit_class_id);
CREATE INDEX idx_cb_location ON credit_batch(location_id);
CREATE INDEX idx_cb_vintage ON credit_batch(vintage_year);
CREATE INDEX idx_cb_status ON credit_batch(status);

-- Link existing carbon_credit to hierarchy
ALTER TABLE carbon_credit ADD COLUMN IF NOT EXISTS credit_class_id UUID REFERENCES credit_class(id);
ALTER TABLE carbon_credit ADD COLUMN IF NOT EXISTS credit_batch_id UUID REFERENCES credit_batch(id);
