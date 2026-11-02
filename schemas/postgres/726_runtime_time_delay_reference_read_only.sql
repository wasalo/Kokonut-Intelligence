-- Delay mappings are curated reference data and are read by systems-thinking
-- services. Runtime application code must not mutate them directly. Curated
-- seeds continue to run under the database owner; Directus grants are unchanged.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS := pg_catalog.to_regclass('public.time_delay');
    relation_kind "char";
BEGIN
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.time_delay is missing';
    END IF;

    SELECT relation.relkind
      INTO relation_kind
      FROM pg_catalog.pg_class AS relation
     WHERE relation.oid = relation_oid;
    IF relation_kind NOT IN ('r', 'p') THEN
        RAISE EXCEPTION 'public.time_delay must remain a table';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        REVOKE ALL PRIVILEGES ON TABLE public.time_delay FROM kokonut_runtime;

        -- Table revocation does not clear standalone column-level grants.
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.time_delay FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.time_delay TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.time_delay IS
    'Curated systems-thinking delay reference. kokonut_runtime retains SELECT only; schemas/seeds/083_time_delays.sql runs through the database owner/maintenance identity. Directus grants are unchanged.';

COMMIT;
