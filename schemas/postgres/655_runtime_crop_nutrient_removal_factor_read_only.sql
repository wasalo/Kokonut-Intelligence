-- Agronomic removal factors are initialized by schema migration 151 and
-- consumed by nutrient-budget calculations. Updates belong in a reviewed
-- reference-data migration, not the general runtime identity.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.crop_nutrient_removal_factor') IS NULL THEN
        RAISE EXCEPTION 'required read-only relation public.crop_nutrient_removal_factor is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.crop_nutrient_removal_factor
            FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.crop_nutrient_removal_factor'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.crop_nutrient_removal_factor FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.crop_nutrient_removal_factor FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.crop_nutrient_removal_factor FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.crop_nutrient_removal_factor TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.crop_nutrient_removal_factor IS
    'Shared agronomic reference factors. kokonut_runtime has read-only access; edits require a reviewed reference-data migration.';

COMMIT;
