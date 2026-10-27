-- Operations protocols are shared versioned handbook references initialized
-- by carbon-framework seeds; runtime services use them as report content.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.operations_protocol') IS NULL THEN
        RAISE EXCEPTION 'required relation public.operations_protocol is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.operations_protocol FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.operations_protocol'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.operations_protocol FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.operations_protocol FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.operations_protocol FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.operations_protocol TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.operations_protocol IS
    'Shared versioned farm-operation handbook references. kokonut_runtime has read-only access; updates require reviewed reference-data changes.';

COMMIT;
