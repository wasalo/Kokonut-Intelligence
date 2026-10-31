-- Managed-hive capture, lifecycle, inspection, and review now use the
-- signed, location-scoped Gateway functions. Retire legacy direct table DML.
-- This change preserves reporting reads; it does not establish tenant-safe SELECT.
BEGIN;

DO $$
DECLARE
    role_name TEXT;
    role_sql TEXT;
    relation_name TEXT;
    column_name TEXT;
    relation_oid REGCLASS;
    protected_relations CONSTANT TEXT[] := ARRAY[
        'hive_record',
        'pollinator_hive_inspection'
    ];
    protected_roles CONSTANT TEXT[] := ARRAY[
        'PUBLIC',
        'kokonut_runtime',
        'kokonut_directus_runtime'
    ];
BEGIN
    FOREACH relation_name IN ARRAY protected_relations LOOP
        relation_oid := pg_catalog.to_regclass(
            pg_catalog.format('public.%I', relation_name)
        );
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.% is missing', relation_name;
        END IF;

        FOREACH role_name IN ARRAY protected_roles LOOP
            IF role_name = 'PUBLIC'
               OR EXISTS (
                   SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name
               ) THEN
                role_sql := CASE
                    WHEN role_name = 'PUBLIC' THEN 'PUBLIC'
                    ELSE pg_catalog.quote_ident(role_name)
                END;

                IF role_name = 'kokonut_runtime' THEN
                    EXECUTE pg_catalog.format(
                        'REVOKE ALL PRIVILEGES ON TABLE %I.%I FROM %s',
                        'public', relation_name, role_sql
                    );
                ELSE
                    EXECUTE pg_catalog.format(
                        'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
                        'ON TABLE %I.%I FROM %s',
                        'public', relation_name, role_sql
                    );
                END IF;

                FOR column_name IN
                    SELECT attribute.attname
                      FROM pg_catalog.pg_attribute AS attribute
                     WHERE attribute.attrelid = relation_oid
                       AND attribute.attnum > 0
                       AND NOT attribute.attisdropped
                LOOP
                    EXECUTE pg_catalog.format(
                        'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                        'ON TABLE %2$I.%3$I FROM %4$s',
                        column_name, 'public', relation_name, role_sql
                    );
                END LOOP;

                IF role_name = 'kokonut_runtime' THEN
                    EXECUTE pg_catalog.format(
                        'GRANT SELECT ON TABLE %I.%I TO %s',
                        'public', relation_name, role_sql
                    );
                END IF;
            END IF;
        END LOOP;

        EXECUTE pg_catalog.format(
            'COMMENT ON TABLE %I.%I IS %L',
            'public',
            relation_name,
            'Managed-hive writes use signed location-scoped Gateway functions; direct runtime and Directus DML is denied. Reporting reads remain non-tenant-isolated.'
        );
    END LOOP;
END;
$$;

COMMIT;
