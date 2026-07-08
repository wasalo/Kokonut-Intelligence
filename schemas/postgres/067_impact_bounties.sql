-- 067_impact_bounties.sql
-- Impact Bounties: Data Collection Incentives

BEGIN;

-- ============================================================================
-- IMPACT BOUNTY
-- ============================================================================

CREATE TABLE IF NOT EXISTS impact_bounty (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bounty_key VARCHAR(100) UNIQUE NOT NULL,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    campaign_id UUID REFERENCES funding_campaign(id) ON DELETE SET NULL,
    bounty_name VARCHAR(255) NOT NULL,
    bounty_type VARCHAR(100) NOT NULL
        CHECK (bounty_type IN (
            'data_collection', 'species_identification', 'soil_sampling',
            'water_measurement', 'photo_documentation', 'practice_verification', 'other'
        )),
    description TEXT NOT NULL,
    data_requirement TEXT NOT NULL,
    schema_id UUID,
    metric_id UUID,
    reward_amount NUMERIC(15,2) NOT NULL,
    reward_currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    reward_token VARCHAR(50),
    max_submissions INT,
    submissions_count INT NOT NULL DEFAULT 0,
    min_evidence_maturity INT NOT NULL DEFAULT 2,
    required_fields JSONB DEFAULT '[]'::jsonb,
    expiration_date DATE,
    bounty_status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (bounty_status IN ('draft', 'active', 'paused', 'fulfilled', 'expired')),
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_bounty_location ON impact_bounty(location_id);
CREATE INDEX IF NOT EXISTS idx_bounty_status ON impact_bounty(bounty_status);
CREATE INDEX IF NOT EXISTS idx_bounty_type ON impact_bounty(bounty_type);

CREATE TRIGGER trg_bounty_updated_at
    BEFORE UPDATE ON impact_bounty
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE impact_bounty IS 'Bounty definitions for incentivized data collection';

-- ============================================================================
-- IMPACT BOUNTY SUBMISSION
-- ============================================================================

CREATE TABLE IF NOT EXISTS impact_bounty_submission (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bounty_id UUID NOT NULL REFERENCES impact_bounty(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    submitter_id UUID,
    wallet_address VARCHAR(42),
    submission_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_cids TEXT[],
    evidence_urls TEXT[],
    attestation_uid VARCHAR(66),
    attestation_id UUID,
    evidence_maturity INT NOT NULL DEFAULT 1,
    quality_score NUMERIC(5,2),
    review_status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected')),
    reviewer_id UUID,
    review_notes TEXT,
    reward_paid BOOLEAN NOT NULL DEFAULT FALSE,
    reward_payout_id UUID,
    submission_date TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(50) NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'under_review', 'approved', 'rejected')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bounty_submission_bounty ON impact_bounty_submission(bounty_id);
CREATE INDEX IF NOT EXISTS idx_bounty_submission_location ON impact_bounty_submission(location_id);
CREATE INDEX IF NOT EXISTS idx_bounty_submission_status ON impact_bounty_submission(status);

CREATE TRIGGER trg_bounty_submission_updated_at
    BEFORE UPDATE ON impact_bounty_submission
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE impact_bounty_submission IS 'Submitted data for bounty claims with evidence, review, and reward tracking';

COMMIT;
