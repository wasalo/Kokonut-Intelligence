-- ============================================================
-- 262_strategy_integrity_gates.sql
-- Audited transitions and immutable approved strategy content.
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy_plan_transition (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_plan_id UUID NOT NULL REFERENCES strategy_plan(id) ON DELETE CASCADE,
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    actor_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reason TEXT,
    evidence JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_transition_plan
    ON strategy_plan_transition(strategy_plan_id, created_at DESC);

CREATE OR REPLACE FUNCTION prevent_strategy_plan_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IN ('approved', 'active') AND (
        NEW.scope_type IS DISTINCT FROM OLD.scope_type OR NEW.scope_id IS DISTINCT FROM OLD.scope_id OR
        NEW.name IS DISTINCT FROM OLD.name OR NEW.version IS DISTINCT FROM OLD.version OR
        NEW.planning_horizon_start IS DISTINCT FROM OLD.planning_horizon_start OR
        NEW.planning_horizon_end IS DISTINCT FROM OLD.planning_horizon_end OR
        NEW.diagnosis_summary IS DISTINCT FROM OLD.diagnosis_summary OR
        NEW.guiding_policy IS DISTINCT FROM OLD.guiding_policy OR
        NEW.theory_of_change IS DISTINCT FROM OLD.theory_of_change OR
        NEW.uncertainty_summary IS DISTINCT FROM OLD.uncertainty_summary OR
        NEW.approval_mode IS DISTINCT FROM OLD.approval_mode OR NEW.visibility IS DISTINCT FROM OLD.visibility OR
        NEW.supersedes_plan_id IS DISTINCT FROM OLD.supersedes_plan_id OR
        NEW.created_by_party_id IS DISTINCT FROM OLD.created_by_party_id
    ) THEN
        RAISE EXCEPTION 'approved or active strategy plan content is immutable; create a new version';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_strategy_plan_immutable ON strategy_plan;
CREATE TRIGGER trg_strategy_plan_immutable BEFORE UPDATE ON strategy_plan
FOR EACH ROW EXECUTE FUNCTION prevent_strategy_plan_mutation();

COMMENT ON TABLE strategy_plan_transition IS 'Audited strategy lifecycle transitions with actor, reason, and evidence';
