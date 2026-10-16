-- Record one bounded, location-scoped actuation intent for a published alert.
-- This function does not approve, deliver, or execute the command.

BEGIN;

ALTER TABLE public.actuation_log
    ADD COLUMN IF NOT EXISTS source_alert_event_id UUID;

CREATE UNIQUE INDEX IF NOT EXISTS ux_actuation_log_source_alert_event
    ON public.actuation_log(source_alert_event_id)
    WHERE source_alert_event_id IS NOT NULL;

COMMENT ON COLUMN public.actuation_log.source_alert_event_id IS
    'Published sensor_alert event that produced this idempotent actuation intent; NULL for legacy records.';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_anomaly_actuation_owner'
    ) THEN
        CREATE ROLE kokonut_anomaly_actuation_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname = 'kokonut_anomaly_actuation_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_actuation_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_anomaly_actuation_owner'
            OR member_role.rolname = 'kokonut_anomaly_actuation_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_actuation_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_anomaly_actuation_owner;
GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_anomaly_actuation_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_anomaly_actuation_owner;

GRANT SELECT (id, event_type, source_table, source_id, payload)
    ON public.platform_event TO kokonut_anomaly_actuation_owner;
GRANT SELECT (location_id, source_reading_id, alert_rule_id, source_event_id,
              outcome, sensor_alert_id)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_actuation_owner;
GRANT SELECT (id, location_id, reading_id, sensor_device_id, alert_rule_id,
              severity, message, reading_value, threshold_value, triggered_at,
              claim_id)
    ON public.sensor_alert TO kokonut_anomaly_actuation_owner;
GRANT SELECT (id, sensor_id, location_id)
    ON public.sensor_reading TO kokonut_anomaly_actuation_owner;
GRANT SELECT (id, location_id, sensor_type_id)
    ON public.sensor_device TO kokonut_anomaly_actuation_owner;
GRANT SELECT (id, enabled, sensor_type_id, severity, actuator_enabled,
              actuator_type, actuator_command, actuator_topic,
              human_approval_required)
    ON public.alert_rule TO kokonut_anomaly_actuation_owner;
GRANT SELECT (id, location_id, sensor_alert_id, source_alert_event_id,
              actuator_type, actuator_command, actuator_topic, command_payload,
              trigger_source, trigger_alert_severity, human_approval_required)
    ON public.actuation_log TO kokonut_anomaly_actuation_owner;
GRANT INSERT (location_id, sensor_alert_id, source_alert_event_id, actuator_type,
              actuator_command, actuator_topic, command_payload, trigger_source,
              trigger_alert_severity, human_approval_required, status, metadata)
    ON public.actuation_log TO kokonut_anomaly_actuation_owner;

REVOKE ALL ON public.actuation_log FROM kokonut_worker_execution;

CREATE OR REPLACE FUNCTION kokonut_security.create_sensor_alert_actuation_intent(
    requested_alert_event_id UUID,
    requested_source_event_id UUID,
    requested_source_reading_id UUID,
    requested_alert_rule_id UUID,
    requested_sensor_alert_id UUID,
    requested_location_id UUID
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    linked_alert RECORD;
    command_payload JSONB;
    command_topic TEXT;
    approval_required BOOLEAN;
    initial_status TEXT;
    inserted_id UUID;
    existing_intent RECORD;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'actuation intent requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'actuation intent is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_alert_event_id IS NULL
       OR requested_source_event_id IS NULL
       OR requested_source_reading_id IS NULL
       OR requested_alert_rule_id IS NULL
       OR requested_sensor_alert_id IS NULL THEN
        RAISE EXCEPTION 'actuation source and alert identifiers are required'
            USING ERRCODE = '22023';
    END IF;

    SELECT alert.id, alert.location_id, alert.reading_id,
           alert.sensor_device_id, alert.alert_rule_id, alert.severity,
           alert.message, alert.reading_value, alert.threshold_value,
           alert.triggered_at, alert.claim_id, rule.actuator_type,
           rule.actuator_command, rule.human_approval_required
      INTO linked_alert
      FROM public.sensor_anomaly_effect AS effect
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
       AND device.location_id = reading.location_id
      JOIN public.alert_rule AS rule
        ON rule.id = effect.alert_rule_id
       AND rule.sensor_type_id = device.sensor_type_id
       AND rule.enabled = TRUE
       AND rule.actuator_enabled = TRUE
       AND rule.actuator_type IS NOT NULL
       AND NULLIF(btrim(rule.actuator_command), '') IS NOT NULL
      JOIN public.sensor_alert AS alert
        ON alert.id = effect.sensor_alert_id
       AND alert.location_id = worker_scope.location_id
       AND alert.reading_id = reading.id
       AND alert.sensor_device_id = device.id
       AND alert.alert_rule_id = effect.alert_rule_id
       AND alert.severity = rule.severity
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
        RAISE EXCEPTION 'actuation source, alert, rule, or location does not match signed scope'
            USING ERRCODE = '42501';
    END IF;

    command_payload := jsonb_build_object(
        'device_id', linked_alert.sensor_device_id,
        'actuator_type', linked_alert.actuator_type,
        'command', linked_alert.actuator_command,
        'parameters', jsonb_build_object('alert_id', linked_alert.id),
        'trigger_source', 'anomaly_detector',
        'alert_id', linked_alert.id,
        'alert_severity', linked_alert.severity
    );
    command_topic := 'actuators/' || worker_scope.location_id::TEXT || '/'
        || linked_alert.actuator_type || '/commands';
    approval_required := COALESCE(linked_alert.human_approval_required, TRUE)
        OR linked_alert.severity = 'critical';
    initial_status := CASE WHEN approval_required
        THEN 'requires_approval' ELSE 'pending' END;

    INSERT INTO public.actuation_log (
        location_id, sensor_alert_id, source_alert_event_id, actuator_type,
        actuator_command, actuator_topic, command_payload, trigger_source,
        trigger_alert_severity, human_approval_required, status, metadata
    ) VALUES (
        worker_scope.location_id, linked_alert.id, requested_alert_event_id,
        linked_alert.actuator_type, linked_alert.actuator_command,
        command_topic, command_payload, 'anomaly_detector',
        linked_alert.severity, approval_required, initial_status,
        jsonb_build_object(
            'source_reading_event_id', requested_source_event_id,
            'source_reading_id', requested_source_reading_id,
            'alert_rule_id', requested_alert_rule_id
        )
    )
    ON CONFLICT (source_alert_event_id)
        WHERE source_alert_event_id IS NOT NULL
    DO NOTHING
    RETURNING id INTO inserted_id;

    IF inserted_id IS NOT NULL THEN
        RETURN inserted_id;
    END IF;

    SELECT existing_row.id, existing_row.location_id,
           existing_row.sensor_alert_id, existing_row.source_alert_event_id,
           existing_row.actuator_type, existing_row.actuator_command,
           existing_row.actuator_topic, existing_row.command_payload,
           existing_row.trigger_source, existing_row.trigger_alert_severity,
           existing_row.human_approval_required
      INTO existing_intent
      FROM public.actuation_log AS existing_row
     WHERE existing_row.source_alert_event_id = requested_alert_event_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'actuation alert-event identity conflicts with existing content'
            USING ERRCODE = '23505';
    END IF;
    IF existing_intent.location_id IS DISTINCT FROM worker_scope.location_id
       OR existing_intent.sensor_alert_id IS DISTINCT FROM linked_alert.id
       OR existing_intent.source_alert_event_id IS DISTINCT FROM requested_alert_event_id
       OR existing_intent.actuator_type IS DISTINCT FROM linked_alert.actuator_type
       OR existing_intent.actuator_command IS DISTINCT FROM linked_alert.actuator_command
       OR existing_intent.actuator_topic IS DISTINCT FROM command_topic
       OR existing_intent.command_payload IS DISTINCT FROM command_payload
       OR existing_intent.trigger_source IS DISTINCT FROM 'anomaly_detector'
       OR existing_intent.trigger_alert_severity IS DISTINCT FROM linked_alert.severity
       OR existing_intent.human_approval_required IS DISTINCT FROM approval_required THEN
        RAISE EXCEPTION 'actuation alert-event identity conflicts with existing content'
            USING ERRCODE = '23505';
    END IF;

    -- Idempotent retries return the existing ID without resetting approval,
    -- transport, response, attempt, or lifecycle state.
    RETURN existing_intent.id;
END;
$$;

ALTER FUNCTION kokonut_security.create_sensor_alert_actuation_intent(
    UUID, UUID, UUID, UUID, UUID, UUID
) OWNER TO kokonut_anomaly_actuation_owner;
REVOKE ALL ON FUNCTION kokonut_security.create_sensor_alert_actuation_intent(
    UUID, UUID, UUID, UUID, UUID, UUID
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.create_sensor_alert_actuation_intent(
    UUID, UUID, UUID, UUID, UUID, UUID
) TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_sensor_alert_actuation_intent(
            UUID, UUID, UUID, UUID, UUID, UUID
        ) FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_sensor_alert_actuation_intent(
            UUID, UUID, UUID, UUID, UUID, UUID
        ) FROM kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_anomaly_actuation_owner;

COMMENT ON FUNCTION kokonut_security.create_sensor_alert_actuation_intent(
    UUID, UUID, UUID, UUID, UUID, UUID
) IS
    'Creates one idempotent actuation intent from a matching signed-location sensor alert and published alert event; it cannot approve, publish, send, execute, or edit actuation state.';

COMMIT;
