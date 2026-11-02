-- EBF pillars and rubric bands are global, curated scoring references.
-- Application code reads them; schemas/seeds/032_ebf_rubric.sql owns writes.
-- Preserve the existing RLS state: these catalogs are not tenant data.
BEGIN;

DO $$
DECLARE
    relation_name text;
    relation_oid regclass;
    relation_kind "char";
    column_name text;
    role_name text;
    sequence_row record;
    target_relations constant text[] := ARRAY['ebf_pillar', 'ebf_rubric_band'];
    application_roles constant text[] := ARRAY['kokonut_runtime', 'kokonut_directus_runtime'];
BEGIN
    FOREACH relation_name IN ARRAY target_relations LOOP
        relation_oid := pg_catalog.to_regclass(pg_catalog.format('public.%I', relation_name));
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.% is missing', relation_name;
        END IF;

        SELECT relation.relkind INTO relation_kind
          FROM pg_catalog.pg_class AS relation
         WHERE relation.oid = relation_oid;
        IF relation_kind NOT IN ('r', 'p') THEN
            RAISE EXCEPTION 'public.% must remain a table', relation_name;
        END IF;

        EXECUTE pg_catalog.format(
            'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM PUBLIC', relation_name
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
                'ON TABLE public.%2$I FROM PUBLIC',
                column_name, relation_name
            );
        END LOOP;

        FOREACH role_name IN ARRAY application_roles LOOP
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
                EXECUTE pg_catalog.format(
                    'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %I',
                    relation_name, role_name
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
                        'ON TABLE public.%2$I FROM %3$I',
                        column_name, relation_name, role_name
                    );
                END LOOP;

                FOR sequence_row IN
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
                     ORDER BY sequence_namespace.nspname, sequence.relname
                LOOP
                    EXECUTE pg_catalog.format(
                        'REVOKE ALL PRIVILEGES ON SEQUENCE %I.%I FROM %I',
                        sequence_row.nspname, sequence_row.relname, role_name
                    );
                END LOOP;

                EXECUTE pg_catalog.format(
                    'GRANT SELECT ON TABLE public.%I TO %I', relation_name, role_name
                );
            END IF;
        END LOOP;

        FOR sequence_row IN
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
             ORDER BY sequence_namespace.nspname, sequence.relname
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON SEQUENCE %I.%I FROM PUBLIC',
                sequence_row.nspname, sequence_row.relname
            );
        END LOOP;
    END LOOP;
END;
$$;

COMMENT ON TABLE public.ebf_pillar IS
    'Global curated EBF pillar reference. Runtime and optional Directus roles retain SELECT only; schemas/seeds/032_ebf_rubric.sql writes through the database maintenance owner. RLS state is unchanged.';
COMMENT ON TABLE public.ebf_rubric_band IS
    'Global curated EBF scoring rubric reference. Runtime and optional Directus roles retain SELECT only; schemas/seeds/032_ebf_rubric.sql writes through the database maintenance owner. RLS state is unchanged.';

INSERT INTO kokonut_security.directus_relation_privilege_policy
    (schema_name, relation_name, access_mode, source_migration)
VALUES
    ('public', 'ebf_pillar', 'read_only', '740_runtime_ebf_reference_catalogs_read_only.sql'),
    ('public', 'ebf_rubric_band', 'read_only', '740_runtime_ebf_reference_catalogs_read_only.sql')
ON CONFLICT (schema_name, relation_name) DO UPDATE
   SET access_mode = EXCLUDED.access_mode,
       source_migration = EXCLUDED.source_migration;

COMMIT;
