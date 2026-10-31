-- Keep data-access evidence readable and appendable, but immutable to runtime.
-- Migration 301 already protects rows with a trigger; this adds a privilege
-- boundary so ordinary application code cannot attempt UPDATE or DELETE.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.data_access_log') IS NULL THEN
        RAISE EXCEPTION 'required append-only relation public.data_access_log is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.data_access_log FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.data_access_log'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE SELECT (%1$I) ON TABLE public.data_access_log FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.data_access_log FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.data_access_log FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.data_access_log FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT, INSERT ON TABLE public.data_access_log TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.data_access_log IS
    'Append-only audit evidence. The general runtime may SELECT and INSERT; UPDATE and DELETE are denied.';

COMMIT;
