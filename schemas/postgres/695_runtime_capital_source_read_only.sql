-- Capital-source records are consumed as reporting inputs. The application
-- has no direct writer; reviewed pilot/catalog seeding uses the maintenance
-- database identity. This revocation affects only kokonut_runtime.
-- It does not establish tenant isolation for SELECT queries.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    relation_oid := pg_catalog.to_regclass('public.capital_source');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.capital_source is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.capital_source FROM kokonut_runtime';

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.capital_source FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        EXECUTE 'GRANT SELECT ON TABLE public.capital_source TO kokonut_runtime';
    END IF;

    COMMENT ON TABLE public.capital_source IS
        'Capital-source reporting records are read-only to kokonut_runtime. Reviewed seed and administration workflows use separate maintenance or Directus authority. This DML boundary does not establish tenant isolation for SELECT queries.';
END;
$$;

COMMIT;
