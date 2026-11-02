-- Service registry rows describe the platform itself and are deployment-owned
-- reference data. Runtime code may read them, but catalog changes belong in a
-- reviewed migration or seed update.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.service_registry');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.service_registry is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.service_registry FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.service_registry FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.service_registry FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.service_registry FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.service_registry TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.service_registry IS
    'Platform service catalog is read-only to kokonut_runtime; reviewed migrations or seeds own catalog changes. This DML boundary does not establish tenant isolation.';

COMMIT;
