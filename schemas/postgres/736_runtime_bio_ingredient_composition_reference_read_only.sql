-- This static bio-ingredient composition reference is populated by the seed
-- path running with the database administrator identity; it has no active
-- application or Directus writer. Preserve runtime reads; importer or
-- administrative changes use that administrator-controlled path. Undocumented external SQL consumers remain outside
-- this repository's source inventory.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
    relation_name TEXT;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'bio_ingredient_composition_reference',
        'bio_regional_input_availability'
    ] LOOP
        relation_oid := pg_catalog.to_regclass(
            pg_catalog.format('public.%I', relation_name)
        );
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.% is missing', relation_name;
        END IF;

        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
        ) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM kokonut_runtime',
                relation_name
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

        EXECUTE pg_catalog.format(
            'COMMENT ON TABLE public.%I IS %L',
            relation_name,
            'Static Bio Factory reference data is read-only to kokonut_runtime. Seed, administrative, or import writes use the administrator-controlled path; undocumented external SQL consumers are not represented by repository source review.'
        );
    END LOOP;
END;
$$;

COMMIT;
