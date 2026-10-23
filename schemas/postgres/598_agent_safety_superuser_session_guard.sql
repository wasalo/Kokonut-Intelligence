-- Keep authenticated worker lifecycle guards from treating a database
-- administrator as a worker merely because PostgreSQL superusers can act as
-- members of every role. Administrative seed/bootstrap sessions must retain
-- their operator lifecycle behavior; explicitly entered worker roles remain
-- guarded through current_user.

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
        OR (
            NOT EXISTS (
                SELECT 1
                  FROM pg_catalog.pg_roles AS session_role
                 WHERE session_role.rolname = session_user
                   AND session_role.rolsuper
            )
            AND pg_catalog.pg_has_role(
                session_user, 'kokonut_worker_execution', 'MEMBER'
            )
        );

    -- Superusers can SET ROLE to an execution role, which current_user catches
    -- above. A plain superuser session is administrative, not a worker login;
    -- pg_has_role alone reports its implicit ability to act as any role.
    -- The caller-controlled compatibility marker can still add a restriction.
    IF NOT authenticated_worker
       AND (caller_agent_marker IS NULL OR caller_agent_marker = '') THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.status IN ('verified', 'published') THEN
            RAISE EXCEPTION 'Agent worker operations cannot insert terminal status % on %',
                NEW.status, TG_TABLE_NAME
                USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'UPDATE'
       AND NEW.status IS DISTINCT FROM OLD.status
       AND NEW.status IN ('verified', 'published') THEN
        RAISE EXCEPTION 'Agent worker operations cannot set status to % on %',
            NEW.status, TG_TABLE_NAME
            USING ERRCODE = '42501';
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.assert_agent_safety() IS
    'Prevents kokonut_worker_execution operations from inserting or promoting governed records to verified/published. Superuser administrative sessions are not inferred to be workers from implicit role membership; explicitly entered worker roles and the restrictive compatibility marker remain guarded.';

COMMIT;
