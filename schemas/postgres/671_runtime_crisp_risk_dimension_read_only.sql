-- Shared CRISP dimension definitions are schema-governed configuration.
-- Per-location scoring adjustments remain writable through crisp_location_weight.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.crisp_risk_dimension');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.crisp_risk_dimension is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.crisp_risk_dimension FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.crisp_risk_dimension FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.crisp_risk_dimension FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.crisp_risk_dimension FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.crisp_risk_dimension TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.crisp_risk_dimension IS
    'Shared CRISP scoring dimension definitions. kokonut_runtime has read-only access; global methodology changes require reviewed migrations. Per-location overrides remain in crisp_location_weight.';

COMMIT;
