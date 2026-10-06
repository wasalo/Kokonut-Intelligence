-- ============================================================
-- 363_expense_farm_weekly_plan_scope.sql
-- Preserve farm scope on expense events and link expenses to weekly plans.
-- ============================================================

BEGIN;

ALTER TABLE expense_event
    ADD COLUMN IF NOT EXISTS farm_id UUID REFERENCES farm(id) ON DELETE RESTRICT;

ALTER TABLE expense_event
    ADD COLUMN IF NOT EXISTS weekly_plan_id UUID REFERENCES weekly_plan(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_expense_event_farm_id
    ON expense_event(farm_id);
CREATE INDEX IF NOT EXISTS idx_expense_event_weekly_plan_id
    ON expense_event(weekly_plan_id);

-- Fail closed if existing weekly plans already disagree with their farm scope.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM weekly_plan wp
        JOIN farm f ON f.id = wp.farm_id
        WHERE wp.location_id IS DISTINCT FROM f.location_id
    ) THEN
        RAISE EXCEPTION 'weekly_plan_farm_location_mismatch: resolve existing rows before installing farm-scope enforcement';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION validate_expense_event_farm_weekly_plan_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    farm_location_id UUID;
    plan_location_id UUID;
    plan_farm_id UUID;
BEGIN
    IF NEW.farm_id IS NOT NULL THEN
        SELECT f.location_id INTO farm_location_id
        FROM farm f
        WHERE f.id = NEW.farm_id
        FOR SHARE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'expense_event % references a missing farm', NEW.id;
        END IF;

        IF farm_location_id IS DISTINCT FROM NEW.location_id THEN
            RAISE EXCEPTION 'expense_event % location does not match its farm', NEW.id;
        END IF;
    END IF;

    IF NEW.weekly_plan_id IS NOT NULL THEN
        SELECT wp.location_id, wp.farm_id
        INTO plan_location_id, plan_farm_id
        FROM weekly_plan wp
        WHERE wp.id = NEW.weekly_plan_id
        FOR SHARE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'expense_event % references a missing weekly plan', NEW.id;
        END IF;

        IF plan_location_id IS DISTINCT FROM NEW.location_id THEN
            RAISE EXCEPTION 'expense_event % location does not match its weekly plan', NEW.id;
        END IF;

        IF plan_farm_id IS NOT NULL AND NEW.farm_id IS DISTINCT FROM plan_farm_id THEN
            RAISE EXCEPTION 'expense_event % farm does not match its weekly plan farm', NEW.id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_expense_event_farm_weekly_plan_scope ON expense_event;
CREATE TRIGGER trg_expense_event_farm_weekly_plan_scope
    BEFORE INSERT OR UPDATE OF farm_id, weekly_plan_id, location_id
    ON expense_event
    FOR EACH ROW
    EXECUTE FUNCTION validate_expense_event_farm_weekly_plan_scope();

CREATE OR REPLACE FUNCTION validate_weekly_plan_farm_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    farm_location_id UUID;
BEGIN
    IF NEW.farm_id IS NOT NULL THEN
        SELECT f.location_id INTO farm_location_id
        FROM farm f
        WHERE f.id = NEW.farm_id
        FOR SHARE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'weekly_plan % references a missing farm', NEW.id;
        END IF;

        IF farm_location_id IS DISTINCT FROM NEW.location_id THEN
            RAISE EXCEPTION 'weekly_plan % location does not match its farm', NEW.id;
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM expense_event e
        WHERE e.weekly_plan_id = NEW.id
          AND (
              e.location_id IS DISTINCT FROM NEW.location_id
              OR (NEW.farm_id IS NOT NULL AND e.farm_id IS DISTINCT FROM NEW.farm_id)
          )
    ) THEN
        RAISE EXCEPTION 'weekly_plan % scope conflicts with linked expense events', NEW.id;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_weekly_plan_farm_scope ON weekly_plan;
CREATE TRIGGER trg_weekly_plan_farm_scope
    BEFORE INSERT OR UPDATE OF farm_id, location_id
    ON weekly_plan
    FOR EACH ROW
    EXECUTE FUNCTION validate_weekly_plan_farm_scope();

-- A farm cannot be moved to another location while scoped plans or expenses
-- still reference its current location. Detach/reconcile those rows first.
CREATE OR REPLACE FUNCTION prevent_farm_reparent_with_financial_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.location_id IS DISTINCT FROM OLD.location_id
       AND (
           EXISTS (SELECT 1 FROM expense_event e WHERE e.farm_id = OLD.id)
           OR EXISTS (SELECT 1 FROM weekly_plan wp WHERE wp.farm_id = OLD.id)
       ) THEN
        RAISE EXCEPTION 'farm % cannot change location while expenses or weekly plans reference it', OLD.id;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_farm_financial_scope ON farm;
CREATE TRIGGER trg_farm_financial_scope
    BEFORE UPDATE OF location_id ON farm
    FOR EACH ROW
    EXECUTE FUNCTION prevent_farm_reparent_with_financial_scope();

COMMENT ON COLUMN expense_event.farm_id IS
    'Optional typed farm scope; when set, farm.location_id must equal expense_event.location_id.';
COMMENT ON COLUMN expense_event.weekly_plan_id IS
    'Optional typed plan relation; farm/location scope must agree with the expense when the plan has a farm.';

COMMIT;
