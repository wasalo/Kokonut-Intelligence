-- ============================================================
-- 087_abundance_validation.sql — 3-Tier Validation
-- ============================================================

-- 1. Validation round
CREATE TABLE IF NOT EXISTS validation_round (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    estimate_id UUID NOT NULL REFERENCES impact_estimate_post(id) ON DELETE CASCADE,
    tier INTEGER NOT NULL CHECK (tier IN (1, 2, 3)),
    round_number INTEGER NOT NULL DEFAULT 1,
    required_expertise NUMERIC(12,4),
    committed_expertise NUMERIC(12,4) DEFAULT 0,
    commit_hash VARCHAR(66),
    commit_revealed BOOLEAN DEFAULT FALSE,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    review_deadline TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'pending',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS vr_estimate ON validation_round(estimate_id);
CREATE INDEX IF NOT EXISTS vr_tier ON validation_round(tier);
CREATE INDEX IF NOT EXISTS vr_status ON validation_round(status);

ALTER TABLE validation_round DROP CONSTRAINT IF EXISTS chk_vr_tier;
ALTER TABLE validation_round ADD CONSTRAINT chk_vr_tier CHECK (tier IN (1, 2, 3));

ALTER TABLE validation_round DROP CONSTRAINT IF EXISTS chk_vr_status;
ALTER TABLE validation_round ADD CONSTRAINT chk_vr_status CHECK (status IN (
    'pending', 'committing', 'committed', 'revealing', 'revealed', 'reviewing', 'completed', 'failed'
));

-- 2. Validator selection
CREATE TABLE IF NOT EXISTS validator_selection (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    round_id UUID NOT NULL REFERENCES validation_round(id) ON DELETE CASCADE,
    evaluator_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    tier INTEGER NOT NULL CHECK (tier IN (1, 2, 3)),
    slot_number INTEGER,
    expertise_score NUMERIC(5,4),
    commitment_amount NUMERIC(12,4),
    status VARCHAR(50) DEFAULT 'selected',
    selected_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS vs_round ON validator_selection(round_id);
CREATE INDEX IF NOT EXISTS vs_evaluator ON validator_selection(evaluator_id);
CREATE INDEX IF NOT EXISTS vs_tier ON validator_selection(tier);

ALTER TABLE validator_selection DROP CONSTRAINT IF EXISTS chk_vs_status;
ALTER TABLE validator_selection ADD CONSTRAINT chk_vs_status CHECK (status IN (
    'selected', 'committed', 'revealed', 'reviewing', 'reviewed', 'penalized', 'withdrawn'
));

-- 3. Validator review
CREATE TABLE IF NOT EXISTS validator_review (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    round_id UUID NOT NULL REFERENCES validation_round(id) ON DELETE CASCADE,
    validator_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    tier INTEGER NOT NULL CHECK (tier IN (1, 2, 3)),
    credibility_score NUMERIC(5,4),
    impact_score NUMERIC(12,4),
    category_scores JSONB,
    sources TEXT[],
    confidence_level VARCHAR(50),
    review_text TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    submitted_at TIMESTAMPTZ,
    attestation_uid VARCHAR(66),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS vr2_round ON validator_review(round_id);
CREATE INDEX IF NOT EXISTS vr2_validator ON validator_review(validator_id);
CREATE INDEX IF NOT EXISTS vr2_tier ON validator_review(tier);

ALTER TABLE validator_review DROP CONSTRAINT IF EXISTS chk_vr2_confidence;
ALTER TABLE validator_review ADD CONSTRAINT chk_vr2_confidence CHECK (confidence_level IS NULL OR confidence_level IN ('high', 'medium', 'low'));

ALTER TABLE validator_review DROP CONSTRAINT IF EXISTS chk_vr2_status;
ALTER TABLE validator_review ADD CONSTRAINT chk_vr2_status CHECK (status IN ('draft', 'submitted', 'attested', 'challenged', 'upheld', 'overturned'));

-- 4. Quadratic vote
CREATE TABLE IF NOT EXISTS quadratic_vote (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    round_id UUID NOT NULL REFERENCES validation_round(id) ON DELETE CASCADE,
    voter_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    review_id UUID REFERENCES validator_review(id) ON DELETE CASCADE,
    vote_weight NUMERIC(5,4) NOT NULL CHECK (vote_weight > 0 AND vote_weight <= 1),
    sqrt_weight NUMERIC(8,6) NOT NULL,
    justification TEXT,
    vote_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'cast',
    cast_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS qv_round ON quadratic_vote(round_id);
CREATE INDEX IF NOT EXISTS qv_voter ON quadratic_vote(voter_id);
CREATE INDEX IF NOT EXISTS qv_review ON quadratic_vote(review_id);

ALTER TABLE quadratic_vote DROP CONSTRAINT IF EXISTS chk_qv_type;
ALTER TABLE quadratic_vote ADD CONSTRAINT chk_qv_type CHECK (vote_type IN ('accuracy', 'penalty', 'weight_adjustment'));

ALTER TABLE quadratic_vote DROP CONSTRAINT IF EXISTS chk_qv_status;
ALTER TABLE quadratic_vote ADD CONSTRAINT chk_qv_status CHECK (status IN ('cast', 'counted', 'disputed', 'invalid'));

-- 5. Validator compensation
CREATE TABLE IF NOT EXISTS validator_compensation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    round_id UUID NOT NULL REFERENCES validation_round(id) ON DELETE CASCADE,
    evaluator_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    tier INTEGER NOT NULL CHECK (tier IN (1, 2, 3)),
    base_compensation NUMERIC(12,4),
    accuracy_bonus NUMERIC(12,4) DEFAULT 0,
    overestimate_penalty NUMERIC(12,4) DEFAULT 0,
    total_compensation NUMERIC(12,4) NOT NULL,
    expertise_earned NUMERIC(5,4),
    deposit_refunded BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'pending',
    distributed_at TIMESTAMPTZ,
    attestation_uid VARCHAR(66),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS vc_round ON validator_compensation(round_id);
CREATE INDEX IF NOT EXISTS vc_evaluator ON validator_compensation(evaluator_id);
CREATE INDEX IF NOT EXISTS vc_status ON validator_compensation(status);

ALTER TABLE validator_compensation DROP CONSTRAINT IF EXISTS chk_vc_status;
ALTER TABLE validator_compensation ADD CONSTRAINT chk_vc_status CHECK (status IN (
    'pending', 'calculated', 'distributed', 'disputed', 'forfeited'
));
