-- Quality grades are a global curated reference, maintained by reviewed
-- migrations or the database maintenance owner rather than farm operators.
-- Preserve reads for the Kernel and optional Directus adapter.
BEGIN;

DO $$
DECLARE
    relation_oid regclass := pg_catalog.to_regclass('public.quality_grade');
    column_name text;
    role_name text;
    sequence_row record;
    application_roles constant text[] := ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime'
    ];
BEGIN
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.quality_grade is missing';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class
         WHERE oid = relation_oid AND relkind IN ('r', 'p')
    ) THEN
        RAISE EXCEPTION 'public.quality_grade must remain a table';
    END IF;

    REVOKE ALL PRIVILEGES ON TABLE public.quality_grade FROM PUBLIC;
    FOR column_name IN
        SELECT attribute.attname
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid = relation_oid
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
            'ON TABLE public.quality_grade FROM PUBLIC', column_name
        );
    END LOOP;

    FOR sequence_row IN
        SELECT sequence_namespace.nspname, sequence.relname
          FROM pg_catalog.pg_depend AS dependency
          JOIN pg_catalog.pg_class AS sequence
            ON sequence.oid = dependency.objid AND sequence.relkind = 'S'
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

    FOREACH role_name IN ARRAY application_roles LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.quality_grade FROM %I', role_name
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
                    'ON TABLE public.quality_grade FROM %2$I', column_name, role_name
                );
            END LOOP;

            FOR sequence_row IN
                SELECT sequence_namespace.nspname, sequence.relname
                  FROM pg_catalog.pg_depend AS dependency
                  JOIN pg_catalog.pg_class AS sequence
                    ON sequence.oid = dependency.objid AND sequence.relkind = 'S'
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
                'GRANT SELECT ON TABLE public.quality_grade TO %I', role_name
            );
        END IF;
    END LOOP;
END;
$$;

COMMENT ON TABLE public.quality_grade IS
    'Global curated produce-quality grading reference. Runtime and optional Directus roles are read-only; reviewed migrations or the database maintenance owner maintain catalog rows.';

INSERT INTO kokonut_security.directus_relation_privilege_policy
    (schema_name, relation_name, access_mode, source_migration)
VALUES
    ('public', 'quality_grade', 'read_only', '741_runtime_quality_grade_catalog_read_only.sql')
ON CONFLICT (schema_name, relation_name) DO UPDATE
   SET access_mode = EXCLUDED.access_mode,
       source_migration = EXCLUDED.source_migration;

COMMIT;
