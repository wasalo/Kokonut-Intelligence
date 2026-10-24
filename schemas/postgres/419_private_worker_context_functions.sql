-- Replace migration 405's broad PUBLIC context-helper grants with explicit
-- runtime, worker-execution, and bounded function-owner privileges.

BEGIN;

REVOKE ALL ON FUNCTION kokonut_security.current_tenant_context()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.set_worker_tenant_context(
    TEXT, UUID, TEXT, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
            TO kokonut_runtime;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_execution') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
            TO kokonut_worker_execution;
        GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(
            TEXT, UUID, TEXT, TEXT
        ) TO kokonut_worker_execution;
        GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
            TO kokonut_worker_execution;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_context_owner') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
            TO kokonut_worker_context_owner;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_farm_activity_event_owner') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
            TO kokonut_farm_activity_event_owner;
    END IF;
END;
$$;

COMMIT;
