-- Keep the optional Directus compatibility role aligned with runtime-owned
-- read-only boundaries introduced by migrations 735–737. The policy registry
-- is reapplied after Directus compatibility grants, so later provisioning
-- cannot restore DML on these relations.
BEGIN;

DO $$
DECLARE
    relation_name TEXT;
    column_name TEXT;
    sequence_name RECORD;
    relation_oid REGCLASS;
BEGIN
    IF pg_catalog.to_regclass(
        'kokonut_security.directus_relation_privilege_policy'
    ) IS NULL THEN
        RAISE EXCEPTION 'Directus relation privilege policy registry is missing';
    END IF;

    FOREACH relation_name IN ARRAY ARRAY[
        'location_baseline',
        'bio_ingredient_composition_reference',
        'bio_regional_input_availability',
        'data_freshness_config'
    ] LOOP
        relation_oid := pg_catalog.to_regclass(
            pg_catalog.format('public.%I', relation_name)
        );
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.% is missing', relation_name;
        END IF;

        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE rolname = 'kokonut_directus_runtime'
        ) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I '
                'FROM kokonut_directus_runtime', relation_name
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
                    'ON TABLE public.%2$I FROM kokonut_directus_runtime',
                    column_name,
                    relation_name
                );
            END LOOP;

            FOR sequence_name IN
                SELECT sequence_namespace.nspname, sequence.relname
                  FROM pg_catalog.pg_depend AS dependency
                  JOIN pg_catalog.pg_class AS sequence
                    ON sequence.oid = dependency.objid
                   AND sequence.relkind = 'S'
                  JOIN pg_catalog.pg_namespace AS sequence_namespace
                    ON sequence_namespace.oid = sequence.relnamespace
                 WHERE dependency.refobjid = relation_oid
                   AND dependency.refclassid = 'pg_catalog.pg_class'::pg_catalog.regclass
                   AND dependency.classid = 'pg_catalog.pg_class'::pg_catalog.regclass
                   AND dependency.deptype IN ('a', 'i')
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE ALL PRIVILEGES ON SEQUENCE %I.%I '
                    'FROM kokonut_directus_runtime',
                    sequence_name.nspname,
                    sequence_name.relname
                );
            END LOOP;

            EXECUTE pg_catalog.format(
                'GRANT SELECT ON TABLE public.%I TO kokonut_directus_runtime',
                relation_name
            );
        END IF;
    END LOOP;
END;
$$;

INSERT INTO kokonut_security.directus_relation_privilege_policy
    (schema_name, relation_name, access_mode, source_migration)
VALUES
    ('public', 'location_baseline', 'read_only', '735_runtime_location_baseline_read_only.sql'),
    ('public', 'bio_ingredient_composition_reference', 'read_only', '736_runtime_bio_ingredient_composition_reference_read_only.sql'),
    ('public', 'bio_regional_input_availability', 'read_only', '736_runtime_bio_ingredient_composition_reference_read_only.sql'),
    ('public', 'data_freshness_config', 'read_only', '737_runtime_data_freshness_config_read_only.sql')
ON CONFLICT (schema_name, relation_name) DO UPDATE
   SET access_mode = EXCLUDED.access_mode,
       source_migration = EXCLUDED.source_migration;

COMMIT;
