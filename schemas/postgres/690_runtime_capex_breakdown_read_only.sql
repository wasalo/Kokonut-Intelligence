-- CAPEX breakdown is a reporting input. Current application call sites read
-- it only; data changes remain available through the reviewed admin path.
-- This DML boundary does not establish tenant isolation for SELECT queries.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.capex_breakdown');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.capex_breakdown is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.capex_breakdown FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.capex_breakdown FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.capex_breakdown FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.capex_breakdown FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.capex_breakdown TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.capex_breakdown IS
    'CAPEX reporting input is read-only to kokonut_runtime; reviewed administration owns mutations. This DML boundary does not establish tenant isolation.';

COMMIT;
