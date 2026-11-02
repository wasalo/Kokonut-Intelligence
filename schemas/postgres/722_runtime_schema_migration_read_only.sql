-- The application reads the migration ledger during fail-closed startup
-- readiness checks. Migration execution and ledger writes remain with the
-- database-owner maintenance path; runtime compatibility grants must not
-- expose ledger mutation.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF pg_catalog.to_regclass('public.schema_migration') IS NULL THEN
        RAISE EXCEPTION 'required relation public.schema_migration is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        REVOKE ALL PRIVILEGES ON TABLE public.schema_migration FROM kokonut_runtime;

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = 'public.schema_migration'::REGCLASS
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.schema_migration FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.schema_migration TO kokonut_runtime;
    END IF;

    COMMENT ON TABLE public.schema_migration IS
        'The ordered migration runner owns ledger writes; kokonut_runtime requires read-only access for application schema readiness.';
END;
$$;

COMMIT;
