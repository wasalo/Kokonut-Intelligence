-- Delete only mock alerts and readings for the exact location authenticated
-- by the sensor_anomaly worker. Both operations are safe to retry.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_sensor_mock_cleanup_owner'
    ) THEN
        CREATE ROLE kokonut_sensor_mock_cleanup_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_sensor_mock_cleanup_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_sensor_mock_cleanup_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_sensor_mock_cleanup_owner'
            OR member_role.rolname = 'kokonut_sensor_mock_cleanup_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_sensor_mock_cleanup_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_sensor_mock_cleanup_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_sensor_mock_cleanup_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_sensor_mock_cleanup_owner;
GRANT SELECT (id, location_id, metadata)
    ON public.sensor_device TO kokonut_sensor_mock_cleanup_owner;
GRANT SELECT (location_id, sensor_device_id)
    ON public.sensor_alert TO kokonut_sensor_mock_cleanup_owner;
GRANT DELETE ON public.sensor_alert TO kokonut_sensor_mock_cleanup_owner;
GRANT SELECT (id, sensor_id, location_id, metadata)
    ON public.sensor_reading TO kokonut_sensor_mock_cleanup_owner;
GRANT DELETE ON public.sensor_reading TO kokonut_sensor_mock_cleanup_owner;

-- Respect existing RLS installations without enabling RLS as a side effect.
-- These policies independently constrain row visibility and deletion when
-- either table is already protected by row-level security.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_device'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'sensor_device'
          AND policyname = 'sensor_mock_cleanup_device_select'
    ) THEN
        CREATE POLICY sensor_mock_cleanup_device_select
            ON public.sensor_device FOR SELECT
            TO kokonut_sensor_mock_cleanup_owner
            USING (
                location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                )
                AND metadata ->> 'mock_sensor_demo' = 'true'
            );
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_alert'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'sensor_alert'
          AND policyname = 'sensor_mock_cleanup_alert_select'
    ) THEN
        CREATE POLICY sensor_mock_cleanup_alert_select
            ON public.sensor_alert FOR SELECT
            TO kokonut_sensor_mock_cleanup_owner
            USING (
                location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                )
                AND EXISTS (
                    SELECT 1
                      FROM public.sensor_device AS device
                     WHERE device.id = sensor_alert.sensor_device_id
                       AND device.location_id = sensor_alert.location_id
                       AND device.metadata ->> 'mock_sensor_demo' = 'true'
                )
            );
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_alert'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'sensor_alert'
          AND policyname = 'sensor_mock_cleanup_alert_delete'
    ) THEN
        CREATE POLICY sensor_mock_cleanup_alert_delete
            ON public.sensor_alert FOR DELETE
            TO kokonut_sensor_mock_cleanup_owner
            USING (
                location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                )
                AND EXISTS (
                    SELECT 1
                      FROM public.sensor_device AS device
                     WHERE device.id = sensor_alert.sensor_device_id
                       AND device.location_id = sensor_alert.location_id
                       AND device.metadata ->> 'mock_sensor_demo' = 'true'
                )
            );
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_reading'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'sensor_reading'
          AND policyname = 'sensor_mock_cleanup_reading_select'
    ) THEN
        CREATE POLICY sensor_mock_cleanup_reading_select
            ON public.sensor_reading FOR SELECT
            TO kokonut_sensor_mock_cleanup_owner
            USING (
                location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                )
                AND metadata ->> 'mock' = 'true'
                AND EXISTS (
                    SELECT 1
                      FROM public.sensor_device AS device
                     WHERE device.id = sensor_reading.sensor_id
                       AND device.location_id = sensor_reading.location_id
                       AND device.metadata ->> 'mock_sensor_demo' = 'true'
                )
            );
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_reading'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'sensor_reading'
          AND policyname = 'sensor_mock_cleanup_reading_delete'
    ) THEN
        CREATE POLICY sensor_mock_cleanup_reading_delete
            ON public.sensor_reading FOR DELETE
            TO kokonut_sensor_mock_cleanup_owner
            USING (
                location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                )
                AND metadata ->> 'mock' = 'true'
                AND EXISTS (
                    SELECT 1
                      FROM public.sensor_device AS device
                     WHERE device.id = sensor_reading.sensor_id
                       AND device.location_id = sensor_reading.location_id
                       AND device.metadata ->> 'mock_sensor_demo' = 'true'
                )
            );
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.delete_mock_sensor_alerts(
    requested_location_id UUID
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    signed_location_id UUID;
    deleted_count INTEGER;
BEGIN
    SELECT scope.location_id
      INTO signed_location_id
      FROM kokonut_security.current_worker_scope(
          'sensor_reading', 'process'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'mock sensor alert cleanup requires signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM signed_location_id THEN
        RAISE EXCEPTION 'mock sensor alert cleanup is outside signed location scope'
            USING ERRCODE = '42501';
    END IF;

    DELETE FROM public.sensor_alert AS alert
    USING public.sensor_device AS device
    WHERE alert.sensor_device_id = device.id
      AND alert.location_id = signed_location_id
      AND device.location_id = signed_location_id
      AND device.metadata ->> 'mock_sensor_demo' = 'true';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

ALTER FUNCTION kokonut_security.delete_mock_sensor_alerts(UUID)
    OWNER TO kokonut_sensor_mock_cleanup_owner;
REVOKE ALL ON FUNCTION kokonut_security.delete_mock_sensor_alerts(UUID)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.delete_mock_sensor_alerts(UUID)
    TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.delete_mock_sensor_alerts(UUID)
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.delete_mock_sensor_alerts(UUID)
            FROM kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_sensor_mock_cleanup_owner;

COMMENT ON FUNCTION kokonut_security.delete_mock_sensor_alerts(UUID) IS
    'Idempotently deletes sensor alerts only for currently mock-marked devices at the exact signed sensor_reading/process location.';

CREATE OR REPLACE FUNCTION kokonut_security.delete_mock_sensor_readings(
    requested_location_id UUID
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    signed_location_id UUID;
    deleted_count INTEGER;
BEGIN
    SELECT scope.location_id
      INTO signed_location_id
      FROM kokonut_security.current_worker_scope(
          'sensor_reading', 'process'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'mock sensor reading cleanup requires signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM signed_location_id THEN
        RAISE EXCEPTION 'mock sensor reading cleanup is outside signed location scope'
            USING ERRCODE = '42501';
    END IF;

    DELETE FROM public.sensor_reading AS reading
    USING public.sensor_device AS device
    WHERE reading.location_id = signed_location_id
      AND device.location_id = signed_location_id
      AND device.id = reading.sensor_id
      AND reading.metadata ->> 'mock' = 'true'
      AND device.metadata ->> 'mock_sensor_demo' = 'true';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

ALTER FUNCTION kokonut_security.delete_mock_sensor_readings(UUID)
    OWNER TO kokonut_sensor_mock_cleanup_owner;
REVOKE ALL ON FUNCTION kokonut_security.delete_mock_sensor_readings(UUID)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.delete_mock_sensor_readings(UUID)
    TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.delete_mock_sensor_readings(UUID)
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.delete_mock_sensor_readings(UUID)
            FROM kokonut_operator_auth;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.delete_mock_sensor_readings(UUID) IS
    'Idempotently deletes only mock-marked sensor readings at the exact signed location when their device is still marked as a demo sensor.';

COMMIT;
