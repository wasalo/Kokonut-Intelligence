-- Waste classifications are seeded reference data. Operational records keep
-- their own type/method values on waste_stream; changing the shared catalogs
-- requires a reviewed schema/data migration rather than runtime DML.
BEGIN;

DO $$
DECLARE
    table_name TEXT;
    column_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['waste_type', 'disposal_method']
    LOOP
        IF to_regclass(format('public.%I', table_name)) IS NULL THEN
            RAISE EXCEPTION 'required read-only reference relation public.% is missing', table_name;
        END IF;

        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
            EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM kokonut_runtime', table_name);

            FOR column_name IN
                SELECT attname
                  FROM pg_catalog.pg_attribute
                 WHERE attrelid = to_regclass(format('public.%I', table_name))
                   AND attnum > 0
                   AND NOT attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE INSERT (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name,
                    table_name
                );
                EXECUTE format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name,
                    table_name
                );
                EXECUTE format(
                    'REVOKE REFERENCES (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name,
                    table_name
                );
            END LOOP;

            EXECUTE format('GRANT SELECT ON TABLE public.%I TO kokonut_runtime', table_name);
        END IF;
    END LOOP;
END;
$$;

COMMENT ON TABLE public.waste_type IS
    'Shared waste classification reference. kokonut_runtime has read-only access; changes require a reviewed schema/data migration.';
COMMENT ON TABLE public.disposal_method IS
    'Shared waste disposal reference. kokonut_runtime has read-only access; changes require a reviewed schema/data migration.';

COMMIT;
