-- `schema_version` records are written by the ordered migration/bootstrap
-- runner, which uses the maintenance database identity. Keep application
-- runtime reads but remove its unnecessary mutation authority. Source review
-- cannot establish whether an external importer uses kokonut_runtime; verify
-- that contract before persistent candidate or production rollout.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        RAISE EXCEPTION 'required role kokonut_runtime is missing';
    END IF;

    relation_oid := pg_catalog.to_regclass('public.schema_version');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.schema_version is missing';
    END IF;

    EXECUTE 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
        'ON TABLE public.schema_version FROM kokonut_runtime';

    FOR column_name IN
        SELECT attribute.attname
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid = relation_oid
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
            'ON TABLE public.schema_version FROM kokonut_runtime',
            column_name
        );
    END LOOP;

    EXECUTE 'GRANT SELECT ON TABLE public.schema_version TO kokonut_runtime';
    COMMENT ON TABLE public.schema_version IS
        'Schema-version metadata is written by the ordered maintenance migration runner; kokonut_runtime is read-only. External runtime-login importer use is unconfirmed, and this does not establish tenant isolation.';
END;
$$;

COMMIT;
