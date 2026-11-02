-- Water-access and attestation-plan records are currently reporting inputs.
-- The application and Directus Auditor paths are read-only; reviewed
-- administration remains outside kokonut_runtime.
-- This DML boundary does not establish tenant isolation for SELECT queries.
BEGIN;

DO $$
DECLARE
    relation_name TEXT;
    column_name TEXT;
    relation_oid REGCLASS;
    read_only_relations CONSTANT TEXT[] := ARRAY[
        'water_access',
        'attestation_plan'
    ];
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        FOREACH relation_name IN ARRAY read_only_relations LOOP
            relation_oid := to_regclass(format('public.%I', relation_name));
            IF relation_oid IS NULL THEN
                RAISE EXCEPTION 'required relation public.% is missing', relation_name;
            END IF;

            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE %I.%I FROM kokonut_runtime',
                'public', relation_name
            );

            FOR column_name IN
                SELECT attname
                  FROM pg_catalog.pg_attribute
                 WHERE attrelid = relation_oid
                   AND attnum > 0
                   AND NOT attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE INSERT (%I) ON TABLE %I.%I FROM kokonut_runtime',
                    column_name, 'public', relation_name
                );
                EXECUTE format(
                    'REVOKE UPDATE (%I) ON TABLE %I.%I FROM kokonut_runtime',
                    column_name, 'public', relation_name
                );
                EXECUTE format(
                    'REVOKE REFERENCES (%I) ON TABLE %I.%I FROM kokonut_runtime',
                    column_name, 'public', relation_name
                );
            END LOOP;

            EXECUTE format(
                'GRANT SELECT ON TABLE %I.%I TO kokonut_runtime',
                'public', relation_name
            );
            EXECUTE format(
                'COMMENT ON TABLE %I.%I IS %L',
                'public', relation_name,
                'Reporting input is read-only to kokonut_runtime; reviewed administration owns mutations. This DML boundary does not establish tenant isolation.'
            );
        END LOOP;
    END IF;
END;
$$;

COMMIT;
