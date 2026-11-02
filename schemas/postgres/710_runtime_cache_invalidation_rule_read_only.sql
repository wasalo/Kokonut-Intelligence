-- Default cache invalidation rules are schema-owned configuration. Repository
-- source review found no application, seed, or Directus writer; custom/external
-- use through kokonut_runtime remains unconfirmed and is a rollout gate.
-- Preserve runtime reads while reserving changes for reviewed maintenance.
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

    relation_oid := pg_catalog.to_regclass('public.cache_invalidation_rule');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.cache_invalidation_rule is missing';
    END IF;

    EXECUTE 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
        'ON TABLE public.cache_invalidation_rule FROM kokonut_runtime';

    FOR column_name IN
        SELECT attribute.attname
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid = relation_oid
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
            'ON TABLE public.cache_invalidation_rule FROM kokonut_runtime',
            column_name
        );
    END LOOP;

    EXECUTE 'GRANT SELECT ON TABLE public.cache_invalidation_rule TO kokonut_runtime';
    COMMENT ON TABLE public.cache_invalidation_rule IS
        'Default cache invalidation rules are maintained through reviewed schema/maintenance changes. kokonut_runtime is read-only. Custom external runtime-login writes are unconfirmed; this does not establish tenant isolation.';
END;
$$;

COMMIT;
