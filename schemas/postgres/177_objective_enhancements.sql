-- ============================================================
-- 177_objective_enhancements.sql - Performance management (MbO / scorecard)
-- ============================================================

DO $$ BEGIN
    CREATE TYPE objective_review_status AS ENUM ('on_track', 'at_risk', 'off_track', 'closed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Link a strategic objective (existing objective table, 053) to a financial plan.
ALTER TABLE objective
    ADD COLUMN IF NOT EXISTS plan_id UUID REFERENCES financial_plan(id) ON DELETE SET NULL;

-- Rolling health status of an objective, governed by the objective workflow spec.
ALTER TABLE objective
    ADD COLUMN IF NOT EXISTS review_status objective_review_status;

-- KPI bindings: each ties an objective to a verified metric / CRISP dimension + target.
CREATE TABLE IF NOT EXISTS objective_kpi (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    objective_id UUID NOT NULL REFERENCES objective(id) ON DELETE CASCADE,
    metric_key VARCHAR(100),
    metric_definition_id UUID REFERENCES metric_definition(id) ON DELETE SET NULL,
    crisp_dimension VARCHAR(100),
    target_value NUMERIC,
    direction VARCHAR(20) NOT NULL DEFAULT 'gte'
        CHECK (direction IN ('gte', 'lte', 'range')),
    current_value_snapshot NUMERIC,
    source_ref VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_objective_kpi_objective ON objective_kpi(objective_id);

-- Review history; each review also advances objective.review_status.
CREATE TABLE IF NOT EXISTS objective_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    objective_id UUID NOT NULL REFERENCES objective(id) ON DELETE CASCADE,
    review_date TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewer_type VARCHAR(20) NOT NULL
        CHECK (reviewer_type IN ('staff', 'farmer', 'agent', 'system')),
    reviewer_id UUID,
    status objective_review_status NOT NULL,
    notes TEXT,
    corrective_work_item_id UUID REFERENCES work_item(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_objective_review_objective ON objective_review(objective_id);

DROP TRIGGER IF EXISTS trg_objective_kpi_updated_at ON objective_kpi;
CREATE TRIGGER trg_objective_kpi_updated_at
    BEFORE UPDATE ON objective_kpi
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE objective_kpi IS 'KPI bindings linking objectives to verified metrics / CRISP dimensions';
COMMENT ON TABLE objective_review IS 'Review history advancing an objective health status';
