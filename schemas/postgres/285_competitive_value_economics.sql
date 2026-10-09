-- ============================================================
-- 285_competitive_value_economics.sql
-- Customer value, value capture, and relative competitive economics.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_customer_value_hypothesis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    position_id UUID REFERENCES strategy_position(id) ON DELETE SET NULL,
    buyer_segment_id UUID REFERENCES buyer_segment(id) ON DELETE SET NULL,
    customer_need TEXT NOT NULL,
    baseline_alternative TEXT NOT NULL,
    proposed_outcome TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'rejected', 'retired')),
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_customer_value_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES strategy_customer_value_hypothesis(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    customer_count INTEGER CHECK (customer_count IS NULL OR customer_count >= 0),
    outcome_score NUMERIC(8,3),
    willingness_to_pay NUMERIC(15,2),
    observed_price NUMERIC(15,2),
    conversion_rate NUMERIC(8,4),
    retention_rate NUMERIC(8,4),
    switching_cost NUMERIC(15,2),
    evidence JSONB NOT NULL DEFAULT '[]',
    confidence VARCHAR(20) NOT NULL DEFAULT 'moderate'
        CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'rejected')),
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_value_capture_bridge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES strategy_customer_value_hypothesis(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    customer_value_created NUMERIC(15,2),
    customer_value_captured NUMERIC(15,2),
    delivery_cost NUMERIC(15,2),
    acquisition_cost NUMERIC(15,2),
    stakeholder_value_distribution JSONB NOT NULL DEFAULT '{}',
    contribution_margin NUMERIC(15,2),
    confidence VARCHAR(20) NOT NULL DEFAULT 'moderate'
        CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'rejected')),
    evidence JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (period_end >= period_start)
);

CREATE TABLE IF NOT EXISTS strategy_competitive_benchmark (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    buyer_segment_id UUID REFERENCES buyer_segment(id) ON DELETE SET NULL,
    benchmark_type VARCHAR(20) NOT NULL CHECK (benchmark_type IN ('cost', 'price', 'quality', 'coverage', 'trust', 'reliability', 'speed')),
    subject_type VARCHAR(20) NOT NULL CHECK (subject_type IN ('kokonut', 'competitor', 'substitute', 'industry')),
    subject_name VARCHAR(255) NOT NULL,
    measure_name VARCHAR(120) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    value NUMERIC(15,4) NOT NULL,
    currency VARCHAR(10),
    observed_at DATE NOT NULL,
    source_ref TEXT,
    confidence VARCHAR(20) NOT NULL DEFAULT 'moderate'
        CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'retired')),
    evidence JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_value_hypothesis_plan
    ON strategy_customer_value_hypothesis(strategy_plan_id, status);
CREATE INDEX IF NOT EXISTS idx_strategy_value_observation_hypothesis
    ON strategy_customer_value_observation(hypothesis_id, observed_at DESC, status);
CREATE INDEX IF NOT EXISTS idx_strategy_value_bridge_hypothesis
    ON strategy_value_capture_bridge(hypothesis_id, period_end DESC, status);
CREATE INDEX IF NOT EXISTS idx_strategy_benchmark_plan
    ON strategy_competitive_benchmark(strategy_plan_id, benchmark_type, observed_at DESC, status);

DROP TRIGGER IF EXISTS trg_strategy_customer_value_hypothesis_updated_at ON strategy_customer_value_hypothesis;
CREATE TRIGGER trg_strategy_customer_value_hypothesis_updated_at
    BEFORE UPDATE ON strategy_customer_value_hypothesis
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE VIEW v_strategy_customer_value_economics AS
SELECT h.strategy_plan_id,
       h.id AS hypothesis_id,
       h.customer_need,
       h.status AS hypothesis_status,
       latest.willingness_to_pay,
       latest.observed_price,
       latest.conversion_rate,
       latest.retention_rate,
       bridge.customer_value_created,
       bridge.customer_value_captured,
       bridge.delivery_cost,
       bridge.acquisition_cost,
       bridge.contribution_margin,
       CASE
           WHEN latest.willingness_to_pay IS NOT NULL AND latest.observed_price IS NOT NULL
           THEN latest.willingness_to_pay - latest.observed_price
           ELSE NULL
       END AS customer_surplus,
       CASE
           WHEN latest.observed_price IS NOT NULL AND latest.willingness_to_pay IS NOT NULL AND latest.willingness_to_pay <> 0
           THEN ROUND((latest.observed_price / latest.willingness_to_pay) * 100, 2)
           ELSE NULL
       END AS value_capture_pct
FROM strategy_customer_value_hypothesis h
LEFT JOIN LATERAL (
    SELECT * FROM strategy_customer_value_observation o
    WHERE o.hypothesis_id = h.id AND o.status IN ('submitted', 'verified')
    ORDER BY o.observed_at DESC LIMIT 1
) latest ON TRUE
LEFT JOIN LATERAL (
    SELECT * FROM strategy_value_capture_bridge b
    WHERE b.hypothesis_id = h.id AND b.status IN ('submitted', 'verified')
    ORDER BY b.period_end DESC LIMIT 1
) bridge ON TRUE;

COMMENT ON TABLE strategy_customer_value_hypothesis IS 'Testable customer-value propositions tied to a strategy position and market segment';
COMMENT ON TABLE strategy_value_capture_bridge IS 'Bridge from value created for customers and stakeholders to value captured and delivery economics';
COMMENT ON TABLE strategy_competitive_benchmark IS 'Comparable cost, price, quality, trust, coverage, reliability, and speed observations';
