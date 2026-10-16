-- Add narrowly scoped, signed-context reads for sensor-anomaly execution.
-- These functions remain dormant until a dedicated worker is provisioned.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_anomaly_read_owner'
    ) THEN
        CREATE ROLE kokonut_anomaly_read_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_anomaly_read_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_read_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_anomaly_read_owner'
            OR member_role.rolname = 'kokonut_anomaly_read_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_read_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_anomaly_read_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_anomaly_read_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_anomaly_read_owner;

GRANT SELECT (id, event_type, source_table, source_id, payload)
    ON public.platform_event TO kokonut_anomaly_read_owner;
GRANT SELECT (id, sensor_id, sensor_type, value, reading_date, reading_time,
              location_id, plot_id, created_at)
    ON public.sensor_reading TO kokonut_anomaly_read_owner;
GRANT SELECT (id, name, location_id, sensor_type_id)
    ON public.sensor_device TO kokonut_anomaly_read_owner;
GRANT SELECT (id, name)
    ON public.sensor_type TO kokonut_anomaly_read_owner;
GRANT SELECT (id, name)
    ON public.location TO kokonut_anomaly_read_owner;
GRANT SELECT (id, name, sensor_type_id, metric, operator, threshold_value,
              threshold_value_max, severity, cooldown_minutes, enabled,
              auto_create_claim, claim_type)
    ON public.alert_rule TO kokonut_anomaly_read_owner;
GRANT SELECT (id, alert_rule_id, sensor_device_id, location_id, triggered_at)
    ON public.sensor_alert TO kokonut_anomaly_read_owner;

-- A few tenant tables already use FORCE ROW LEVEL SECURITY. The function
-- owner has no login or memberships; these policies let only its bounded
-- SECURITY DEFINER functions see rows, which still filter by signed scope.
DO $$
DECLARE
    target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'platform_event', 'sensor_reading', 'sensor_device', 'sensor_type',
        'location', 'alert_rule', 'sensor_alert'
    ] LOOP
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
              AND policyname = 'anomaly_read_owner_select'
        ) THEN
            EXECUTE format(
                'CREATE POLICY anomaly_read_owner_select ON public.%I '
                'FOR SELECT TO kokonut_anomaly_read_owner USING (true)',
                target_table
            );
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON public.platform_event, public.sensor_reading,
    public.sensor_device, public.sensor_type, public.location,
    public.alert_rule, public.sensor_alert
    FROM kokonut_worker_execution;

CREATE OR REPLACE FUNCTION kokonut_security.read_sensor_anomaly_source(
    requested_source_event_id UUID,
    requested_location_id UUID,
    requested_sensor_id TEXT
)
RETURNS TABLE (
    reading_id UUID,
    sensor_id UUID,
    sensor_type TEXT,
    reading_value NUMERIC,
    reading_date DATE,
    reading_time TIME,
    location_id UUID,
    plot_id UUID,
    sensor_device_id UUID,
    sensor_name TEXT,
    sensor_type_id UUID,
    sensor_type_name TEXT,
    location_name TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'anomaly source read requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'anomaly source read is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_source_event_id IS NULL
       OR requested_sensor_id IS NULL
       OR BTRIM(requested_sensor_id) = '' THEN
        RAISE EXCEPTION 'anomaly source event and sensor identifiers are required'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT reading.id,
           reading.sensor_id,
           reading.sensor_type::TEXT,
           reading.value,
           reading.reading_date,
           reading.reading_time,
           reading.location_id,
           reading.plot_id,
           device.id,
           COALESCE(device.name, 'Unknown')::TEXT,
           device.sensor_type_id,
           sensor_type.name::TEXT,
           COALESCE(location.name, 'Unknown')::TEXT
      FROM public.platform_event AS source_event
      JOIN public.sensor_reading AS reading
        ON reading.id = source_event.source_id
       AND reading.location_id = worker_scope.location_id
      JOIN public.sensor_device AS device
        ON device.id = reading.sensor_id
       AND device.location_id = reading.location_id
      JOIN public.sensor_type AS sensor_type
        ON sensor_type.id = device.sensor_type_id
       AND reading.sensor_type = sensor_type.name
      LEFT JOIN public.location AS location
        ON location.id = reading.location_id
     WHERE source_event.id = requested_source_event_id
       AND source_event.event_type = 'sensor_reading'
       AND source_event.source_table = 'sensor_reading'
       AND source_event.source_id = reading.id
       AND source_event.payload ->> 'location_id' = worker_scope.location_id::TEXT
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
       AND requested_sensor_id = reading.sensor_id::TEXT;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'anomaly source, sensor, or location does not match signed scope'
            USING ERRCODE = '42501';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_sensor_anomaly_rules(
    requested_sensor_device_id UUID,
    requested_location_id UUID
)
RETURNS TABLE (
    rule_id UUID,
    rule_name TEXT,
    sensor_type_id UUID,
    sensor_type TEXT,
    metric TEXT,
    operator TEXT,
    threshold_value NUMERIC,
    threshold_value_max NUMERIC,
    severity TEXT,
    cooldown_minutes INTEGER,
    auto_create_claim BOOLEAN,
    claim_type TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'anomaly rule read requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'anomaly rule read is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_sensor_device_id IS NULL OR NOT EXISTS (
        SELECT 1
          FROM public.sensor_device AS device
         WHERE device.id = requested_sensor_device_id
           AND device.location_id = worker_scope.location_id
    ) THEN
        RAISE EXCEPTION 'anomaly rule device does not match signed location'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT rule.id,
           rule.name::TEXT,
           rule.sensor_type_id,
           sensor_type.name::TEXT,
           rule.metric::TEXT,
           rule.operator::TEXT,
           rule.threshold_value,
           rule.threshold_value_max,
           rule.severity::TEXT,
           COALESCE(rule.cooldown_minutes, 60),
           COALESCE(rule.auto_create_claim, FALSE),
           rule.claim_type::TEXT
      FROM public.sensor_device AS device
      JOIN public.alert_rule AS rule
        ON rule.sensor_type_id = device.sensor_type_id
       AND rule.enabled = TRUE
      JOIN public.sensor_type AS sensor_type
        ON sensor_type.id = rule.sensor_type_id
     WHERE device.id = requested_sensor_device_id
       AND device.location_id = worker_scope.location_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.evaluate_sensor_anomaly_rule(
    requested_source_event_id UUID,
    requested_reading_id UUID,
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
    source_reading RECORD;
    alert_rule RECORD;
    observed_value NUMERIC;
    calculated_rate NUMERIC;
    old_value NUMERIC;
    new_value NUMERIC;
    old_measured_at TIMESTAMP WITHOUT TIME ZONE;
    new_measured_at TIMESTAMP WITHOUT TIME ZONE;
    history_count BIGINT;
    comparison_result BOOLEAN := FALSE;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'anomaly rule evaluation requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'anomaly rule evaluation is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_source_event_id IS NULL
       OR requested_reading_id IS NULL
       OR requested_alert_rule_id IS NULL THEN
        RAISE EXCEPTION 'anomaly source event, reading, and rule are required'
            USING ERRCODE = '22023';
    END IF;

    SELECT reading.id, reading.sensor_id, reading.sensor_type,
           reading.value, reading.location_id, device.sensor_type_id
      INTO source_reading
      FROM public.platform_event AS source_event
      JOIN public.sensor_reading AS reading
        ON reading.id = source_event.source_id
       AND reading.location_id = worker_scope.location_id
      JOIN public.sensor_device AS device
        ON device.id = reading.sensor_id
       AND device.location_id = reading.location_id
      JOIN public.sensor_type AS sensor_type
        ON sensor_type.id = device.sensor_type_id
       AND reading.sensor_type = sensor_type.name
     WHERE source_event.id = requested_source_event_id
       AND source_event.event_type = 'sensor_reading'
       AND source_event.source_table = 'sensor_reading'
       AND source_event.source_id = requested_reading_id
       AND source_event.payload ->> 'location_id' = worker_scope.location_id::TEXT
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
       AND reading.id = requested_reading_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'anomaly reading does not match signed location'
            USING ERRCODE = '42501';
    END IF;

    SELECT rule.metric, rule.operator, rule.threshold_value,
           rule.threshold_value_max, rule.enabled
      INTO alert_rule
      FROM public.alert_rule AS rule
     WHERE rule.id = requested_alert_rule_id
       AND rule.sensor_type_id = source_reading.sensor_type_id;
    IF NOT FOUND OR alert_rule.enabled IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'anomaly rule is unavailable for the source reading'
            USING ERRCODE = '42501';
    END IF;

    IF alert_rule.metric = 'value' THEN
        observed_value := source_reading.value;
    ELSIF alert_rule.metric = 'rate_of_change' THEN
        SELECT MAX(history.value) FILTER (WHERE history.position = 1),
               MAX(history.value) FILTER (WHERE history.position = 2),
               MAX(history.measured_at) FILTER (WHERE history.position = 1),
               MAX(history.measured_at) FILTER (WHERE history.position = 2),
               COUNT(*)
          INTO old_value, new_value, old_measured_at, new_measured_at, history_count
          FROM (
              SELECT reading.value,
                     (reading.reading_date + COALESCE(reading.reading_time, TIME '00:00'))
                         AS measured_at,
                     ROW_NUMBER() OVER (ORDER BY reading.created_at ASC) AS position
                FROM public.sensor_reading AS reading
               WHERE reading.sensor_id = source_reading.sensor_id
                 AND reading.sensor_type = source_reading.sensor_type
                 AND reading.location_id = worker_scope.location_id
                 AND reading.created_at >= NOW() - INTERVAL '24 hours'
               ORDER BY reading.created_at ASC
               LIMIT 2
          ) AS history;
        IF history_count < 2 OR new_measured_at <= old_measured_at THEN
            RETURN FALSE;
        END IF;
        calculated_rate := (new_value - old_value)
            / NULLIF(EXTRACT(EPOCH FROM (new_measured_at - old_measured_at)) / 3600.0, 0);
        observed_value := calculated_rate;
    ELSIF alert_rule.metric = 'gap' THEN
        SELECT EXTRACT(EPOCH FROM (NOW() - MAX(reading.created_at))) / 3600.0
          INTO observed_value
          FROM public.sensor_reading AS reading
         WHERE reading.sensor_id = source_reading.sensor_id
           AND reading.sensor_type = source_reading.sensor_type
           AND reading.location_id = worker_scope.location_id;
    ELSIF alert_rule.metric IN ('min', 'max') THEN
        SELECT CASE alert_rule.metric
                   WHEN 'min' THEN MIN(reading.value)
                   ELSE MAX(reading.value)
               END,
               COUNT(*)
          INTO observed_value, history_count
          FROM public.sensor_reading AS reading
         WHERE reading.sensor_id = source_reading.sensor_id
           AND reading.sensor_type = source_reading.sensor_type
           AND reading.location_id = worker_scope.location_id
           AND reading.created_at >= NOW() - INTERVAL '24 hours';
        IF history_count = 0 THEN
            RETURN FALSE;
        END IF;
    ELSE
        RETURN FALSE;
    END IF;

    IF observed_value IS NULL THEN
        RETURN FALSE;
    END IF;
    comparison_result := CASE alert_rule.operator
        WHEN 'gt' THEN observed_value > alert_rule.threshold_value
        WHEN 'lt' THEN observed_value < alert_rule.threshold_value
        WHEN 'gte' THEN observed_value >= alert_rule.threshold_value
        WHEN 'lte' THEN observed_value <= alert_rule.threshold_value
        WHEN 'eq' THEN ABS(observed_value - alert_rule.threshold_value) < 0.001
        WHEN 'neq' THEN ABS(observed_value - alert_rule.threshold_value) >= 0.001
        WHEN 'outside_range' THEN
            alert_rule.threshold_value_max IS NOT NULL
            AND (observed_value < alert_rule.threshold_value
                 OR observed_value > alert_rule.threshold_value_max)
        ELSE FALSE
    END;
    RETURN COALESCE(comparison_result, FALSE);
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.sensor_anomaly_in_cooldown(
    requested_sensor_device_id UUID,
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
    configured_cooldown INTEGER;
    last_triggered_at TIMESTAMPTZ;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'anomaly cooldown read requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'anomaly cooldown read is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;

    SELECT COALESCE(rule.cooldown_minutes, 60)
      INTO configured_cooldown
      FROM public.alert_rule AS rule
      JOIN public.sensor_device AS device
        ON device.sensor_type_id = rule.sensor_type_id
     WHERE rule.id = requested_alert_rule_id
       AND rule.enabled = TRUE
       AND device.id = requested_sensor_device_id
       AND device.location_id = worker_scope.location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'anomaly cooldown rule or device does not match signed location'
            USING ERRCODE = '42501';
    END IF;
    IF configured_cooldown <= 0 THEN
        RETURN FALSE;
    END IF;

    SELECT MAX(alert.triggered_at)
      INTO last_triggered_at
      FROM public.sensor_alert AS alert
     WHERE alert.alert_rule_id = requested_alert_rule_id
       AND alert.sensor_device_id = requested_sensor_device_id
       AND alert.location_id = worker_scope.location_id;

    RETURN last_triggered_at IS NOT NULL
       AND last_triggered_at > NOW() - MAKE_INTERVAL(mins => configured_cooldown);
END;
$$;

ALTER FUNCTION kokonut_security.read_sensor_anomaly_source(UUID, UUID, TEXT)
    OWNER TO kokonut_anomaly_read_owner;
ALTER FUNCTION kokonut_security.list_sensor_anomaly_rules(UUID, UUID)
    OWNER TO kokonut_anomaly_read_owner;
ALTER FUNCTION kokonut_security.evaluate_sensor_anomaly_rule(UUID, UUID, UUID, UUID)
    OWNER TO kokonut_anomaly_read_owner;
ALTER FUNCTION kokonut_security.sensor_anomaly_in_cooldown(UUID, UUID, UUID)
    OWNER TO kokonut_anomaly_read_owner;

REVOKE ALL ON FUNCTION kokonut_security.read_sensor_anomaly_source(UUID, UUID, TEXT)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_sensor_anomaly_rules(UUID, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.evaluate_sensor_anomaly_rule(UUID, UUID, UUID, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.sensor_anomaly_in_cooldown(UUID, UUID, UUID)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.read_sensor_anomaly_source(UUID, UUID, TEXT)
    TO kokonut_worker_execution;
GRANT EXECUTE ON FUNCTION kokonut_security.list_sensor_anomaly_rules(UUID, UUID)
    TO kokonut_worker_execution;
GRANT EXECUTE ON FUNCTION kokonut_security.evaluate_sensor_anomaly_rule(UUID, UUID, UUID, UUID)
    TO kokonut_worker_execution;
GRANT EXECUTE ON FUNCTION kokonut_security.sensor_anomaly_in_cooldown(UUID, UUID, UUID)
    TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.read_sensor_anomaly_source(UUID, UUID, TEXT)
            FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_sensor_anomaly_rules(UUID, UUID)
            FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.evaluate_sensor_anomaly_rule(UUID, UUID, UUID, UUID)
            FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.sensor_anomaly_in_cooldown(UUID, UUID, UUID)
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.read_sensor_anomaly_source(UUID, UUID, TEXT)
            FROM kokonut_operator_auth;
        REVOKE ALL ON FUNCTION kokonut_security.list_sensor_anomaly_rules(UUID, UUID)
            FROM kokonut_operator_auth;
        REVOKE ALL ON FUNCTION kokonut_security.evaluate_sensor_anomaly_rule(UUID, UUID, UUID, UUID)
            FROM kokonut_operator_auth;
        REVOKE ALL ON FUNCTION kokonut_security.sensor_anomaly_in_cooldown(UUID, UUID, UUID)
            FROM kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_anomaly_read_owner;

COMMENT ON FUNCTION kokonut_security.read_sensor_anomaly_source(UUID, UUID, TEXT) IS
    'Reads exactly one event-linked sensor reading and its notification context under matching signed worker location.';
COMMENT ON FUNCTION kokonut_security.list_sensor_anomaly_rules(UUID, UUID) IS
    'Lists enabled alert rules for one device under its matching signed worker location.';
COMMENT ON FUNCTION kokonut_security.evaluate_sensor_anomaly_rule(UUID, UUID, UUID, UUID) IS
    'Evaluates one enabled alert rule against an event-linked source reading and location-bounded 24-hour history.';
COMMENT ON FUNCTION kokonut_security.sensor_anomaly_in_cooldown(UUID, UUID, UUID) IS
    'Checks the configured cooldown for one device/rule pair under matching signed worker location.';

COMMIT;
