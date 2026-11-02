-- Freshness configuration is maintained by the seed path running with the
-- database administrator identity.
-- The isolated freshness worker reads this relation only through migration
-- 645's bounded list_freshness_configs function. Preserve runtime SELECT for
-- compatibility while keeping writes on the administrator-controlled path.
-- This DML boundary does not change the signed freshness-worker contract.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    relation_oid := pg_catalog.to_regclass('public.data_freshness_config');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.data_freshness_config is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.data_freshness_config '
            'FROM kokonut_runtime';

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.data_freshness_config FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        EXECUTE 'GRANT SELECT ON TABLE public.data_freshness_config '
            'TO kokonut_runtime';
    END IF;

    COMMENT ON TABLE public.data_freshness_config IS
    'Data freshness configuration is read-only to kokonut_runtime. The isolated worker reads through migration 645 bounded functions; seed/admin writes use the administrator-controlled path.';
END;
$$;

COMMIT;
