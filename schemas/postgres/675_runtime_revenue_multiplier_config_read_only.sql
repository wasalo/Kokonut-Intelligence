-- Revenue multiplier parameters are configuration consumed by analytics.
-- Curated seed/admin workflows own changes; general runtime remains read-only.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        relation_oid := to_regclass('public.revenue_multiplier_config');
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.revenue_multiplier_config is missing';
        END IF;

        REVOKE ALL PRIVILEGES ON TABLE public.revenue_multiplier_config FROM kokonut_runtime;

        FOR column_name IN
            SELECT attname
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I) ON TABLE public.revenue_multiplier_config FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE UPDATE (%1$I) ON TABLE public.revenue_multiplier_config FROM kokonut_runtime',
                column_name
            );
            EXECUTE format(
                'REVOKE REFERENCES (%1$I) ON TABLE public.revenue_multiplier_config FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        GRANT SELECT ON TABLE public.revenue_multiplier_config TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.revenue_multiplier_config IS
    'Shared revenue-multiplier parameters. kokonut_runtime has read-only access; changes use curated seed or administrative provisioning.';

COMMIT;
