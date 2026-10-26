-- Create a source-validated alert and its append-only ingestion audit entry.
-- This is a bounded worker operation; it does not create claims or publish events.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_anomaly_alert_owner'
    ) THEN
        CREATE ROLE kokonut_anomaly_alert_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_anomaly_alert_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_alert_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_anomaly_alert_owner'
            OR member_role.rolname = 'kokonut_anomaly_alert_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_alert_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_anomaly_alert_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_anomaly_alert_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_anomaly_alert_owner;

GRANT SELECT (id, event_type, source_table, source_id, payload)
    ON public.platform_event TO kokonut_anomaly_alert_owner;
GRANT SELECT (id, sensor_id, sensor_type, value, location_id)
    ON public.sensor_reading TO kokonut_anomaly_alert_owner;
GRANT SELECT (id, location_id, sensor_type_id)
    ON public.sensor_device TO kokonut_anomaly_alert_owner;
GRANT SELECT (id, name)
    ON public.sensor_type TO kokonut_anomaly_alert_owner;
GRANT SELECT (id, sensor_type_id, threshold_value, severity, enabled)
    ON public.alert_rule TO kokonut_anomaly_alert_owner;
GRANT SELECT (location_id, source_reading_id, alert_rule_id, source_event_id,
              outcome, sensor_alert_id)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_alert_owner;
GRANT UPDATE (outcome, sensor_alert_id, updated_at)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_alert_owner;
GRANT INSERT (location_id, sensor_device_id, alert_rule_id, reading_id, severity,
              status, message, reading_value, threshold_value)
    ON public.sensor_alert TO kokonut_anomaly_alert_owner;
GRANT SELECT (id, triggered_at)
    ON public.sensor_alert TO kokonut_anomaly_alert_owner;
GRANT INSERT (source_system, source_table, source_id, target_table, target_id,
              operation, payload_hash, status, rows_affected, location_id)
    ON public.ingestion_log TO kokonut_anomaly_alert_owner;

-- This function owner has no login or role memberships. Where source tables
-- already use RLS, its only access is through the bounded SECURITY DEFINER
-- function below, whose query verifies the signed worker scope.
DO $$
DECLARE
    target_table TEXT;
    policy_name TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'platform_event', 'sensor_reading', 'sensor_device', 'sensor_type',
        'alert_rule', 'sensor_anomaly_effect'
    ] LOOP
        policy_name := 'anomaly_alert_owner_' || target_table || '_select';
        IF EXISTS (
            SELECT 1 FROM pg_class AS relation
            JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname = 'public'
              AND relation.relname = target_table
              AND relation.relrowsecurity
        ) AND NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = target_table
              AND policyname = policy_name
        ) THEN
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR SELECT '
                'TO kokonut_anomaly_alert_owner USING (true)',
                policy_name, target_table
            );
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_anomaly_effect'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'sensor_anomaly_effect'
          AND policyname = 'anomaly_alert_owner_effect_update'
    ) THEN
        CREATE POLICY anomaly_alert_owner_effect_update
            ON public.sensor_anomaly_effect
            FOR UPDATE TO kokonut_anomaly_alert_owner
            USING (location_id = (
                SELECT scope.location_id
                  FROM kokonut_security.current_worker_scope(
                      'sensor_reading', 'process'
                  ) AS scope
            ))
            WITH CHECK (location_id = (
                SELECT scope.location_id
                  FROM kokonut_security.current_worker_scope(
                      'sensor_reading', 'process'
                  ) AS scope
            ));
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
          AND policyname = 'anomaly_alert_owner_select'
    ) THEN
        CREATE POLICY anomaly_alert_owner_select ON public.sensor_alert
            FOR SELECT TO kokonut_anomaly_alert_owner
            USING (location_id = (
                SELECT scope.location_id
                  FROM kokonut_security.current_worker_scope(
                      'sensor_reading', 'process'
                  ) AS scope
            ));
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
          AND policyname = 'anomaly_alert_owner_insert'
    ) THEN
        CREATE POLICY anomaly_alert_owner_insert ON public.sensor_alert
            FOR INSERT TO kokonut_anomaly_alert_owner
            WITH CHECK (location_id = (
                SELECT scope.location_id
                  FROM kokonut_security.current_worker_scope(
                      'sensor_reading', 'process'
                  ) AS scope
            ));
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'ingestion_log'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'ingestion_log'
          AND policyname = 'anomaly_alert_owner_insert'
    ) THEN
        CREATE POLICY anomaly_alert_owner_insert ON public.ingestion_log
            FOR INSERT TO kokonut_anomaly_alert_owner
            WITH CHECK (location_id = (
                SELECT scope.location_id
                  FROM kokonut_security.current_worker_scope(
                      'sensor_reading', 'process'
                  ) AS scope
            ));
    END IF;
END;
$$;

REVOKE ALL ON public.sensor_alert, public.ingestion_log
    FROM kokonut_worker_execution;

CREATE OR REPLACE FUNCTION kokonut_security.create_sensor_anomaly_alert(
    requested_source_event_id UUID,
    requested_source_reading_id UUID,
    requested_alert_rule_id UUID,
    requested_location_id UUID,
    requested_message TEXT,
    requested_payload_hash TEXT
)
RETURNS TABLE (
    sensor_alert_id UUID,
    triggered_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    source_row RECORD;
    alert_row RECORD;
    receipt_exists BOOLEAN;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'sensor alert creation requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'sensor alert creation is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_source_event_id IS NULL
       OR requested_source_reading_id IS NULL
       OR requested_alert_rule_id IS NULL
       OR requested_message IS NULL
       OR BTRIM(requested_message) = ''
       OR LENGTH(requested_message) > 2000
       OR requested_payload_hash IS NULL
       OR requested_payload_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'sensor alert source, message, or audit hash is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT reading.id AS reading_id,
           reading.sensor_id AS sensor_device_id,
           reading.value AS reading_value,
           reading.location_id,
           rule.id AS alert_rule_id,
           rule.threshold_value,
           rule.severity
      INTO source_row
      FROM public.platform_event AS source_event
      JOIN public.sensor_reading AS reading
        ON reading.id = source_event.source_id
       AND reading.location_id = worker_scope.location_id
      JOIN public.sensor_device AS device
        ON device.id = reading.sensor_id
       AND device.location_id = reading.location_id
      JOIN public.sensor_type AS sensor_type
        ON sensor_type.id = device.sensor_type_id
       AND reading.sensor_type::TEXT = sensor_type.name
      JOIN public.alert_rule AS rule
        ON rule.id = requested_alert_rule_id
       AND rule.sensor_type_id = device.sensor_type_id
       AND rule.enabled = TRUE
     WHERE source_event.id = requested_source_event_id
       AND source_event.event_type = 'sensor_reading'
       AND source_event.source_table = 'sensor_reading'
       AND source_event.source_id = requested_source_reading_id
       AND source_event.payload ->> 'location_id' = worker_scope.location_id::TEXT
       AND reading.id = requested_source_reading_id
       AND (
           source_event.payload ->> 'sensor_id' = reading.sensor_id::TEXT
           OR source_event.payload ->> 'sensor_device_id' = reading.sensor_id::TEXT
       )
       AND (
           source_event.payload ->> 'sensor_id' IS NULL
           OR source_event.payload ->> 'sensor_id' = reading.sensor_id::TEXT
       )
       AND (
           source_event.payload ->> 'sensor_device_id' IS NULL
           OR source_event.payload ->> 'sensor_device_id' = reading.sensor_id::TEXT
       );
    IF NOT FOUND THEN
        RAISE EXCEPTION 'sensor alert source, rule, device, or location does not match signed scope'
            USING ERRCODE = '42501';
    END IF;

    SELECT TRUE
      INTO receipt_exists
      FROM public.sensor_anomaly_effect AS effect
     WHERE effect.location_id = worker_scope.location_id
       AND effect.source_event_id = requested_source_event_id
       AND effect.source_reading_id = requested_source_reading_id
       AND effect.alert_rule_id = requested_alert_rule_id
       AND effect.outcome = 'no_match'
       AND effect.sensor_alert_id IS NULL
     FOR UPDATE;
    IF NOT COALESCE(receipt_exists, FALSE) THEN
        RAISE EXCEPTION 'sensor alert requires a reserved anomaly receipt'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO public.sensor_alert AS inserted_alert (
        location_id, sensor_device_id, alert_rule_id, reading_id, severity,
        status, message, reading_value, threshold_value
    ) VALUES (
        worker_scope.location_id, source_row.sensor_device_id,
        source_row.alert_rule_id, source_row.reading_id, source_row.severity,
        'open', requested_message, source_row.reading_value,
        source_row.threshold_value
    )
    RETURNING inserted_alert.id, inserted_alert.triggered_at
         INTO alert_row;

    INSERT INTO public.ingestion_log (
        source_system, source_table, source_id, target_table, target_id,
        operation, payload_hash, status, rows_affected, location_id
    ) VALUES (
        'anomaly_detector', 'sensor_reading', source_row.reading_id::TEXT,
        'sensor_alert', alert_row.id, 'insert', requested_payload_hash,
        'success', 1, worker_scope.location_id
    );

    UPDATE public.sensor_anomaly_effect AS effect
       SET outcome = 'alert_created',
           sensor_alert_id = alert_row.id,
           updated_at = statement_timestamp()
     WHERE effect.location_id = worker_scope.location_id
       AND effect.source_event_id = requested_source_event_id
       AND effect.source_reading_id = requested_source_reading_id
       AND effect.alert_rule_id = requested_alert_rule_id
       AND effect.outcome = 'no_match'
       AND effect.sensor_alert_id IS NULL
    RETURNING TRUE INTO receipt_exists;
    IF NOT COALESCE(receipt_exists, FALSE) THEN
        RAISE EXCEPTION 'anomaly receipt changed before alert creation completed'
            USING ERRCODE = '23505';
    END IF;

    sensor_alert_id := alert_row.id;
    triggered_at := alert_row.triggered_at;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.create_sensor_anomaly_alert(
    UUID, UUID, UUID, UUID, TEXT, TEXT
) OWNER TO kokonut_anomaly_alert_owner;
REVOKE ALL ON FUNCTION kokonut_security.create_sensor_anomaly_alert(
    UUID, UUID, UUID, UUID, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.create_sensor_anomaly_alert(
    UUID, UUID, UUID, UUID, TEXT, TEXT
) TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_sensor_anomaly_alert(
            UUID, UUID, UUID, UUID, TEXT, TEXT
        ) FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_sensor_anomaly_alert(
            UUID, UUID, UUID, UUID, TEXT, TEXT
        ) FROM kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_anomaly_alert_owner;

COMMENT ON FUNCTION kokonut_security.create_sensor_anomaly_alert(
    UUID, UUID, UUID, UUID, TEXT, TEXT
) IS
    'Creates one location-bound alert and its append-only ingestion audit entry, atomically advancing the receipt, only for a signed, event-linked reading, enabled rule, and reserved anomaly receipt.';

COMMIT;
