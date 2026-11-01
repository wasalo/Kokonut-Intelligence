-- Chat intent defaults are seeded by schema migration 140. The only source
-- runtime callsite reads active intents; reserve changes for reviewed schema
-- or maintenance work while preserving runtime SELECT. External SQL clients
-- using kokonut_runtime are unconfirmed and must be checked before rollout.
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

    relation_oid := pg_catalog.to_regclass('public.chat_intent');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.chat_intent is missing';
    END IF;

    EXECUTE 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
        'ON TABLE public.chat_intent FROM kokonut_runtime';

    FOR column_name IN
        SELECT attribute.attname
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid = relation_oid
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
            'ON TABLE public.chat_intent FROM kokonut_runtime',
            column_name
        );
    END LOOP;

    EXECUTE 'GRANT SELECT ON TABLE public.chat_intent TO kokonut_runtime';
    COMMENT ON TABLE public.chat_intent IS
        'Default chat intents are maintained through reviewed schema/maintenance changes. kokonut_runtime is read-only. External runtime-login writes are unconfirmed and must be checked before rollout. This does not establish tenant isolation.';
END;
$$;

COMMIT;
