-- Crop GDD and phenology defaults are shared configuration read by analytics.
-- The curated seed/admin path owns changes; general runtime queries stay valid.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.crop_gdd_config');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.crop_gdd_config is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.crop_gdd_config FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.crop_gdd_config FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.crop_gdd_config FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.crop_gdd_config FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.crop_gdd_config TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.crop_gdd_config IS
    'Shared crop phenology and GDD defaults. kokonut_runtime has read-only access; changes use the curated administrative path.';

COMMIT;
