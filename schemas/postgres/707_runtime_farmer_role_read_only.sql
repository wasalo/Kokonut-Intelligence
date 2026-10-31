-- Farmer roles define default authorization permissions. The runtime reads
-- those defaults when assigning a role, but role-definition changes belong to
-- the reviewed maintenance/schema path. External runtime-login importers are
-- not confirmed by repository source review. This DML boundary does not prove
-- tenant isolation for the role catalog read.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    relation_oid := pg_catalog.to_regclass('public.farmer_role');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.farmer_role is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.farmer_role FROM kokonut_runtime';

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.farmer_role FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        EXECUTE 'GRANT SELECT ON TABLE public.farmer_role TO kokonut_runtime';
    END IF;

    COMMENT ON TABLE public.farmer_role IS
        'Farmer role defaults are readable by kokonut_runtime for role assignment; definition changes require reviewed maintenance/schema authority. External importer use through kokonut_runtime is unconfirmed. This boundary does not establish tenant isolation.';
END;
$$;

COMMIT;
