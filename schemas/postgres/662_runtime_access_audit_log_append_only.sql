-- Keep capability-access audit evidence readable and appendable, but prevent
-- runtime mutation. Any retention cleanup requires separately authorized
-- administration under a configured retention policy.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.access_audit_log') IS NULL THEN
        RAISE EXCEPTION 'required append-only relation public.access_audit_log is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.access_audit_log FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.access_audit_log'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE SELECT (%1$I) ON TABLE public.access_audit_log FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.access_audit_log FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.access_audit_log FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.access_audit_log FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT, INSERT ON TABLE public.access_audit_log TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.access_audit_log IS
    'Capability-access audit evidence. The runtime role may SELECT and INSERT only; retention cleanup requires separately authorized administration under a configured policy.';

COMMIT;
