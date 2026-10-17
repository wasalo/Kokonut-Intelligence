-- Enqueue an anomaly notification without exposing the shared outbox to workers.
-- This records intent only; a separate delivery worker owns claims and attempts.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_anomaly_notification_owner'
    ) THEN
        CREATE ROLE kokonut_anomaly_notification_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_anomaly_notification_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_notification_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_anomaly_notification_owner'
            OR member_role.rolname = 'kokonut_anomaly_notification_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_notification_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_anomaly_notification_owner;
GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_anomaly_notification_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_anomaly_notification_owner;

GRANT SELECT (id, event_type, source_table, source_id, payload)
    ON public.platform_event TO kokonut_anomaly_notification_owner;
GRANT SELECT (location_id, source_reading_id, alert_rule_id, source_event_id,
              outcome, sensor_alert_id)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_notification_owner;
GRANT SELECT (id, location_id, reading_id, sensor_device_id, alert_rule_id,
              severity, message, reading_value, threshold_value, triggered_at,
              claim_id)
    ON public.sensor_alert TO kokonut_anomaly_notification_owner;
GRANT SELECT (id, sensor_id, location_id)
    ON public.sensor_reading TO kokonut_anomaly_notification_owner;
GRANT SELECT (id, name, location_id, sensor_type_id)
    ON public.sensor_device TO kokonut_anomaly_notification_owner;
GRANT SELECT (id, name)
    ON public.sensor_type TO kokonut_anomaly_notification_owner;
GRANT SELECT (id, sensor_type_id)
    ON public.alert_rule TO kokonut_anomaly_notification_owner;
GRANT SELECT (source_event_id, event_type, channel, destination_key, payload,
              location_id)
    ON public.notification_outbox TO kokonut_anomaly_notification_owner;
GRANT INSERT (source_event_id, event_type, channel, destination_key, payload,
              location_id)
    ON public.notification_outbox TO kokonut_anomaly_notification_owner;

REVOKE ALL ON public.notification_outbox FROM kokonut_worker_execution;

CREATE OR REPLACE FUNCTION kokonut_security.enqueue_sensor_alert_notification_intent(
    requested_alert_event_id UUID,
    requested_source_event_id UUID,
    requested_source_reading_id UUID,
    requested_alert_rule_id UUID,
    requested_sensor_alert_id UUID,
    requested_location_id UUID,
    requested_channel TEXT,
    requested_destination_key TEXT,
    requested_payload JSONB
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    linked_alert RECORD;
    was_inserted BOOLEAN;
    existing_intent RECORD;
    allowed_keys TEXT[];
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'notification enqueue requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'notification enqueue is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_alert_event_id IS NULL
       OR requested_source_event_id IS NULL
       OR requested_source_reading_id IS NULL
       OR requested_alert_rule_id IS NULL
       OR requested_sensor_alert_id IS NULL THEN
        RAISE EXCEPTION 'notification source and alert identifiers are required'
            USING ERRCODE = '22023';
    END IF;
    IF requested_channel IS NULL
       OR requested_channel NOT IN ('webhook', 'directus', 'email')
       OR requested_destination_key IS DISTINCT FROM 'primary' THEN
        RAISE EXCEPTION 'notification channel or destination is not allowed'
            USING ERRCODE = '22023';
    END IF;
    IF requested_payload IS NULL
       OR jsonb_typeof(requested_payload) IS DISTINCT FROM 'object'
       OR octet_length(requested_payload::TEXT) > 16384 THEN
        RAISE EXCEPTION 'notification payload must be an object no larger than 16 KiB'
            USING ERRCODE = '22023';
    END IF;

    allowed_keys := CASE requested_channel
        WHEN 'webhook' THEN ARRAY[
            'text', 'alert_id', 'severity', 'message', 'sensor_device_id',
            'sensor_name', 'sensor_type', 'location_id', 'location_name',
            'reading_value', 'threshold_value', 'triggered_at', 'claim_id'
        ]
        WHEN 'directus' THEN ARRAY[
            'subject', 'message', 'type', 'recipient', 'status'
        ]
        ELSE ARRAY['subject', 'body']
    END;
    IF EXISTS (
        SELECT 1
          FROM jsonb_object_keys(requested_payload) AS payload_keys(payload_key)
         WHERE payload_key <> ALL (allowed_keys)
    ) THEN
        RAISE EXCEPTION 'notification payload contains unsupported fields'
            USING ERRCODE = '22023';
    END IF;

    SELECT alert.id, alert.location_id, alert.reading_id,
           alert.sensor_device_id, alert.alert_rule_id, alert.severity,
           alert.message, alert.claim_id, device.name AS sensor_name,
           sensor_type.name AS sensor_type
      INTO linked_alert
      FROM public.sensor_anomaly_effect AS effect
      JOIN public.platform_event AS source_event
        ON source_event.id = effect.source_event_id
       AND source_event.event_type = 'sensor_reading'
       AND source_event.source_table = 'sensor_reading'
       AND source_event.source_id = effect.source_reading_id
       AND source_event.payload ->> 'location_id' = worker_scope.location_id::TEXT
      JOIN public.sensor_reading AS reading
        ON reading.id = source_event.source_id
       AND reading.id = effect.source_reading_id
       AND reading.location_id = worker_scope.location_id
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
       )
      JOIN public.sensor_device AS device
        ON device.id::TEXT = reading.sensor_id::TEXT
       AND device.location_id = reading.location_id
      JOIN public.sensor_type AS sensor_type
        ON sensor_type.id = device.sensor_type_id
      JOIN public.sensor_alert AS alert
        ON alert.id = effect.sensor_alert_id
       AND alert.location_id = worker_scope.location_id
       AND alert.reading_id = reading.id
       AND alert.sensor_device_id = device.id
       AND alert.alert_rule_id = effect.alert_rule_id
      JOIN public.alert_rule AS rule
        ON rule.id = effect.alert_rule_id
       AND rule.sensor_type_id = device.sensor_type_id
      JOIN public.platform_event AS alert_event
        ON alert_event.id = requested_alert_event_id
       AND alert_event.event_type = 'sensor_alert'
       AND alert_event.source_table = 'sensor_alert'
       AND alert_event.source_id = alert.id
       AND alert_event.payload ->> 'alert_id' = alert.id::TEXT
       AND alert_event.payload ->> 'location_id' = worker_scope.location_id::TEXT
     WHERE effect.source_event_id = requested_source_event_id
       AND effect.source_reading_id = requested_source_reading_id
       AND effect.alert_rule_id = requested_alert_rule_id
       AND effect.location_id = worker_scope.location_id
       AND effect.outcome = 'alert_created'
       AND effect.sensor_alert_id = requested_sensor_alert_id
       AND alert.id = requested_sensor_alert_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'notification alert and source receipt do not match signed scope'
            USING ERRCODE = '42501';
    END IF;

    IF requested_channel = 'webhook' THEN
        IF NOT (requested_payload ?& ARRAY[
                'text', 'alert_id', 'severity', 'message', 'sensor_device_id',
                'sensor_name', 'sensor_type', 'location_id', 'location_name',
                'reading_value', 'threshold_value', 'triggered_at', 'claim_id'
            ])
           OR requested_payload ->> 'alert_id' IS DISTINCT FROM linked_alert.id::TEXT
           OR requested_payload ->> 'location_id' IS DISTINCT FROM worker_scope.location_id::TEXT
           OR requested_payload ->> 'severity' IS DISTINCT FROM linked_alert.severity
           OR requested_payload ->> 'message' IS DISTINCT FROM linked_alert.message
           OR requested_payload ->> 'sensor_device_id' IS DISTINCT FROM linked_alert.sensor_device_id::TEXT
           OR requested_payload ->> 'sensor_name' IS DISTINCT FROM linked_alert.sensor_name
           OR requested_payload ->> 'sensor_type' IS DISTINCT FROM linked_alert.sensor_type THEN
            RAISE EXCEPTION 'webhook notification does not match the linked alert'
                USING ERRCODE = '42501';
        END IF;
    ELSIF requested_channel = 'directus' THEN
        IF requested_payload <> jsonb_build_object(
            'subject', 'Sensor Alert: ' || COALESCE(linked_alert.sensor_name, 'Unknown'),
            'message', linked_alert.message,
            'type', linked_alert.severity,
            'recipient', 'role:00000000-0000-0000-0000-000000000006',
            'status', 'unread'
        ) THEN
            RAISE EXCEPTION 'Directus notification does not match the linked alert contract'
                USING ERRCODE = '42501';
        END IF;
    ELSE
        IF NOT (requested_payload ?& ARRAY['subject', 'body'])
           OR requested_payload ->> 'subject' IS DISTINCT FROM
              '[' || UPPER(linked_alert.severity) || '] Sensor Alert: '
                  || COALESCE(linked_alert.sensor_name, 'Unknown')
           OR requested_payload ->> 'body' IS NULL
           OR position(('Alert ID: ' || linked_alert.id::TEXT) IN
                       (requested_payload ->> 'body')) = 0 THEN
            RAISE EXCEPTION 'email notification does not match the linked alert'
                USING ERRCODE = '42501';
        END IF;
    END IF;

    was_inserted := FALSE;
    INSERT INTO public.notification_outbox (
        source_event_id, event_type, channel, destination_key, payload, location_id
    ) VALUES (
        requested_alert_event_id, 'sensor_alert', requested_channel,
        requested_destination_key, requested_payload, worker_scope.location_id
    )
    ON CONFLICT (source_event_id, channel, destination_key) DO NOTHING
    RETURNING TRUE INTO was_inserted;

    IF COALESCE(was_inserted, FALSE) THEN
        RETURN TRUE;
    END IF;

    SELECT event_type, payload, location_id
      INTO existing_intent
      FROM public.notification_outbox
     WHERE source_event_id = requested_alert_event_id
       AND channel = requested_channel
       AND destination_key = requested_destination_key;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'notification identity conflicts with existing content'
            USING ERRCODE = '23505';
    END IF;
    IF existing_intent.event_type IS DISTINCT FROM 'sensor_alert'
       OR existing_intent.payload IS DISTINCT FROM requested_payload
       OR existing_intent.location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'notification identity conflicts with existing content'
            USING ERRCODE = '23505';
    END IF;
    RETURN FALSE;
END;
$$;

ALTER FUNCTION kokonut_security.enqueue_sensor_alert_notification_intent(
    UUID, UUID, UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
) OWNER TO kokonut_anomaly_notification_owner;
REVOKE ALL ON FUNCTION kokonut_security.enqueue_sensor_alert_notification_intent(
    UUID, UUID, UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.enqueue_sensor_alert_notification_intent(
    UUID, UUID, UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
) TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.enqueue_sensor_alert_notification_intent(
            UUID, UUID, UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
        ) FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.enqueue_sensor_alert_notification_intent(
            UUID, UUID, UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
        ) FROM kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_anomaly_notification_owner;

COMMENT ON FUNCTION kokonut_security.enqueue_sensor_alert_notification_intent(
    UUID, UUID, UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
) IS
    'Enqueues an allowlisted, idempotent notification intent only for a matching signed-location sensor alert; it cannot claim, deliver, replay, dispose, or edit notification state.';

COMMIT;
