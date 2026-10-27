-- Carbon benchmarks are shared literature references initialized by seeds.
-- Application consumers use them as inputs to analytics and CRISP scoring;
-- runtime edits must go through a reviewed reference-data update.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.carbon_benchmark') IS NULL THEN
        RAISE EXCEPTION 'required relation public.carbon_benchmark is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.carbon_benchmark FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.carbon_benchmark'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.carbon_benchmark FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.carbon_benchmark FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.carbon_benchmark FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.carbon_benchmark TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.carbon_benchmark IS
    'Shared literature reference data for carbon analytics. kokonut_runtime has read-only access; updates require a reviewed reference-data migration.';

COMMIT;
