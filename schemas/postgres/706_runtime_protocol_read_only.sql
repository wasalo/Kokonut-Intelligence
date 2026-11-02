-- Protocol references are read-only to the application runtime. Repository
-- writes are seeded with the maintenance identity; external importer use of
-- kokonut_runtime is not established by source review. This DML boundary does
-- not establish tenant isolation for SELECT queries.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    relation_oid := pg_catalog.to_regclass('public.protocol');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.protocol is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.protocol FROM kokonut_runtime';

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.protocol FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        EXECUTE 'GRANT SELECT ON TABLE public.protocol TO kokonut_runtime';
    END IF;

    COMMENT ON TABLE public.protocol IS
        'Protocol reference records are read-only to kokonut_runtime. Seed, administrative, and import writes require separate maintenance authority. External importer use through kokonut_runtime is unconfirmed by repository source review. This DML boundary does not establish tenant isolation for SELECT queries.';
END;
$$;

COMMIT;
