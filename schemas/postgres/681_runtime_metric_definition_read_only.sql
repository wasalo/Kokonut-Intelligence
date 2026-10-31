-- Metric definitions are governed reference inputs to the Kernel runtime.
-- Curated changes are applied through the admin seed/migration path; runtime
-- computations read definitions and write separate metric_value rows.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.metric_definition');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.metric_definition is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.metric_definition FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.metric_definition FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.metric_definition FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.metric_definition FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.metric_definition TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.metric_definition IS
    'Governed metric definitions are read-only to kokonut_runtime; curated changes use the admin seed/migration path. This DML boundary does not establish tenant isolation.';

COMMIT;
