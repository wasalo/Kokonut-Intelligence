-- Yield benchmarks are read inputs to the analytics service. Keep them
-- readable to the Kernel runtime and reserve mutation for the separate
-- administration path.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.yield_benchmark');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.yield_benchmark is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.yield_benchmark FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.yield_benchmark FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.yield_benchmark FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.yield_benchmark FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.yield_benchmark TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.yield_benchmark IS
    'Location-scoped yield comparison inputs. kokonut_runtime has read-only access; this DML boundary does not establish tenant isolation.';

COMMIT;
