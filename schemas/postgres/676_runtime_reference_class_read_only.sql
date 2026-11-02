-- Governed reference classes are consumed by forecasting and prediction
-- analysis. The Kernel runtime may select them but has no application writer;
-- curated administration remains responsible for creating and reviewing them.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.reference_class');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.reference_class is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.reference_class FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.reference_class FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.reference_class FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.reference_class FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.reference_class TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.reference_class IS
    'Governed prediction reference classes. kokonut_runtime has read-only access; curated administration creates and reviews records.';

COMMIT;
