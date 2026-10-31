-- The public farm summary is a grouped projection, never a mutation surface.
-- Preserve runtime reads while removing grants that cannot be used to update
-- this view and must not become usable if its definition changes later.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
    relation_kind "char";
BEGIN
    relation_oid := pg_catalog.to_regclass('public.v_public_farm_summary');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.v_public_farm_summary is missing';
    END IF;

    SELECT class.relkind
      INTO relation_kind
      FROM pg_catalog.pg_class AS class
     WHERE class.oid = relation_oid;
    IF relation_kind <> 'v' THEN
        RAISE EXCEPTION 'public.v_public_farm_summary must remain a view';
    END IF;

    IF pg_catalog.pg_relation_is_updatable(relation_oid, TRUE) <> 0 THEN
        RAISE EXCEPTION 'public.v_public_farm_summary must remain non-updatable';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.v_public_farm_summary '
                'FROM kokonut_runtime';

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.v_public_farm_summary FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        EXECUTE 'GRANT SELECT ON TABLE public.v_public_farm_summary '
                'TO kokonut_runtime';
    END IF;
END;
$$;

COMMENT ON VIEW public.v_public_farm_summary IS
    'Public grouped farm summary; kokonut_runtime may read but not mutate this projection.';

COMMIT;
