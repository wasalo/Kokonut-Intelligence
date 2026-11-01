-- The framework catalogs are maintained by curated seeds and read by the
-- application. Keep the read paths while removing unused shared-runtime DML.
-- Directus and the database owner/maintenance identity are intentionally unchanged.
BEGIN;

DO $$
DECLARE
    relation_name TEXT;
    column_name TEXT;
    relation_oid REGCLASS;
    relation_kind "char";
    target_relations CONSTANT TEXT[] := ARRAY[
        'form_of_capital',
        'sdg',
        'pillar_of_value',
        'regeneration_principle'
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

            -- Table-level revocation does not clear standalone column grants.
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

COMMENT ON TABLE public.form_of_capital IS
    'Curated global framework reference. kokonut_runtime retains SELECT only; curated seed writes run through the database owner/maintenance identity. Directus grants are unchanged.';
COMMENT ON TABLE public.sdg IS
    'Curated global Sustainable Development Goal reference. kokonut_runtime retains SELECT only; curated seed writes run through the database owner/maintenance identity. Directus grants are unchanged.';
COMMENT ON TABLE public.pillar_of_value IS
    'Curated global value-framework reference. kokonut_runtime retains SELECT only; curated seed writes run through the database owner/maintenance identity. Directus grants are unchanged.';
COMMENT ON TABLE public.regeneration_principle IS
    'Curated global regeneration-principle reference. kokonut_runtime retains SELECT only; curated seed writes run through the database owner/maintenance identity. Directus grants are unchanged.';

COMMIT;
