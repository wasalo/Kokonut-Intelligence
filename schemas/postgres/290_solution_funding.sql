-- ============================================================
-- 290_solution_funding.sql
-- Stage-appropriate solution funding and milestone releases.
-- ============================================================

ALTER TABLE funding_request
    ADD COLUMN IF NOT EXISTS solution_id UUID REFERENCES solution(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS solution_funding_case (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id UUID NOT NULL REFERENCES solution(id) ON DELETE CASCADE,
    experiment_id UUID REFERENCES solution_experiment(id) ON DELETE SET NULL,
    strategy_investment_id UUID REFERENCES strategy_investment_case(id) ON DELETE SET NULL,
    capital_stage VARCHAR(20) NOT NULL CHECK (capital_stage IN ('discovery', 'experiment', 'pilot', 'replication', 'scale', 'maintenance')),
    funding_instrument VARCHAR(30) NOT NULL CHECK (funding_instrument IN ('grant', 'budget', 'bounty', 'loan', 'investment', 'community_fund', 'in_kind')),
    requested_amount NUMERIC(15,2) NOT NULL CHECK (requested_amount >= 0),
    minimum_viable_amount NUMERIC(15,2) CHECK (minimum_viable_amount IS NULL OR minimum_viable_amount >= 0),
    maximum_authorized_amount NUMERIC(15,2) CHECK (maximum_authorized_amount IS NULL OR maximum_authorized_amount >= requested_amount),
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    risk_adjusted_expected_value NUMERIC(15,2),
    public_goods_value NUMERIC(15,2),
    community_share NUMERIC(15,2),
    downside_exposure NUMERIC(15,2),
    decision_status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (decision_status IN ('draft', 'submitted', 'approved', 'rejected', 'closed')),
    rationale TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]',
    submitted_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (minimum_viable_amount IS NULL OR maximum_authorized_amount IS NULL OR minimum_viable_amount <= maximum_authorized_amount)
);

CREATE TABLE IF NOT EXISTS solution_funding_tranche (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    funding_case_id UUID NOT NULL REFERENCES solution_funding_case(id) ON DELETE CASCADE,
    tranche_number INTEGER NOT NULL CHECK (tranche_number > 0),
    amount NUMERIC(15,2) NOT NULL CHECK (amount >= 0),
    milestone_conditions JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'approved', 'released', 'blocked', 'returned')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    released_at TIMESTAMPTZ,
    released_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    UNIQUE (funding_case_id, tranche_number)
);

CREATE TABLE IF NOT EXISTS solution_funding_release (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tranche_id UUID NOT NULL REFERENCES solution_funding_tranche(id) ON DELETE CASCADE,
    amount NUMERIC(15,2) NOT NULL CHECK (amount >= 0),
    milestone_evidence JSONB NOT NULL DEFAULT '[]',
    released_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    released_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_solution_funding_case_solution ON solution_funding_case(solution_id, capital_stage, decision_status);
CREATE INDEX IF NOT EXISTS idx_solution_funding_tranche_case ON solution_funding_tranche(funding_case_id, status);

COMMENT ON TABLE solution_funding_case IS 'Stage-appropriate capital case for experimentation, pilots, replication, scale, or maintenance';
COMMENT ON TABLE solution_funding_tranche IS 'Milestone-conditioned funding tranche requiring evidence before release';
