-- Legacy agent-action logging has no authenticated runtime writer. Keep the
-- historical log readable for exports while forcing future writes through a
-- separately reviewed signed worker or operator path. Directus uses its own
-- runtime role and its existing permissions are intentionally unchanged.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.agent_action_log') IS NULL THEN
        RAISE EXCEPTION 'required relation public.agent_action_log is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.agent_action_log FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.agent_action_log'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.agent_action_log FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.agent_action_log FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.agent_action_log FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.agent_action_log TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.agent_action_log IS
    'Historical agent-action evidence. kokonut_runtime has read-only access; writes require an authenticated, scoped worker or operator boundary.';

COMMIT;
