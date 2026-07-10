-- ============================================================
-- 089_abundance_economics.sql — Coin Economics
-- ============================================================

-- 1. Coin inflation event
CREATE TABLE IF NOT EXISTS coin_inflation_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    validation_id UUID REFERENCES periodic_validation(id) ON DELETE SET NULL,
    estimate_id UUID REFERENCES impact_estimate_post(id) ON DELETE SET NULL,
    amount NUMERIC(18,8) NOT NULL,
    recipient_address VARCHAR(42),
    recipient_evaluator_id UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    basis_impact_score NUMERIC(12,4),
    inflation_rate_at_issuance NUMERIC(8,6),
    attestation_uid VARCHAR(66),
    chain VARCHAR(50) DEFAULT 'celo',
    status VARCHAR(50) DEFAULT 'pending',
    issued_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS cie_validation ON coin_inflation_event(validation_id);
CREATE INDEX IF NOT EXISTS cie_recipient ON coin_inflation_event(recipient_address);
CREATE INDEX IF NOT EXISTS cie_status ON coin_inflation_event(status);

ALTER TABLE coin_inflation_event DROP CONSTRAINT IF EXISTS chk_cie_status;
ALTER TABLE coin_inflation_event ADD CONSTRAINT chk_cie_status CHECK (status IN ('pending', 'issued', 'confirmed', 'failed', 'reversed'));

-- 2. Inflation schedule
CREATE TABLE IF NOT EXISTS inflation_schedule (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schedule_name VARCHAR(255) NOT NULL,
    max_supply NUMERIC(18,8),
    initial_inflation_rate NUMERIC(8,6) NOT NULL,
    decay_rate NUMERIC(8,6) DEFAULT 0,
    target_value_growth_pct NUMERIC(8,4),
    effective_from DATE NOT NULL,
    effective_until DATE,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE inflation_schedule DROP CONSTRAINT IF EXISTS chk_is_status;
ALTER TABLE inflation_schedule ADD CONSTRAINT chk_is_status CHECK (status IN ('active', 'paused', 'expired'));

-- 3. Validator compensation detail
CREATE TABLE IF NOT EXISTS validator_compensation_detail (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    compensation_id UUID NOT NULL REFERENCES validator_compensation(id) ON DELETE CASCADE,
    evaluator_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    accuracy_score NUMERIC(5,4) NOT NULL,
    overestimate_delta NUMERIC(12,4) DEFAULT 0,
    overestimate_penalty NUMERIC(12,4) DEFAULT 0,
    accuracy_bonus NUMERIC(12,4) DEFAULT 0,
    base_amount NUMERIC(12,4) NOT NULL,
    total_amount NUMERIC(12,4) NOT NULL,
    expertise_points_earned NUMERIC(8,4),
    reason TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS vcd_compensation ON validator_compensation_detail(compensation_id);
CREATE INDEX IF NOT EXISTS vcd_evaluator ON validator_compensation_detail(evaluator_id);

-- 4. Incentive alignment log
CREATE TABLE IF NOT EXISTS incentive_alignment_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evaluator_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    round_id UUID REFERENCES validation_round(id) ON DELETE SET NULL,
    accuracy_score NUMERIC(5,4),
    compensation_amount NUMERIC(12,4),
    expertise_change NUMERIC(8,4),
    alignment_score NUMERIC(5,4),
    period_start DATE,
    period_end DATE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ial_evaluator ON incentive_alignment_log(evaluator_id);
CREATE INDEX IF NOT EXISTS ial_period ON incentive_alignment_log(period_start, period_end);

-- 5. Funding request
CREATE TABLE IF NOT EXISTS funding_request (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposer_id UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    project_hash VARCHAR(66),
    project_description TEXT,
    expected_impact_score NUMERIC(12,4) NOT NULL,
    credibility_score NUMERIC(5,4),
    requested_amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    timeline_months INTEGER,
    contributor_breakdown JSONB,
    investor_terms TEXT,
    risk_assessment NUMERIC(5,4),
    validation_round_id UUID REFERENCES validation_round(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS fr_proposer ON funding_request(proposer_id);
CREATE INDEX IF NOT EXISTS fr_location ON funding_request(location_id);
CREATE INDEX IF NOT EXISTS fr_status ON funding_request(status);

ALTER TABLE funding_request DROP CONSTRAINT IF EXISTS chk_fr_status;
ALTER TABLE funding_request ADD CONSTRAINT chk_fr_status CHECK (status IN (
    'draft', 'submitted', 'validating', 'open_for_bids', 'funded', 'completed', 'cancelled'
));

-- 6. Funding bid
CREATE TABLE IF NOT EXISTS funding_bid (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL REFERENCES funding_request(id) ON DELETE CASCADE,
    investor_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    bid_amount NUMERIC(15,2) NOT NULL,
    expected_return_pct NUMERIC(5,2),
    terms TEXT,
    risk_assessment NUMERIC(5,4),
    status VARCHAR(50) DEFAULT 'submitted',
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS fb_request ON funding_bid(request_id);
CREATE INDEX IF NOT EXISTS fb_investor ON funding_bid(investor_id);
CREATE INDEX IF NOT EXISTS fb_status ON funding_bid(status);

ALTER TABLE funding_bid DROP CONSTRAINT IF EXISTS chk_fb_status;
ALTER TABLE funding_bid ADD CONSTRAINT chk_fb_status CHECK (status IN ('submitted', 'accepted', 'rejected', 'withdrawn', 'executed'));

-- 7. Fund distribution
CREATE TABLE IF NOT EXISTS fund_distribution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL REFERENCES funding_request(id) ON DELETE CASCADE,
    project_id UUID,
    entity_id UUID NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    share_pct NUMERIC(5,2) NOT NULL,
    share_amount NUMERIC(15,2),
    consensus_status VARCHAR(50) DEFAULT 'pending',
    consensus_reached_at TIMESTAMPTZ,
    distribution_tx_hash VARCHAR(66),
    status VARCHAR(50) DEFAULT 'pending',
    distributed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS fd_request ON fund_distribution(request_id);
CREATE INDEX IF NOT EXISTS fd_entity ON fund_distribution(entity_id);
CREATE INDEX IF NOT EXISTS fd_status ON fund_distribution(status);

ALTER TABLE fund_distribution DROP CONSTRAINT IF EXISTS chk_fd_entity_type;
ALTER TABLE fund_distribution ADD CONSTRAINT chk_fd_entity_type CHECK (entity_type IN ('contributor', 'influencer', 'investor', 'commons', 'other'));

ALTER TABLE fund_distribution DROP CONSTRAINT IF EXISTS chk_fd_consensus;
ALTER TABLE fund_distribution ADD CONSTRAINT chk_fd_consensus CHECK (consensus_status IN ('pending', 'agreed', 'disputed', 'mediated'));

ALTER TABLE fund_distribution DROP CONSTRAINT IF EXISTS chk_fd_status;
ALTER TABLE fund_distribution ADD CONSTRAINT chk_fd_status CHECK (status IN ('pending', 'distributed', 'held', 'released'));
