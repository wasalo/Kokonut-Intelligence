-- Runtime services have moved sensor-alert creation and cleanup behind
-- location-scoped SECURITY DEFINER functions. Keep SELECT compatibility for
-- current readers, but remove direct DML from shared application identities.
-- This narrows write privilege; it does not establish tenant isolation.
BEGIN;

DO $$
DECLARE
    role_name TEXT;
    column_name TEXT;
    relation_oid REGCLASS := pg_catalog.to_regclass('public.sensor_alert');
BEGIN
    IF relation_oid IS NULL THEN
        RAISE EXCEPTION 'required relation public.sensor_alert is missing';
    END IF;

    REVOKE ALL PRIVILEGES ON TABLE public.sensor_alert FROM PUBLIC;
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_worker_execution'
    ] LOOP
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name
        ) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.sensor_alert FROM %I',
                role_name
            );

            -- Table-level revoke does not clear standalone column grants.
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = relation_oid
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE SELECT (%1$I), INSERT (%1$I), UPDATE (%1$I), '
                    'REFERENCES (%1$I) '
                    'ON TABLE public.sensor_alert FROM %2$I',
                    column_name, role_name
                );
            END LOOP;

            IF role_name = 'kokonut_runtime' THEN
                GRANT SELECT ON TABLE public.sensor_alert TO kokonut_runtime;
            END IF;
        END IF;
    END LOOP;

    FOR column_name IN
        SELECT attribute.attname
          FROM pg_catalog.pg_attribute AS attribute
         WHERE attribute.attrelid = relation_oid
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE SELECT (%1$I), INSERT (%1$I), UPDATE (%1$I), '
            'REFERENCES (%1$I) ON TABLE public.sensor_alert FROM PUBLIC',
            column_name
        );
    END LOOP;
END;
$$;

COMMENT ON TABLE public.sensor_alert IS
    'Shared runtime retains SELECT only; sensor alert writes require the signed location-scoped worker functions. Directus/maintenance grants are unchanged. This DML boundary does not establish tenant isolation.';

COMMIT;
