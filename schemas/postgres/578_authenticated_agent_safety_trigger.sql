-- Enforce the legacy governed-lifecycle guard for authenticated worker roles.
-- The caller-set app.agent_id marker remains restrictive for compatibility,
-- but the database role is the trusted worker identity signal.

BEGIN;

CREATE OR REPLACE FUNCTION public.assert_agent_safety()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
DECLARE
    caller_agent_marker TEXT;
    authenticated_worker BOOLEAN;
BEGIN
    caller_agent_marker := current_setting('app.agent_id', TRUE);
    authenticated_worker :=
        current_user = 'kokonut_worker_execution'
        OR pg_catalog.pg_has_role(
            session_user, 'kokonut_worker_execution', 'MEMBER'
        );

    -- app.agent_id is caller-controlled and can only add a restriction. A
    -- worker's database role independently activates the guard, even when
    -- that compatibility marker is absent or cleared.
    IF NOT authenticated_worker
       AND (caller_agent_marker IS NULL OR caller_agent_marker = '') THEN
        RETURN NEW;
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status
       AND NEW.status IN ('verified', 'published') THEN
        RAISE EXCEPTION 'Agent worker operations cannot set status to % on %',
            NEW.status, TG_TABLE_NAME
            USING ERRCODE = '42501';
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.assert_agent_safety() IS
    'Prevents authenticated kokonut_worker_execution operations from changing governed status to verified or published. The caller-set app.agent_id compatibility marker adds this restriction but is not an identity or authorization boundary.';

COMMIT;
