-- Landscape writes now use the signed location-scoped Gateway capture from
-- migration 702. Retire only kokonut_runtime table/column DML; leave SELECT,
-- Directus, migration-702 writer-owner, and maintenance/importer grants intact.
-- Repository source review does not establish whether external importers use
-- the shared runtime login; verify those consumers before candidate rollout.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_name TEXT;
    relation_oid REGCLASS;
    protected_relations CONSTANT TEXT[] := ARRAY[
        'habitat_zone',
        'wildlife_corridor',
        'hedgerow_record',
        'buffer_zone_monitoring',
        'landscape_biodiversity_score'
    ];
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        RAISE EXCEPTION 'required role kokonut_runtime is missing';
    END IF;

    FOREACH relation_name IN ARRAY protected_relations LOOP
        relation_oid := pg_catalog.to_regclass(
            pg_catalog.format('public.%I', relation_name)
        );
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.% is missing', relation_name;
        END IF;

        EXECUTE pg_catalog.format(
            'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
            'ON TABLE %I.%I FROM kokonut_runtime',
            'public', relation_name
        );

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE %2$I.%3$I FROM kokonut_runtime',
                column_name, 'public', relation_name
            );
        END LOOP;
    END LOOP;
END;
$$;

COMMIT;
