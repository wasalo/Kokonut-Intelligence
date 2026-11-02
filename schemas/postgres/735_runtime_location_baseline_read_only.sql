-- Effective-dated location baselines have no active application writer. The
-- original migration backfilled this relation from location; future import or
-- administrative changes use the administrator-controlled seed/import path.
-- This boundary preserves application reads and does not establish tenant
-- isolation for those reads.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    relation_oid := pg_catalog.to_regclass('public.location_baseline');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.location_baseline is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.location_baseline FROM kokonut_runtime';

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.location_baseline FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        EXECUTE 'GRANT SELECT ON TABLE public.location_baseline TO kokonut_runtime';
    END IF;

    COMMENT ON TABLE public.location_baseline IS
        'Effective-dated location baseline history is read-only to kokonut_runtime. Administrative/import writes use the administrator-controlled seed/import path. This DML boundary does not establish tenant isolation for SELECT queries.';
END;
$$;

COMMIT;
