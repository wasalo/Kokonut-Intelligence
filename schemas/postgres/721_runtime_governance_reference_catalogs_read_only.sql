-- Governance category and scope catalogs are migration-seeded references.
-- Keep the global read path, while removing direct writes from kokonut_runtime.
-- Directus and maintenance privileges are intentionally unchanged.
BEGIN;

DO $$
DECLARE
    relation_name TEXT;
    column_name TEXT;
    relation_oid REGCLASS;
    relation_kind "char";
    target_relations CONSTANT TEXT[] := ARRAY[
        'data_governance_category',
        'data_governance_scope'
    ];
BEGIN
    FOREACH relation_name IN ARRAY target_relations LOOP
        relation_oid := pg_catalog.to_regclass(
            pg_catalog.format('public.%I', relation_name)
        );
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.% is missing', relation_name;
        END IF;

        SELECT relation.relkind
          INTO relation_kind
          FROM pg_catalog.pg_class AS relation
         WHERE relation.oid = relation_oid;
        IF relation_kind NOT IN ('r', 'p') THEN
            RAISE EXCEPTION 'public.% must remain a table', relation_name;
        END IF;

        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
        ) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM kokonut_runtime',
                relation_name
            );

            -- Table-level REVOKE does not clear independently granted column
            -- privileges, so remove those explicitly as well.
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = relation_oid
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                    'ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name,
                    relation_name
                );
            END LOOP;

            EXECUTE pg_catalog.format(
                'GRANT SELECT ON TABLE public.%I TO kokonut_runtime',
                relation_name
            );
        END IF;
    END LOOP;
END;
$$;

COMMENT ON TABLE public.data_governance_category IS
    'Migration-seeded global category reference. kokonut_runtime retains SELECT only; maintenance and Directus privileges are unchanged. Retention windows are configured in data_retention_policy, not this catalog.';

COMMENT ON TABLE public.data_governance_scope IS
    'Migration-seeded global consent-scope reference. kokonut_runtime retains SELECT only; maintenance and Directus privileges are unchanged.';

COMMIT;
