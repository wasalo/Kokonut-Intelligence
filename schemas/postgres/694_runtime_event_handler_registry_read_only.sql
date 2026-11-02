-- Event-handler definitions are migration/admin-managed configuration.
-- Runtime workers and CLI paths read the registry; dispatch state remains
-- owned by the dedicated event-dispatch role and bounded functions.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    relation_oid := pg_catalog.to_regclass('public.event_handler');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.event_handler is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.event_handler FROM kokonut_runtime';

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.event_handler FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        EXECUTE 'GRANT SELECT ON TABLE public.event_handler TO kokonut_runtime';
    END IF;

    COMMENT ON TABLE public.event_handler IS
        'Event-handler registry is configuration managed by ordered migrations and explicit administration; kokonut_runtime may read but not mutate it. Dispatch state uses its separate worker boundary.';
END;
$$;

COMMIT;
