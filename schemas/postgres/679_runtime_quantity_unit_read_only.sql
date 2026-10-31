-- Quantity units are a shared reference catalog seeded by the schema. Keep
-- them readable to the Kernel runtime and reserve catalog changes for the
-- separate administration path.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.quantity_unit');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.quantity_unit is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.quantity_unit FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.quantity_unit FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.quantity_unit FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.quantity_unit FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.quantity_unit TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.quantity_unit IS
    'Shared quantity-unit reference catalog. kokonut_runtime has read-only access; catalog maintenance uses the separate administration path.';

COMMIT;
