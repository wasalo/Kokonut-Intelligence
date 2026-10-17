-- Publish a canonical sensor-alert event through the dormant worker role.
-- This creates queue intent only; it does not claim, deliver, or acknowledge it.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_anomaly_event_owner'
    ) THEN
        CREATE ROLE kokonut_anomaly_event_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_anomaly_event_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_event_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_anomaly_event_owner'
            OR member_role.rolname = 'kokonut_anomaly_event_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_event_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_anomaly_event_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_anomaly_event_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_anomaly_event_owner;

GRANT SELECT (id, event_type, source_table, source_id, payload, priority)
    ON public.platform_event TO kokonut_anomaly_event_owner;
GRANT SELECT (location_id, source_reading_id, alert_rule_id, source_event_id,
              outcome, sensor_alert_id)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_event_owner;
GRANT SELECT (id, location_id, reading_id, sensor_device_id, alert_rule_id,
              severity, message, reading_value, threshold_value, triggered_at,
              claim_id)
    ON public.sensor_alert TO kokonut_anomaly_event_owner;
GRANT SELECT (id, sensor_id, location_id)
    ON public.sensor_reading TO kokonut_anomaly_event_owner;
GRANT SELECT (id, name, location_id, sensor_type_id)
    ON public.sensor_device TO kokonut_anomaly_event_owner;
GRANT SELECT (id, name, severity, sensor_type_id)
    ON public.alert_rule TO kokonut_anomaly_event_owner;
GRANT SELECT (id, name)
    ON public.sensor_type TO kokonut_anomaly_event_owner;
GRANT INSERT (id, event_type, source_table, source_id, payload, priority,
              status, max_retries)
    ON public.platform_event TO kokonut_anomaly_event_owner;

REVOKE ALL ON public.platform_event FROM kokonut_worker_execution;

CREATE OR REPLACE FUNCTION kokonut_security.publish_sensor_alert_event(
    requested_alert_event_id UUID,
    requested_source_event_id UUID,
    requested_source_reading_id UUID,
    requested_alert_rule_id UUID,
    requested_sensor_alert_id UUID,
    requested_location_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    event_payload JSONB;
    event_priority TEXT;
    was_inserted BOOLEAN;
    existing_event RECORD;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'alert event publication requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'alert event publication is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_alert_event_id IS NULL THEN
        RAISE EXCEPTION 'alert event ID is required'
            USING ERRCODE = '22023';
    END IF;

    SELECT jsonb_build_object(
               'alert_id', alert.id,
               'sensor_device_id', device.id,
               'sensor_id', reading.sensor_id,
               'severity', alert.severity,
               'rule_name', rule.name,
               'reading_value', alert.reading_value,
               'threshold_value', alert.threshold_value,
               'message', alert.message,
               'location_id', alert.location_id
           ),
           CASE WHEN alert.severity = 'critical' THEN 'high' ELSE 'normal' END
      INTO event_payload, event_priority
      FROM public.sensor_anomaly_effect AS effect
      JOIN public.sensor_alert AS alert
        ON alert.id = effect.sensor_alert_id
      JOIN public.platform_event AS source_event
        ON source_event.id = effect.source_event_id
       AND source_event.event_type = 'sensor_reading'
       AND source_event.source_table = 'sensor_reading'
       AND source_event.source_id = effect.source_reading_id
       AND source_event.payload ->> 'location_id' = worker_scope.location_id::TEXT
       AND (
           source_event.payload ->> 'sensor_id' IS NOT NULL
           OR source_event.payload ->> 'sensor_device_id' IS NOT NULL
       )
      JOIN public.sensor_reading AS reading
        ON reading.id = source_event.source_id
       AND reading.id = effect.source_reading_id
       AND reading.location_id = worker_scope.location_id
       AND (
           source_event.payload ->> 'sensor_id' IS NULL
           OR source_event.payload ->> 'sensor_id' = reading.sensor_id::TEXT
       )
       AND (
           source_event.payload ->> 'sensor_device_id' IS NULL
           OR source_event.payload ->> 'sensor_device_id' = reading.sensor_id::TEXT
       )
       AND (
           source_event.payload ->> 'sensor_id' = reading.sensor_id::TEXT
           OR source_event.payload ->> 'sensor_device_id' = reading.sensor_id::TEXT
       )
      JOIN public.sensor_device AS device
        ON device.id::TEXT = reading.sensor_id::TEXT
       AND device.id = alert.sensor_device_id
       AND device.location_id = reading.location_id
      JOIN public.alert_rule AS rule
        ON rule.id = effect.alert_rule_id
       AND rule.id = alert.alert_rule_id
       AND rule.sensor_type_id = device.sensor_type_id
      JOIN public.sensor_type AS sensor_type
        ON sensor_type.id = device.sensor_type_id
     WHERE effect.source_event_id = requested_source_event_id
       AND effect.source_reading_id = requested_source_reading_id
       AND effect.alert_rule_id = requested_alert_rule_id
       AND effect.location_id = worker_scope.location_id
       AND effect.outcome = 'alert_created'
       AND effect.sensor_alert_id = requested_sensor_alert_id
       AND alert.id = requested_sensor_alert_id
       AND alert.location_id = worker_scope.location_id
       AND alert.reading_id = reading.id
       AND alert.severity = rule.severity;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'alert event source or effect receipt does not match signed scope'
            USING ERRCODE = '42501';
    END IF;

    was_inserted := FALSE;
    INSERT INTO public.platform_event (
        id, event_type, source_table, source_id, payload, priority, status, max_retries
    ) VALUES (
        requested_alert_event_id, 'sensor_alert', 'sensor_alert',
        requested_sensor_alert_id, event_payload, event_priority, 'pending', 3
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING TRUE INTO was_inserted;

    IF COALESCE(was_inserted, FALSE) THEN
        RETURN TRUE;
    END IF;

    SELECT event_type, source_table, source_id, payload, priority
      INTO existing_event
      FROM public.platform_event
     WHERE id = requested_alert_event_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'alert event ID conflicts with existing event content'
            USING ERRCODE = '23505';
    END IF;
    IF existing_event.event_type IS DISTINCT FROM 'sensor_alert'
       OR existing_event.source_table IS DISTINCT FROM 'sensor_alert'
       OR existing_event.source_id IS DISTINCT FROM requested_sensor_alert_id
       OR existing_event.payload IS DISTINCT FROM event_payload
       OR existing_event.priority IS DISTINCT FROM event_priority THEN
        RAISE EXCEPTION 'alert event ID conflicts with existing event content'
            USING ERRCODE = '23505';
    END IF;
    RETURN FALSE;
END;
$$;

ALTER FUNCTION kokonut_security.publish_sensor_alert_event(UUID, UUID, UUID, UUID, UUID, UUID)
    OWNER TO kokonut_anomaly_event_owner;
REVOKE ALL ON FUNCTION kokonut_security.publish_sensor_alert_event(UUID, UUID, UUID, UUID, UUID, UUID)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.publish_sensor_alert_event(UUID, UUID, UUID, UUID, UUID, UUID)
    TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.publish_sensor_alert_event(UUID, UUID, UUID, UUID, UUID, UUID)
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.publish_sensor_alert_event(UUID, UUID, UUID, UUID, UUID, UUID)
            FROM kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_anomaly_event_owner;

COMMENT ON FUNCTION kokonut_security.publish_sensor_alert_event(UUID, UUID, UUID, UUID, UUID, UUID) IS
    'Publishes one canonical sensor_alert event for a matching alert_created receipt and signed worker location; it cannot claim, deliver, or acknowledge queue state.';

COMMIT;
