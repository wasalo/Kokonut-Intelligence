-- ============================================================
-- 365_expense_weekly_plan_scope_exception.sql
-- Permit an explicit same-location cross-farm weekly-plan edge while
-- preserving strict default farm and location scope validation.
-- ============================================================

BEGIN;

ALTER TABLE expense_event
    ADD COLUMN IF NOT EXISTS weekly_plan_scope_exception BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS weekly_plan_scope_exception_reason TEXT;

ALTER TABLE expense_event
    DROP CONSTRAINT IF EXISTS chk_expense_event_weekly_plan_scope_exception,
    ADD CONSTRAINT chk_expense_event_weekly_plan_scope_exception CHECK (
        (
            weekly_plan_scope_exception = FALSE
            AND weekly_plan_scope_exception_reason IS NULL
        )
        OR
        (
            weekly_plan_scope_exception = TRUE
            AND weekly_plan_id IS NOT NULL
            AND farm_id IS NOT NULL
            AND NULLIF(BTRIM(weekly_plan_scope_exception_reason), '') IS NOT NULL
        )
    );

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

    IF NEW.weekly_plan_scope_exception AND NEW.weekly_plan_id IS NULL THEN
        RAISE EXCEPTION 'expense_event % scope exception requires a weekly plan', NEW.id;
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

        IF NEW.weekly_plan_scope_exception AND (NEW.farm_id IS NULL OR plan_farm_id IS NULL) THEN
            RAISE EXCEPTION 'expense_event % cross-farm exception requires both farm identities', NEW.id;
        END IF;

        IF plan_farm_id IS NOT NULL AND NEW.farm_id IS DISTINCT FROM plan_farm_id
           AND NOT NEW.weekly_plan_scope_exception THEN
            RAISE EXCEPTION 'expense_event % farm does not match its weekly plan farm; explicit same-location scope exception required', NEW.id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_expense_event_farm_weekly_plan_scope ON expense_event;
CREATE TRIGGER trg_expense_event_farm_weekly_plan_scope
    BEFORE INSERT OR UPDATE OF
        farm_id, weekly_plan_id, location_id,
        weekly_plan_scope_exception, weekly_plan_scope_exception_reason
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
              OR (
                  e.farm_id IS DISTINCT FROM NEW.farm_id
                  AND (
                      NOT e.weekly_plan_scope_exception
                      OR NULLIF(BTRIM(e.weekly_plan_scope_exception_reason), '') IS NULL
                  )
              )
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

COMMENT ON COLUMN expense_event.weekly_plan_scope_exception IS
    'Explicit per-expense owner-approved exception for different farms at the same location; never waives location consistency.';
COMMENT ON COLUMN expense_event.weekly_plan_scope_exception_reason IS
    'Required nonblank audit rationale whenever weekly_plan_scope_exception is true.';
COMMENT ON COLUMN expense_event.weekly_plan_id IS
    'Optional typed plan relation; farm equality is required unless an explicit per-row same-location scope exception is recorded.';

COMMIT;
