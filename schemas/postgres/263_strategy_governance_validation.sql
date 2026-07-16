-- ============================================================
-- 263_strategy_governance_validation.sql
-- Validate typed strategy governance links and scope compatibility.
-- ============================================================

CREATE OR REPLACE FUNCTION validate_strategy_governance_link()
RETURNS TRIGGER AS $$
DECLARE
    plan_scope_type VARCHAR(20);
    plan_scope_id UUID;
    record_scope_type VARCHAR(30);
    record_scope_id UUID;
    record_exists BOOLEAN;
BEGIN
    SELECT scope_type, scope_id INTO plan_scope_type, plan_scope_id FROM strategy_plan WHERE id = NEW.strategy_plan_id;
    IF plan_scope_type IS NULL THEN RAISE EXCEPTION 'strategy plan does not exist'; END IF;
    IF NEW.record_type = 'governance_circle' THEN
        SELECT TRUE, scope_type, scope_id INTO record_exists, record_scope_type, record_scope_id FROM governance_circle WHERE id = NEW.record_id;
    ELSIF NEW.record_type = 'stakeholder_decision' THEN
        SELECT TRUE, scope_type, scope_id INTO record_exists, record_scope_type, record_scope_id FROM stakeholder_decision WHERE id = NEW.record_id;
    ELSE
        RETURN NEW;
    END IF;
    IF NOT COALESCE(record_exists, FALSE) THEN RAISE EXCEPTION 'linked governance record does not exist'; END IF;
    IF record_scope_id IS NOT NULL AND record_scope_id <> plan_scope_id THEN RAISE EXCEPTION 'linked governance record is outside strategy plan scope'; END IF;
    IF plan_scope_type = 'organization' AND record_scope_type NOT IN ('organization', 'network') THEN RAISE EXCEPTION 'incompatible organization governance scope'; END IF;
    IF plan_scope_type = 'location' AND record_scope_type NOT IN ('location', 'farm', 'network') THEN RAISE EXCEPTION 'incompatible location governance scope'; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_strategy_governance_link_validate ON strategy_governance_link;
CREATE TRIGGER trg_strategy_governance_link_validate BEFORE INSERT OR UPDATE ON strategy_governance_link
FOR EACH ROW EXECUTE FUNCTION validate_strategy_governance_link();
