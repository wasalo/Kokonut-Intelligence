-- Process benchmarks have no application write/read path, seed, or Directus
-- collection policy. The owner confirmed no external importer uses the runtime
-- database identity. Preserve SELECT and separate maintenance authority.
-- This boundary does not establish tenant isolation for SELECT queries.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    relation_oid := pg_catalog.to_regclass('public.process_benchmark');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.process_benchmark is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.process_benchmark FROM kokonut_runtime';

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.process_benchmark FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        EXECUTE 'GRANT SELECT ON TABLE public.process_benchmark TO kokonut_runtime';
    END IF;

    COMMENT ON TABLE public.process_benchmark IS
        'Process benchmarks are read-only to kokonut_runtime. Administrative or import writes require separate maintenance authority. This DML boundary does not establish tenant isolation for SELECT queries.';
END;
$$;

COMMIT;
