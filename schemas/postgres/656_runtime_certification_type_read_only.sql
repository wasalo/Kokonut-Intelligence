-- Certification types are initialized by migration 143 and used as shared
-- lookup data. Runtime edits must go through a reviewed reference-data
-- migration rather than the general application identity.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.certification_type') IS NULL THEN
        RAISE EXCEPTION 'required read-only relation public.certification_type is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.certification_type
            FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.certification_type'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.certification_type FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.certification_type FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.certification_type FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.certification_type TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.certification_type IS
    'Shared certification reference data. kokonut_runtime has read-only access; edits require a reviewed reference-data migration.';

COMMIT;
