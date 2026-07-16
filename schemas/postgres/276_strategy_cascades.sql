-- ============================================================
-- 276_strategy_cascades.sql
-- Organization-to-location strategic planning cascade.
-- ============================================================

ALTER TABLE strategy_plan
    ADD COLUMN IF NOT EXISTS parent_strategy_plan_id UUID REFERENCES strategy_plan(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS cascade_mode VARCHAR(20) NOT NULL DEFAULT 'independent'
        CHECK (cascade_mode IN ('inherited', 'adapted', 'independent')),
    ADD COLUMN IF NOT EXISTS cascade_rationale TEXT,
    ADD COLUMN IF NOT EXISTS cascade_status VARCHAR(20) NOT NULL DEFAULT 'not_applicable'
        CHECK (cascade_status IN ('not_applicable', 'aligned', 'needs_review', 'conflicted'));

CREATE INDEX IF NOT EXISTS idx_strategy_plan_parent ON strategy_plan(parent_strategy_plan_id, status);

CREATE OR REPLACE FUNCTION validate_strategy_plan_cascade()
RETURNS TRIGGER AS $$
DECLARE
    parent_scope_type VARCHAR(20);
    parent_scope_id UUID;
BEGIN
    IF NEW.parent_strategy_plan_id IS NULL THEN
        RETURN NEW;
    END IF;
    IF NEW.parent_strategy_plan_id = NEW.id THEN
        RAISE EXCEPTION 'strategy plan cannot parent itself';
    END IF;
    SELECT scope_type, scope_id INTO parent_scope_type, parent_scope_id
    FROM strategy_plan WHERE id = NEW.parent_strategy_plan_id;
    IF parent_scope_type IS NULL THEN
        RAISE EXCEPTION 'parent strategy plan does not exist';
    END IF;
    IF NEW.scope_type <> 'location' OR parent_scope_type <> 'organization' THEN
        RAISE EXCEPTION 'only location strategy plans may cascade from organization plans';
    END IF;
    IF NEW.cascade_mode = 'independent' THEN
        RAISE EXCEPTION 'cascaded strategy plans must be inherited or adapted';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_strategy_plan_cascade_validate ON strategy_plan;
CREATE TRIGGER trg_strategy_plan_cascade_validate BEFORE INSERT OR UPDATE ON strategy_plan
FOR EACH ROW EXECUTE FUNCTION validate_strategy_plan_cascade();

CREATE OR REPLACE FUNCTION prevent_strategy_cascade_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IN ('approved', 'active') AND (
        NEW.parent_strategy_plan_id IS DISTINCT FROM OLD.parent_strategy_plan_id OR
        NEW.cascade_mode IS DISTINCT FROM OLD.cascade_mode OR
        NEW.cascade_rationale IS DISTINCT FROM OLD.cascade_rationale
    ) THEN
        RAISE EXCEPTION 'approved or active strategy cascade is immutable; create a new version';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_strategy_cascade_immutable ON strategy_plan;
CREATE TRIGGER trg_strategy_cascade_immutable BEFORE UPDATE ON strategy_plan
FOR EACH ROW EXECUTE FUNCTION prevent_strategy_cascade_mutation();

CREATE OR REPLACE VIEW v_strategy_cascade AS
SELECT child.id AS child_plan_id,
       child.scope_id AS child_scope_id,
       child.name AS child_plan_name,
       child.status AS child_status,
       child.cascade_mode,
       child.cascade_status,
       parent.id AS parent_plan_id,
       parent.scope_id AS parent_scope_id,
       parent.name AS parent_plan_name,
       parent.status AS parent_status
FROM strategy_plan child
JOIN strategy_plan parent ON parent.id = child.parent_strategy_plan_id;

COMMENT ON COLUMN strategy_plan.cascade_mode IS 'Location plans inherit or adapt an organization strategy; independent plans have no parent';
