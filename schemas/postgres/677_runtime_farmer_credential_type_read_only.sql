-- Seeded farmer credential types are descriptive guidance. Credential records
-- retain their submitted type as text, so the runtime has no application writer.
-- Keep the catalog readable while reserving changes for curated administration.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.farmer_credential_type');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.farmer_credential_type is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.farmer_credential_type FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.farmer_credential_type FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.farmer_credential_type FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.farmer_credential_type FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.farmer_credential_type TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.farmer_credential_type IS
    'Curated farmer credential type guidance. kokonut_runtime has read-only access; credential records retain their type as submitted text.';

COMMIT;
