-- ============================================================
-- 286_advantage_outcomes_renewal.sql
-- Realized advantage outcomes and durability/renewal tracking.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_advantage_outcome (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    advantage_id UUID NOT NULL REFERENCES strategy_advantage(id) ON DELETE CASCADE,
    objective_id UUID REFERENCES objective(id) ON DELETE SET NULL,
    objective_kpi_id UUID REFERENCES objective_kpi(id) ON DELETE SET NULL,
    outcome_type VARCHAR(30) NOT NULL CHECK (outcome_type IN ('cost_reduction', 'price_premium', 'retention', 'conversion', 'market_share', 'customer_outcome', 'risk_reduction', 'replication_cost', 'revenue_growth')),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    baseline_value NUMERIC(15,4),
    target_value NUMERIC(15,4),
    actual_value NUMERIC(15,4),
    comparator_type VARCHAR(20) CHECK (comparator_type IS NULL OR comparator_type IN ('baseline', 'competitor', 'industry', 'target')),
    comparator_value NUMERIC(15,4),
    unit VARCHAR(50),
    attribution_confidence VARCHAR(20) NOT NULL DEFAULT 'moderate'
        CHECK (attribution_confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'verified', 'rejected')),
    evidence JSONB NOT NULL DEFAULT '[]',
    observed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (period_end >= period_start)
);

CREATE TABLE IF NOT EXISTS strategy_advantage_renewal_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    advantage_id UUID NOT NULL REFERENCES strategy_advantage(id) ON DELETE CASCADE,
    investment_id UUID REFERENCES strategy_investment_case(id) ON DELETE SET NULL,
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('reinforce', 'renew', 'erode', 'imitate', 'substitute', 'retire')),
    event_date DATE NOT NULL,
    description TEXT NOT NULL,
    expected_effect TEXT,
    observed_effect TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'approved', 'completed', 'rejected')),
    evidence JSONB NOT NULL DEFAULT '[]',
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_advantage_outcome_advantage
    ON strategy_advantage_outcome(advantage_id, period_end DESC, status);
CREATE INDEX IF NOT EXISTS idx_strategy_advantage_renewal_advantage
    ON strategy_advantage_renewal_event(advantage_id, event_date DESC, event_type);

CREATE OR REPLACE VIEW v_strategy_advantage_performance AS
SELECT a.id AS advantage_id,
       a.strategy_plan_id,
       a.name,
       a.status AS advantage_status,
       a.defensibility_score,
       latest.outcome_type AS latest_outcome_type,
       latest.baseline_value,
       latest.actual_value,
       latest.comparator_type,
       latest.comparator_value,
       latest.attribution_confidence,
       CASE
           WHEN latest.actual_value IS NULL THEN NULL
           WHEN latest.baseline_value IS NULL THEN NULL
           ELSE latest.actual_value - latest.baseline_value
       END AS outcome_delta,
       COALESCE(events.renewal_event_count, 0) AS renewal_event_count,
       COALESCE(events.erosion_event_count, 0) AS erosion_event_count,
       COALESCE(events.completed_reinforcement_count, 0) AS completed_reinforcement_count
FROM strategy_advantage a
LEFT JOIN LATERAL (
    SELECT * FROM strategy_advantage_outcome o
    WHERE o.advantage_id = a.id AND o.status IN ('submitted', 'verified')
    ORDER BY o.period_end DESC LIMIT 1
) latest ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(*) FILTER (WHERE event_type IN ('reinforce', 'renew')) AS renewal_event_count,
           COUNT(*) FILTER (WHERE event_type IN ('erode', 'imitate', 'substitute')) AS erosion_event_count,
           COUNT(*) FILTER (WHERE event_type = 'reinforce' AND status = 'completed') AS completed_reinforcement_count
    FROM strategy_advantage_renewal_event e WHERE e.advantage_id = a.id
) events ON TRUE;

COMMENT ON TABLE strategy_advantage_outcome IS 'Observed customer, cost, price, market, and risk outcomes attributable to a strategic advantage';
COMMENT ON TABLE strategy_advantage_renewal_event IS 'Durability events showing how an advantage is reinforced, eroded, imitated, substituted, or retired';
