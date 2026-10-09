-- ============================================================
-- 280_strategy_contingencies.sql
-- Scenario-linked strategic choices and adaptation decisions.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_contingency_choice (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    scenario_id UUID NOT NULL REFERENCES forecast_scenario(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    trigger_metric_key VARCHAR(100),
    trigger_operator VARCHAR(10) CHECK (trigger_operator IS NULL OR trigger_operator IN ('lt', 'lte', 'eq', 'gte', 'gt')),
    trigger_threshold NUMERIC,
    action_summary TEXT NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'approved', 'active', 'retired')),
    approved_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status NOT IN ('approved', 'active') OR approved_at IS NOT NULL),
    CHECK ((trigger_metric_key IS NULL AND trigger_operator IS NULL AND trigger_threshold IS NULL)
        OR (trigger_metric_key IS NOT NULL AND trigger_operator IS NOT NULL AND trigger_threshold IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS strategy_adaptation_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    contingency_choice_id UUID NOT NULL REFERENCES strategy_contingency_choice(id) ON DELETE RESTRICT,
    from_strategy_plan_id UUID REFERENCES strategy_plan(id) ON DELETE SET NULL,
    to_strategy_plan_id UUID REFERENCES strategy_plan(id) ON DELETE SET NULL,
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('activate', 'defer', 'retire', 'revise')),
    rationale TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'approved', 'applied', 'superseded')),
    decided_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_contingency_plan
    ON strategy_contingency_choice(strategy_plan_id, status, priority);
CREATE INDEX IF NOT EXISTS idx_strategy_adaptation_plan
    ON strategy_adaptation_event(strategy_plan_id, created_at DESC);

COMMENT ON TABLE strategy_contingency_choice IS 'Approved strategic options tied to explicit forecast scenarios and measurable triggers';
COMMENT ON TABLE strategy_adaptation_event IS 'Durable record of human decisions to adapt, defer, retire, or revise strategy';
