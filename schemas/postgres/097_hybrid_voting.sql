-- ============================================================
-- 097_hybrid_voting.sql — Hybrid DAO Voting
-- ============================================================

-- 1. DAO vote (extends governance_event with QV)
CREATE TABLE IF NOT EXISTS dao_vote (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id VARCHAR(100) NOT NULL,
    voter_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    vote_weight NUMERIC(5,4) NOT NULL CHECK (vote_weight > 0 AND vote_weight <= 1),
    sqrt_weight NUMERIC(8,6) NOT NULL,
    vote_choice VARCHAR(50) NOT NULL,
    voting_method VARCHAR(50) NOT NULL,
    token_amount NUMERIC(18,8),
    reputation_weight NUMERIC(5,4),
    delegation_id UUID,
    chain VARCHAR(50),
    tx_hash VARCHAR(66),
    metadata JSONB DEFAULT '{}',
    cast_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(proposal_id, voter_id)
);

CREATE INDEX IF NOT EXISTS dv_proposal ON dao_vote(proposal_id);
CREATE INDEX IF NOT EXISTS dv_voter ON dao_vote(voter_id);
CREATE INDEX IF NOT EXISTS dv_method ON dao_vote(voting_method);

ALTER TABLE dao_vote DROP CONSTRAINT IF EXISTS dv_choice;
ALTER TABLE dao_vote ADD CONSTRAINT dv_choice CHECK (vote_choice IN ('for', 'against', 'abstain'));

ALTER TABLE dao_vote DROP CONSTRAINT IF EXISTS dv_method;
ALTER TABLE dao_vote ADD CONSTRAINT dv_method CHECK (voting_method IN ('quadratic', 'reputation', 'token_weighted', 'one_person_one_vote'));

-- 2. DAO proposal extended
CREATE TABLE IF NOT EXISTS dao_proposal_extended (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_key VARCHAR(100) NOT NULL UNIQUE,
    proposal_title TEXT NOT NULL,
    proposal_body TEXT NOT NULL,
    proposer_id UUID REFERENCES evaluator(id) ON DELETE SET NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    voting_method VARCHAR(50) NOT NULL DEFAULT 'quadratic',
    min_reputation_required NUMERIC(8,4) DEFAULT 0,
    voting_start TIMESTAMPTZ,
    voting_end TIMESTAMPTZ,
    quorum_pct NUMERIC(5,2) DEFAULT 50.0,
    passing_threshold_pct NUMERIC(5,2) DEFAULT 50.0,
    total_votes_cast INTEGER DEFAULT 0,
    total_for NUMERIC(8,4) DEFAULT 0,
    total_against NUMERIC(8,4) DEFAULT 0,
    result VARCHAR(50),
    executed_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS dpe_location ON dao_proposal_extended(location_id);
CREATE INDEX IF NOT EXISTS dpe_status ON dao_proposal_extended(status);
CREATE INDEX IF NOT EXISTS dpe_voting_end ON dao_proposal_extended(voting_end);

ALTER TABLE dao_proposal_extended DROP CONSTRAINT IF EXISTS dpe_status;
ALTER TABLE dao_proposal_extended ADD CONSTRAINT dpe_status CHECK (status IN ('draft', 'active', 'voting', 'passed', 'rejected', 'executed', 'cancelled'));

-- 3. Reputation token (non-transferable)
CREATE TABLE IF NOT EXISTS reputation_token (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    voter_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    domain VARCHAR(100) NOT NULL,
    reputation_amount NUMERIC(10,4) NOT NULL DEFAULT 0,
    earned_from VARCHAR(100),
    source_record_id UUID,
    earned_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(voter_id, domain, source_record_id)
);

CREATE INDEX IF NOT EXISTS rt_voter ON reputation_token(voter_id);
CREATE INDEX IF NOT EXISTS rt_domain ON reputation_token(domain);

-- 4. Delegation record
CREATE TABLE IF NOT EXISTS delegation_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    delegator_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    delegate_id UUID NOT NULL REFERENCES evaluator(id) ON DELETE CASCADE,
    domain VARCHAR(100),
    delegation_scope VARCHAR(100) DEFAULT 'all',
    delegation_pct NUMERIC(5,2) DEFAULT 100.0,
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date DATE,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS dr_delegator ON delegation_record(delegator_id);
CREATE INDEX IF NOT EXISTS dr_delegate ON delegation_record(delegate_id);
CREATE INDEX IF NOT EXISTS dr_status ON delegation_record(status);

ALTER TABLE delegation_record DROP CONSTRAINT IF EXISTS dr_status;
ALTER TABLE delegation_record ADD CONSTRAINT dr_status CHECK (status IN ('active', 'revoked', 'expired'));

-- 5. Public view
CREATE OR REPLACE VIEW v_public_dao_proposal_summary AS
SELECT
    dpe.id,
    dpe.proposal_key,
    dpe.proposal_title,
    dpe.voting_method,
    dpe.total_votes_cast,
    dpe.total_for,
    dpe.total_against,
    dpe.result,
    dpe.status,
    dpe.voting_start,
    dpe.voting_end,
    l.name AS location_name
FROM dao_proposal_extended dpe
LEFT JOIN location l ON l.id = dpe.location_id
WHERE dpe.status IN ('active', 'voting', 'passed', 'executed');
