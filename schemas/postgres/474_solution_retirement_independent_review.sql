-- Retirement approval must be attributable and independent of its proposer.

BEGIN;

CREATE OR REPLACE FUNCTION kokonut_security.enforce_solution_retirement_independent_review()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND NEW.created_by_party_id IS DISTINCT FROM OLD.created_by_party_id THEN
        RAISE EXCEPTION 'solution retirement proposer attribution is immutable'
            USING ERRCODE = '55000';
    END IF;

    IF TG_OP = 'UPDATE'
       AND OLD.approved_by_party_id IS NOT NULL
       AND (NEW.approved_by_party_id IS DISTINCT FROM OLD.approved_by_party_id
            OR NEW.approved_at IS DISTINCT FROM OLD.approved_at) THEN
        RAISE EXCEPTION 'solution retirement approval attribution is immutable'
            USING ERRCODE = '55000';
    END IF;

    IF NEW.approved_by_party_id IS NOT NULL
       AND (NEW.created_by_party_id IS NULL
            OR NEW.approved_by_party_id = NEW.created_by_party_id) THEN
        RAISE EXCEPTION 'solution retirement requires an independent attributed reviewer'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.status IN ('approved', 'migration', 'sunset', 'completed')
       AND (NEW.created_by_party_id IS NULL
            OR NEW.approved_by_party_id IS NULL
            OR NEW.approved_at IS NULL
            OR NEW.approved_by_party_id = NEW.created_by_party_id) THEN
        RAISE EXCEPTION 'approved solution retirement requires an independent attributed reviewer'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION kokonut_security.enforce_solution_retirement_independent_review()
    FROM PUBLIC;

DROP TRIGGER IF EXISTS trg_solution_retirement_independent_review
    ON public.solution_retirement;
CREATE TRIGGER trg_solution_retirement_independent_review
    BEFORE INSERT OR UPDATE ON public.solution_retirement
    FOR EACH ROW
    EXECUTE FUNCTION kokonut_security.enforce_solution_retirement_independent_review();

COMMENT ON FUNCTION kokonut_security.enforce_solution_retirement_independent_review() IS
'Enforces attributed, independent retirement review for new and changed retirement states; the proposer cannot approve their own proposal, approval attribution cannot be replaced, and unreviewed legacy rows are not rewritten by this migration.';

COMMIT;
