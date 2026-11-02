-- The application reads a location-scoped living-wage reference, while the
-- repository's Adelphi example is loaded through the maintenance seed path.
-- External importer use through kokonut_runtime is not established by source
-- review; this boundary does not remove separate maintenance/import grants.
-- This DML boundary does not establish tenant isolation for SELECT queries.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    relation_oid := pg_catalog.to_regclass('public.living_wage_benchmark');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.living_wage_benchmark is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.living_wage_benchmark FROM kokonut_runtime';

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.living_wage_benchmark FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        EXECUTE 'GRANT SELECT ON TABLE public.living_wage_benchmark TO kokonut_runtime';
    END IF;

    COMMENT ON TABLE public.living_wage_benchmark IS
        'Living-wage benchmark references are read-only to kokonut_runtime. Seed, administrative, or import writes require separate maintenance authority. External importer use through kokonut_runtime is unconfirmed by repository source review. This DML boundary does not establish tenant isolation for SELECT queries.';
END;
$$;

COMMIT;
