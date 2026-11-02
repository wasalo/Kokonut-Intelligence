-- These global lookup catalogues are initialized by schema migrations and
-- consumed by operational services as read-only references. Runtime edits
-- require a reviewed reference-data migration.
BEGIN;

DO $$
DECLARE
    table_name TEXT;
    column_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'cooperative_type',
        'dfs_insurance_product_type'
    ] LOOP
        IF to_regclass(format('public.%I', table_name)) IS NULL THEN
            RAISE EXCEPTION 'required read-only reference relation public.% is missing', table_name;
        END IF;
    END LOOP;

    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        FOREACH table_name IN ARRAY ARRAY[
            'cooperative_type',
            'dfs_insurance_product_type'
        ] LOOP
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM kokonut_runtime',
                table_name
            );

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

            EXECUTE format(
                'GRANT SELECT ON TABLE public.%I TO kokonut_runtime',
                table_name
            );
        END LOOP;
    END IF;
END;
$$;

COMMENT ON TABLE public.cooperative_type IS
    'Shared cooperative-type reference data. kokonut_runtime has read-only access; edits require a reviewed reference-data migration.';
COMMENT ON TABLE public.dfs_insurance_product_type IS
    'Shared insurance-product reference data. kokonut_runtime has read-only access; edits require a reviewed reference-data migration.';

COMMIT;
