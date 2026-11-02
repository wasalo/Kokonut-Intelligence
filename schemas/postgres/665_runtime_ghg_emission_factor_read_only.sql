-- Emission factors are shared reference values initialized by carbon seeds.
-- Runtime services use them as calculation inputs; updates require a reviewed
-- reference-data change rather than an unscoped application write.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.ghg_emission_factor') IS NULL THEN
        RAISE EXCEPTION 'required relation public.ghg_emission_factor is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.ghg_emission_factor FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.ghg_emission_factor'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.ghg_emission_factor FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.ghg_emission_factor FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.ghg_emission_factor FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.ghg_emission_factor TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.ghg_emission_factor IS
    'Shared greenhouse-gas emission-factor references. kokonut_runtime has read-only access; updates require reviewed reference-data changes.';

COMMIT;
