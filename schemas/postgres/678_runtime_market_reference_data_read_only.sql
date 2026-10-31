-- Commodity categories and market units are reference labels seeded by the
-- schema. Keep them readable to the Kernel runtime while reserving catalog
-- maintenance for the separate administration path.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.market_reference_data');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.market_reference_data is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.market_reference_data FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.market_reference_data FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.market_reference_data FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.market_reference_data FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.market_reference_data TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.market_reference_data IS
    'Shared commodity-category and unit reference labels. kokonut_runtime has read-only access; catalog maintenance uses the separate administration path.';

COMMIT;
