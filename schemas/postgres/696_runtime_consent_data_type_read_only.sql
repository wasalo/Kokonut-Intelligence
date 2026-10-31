-- Consent data categories are catalog configuration, not consent records or
-- retention decisions. Schema migrations seed the catalog with the maintenance
-- identity; dynamic retention windows remain in data_retention_policy.
-- Preserve Directus and maintenance access; restrict only kokonut_runtime.
BEGIN;

DO $$
DECLARE
    column_name TEXT;
    relation_oid REGCLASS;
BEGIN
    relation_oid := pg_catalog.to_regclass('public.consent_data_type');
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.consent_data_type is missing';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.consent_data_type FROM kokonut_runtime';

        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = relation_oid
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                'ON TABLE public.consent_data_type FROM kokonut_runtime',
                column_name
            );
        END LOOP;

        EXECUTE 'GRANT SELECT ON TABLE public.consent_data_type TO kokonut_runtime';
    END IF;

    COMMENT ON TABLE public.consent_data_type IS
        'Consent data categories are read-only to kokonut_runtime. Schema/maintenance and separately authorized Directus administration remain available. Dynamic retention windows are configured in data_retention_policy; this DML boundary does not establish tenant isolation for SELECT.';
END;
$$;

COMMIT;
