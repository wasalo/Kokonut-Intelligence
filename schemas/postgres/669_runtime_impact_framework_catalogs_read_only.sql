-- Impact frameworks and dimensions are shared, seeded reporting references.
-- Keep the Kernel runtime read-only; operator-maintained changes remain on the
-- separate administrative path.
BEGIN;

DO $$
DECLARE
    relation_name TEXT;
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        FOREACH relation_name IN ARRAY ARRAY[
            'impact_framework',
            'impact_dimension'
        ] LOOP
            relation_oid := to_regclass(format('public.%I', relation_name));
            IF relation_oid IS NULL THEN
                RAISE EXCEPTION 'required relation public.% is missing', relation_name;
            END IF;

            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM kokonut_runtime',
                relation_name
            );

            FOR column_name IN
                SELECT attname
                  FROM pg_catalog.pg_attribute
                 WHERE attrelid = relation_oid
                   AND attnum > 0
                   AND NOT attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE INSERT (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name, relation_name
                );
                EXECUTE format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name, relation_name
                );
                EXECUTE format(
                    'REVOKE REFERENCES (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name, relation_name
                );
            END LOOP;

            EXECUTE format(
                'GRANT SELECT ON TABLE public.%I TO kokonut_runtime',
                relation_name
            );
        END LOOP;
    END IF;
END;
$$;

COMMENT ON TABLE public.impact_framework IS
    'Shared impact-framework reporting references. kokonut_runtime has read-only access; updates use the administrative reference-data path.';
COMMENT ON TABLE public.impact_dimension IS
    'Shared impact-framework dimension references. kokonut_runtime has read-only access; updates use the administrative reference-data path.';

COMMIT;
