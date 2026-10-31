-- Crop-family taxonomy is shared reference data used by crop-rotation reads.
-- Its initial taxonomy is seeded in migration 150; edits belong to seed/admin
-- maintenance, not to the general application runtime identity.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.crop_family') IS NULL THEN
        RAISE EXCEPTION 'required read-only relation public.crop_family is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.crop_family FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.crop_family'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.crop_family FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.crop_family FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.crop_family FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.crop_family TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.crop_family IS
    'Shared crop-family reference taxonomy. kokonut_runtime has read-only access; seed/admin processes own taxonomy changes.';

COMMIT;
