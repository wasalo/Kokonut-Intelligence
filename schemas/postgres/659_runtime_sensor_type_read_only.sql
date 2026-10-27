-- Sensor-type definitions control the units and accepted ranges used when
-- devices are registered and readings are validated. The core taxonomy is
-- seeded by migration 011; new definitions and corrections require a reviewed
-- schema/data migration rather than general runtime table access.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF to_regclass('public.sensor_type') IS NULL THEN
        RAISE EXCEPTION 'required read-only reference relation public.sensor_type is missing';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.sensor_type FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = 'public.sensor_type'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.sensor_type FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.sensor_type FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.sensor_type FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.sensor_type TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.sensor_type IS
    'Shared sensor measurement definitions. kokonut_runtime has read-only access; unit/range changes require a reviewed schema/data migration.';

COMMIT;
