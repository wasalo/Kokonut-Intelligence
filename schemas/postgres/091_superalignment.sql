-- ============================================================
-- 091_superalignment.sql — Superalignment Framework
-- ============================================================

-- 1. Ecosystem registry
CREATE TABLE IF NOT EXISTS ecosystem_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ecosystem_name VARCHAR(255) NOT NULL UNIQUE,
    chain VARCHAR(50),
    currency_name VARCHAR(100),
    currency_symbol VARCHAR(20),
    chain_id INTEGER,
    contract_address VARCHAR(42),
    participation_rules TEXT,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE ecosystem_registry DROP CONSTRAINT IF EXISTS chk_er_status;
ALTER TABLE ecosystem_registry ADD CONSTRAINT chk_er_status CHECK (status IN ('active', 'inactive', 'deprecated'));

-- 2. Cross-ecosystem impact
CREATE TABLE IF NOT EXISTS cross_ecosystem_impact (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contributor_id UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    source_ecosystem_id UUID NOT NULL REFERENCES ecosystem_registry(id) ON DELETE CASCADE,
    target_ecosystem_id UUID NOT NULL REFERENCES ecosystem_registry(id) ON DELETE CASCADE,
    project_hash VARCHAR(66),
    impact_score NUMERIC(12,4) NOT NULL,
    impact_category VARCHAR(100),
    propagation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    attestation_uid VARCHAR(66),
    status VARCHAR(50) DEFAULT 'recorded',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS cei_contributor ON cross_ecosystem_impact(contributor_id);
CREATE INDEX IF NOT EXISTS cei_source ON cross_ecosystem_impact(source_ecosystem_id);
CREATE INDEX IF NOT EXISTS cei_target ON cross_ecosystem_impact(target_ecosystem_id);

ALTER TABLE cross_ecosystem_impact DROP CONSTRAINT IF EXISTS chk_cei_status;
ALTER TABLE cross_ecosystem_impact ADD CONSTRAINT chk_cei_status CHECK (status IN ('recorded', 'validated', 'disputed'));

-- 3. Superalignment score
CREATE TABLE IF NOT EXISTS superalignment_score (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ecosystem_id UUID NOT NULL REFERENCES ecosystem_registry(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    participant_alignment_score NUMERIC(5,2) CHECK (participant_alignment_score >= 0 AND participant_alignment_score <= 100),
    cross_ecosystem_alignment_score NUMERIC(5,2) CHECK (cross_ecosystem_alignment_score >= 0 AND cross_ecosystem_alignment_score <= 100),
    composite_alignment_score NUMERIC(5,2) CHECK (composite_alignment_score >= 0 AND composite_alignment_score <= 100),
    adversarial_signals_detected INTEGER DEFAULT 0,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ss_ecosystem ON superalignment_score(ecosystem_id);
CREATE INDEX IF NOT EXISTS ss_period ON superalignment_score(period_start, period_end);
