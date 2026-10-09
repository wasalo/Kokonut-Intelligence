-- ============================================================
-- 266_strategy_control_variance.sql
-- Benefits and auditable strategic control variances.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_benefit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    investment_id UUID REFERENCES strategy_investment_case(id) ON DELETE SET NULL,
    initiative_id UUID REFERENCES strategy_initiative(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    benefit_type VARCHAR(30) NOT NULL CHECK (benefit_type IN ('financial', 'ecological', 'social', 'governance', 'capability', 'resilience')),
    baseline_value NUMERIC,
    target_value NUMERIC,
    expected_value NUMERIC,
    actual_value NUMERIC,
    unit VARCHAR(50),
    direction VARCHAR(10) NOT NULL DEFAULT 'gte' CHECK (direction IN ('gte', 'lte', 'range')),
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'measuring', 'on_track', 'at_risk', 'realized', 'not_realized', 'cancelled')),
    owner_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    realization_due_at DATE,
    evidence JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_variance_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    subject_type VARCHAR(40) NOT NULL CHECK (subject_type IN ('objective_kpi', 'budget', 'capacity', 'risk', 'benefit', 'initiative')),
    subject_id UUID NOT NULL,
    metric_key VARCHAR(120) NOT NULL,
    period_start DATE,
    period_end DATE,
    planned_value NUMERIC,
    actual_value NUMERIC,
    variance_value NUMERIC,
    variance_pct NUMERIC,
    status VARCHAR(20) NOT NULL CHECK (status IN ('within_tolerance', 'warning', 'breach', 'not_measurable')),
    root_cause TEXT,
    corrective_work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    observed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidence JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_strategy_benefit_plan ON strategy_benefit(strategy_plan_id, status, realization_due_at);
CREATE INDEX IF NOT EXISTS idx_strategy_variance_plan ON strategy_variance_observation(strategy_plan_id, subject_type, status, observed_at DESC);

CREATE OR REPLACE VIEW v_strategy_benefit_health AS
SELECT strategy_plan_id,
       COUNT(*) AS benefit_count,
       COUNT(*) FILTER (WHERE status IN ('on_track', 'realized')) AS on_track_or_realized_count,
       COUNT(*) FILTER (WHERE status IN ('at_risk', 'not_realized')) AS benefit_risk_count,
       ROUND(AVG(CASE WHEN target_value IS NOT NULL AND actual_value IS NOT NULL AND target_value <> 0
                      THEN actual_value / target_value * 100 ELSE NULL END), 1) AS average_target_attainment_pct
FROM strategy_benefit
GROUP BY strategy_plan_id;

CREATE OR REPLACE VIEW v_strategy_kernel_benefit_execution AS
SELECT base.*,
       COALESCE(sb.benefit_count, 0) AS benefit_count,
       COALESCE(sb.on_track_or_realized_count, 0) AS on_track_or_realized_benefit_count,
       COALESCE(sb.benefit_risk_count, 0) AS benefit_risk_count,
       sb.average_target_attainment_pct
FROM v_strategy_kernel_execution base
LEFT JOIN v_strategy_benefit_health sb ON sb.strategy_plan_id = base.strategy_plan_id;

COMMENT ON TABLE strategy_benefit IS 'Expected and realized strategic benefits across financial, ecological, social, governance, capability, and resilience dimensions';
COMMENT ON TABLE strategy_variance_observation IS 'Historical control observation for KPI, budget, capacity, risk, benefit, and initiative variance';
