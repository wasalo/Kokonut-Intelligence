-- Capital Accounting layer (Keynes-inspired, constructive only).
--
-- Extends the 8 Forms of Capital from a static stock inventory into a
-- dynamic capital-accounting system:
--   1. capital_capacity_assessment  -- stock vs regenerative output capacity
--      (Keynes: "Our Output Capacity and The National Income").
--   2. capital_diversion_observation -- consumption vs reinvestment diversion
--      index (Keynes: divert surplus from consumption to the capital base).
--   3. capital_capture_risk          -- value-leakage / concentration early
--      warning (Keynes: managed containment analog).
--   4. regenerative_credit_ledger     -- DRAFT-only deferred-pay / compulsory
--      savings analog: withheld value credited as a claim on future
--      regenerative output, redeemable later. Settlement requires human
--      confirmation and preserves custody/invariants (see AGENTS.md).
--
-- All agent-facing writes to regenerative_credit_ledger are restricted to
-- status='draft' via services/agents/safety.py. No autonomous settlement,
-- redemption, or on-chain drawdown.
--
-- Idempotent: safe to re-run and extend.

CREATE TABLE IF NOT EXISTS capital_capacity_assessment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    capital_key VARCHAR(50) NOT NULL,
    period_start DATE,
    period_end DATE,
    stock_estimate NUMERIC(18,6) NOT NULL DEFAULT 0,
    output_capacity_estimate NUMERIC(18,6) NOT NULL DEFAULT 0,
    mobilization_pct NUMERIC(7,4),   -- stock_estimate / output_capacity_estimate
    assessed_by UUID,
    status VARCHAR(50) DEFAULT 'draft',  -- draft, verified, published, rejected
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (capital_key IN (
        'natural', 'financial', 'social', 'human', 'material',
        'intellectual', 'cultural', 'health')),
    CHECK (status IN ('draft', 'verified', 'published', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_cap_capacity_loc ON capital_capacity_assessment(location_id, capital_key);

CREATE TABLE IF NOT EXISTS capital_diversion_observation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    period_start DATE,
    period_end DATE,
    consumption_value NUMERIC(18,6) NOT NULL DEFAULT 0,
    reinvestment_value NUMERIC(18,6) NOT NULL DEFAULT 0,
    diversion_index NUMERIC(7,4),  -- reinvestment / (consumption + reinvestment)
    shock_flag BOOLEAN DEFAULT FALSE,
    source VARCHAR(100),  -- computed, reported, imported
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cap_diversion_loc ON capital_diversion_observation(location_id);

CREATE TABLE IF NOT EXISTS capital_capture_risk (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    capital_key VARCHAR(50) NOT NULL,
    concentration_metric NUMERIC(18,6),
    leakage_signal NUMERIC(7,4),
    capture_risk_level VARCHAR(20) DEFAULT 'low',  -- low, medium, high, unknown
    mitigation_note TEXT,
    policy_scope VARCHAR(100),  -- from anti_capture_governance_policy
    assessed_by UUID,
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (capital_key IN (
        'natural', 'financial', 'social', 'human', 'material',
        'intellectual', 'cultural', 'health')),
    CHECK (capture_risk_level IN ('low', 'medium', 'high', 'unknown')),
    CHECK (status IN ('draft', 'verified', 'published', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_cap_capture_loc ON capital_capture_risk(location_id, capital_key);

-- Deferred regenerative credit ledger (Keynes deferred-pay / compulsory
-- savings analog). Agents may ONLY write status='draft'; settlement and
-- redemption are human-approved flows out of scope for this module.
CREATE TABLE IF NOT EXISTS regenerative_credit_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    contributor_party_id UUID,  -- stakeholder party (human/agent/staff)
    source_type VARCHAR(50) NOT NULL,  -- carbon_credit_surplus,
                                              -- cooperative_surplus,
                                              -- federation_underwrite
    source_ref_id UUID,
    withheld_amount NUMERIC(18,6) NOT NULL DEFAULT 0,
    unit VARCHAR(50) NOT NULL DEFAULT 'usd',
    redeemable_against VARCHAR(50) DEFAULT 'regenerative_investment',
    credit_status VARCHAR(50) DEFAULT 'draft',  -- draft, proposed_settlement,
                                                    -- settled, cancelled
    idempotency_key VARCHAR(255) UNIQUE,
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    CHECK (source_type IN (
        'carbon_credit_surplus', 'cooperative_surplus', 'federation_underwrite')),
    CHECK (redeemable_against IN (
        'regenerative_investment', 'shared_dividend', 'stewardship_grant')),
    CHECK (credit_status IN ('draft', 'proposed_settlement', 'settled', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_regen_credit_loc ON regenerative_credit_ledger(location_id, credit_status);

-- Latest capital dashboard view (advisory). Joins the 8 Forms of Capital
-- definitions with the most recent assessment rows per location.
CREATE OR REPLACE VIEW v_capital_dashboard AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    foc.capital_key,
    foc.name AS capital_name,
    ca.stock_estimate,
    ca.output_capacity_estimate,
    ca.mobilization_pct,
    cd.diversion_index,
    ccr.capture_risk_level,
    COALESCE((
        SELECT SUM(rcl.withheld_amount)
        FROM regenerative_credit_ledger rcl
        WHERE rcl.location_id = l.id
          AND rcl.credit_status = 'draft'
    ), 0) AS draft_credit_total
FROM location l
CROSS JOIN form_of_capital foc
LEFT JOIN LATERAL (
    SELECT *
    FROM capital_capacity_assessment a
    WHERE a.location_id = l.id AND a.capital_key = foc.capital_key
    ORDER BY a.period_end DESC NULLS LAST, a.created_at DESC
    LIMIT 1
) ca ON TRUE
LEFT JOIN LATERAL (
    SELECT *
    FROM capital_diversion_observation d
    WHERE d.location_id = l.id
    ORDER BY d.period_end DESC NULLS LAST, d.created_at DESC
    LIMIT 1
) cd ON TRUE
LEFT JOIN LATERAL (
    SELECT *
    FROM capital_capture_risk c
    WHERE c.location_id = l.id AND c.capital_key = foc.capital_key
    ORDER BY c.created_at DESC
    LIMIT 1
) ccr ON TRUE
WHERE foc.is_active = TRUE;
