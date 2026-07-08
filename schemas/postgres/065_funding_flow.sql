-- 065_funding_flow.sql
-- Funding Flow: Donor-to-Farm, Crowdfunding, Impact-Linked Payouts

BEGIN;

-- ============================================================================
-- DONOR
-- ============================================================================

CREATE TABLE IF NOT EXISTS donor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name VARCHAR(255),
    donor_type VARCHAR(100) NOT NULL DEFAULT 'individual'
        CHECK (donor_type IN ('individual', 'institutional', 'dao', 'corporate', 'anonymous')),
    wallet_address VARCHAR(42),
    chain VARCHAR(50),
    email VARCHAR(255),
    is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_donor_updated_at
    BEFORE UPDATE ON donor
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE donor IS 'Donor identity for crowdfunding and direct donations';

-- ============================================================================
-- FUNDING CAMPAIGN
-- ============================================================================

CREATE TABLE IF NOT EXISTS funding_campaign (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_key VARCHAR(100) UNIQUE NOT NULL,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organization(id) ON DELETE SET NULL,
    campaign_name VARCHAR(255) NOT NULL,
    campaign_type VARCHAR(100) NOT NULL DEFAULT 'crowdfunding'
        CHECK (campaign_type IN ('crowdfunding', 'match_fund', 'impact_bounty', 'recurring', 'emergency', 'grant_round')),
    goal_amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    raised_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    start_date DATE,
    end_date DATE,
    description TEXT,
    impact_link TEXT,
    attestation_uid VARCHAR(66),
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'funded', 'completed', 'expired', 'cancelled')),
    metadata JSONB DEFAULT '{}'::jsonb,
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_campaign_location ON funding_campaign(location_id);
CREATE INDEX IF NOT EXISTS idx_campaign_status ON funding_campaign(status);
CREATE INDEX IF NOT EXISTS idx_campaign_type ON funding_campaign(campaign_type);

CREATE TRIGGER trg_campaign_updated_at
    BEFORE UPDATE ON funding_campaign
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE funding_campaign IS 'Funding campaigns with goals, progress, and impact linkage';

-- ============================================================================
-- DONATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS donation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES funding_campaign(id) ON DELETE SET NULL,
    donor_id UUID NOT NULL REFERENCES donor(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    payment_method VARCHAR(100)
        CHECK (payment_method IN ('crypto', 'mobile_money', 'bank_transfer', 'card', 'other')),
    chain VARCHAR(50),
    tx_hash VARCHAR(66),
    donation_date TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
    recurring_interval VARCHAR(50),
    linked_attestation_uid VARCHAR(66),
    linked_metric_id UUID,
    receipt_issued BOOLEAN NOT NULL DEFAULT FALSE,
    tax_deductible BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'completed'
        CHECK (status IN ('pending', 'completed', 'refunded', 'failed')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_donation_campaign ON donation(campaign_id);
CREATE INDEX IF NOT EXISTS idx_donation_donor ON donation(donor_id);
CREATE INDEX IF NOT EXISTS idx_donation_location ON donation(location_id);
CREATE INDEX IF NOT EXISTS idx_donation_status ON donation(status);

CREATE TRIGGER trg_donation_updated_at
    BEFORE UPDATE ON donation
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE donation IS 'Individual donations with payment method, recurring support, and impact linkage';

-- ============================================================================
-- IMPACT PAYOUT RULE
-- ============================================================================

CREATE TABLE IF NOT EXISTS impact_payout_rule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    campaign_id UUID REFERENCES funding_campaign(id) ON DELETE SET NULL,
    metric_id UUID NOT NULL,
    payout_type VARCHAR(100) NOT NULL
        CHECK (payout_type IN ('milestone', 'threshold', 'proportional', 'bounty')),
    trigger_condition TEXT NOT NULL,
    payout_amount NUMERIC(15,2),
    payout_currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    payout_recipient VARCHAR(100) NOT NULL
        CHECK (payout_recipient IN ('farm_operator', 'community_pool', 'data_collector', 'other')),
    attestation_required BOOLEAN NOT NULL DEFAULT TRUE,
    min_evidence_maturity INTEGER NOT NULL DEFAULT 4,
    enforcement_mode VARCHAR(100) NOT NULL DEFAULT 'directus_hook'
        CHECK (enforcement_mode IN ('directus_hook', 'smart_contract', 'manual_review')),
    status VARCHAR(50) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'paused', 'cancelled')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payout_rule_location ON impact_payout_rule(location_id);
CREATE INDEX IF NOT EXISTS idx_payout_rule_campaign ON impact_payout_rule(campaign_id);
CREATE INDEX IF NOT EXISTS idx_payout_rule_status ON impact_payout_rule(status);

CREATE TRIGGER trg_payout_rule_updated_at
    BEFORE UPDATE ON impact_payout_rule
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE impact_payout_rule IS 'Rules for automatic payouts when metrics hit thresholds';

-- ============================================================================
-- IMPACT PAYOUT EXECUTION
-- ============================================================================

CREATE TABLE IF NOT EXISTS impact_payout_execution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id UUID NOT NULL REFERENCES impact_payout_rule(id) ON DELETE CASCADE,
    donation_id UUID REFERENCES donation(id) ON DELETE SET NULL,
    attestation_uid VARCHAR(66),
    metric_value NUMERIC(18,4),
    payout_amount NUMERIC(15,2) NOT NULL,
    payout_date TIMESTAMPTZ,
    tx_hash VARCHAR(66),
    status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'executed', 'verified', 'failed')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payout_exec_rule ON impact_payout_execution(rule_id);
CREATE INDEX IF NOT EXISTS idx_payout_exec_status ON impact_payout_execution(status);

CREATE TRIGGER trg_payout_exec_updated_at
    BEFORE UPDATE ON impact_payout_execution
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE impact_payout_execution IS 'Record of executed impact-linked payouts with on-chain proof';

-- ============================================================================
-- VIEWS
-- ============================================================================

CREATE OR REPLACE VIEW v_public_funding_campaigns AS
SELECT
    fc.id,
    fc.campaign_key,
    fc.location_id,
    l.name AS location_name,
    fc.campaign_name,
    fc.campaign_type,
    fc.goal_amount,
    fc.currency,
    fc.raised_amount,
    CASE WHEN fc.goal_amount > 0 THEN ROUND((fc.raised_amount / fc.goal_amount * 100)::numeric, 1) ELSE 0 END AS progress_pct,
    fc.start_date,
    fc.end_date,
    fc.description,
    fc.status,
    fc.created_at
FROM funding_campaign fc
JOIN location l ON fc.location_id = l.id
WHERE l.status IN ('active', 'verified', 'published')
  AND fc.status IN ('active', 'funded', 'completed');

CREATE OR REPLACE VIEW v_public_donation_summary AS
SELECT
    d.location_id,
    l.name AS location_name,
    d.campaign_id,
    fc.campaign_name,
    COUNT(*) AS donation_count,
    SUM(d.amount) AS total_raised,
    AVG(d.amount) AS avg_donation,
    MAX(d.donation_date) AS latest_donation
FROM donation d
JOIN location l ON d.location_id = l.id
LEFT JOIN funding_campaign fc ON d.campaign_id = fc.id
WHERE l.status IN ('active', 'verified', 'published')
  AND d.status = 'completed'
GROUP BY d.location_id, l.name, d.campaign_id, fc.campaign_name;

CREATE OR REPLACE VIEW v_public_impact_payout_summary AS
SELECT
    ipr.id,
    ipr.location_id,
    l.name AS location_name,
    ipr.payout_type,
    ipr.trigger_condition,
    ipr.payout_amount,
    ipr.payout_currency,
    ipr.payout_recipient,
    ipr.attestation_required,
    ipr.min_evidence_maturity,
    ipr.status,
    (SELECT COUNT(*)::int FROM impact_payout_execution ipe WHERE ipe.rule_id = ipr.id AND ipe.status = 'executed') AS executions_count,
    (SELECT COALESCE(SUM(ipe.payout_amount), 0) FROM impact_payout_execution ipe WHERE ipe.rule_id = ipr.id AND ipe.status = 'executed') AS total_paid
FROM impact_payout_rule ipr
LEFT JOIN location l ON ipr.location_id = l.id
WHERE ipr.status = 'active';

COMMIT;
