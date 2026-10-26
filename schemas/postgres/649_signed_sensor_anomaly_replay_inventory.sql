-- Provide a bounded inventory of unreceipted sensor-reading events for one
-- signed location. The existing event worker performs the effects and owns
-- the per-reading/rule idempotency boundary.
BEGIN;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_anomaly_read_owner;
GRANT SELECT (created_at) ON public.platform_event TO kokonut_anomaly_read_owner;
GRANT SELECT (source_reading_id, alert_rule_id, location_id)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_read_owner;

DO $$
BEGIN
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
          AND policyname = 'anomaly_read_owner_select'
    ) THEN
        CREATE POLICY anomaly_read_owner_select ON public.sensor_anomaly_effect
            FOR SELECT TO kokonut_anomaly_read_owner USING (true);
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_sensor_anomaly_events_since(
    requested_location_id UUID,
    requested_since TIMESTAMPTZ,
    requested_batch_size INTEGER
)
RETURNS TABLE (event_id UUID, sensor_id TEXT, event_created_at TIMESTAMPTZ)
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
        RAISE EXCEPTION 'anomaly event inventory requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'anomaly event inventory is outside the signed location'
            USING ERRCODE = '42501';
    END IF;
    IF requested_since IS NULL
       OR requested_since < statement_timestamp() - INTERVAL '24 hours'
       OR requested_since > statement_timestamp()
       OR requested_batch_size IS NULL
       OR requested_batch_size < 1 OR requested_batch_size > 100 THEN
        RAISE EXCEPTION 'anomaly event inventory window or batch size is invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    WITH candidates AS (
        SELECT DISTINCT ON (reading.id)
               source_event.id AS event_id,
               reading.sensor_id::TEXT AS sensor_id,
               source_event.created_at AS event_created_at
          FROM public.platform_event AS source_event
          JOIN public.sensor_reading AS reading
            ON reading.id = source_event.source_id
           AND reading.location_id = worker_scope.location_id
          JOIN public.sensor_device AS device
            ON device.id = reading.sensor_id
           AND device.location_id = reading.location_id
           AND device.sensor_type_id IS NOT NULL
          JOIN public.sensor_type AS sensor_type
            ON sensor_type.id = device.sensor_type_id
           AND sensor_type.name = reading.sensor_type
         WHERE source_event.event_type = 'sensor_reading'
           AND source_event.source_table = 'sensor_reading'
           AND source_event.source_id = reading.id
           AND source_event.created_at >= requested_since
           AND source_event.created_at <= statement_timestamp()
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
           AND EXISTS (
               SELECT 1
                 FROM public.alert_rule AS rule
                WHERE rule.enabled = TRUE
                  AND rule.sensor_type_id = device.sensor_type_id
                  AND NOT EXISTS (
                      SELECT 1
                        FROM public.sensor_anomaly_effect AS effect
                       WHERE effect.source_reading_id = reading.id
                         AND effect.alert_rule_id = rule.id
                         AND effect.location_id = worker_scope.location_id
                  )
           )
         ORDER BY reading.id, source_event.created_at, source_event.id
    )
    SELECT candidate.event_id, candidate.sensor_id, candidate.event_created_at
      FROM candidates AS candidate
     ORDER BY candidate.event_created_at, candidate.event_id
     LIMIT requested_batch_size;
END;
$$;

ALTER FUNCTION kokonut_security.list_sensor_anomaly_events_since(UUID, TIMESTAMPTZ, INTEGER)
    OWNER TO kokonut_anomaly_read_owner;
REVOKE ALL ON FUNCTION kokonut_security.list_sensor_anomaly_events_since(UUID, TIMESTAMPTZ, INTEGER)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.list_sensor_anomaly_events_since(UUID, TIMESTAMPTZ, INTEGER)
    TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_sensor_anomaly_events_since(UUID, TIMESTAMPTZ, INTEGER)
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_sensor_anomaly_events_since(UUID, TIMESTAMPTZ, INTEGER)
            FROM kokonut_operator_auth;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_sensor_anomaly_events_since(UUID, TIMESTAMPTZ, INTEGER) IS
    'Lists at most 100 recent unreceipted sensor-reading events for the exact signed sensor_reading/process location; event effects are delegated to the idempotent event worker.';

COMMIT;
