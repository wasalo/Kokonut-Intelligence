-- Add an exact-device event inventory for the legacy `--sensor` replay option.
-- The source list is still bounded by signed location scope and the same
-- idempotent sensor-anomaly receipts used by the general inventory.
BEGIN;

-- 649 introduced the event-created timestamp and receipt-source grants for
-- this owner. Repeat the exact read grants here so this function's required
-- projection remains visible beside its definition and is replay-safe.
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_anomaly_read_owner;
GRANT SELECT (created_at) ON public.platform_event
    TO kokonut_anomaly_read_owner;
GRANT SELECT (source_reading_id, alert_rule_id, location_id)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_read_owner;

-- Some installations enable or force RLS on these source tables after
-- migration 412. The anomaly inventory needs only the columns already granted
-- to its membership-free reader role; signed location and sensor predicates
-- remain enforced by the SECURITY DEFINER function below.
DO $$
DECLARE
    target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'platform_event', 'sensor_reading', 'sensor_device', 'sensor_type',
        'alert_rule'
    ] LOOP
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class AS relation
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = relation.relnamespace
             WHERE namespace.nspname = 'public'
               AND relation.relname = target_table
               AND relation.relrowsecurity
        ) AND NOT EXISTS (
            SELECT 1
              FROM pg_catalog.pg_policies
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

CREATE OR REPLACE FUNCTION kokonut_security.list_sensor_anomaly_events_for_sensor_since(
    requested_location_id UUID,
    requested_sensor_id UUID,
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
      FROM kokonut_security.current_worker_scope(
          'sensor_reading', 'process'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'sensor-specific anomaly inventory requires signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM worker_scope.location_id
       OR requested_sensor_id IS NULL THEN
        RAISE EXCEPTION 'sensor-specific anomaly inventory is outside signed scope'
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
           AND reading.sensor_id = requested_sensor_id
          JOIN public.sensor_device AS device
            ON device.id = reading.sensor_id
           AND device.id = requested_sensor_id
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

ALTER FUNCTION kokonut_security.list_sensor_anomaly_events_for_sensor_since(
    UUID, UUID, TIMESTAMPTZ, INTEGER
) OWNER TO kokonut_anomaly_read_owner;
REVOKE ALL ON FUNCTION kokonut_security.list_sensor_anomaly_events_for_sensor_since(
    UUID, UUID, TIMESTAMPTZ, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.list_sensor_anomaly_events_for_sensor_since(
    UUID, UUID, TIMESTAMPTZ, INTEGER
) TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_sensor_anomaly_events_for_sensor_since(
            UUID, UUID, TIMESTAMPTZ, INTEGER
        ) FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_sensor_anomaly_events_for_sensor_since(
            UUID, UUID, TIMESTAMPTZ, INTEGER
        ) FROM kokonut_operator_auth;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_sensor_anomaly_events_for_sensor_since(
    UUID, UUID, TIMESTAMPTZ, INTEGER
) IS
    'Lists at most 100 unreceipted sensor-reading events for the exact sensor device and signed sensor_reading/process location.';

COMMIT;
