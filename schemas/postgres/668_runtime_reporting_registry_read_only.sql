-- Reporting-standard and adapter registries are shared metadata. Their
-- contents are introduced through reviewed seed/schema updates, not runtime
-- writes. Keep them readable to the Kernel runtime.
BEGIN;

DO $$
DECLARE
    relation_name TEXT;
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        FOREACH relation_name IN ARRAY ARRAY[
            'gri_indicator',
            'governance_framework'
        ] LOOP
            relation_oid := to_regclass(format('public.%I', relation_name));
            IF relation_oid IS NULL THEN
                RAISE EXCEPTION 'required relation public.% is missing', relation_name;
            END IF;

            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM kokonut_runtime',
                relation_name
            );

            FOR column_name IN
                SELECT attname
                  FROM pg_catalog.pg_attribute
                 WHERE attrelid = relation_oid
                   AND attnum > 0
                   AND NOT attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE INSERT (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name, relation_name
                );
                EXECUTE format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name, relation_name
                );
                EXECUTE format(
                    'REVOKE REFERENCES (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name, relation_name
                );
            END LOOP;

            EXECUTE format(
                'GRANT SELECT ON TABLE public.%I TO kokonut_runtime',
                relation_name
            );
        END LOOP;
    END IF;
END;
$$;

COMMENT ON TABLE public.gri_indicator IS
    'Shared GRI reporting indicator mapping. kokonut_runtime has read-only access; changes require a reviewed reference-data update.';
COMMENT ON TABLE public.governance_framework IS
    'Registry of supported governance adapters and deployments. kokonut_runtime has read-only access; changes require a reviewed schema or seed update.';

COMMIT;
