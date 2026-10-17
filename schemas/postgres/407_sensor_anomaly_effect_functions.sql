-- Expose only location-verified anomaly idempotency operations to the
-- dedicated worker execution role. No dispatcher or login is provisioned.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_anomaly_effect_owner'
    ) THEN
        CREATE ROLE kokonut_anomaly_effect_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_anomaly_effect_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_effect_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_anomaly_effect_owner'
            OR member_role.rolname = 'kokonut_anomaly_effect_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_effect_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_anomaly_effect_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_anomaly_effect_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_anomaly_effect_owner;

GRANT SELECT (id, event_type, source_table, source_id, payload)
    ON public.platform_event TO kokonut_anomaly_effect_owner;
GRANT SELECT (id, sensor_id, location_id)
    ON public.sensor_reading TO kokonut_anomaly_effect_owner;
GRANT SELECT (id, location_id)
    ON public.sensor_device TO kokonut_anomaly_effect_owner;
GRANT SELECT (id, enabled)
    ON public.alert_rule TO kokonut_anomaly_effect_owner;
GRANT SELECT (id, location_id, reading_id, alert_rule_id, sensor_device_id)
    ON public.sensor_alert TO kokonut_anomaly_effect_owner;
GRANT SELECT (source_reading_id, alert_rule_id, source_event_id, location_id, outcome)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_effect_owner;
GRANT INSERT (location_id, source_reading_id, alert_rule_id, source_event_id, outcome)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_effect_owner;
GRANT UPDATE (outcome, sensor_alert_id, updated_at)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_effect_owner;
REVOKE ALL ON public.sensor_anomaly_effect FROM kokonut_worker_execution;

CREATE OR REPLACE FUNCTION kokonut_security.reserve_sensor_anomaly_effect(
    requested_source_event_id UUID,
    requested_source_reading_id UUID,
    requested_alert_rule_id UUID,
    requested_location_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    was_inserted BOOLEAN;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'anomaly effect reservation requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'anomaly effect reservation is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM public.platform_event AS source_event
          JOIN public.sensor_reading AS reading
            ON reading.id = source_event.source_id
          JOIN public.sensor_device AS device
            ON device.id::TEXT = reading.sensor_id::TEXT
           AND device.location_id = reading.location_id
          JOIN public.alert_rule AS rule
            ON rule.id = requested_alert_rule_id
           AND rule.enabled = TRUE
         WHERE source_event.id = requested_source_event_id
           AND source_event.event_type = 'sensor_reading'
           AND source_event.source_table = 'sensor_reading'
           AND source_event.source_id = requested_source_reading_id
           AND source_event.payload ->> 'location_id' = worker_scope.location_id::TEXT
           AND reading.id = requested_source_reading_id
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
    ) THEN
        RAISE EXCEPTION 'anomaly source, rule, or location does not match signed scope'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO public.sensor_anomaly_effect (
        location_id, source_reading_id, alert_rule_id, source_event_id, outcome
    ) VALUES (
        worker_scope.location_id, requested_source_reading_id,
        requested_alert_rule_id, requested_source_event_id, 'no_match'
    )
    ON CONFLICT DO NOTHING
    RETURNING TRUE INTO was_inserted;

    RETURN COALESCE(was_inserted, FALSE);
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.record_sensor_anomaly_effect_outcome(
    requested_source_event_id UUID,
    requested_source_reading_id UUID,
    requested_alert_rule_id UUID,
    requested_location_id UUID,
    requested_outcome TEXT,
    requested_sensor_alert_id UUID DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    was_updated BOOLEAN;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'anomaly effect update requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'anomaly effect update is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_outcome IS NULL
       OR requested_outcome NOT IN ('cooldown', 'alert_created') THEN
        RAISE EXCEPTION 'unsupported anomaly effect outcome'
            USING ERRCODE = '22023';
    END IF;

    IF requested_outcome = 'alert_created' THEN
        IF requested_sensor_alert_id IS NULL OR NOT EXISTS (
            SELECT 1
              FROM public.sensor_alert AS alert
              JOIN public.sensor_reading AS reading
                ON reading.id = alert.reading_id
              JOIN public.sensor_device AS device
                ON device.id = alert.sensor_device_id
               AND device.id::TEXT = reading.sensor_id::TEXT
               AND device.location_id = reading.location_id
             WHERE alert.id = requested_sensor_alert_id
               AND alert.location_id = worker_scope.location_id
               AND alert.reading_id = requested_source_reading_id
               AND alert.alert_rule_id = requested_alert_rule_id
               AND reading.location_id = worker_scope.location_id
        ) THEN
            RAISE EXCEPTION 'alert does not match the signed source reading and location'
                USING ERRCODE = '42501';
        END IF;
    ELSIF requested_sensor_alert_id IS NOT NULL THEN
        RAISE EXCEPTION 'only alert_created outcomes may reference an alert'
            USING ERRCODE = '22023';
    END IF;

    UPDATE public.sensor_anomaly_effect AS effect
       SET outcome = requested_outcome,
           sensor_alert_id = requested_sensor_alert_id,
           updated_at = statement_timestamp()
     WHERE effect.location_id = worker_scope.location_id
       AND effect.source_event_id = requested_source_event_id
       AND effect.source_reading_id = requested_source_reading_id
       AND effect.alert_rule_id = requested_alert_rule_id
       AND effect.outcome = 'no_match'
    RETURNING TRUE INTO was_updated;

    RETURN COALESCE(was_updated, FALSE);
END;
$$;

ALTER FUNCTION kokonut_security.reserve_sensor_anomaly_effect(UUID, UUID, UUID, UUID)
    OWNER TO kokonut_anomaly_effect_owner;
ALTER FUNCTION kokonut_security.record_sensor_anomaly_effect_outcome(
    UUID, UUID, UUID, UUID, TEXT, UUID
) OWNER TO kokonut_anomaly_effect_owner;

REVOKE ALL ON FUNCTION kokonut_security.reserve_sensor_anomaly_effect(UUID, UUID, UUID, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.record_sensor_anomaly_effect_outcome(
    UUID, UUID, UUID, UUID, TEXT, UUID
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.reserve_sensor_anomaly_effect(UUID, UUID, UUID, UUID)
    TO kokonut_worker_execution;
GRANT EXECUTE ON FUNCTION kokonut_security.record_sensor_anomaly_effect_outcome(
    UUID, UUID, UUID, UUID, TEXT, UUID
) TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.reserve_sensor_anomaly_effect(UUID, UUID, UUID, UUID)
            FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.record_sensor_anomaly_effect_outcome(
            UUID, UUID, UUID, UUID, TEXT, UUID
        ) FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.reserve_sensor_anomaly_effect(UUID, UUID, UUID, UUID)
            FROM kokonut_operator_auth;
        REVOKE ALL ON FUNCTION kokonut_security.record_sensor_anomaly_effect_outcome(
            UUID, UUID, UUID, UUID, TEXT, UUID
        ) FROM kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_anomaly_effect_owner;

COMMENT ON FUNCTION kokonut_security.reserve_sensor_anomaly_effect(UUID, UUID, UUID, UUID) IS
    'Reserves one anomaly receipt only for a signed sensor_reading/process scope whose event, payload selectors, reading, device, and enabled rule agree.';
COMMENT ON FUNCTION kokonut_security.record_sensor_anomaly_effect_outcome(
    UUID, UUID, UUID, UUID, TEXT, UUID
) IS
    'Transitions only a matching no_match anomaly receipt to cooldown or alert_created; an alert link must match the same source reading, rule, device, and location.';

COMMIT;
