-- Retire unscoped adoption readiness/configuration writes pending scoped actions.

BEGIN;

DO $$
DECLARE
    target_table_name TEXT;
    target_table TEXT;
    target_role TEXT;
    target_column TEXT;
BEGIN
    FOREACH target_table_name IN ARRAY ARRAY[
        'solution_adopter_readiness', 'solution_configuration'
    ] LOOP
        target_table := pg_catalog.format('public.%I', target_table_name);
        IF pg_catalog.to_regclass(target_table) IS NULL THEN
            RAISE EXCEPTION 'Expected adoption table % is missing', target_table;
        END IF;

        EXECUTE pg_catalog.format(
            'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE %s FROM PUBLIC',
            target_table
        );
        FOR target_column IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = pg_catalog.to_regclass(target_table)
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%I), UPDATE (%I) ON TABLE %s FROM PUBLIC',
                target_column, target_column, target_table
            );
        END LOOP;

        FOREACH target_role IN ARRAY ARRAY[
            'kokonut_runtime', 'kokonut_directus_runtime'
        ] LOOP
            IF EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role
            ) THEN
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE %s FROM %I',
                    target_table, target_role
                );
                FOR target_column IN
                    SELECT attribute.attname
                      FROM pg_catalog.pg_attribute AS attribute
                     WHERE attribute.attrelid = pg_catalog.to_regclass(target_table)
                       AND attribute.attnum > 0
                       AND NOT attribute.attisdropped
                LOOP
                    EXECUTE pg_catalog.format(
                        'REVOKE INSERT (%I), UPDATE (%I) ON TABLE %s FROM %I',
                        target_column, target_column, target_table, target_role
                    );
                END LOOP;
            END IF;
        END LOOP;
    END LOOP;
END;
$$;

COMMENT ON TABLE public.solution_adopter_readiness IS
    'Readiness records are not directly mutable by shared runtime/Directus roles; use a location-scoped assessment and independent review action.';
COMMENT ON TABLE public.solution_configuration IS
    'Configuration records are not directly mutable by shared runtime/Directus roles; use a location-scoped draft and independent approval action.';

COMMIT;
