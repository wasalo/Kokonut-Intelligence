-- Complete the bounded anomaly worker's durable delivery contract.
-- This migration exposes neither provider credentials nor actuator commands.

BEGIN;

GRANT SELECT (id, name)
    ON public.location TO kokonut_anomaly_event_owner;
GRANT SELECT (triggered_at, claim_id)
    ON public.sensor_alert TO kokonut_anomaly_event_owner;

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
               'alert_rule_id', rule.id,
               'sensor_device_id', device.id,
               'sensor_id', reading.sensor_id,
               'severity', alert.severity,
               'rule_name', rule.name,
               'reading_value', alert.reading_value,
               'threshold_value', alert.threshold_value,
               'message', alert.message,
               'triggered_at', alert.triggered_at,
               'claim_id', alert.claim_id,
               'sensor_name', COALESCE(device.name, 'Unknown'),
               'sensor_type', sensor_type.name,
               'location_id', alert.location_id,
               'location_name', COALESCE(location.name, 'Unknown')
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
      LEFT JOIN public.location AS location
        ON location.id = alert.location_id
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

-- This read returns one boolean only. The follow-up intent function revalidates
-- the same lineage and constructs the command payload inside its own boundary.
CREATE OR REPLACE FUNCTION kokonut_security.sensor_alert_actuation_enabled(
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
    is_enabled BOOLEAN;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'actuation configuration read requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'actuation configuration read is outside the signed worker scope'
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

    SELECT COALESCE(rule.actuator_enabled, FALSE)
           AND rule.actuator_type IS NOT NULL
           AND NULLIF(btrim(rule.actuator_command), '') IS NOT NULL
      INTO is_enabled
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
      JOIN public.sensor_alert AS alert
        ON alert.id = effect.sensor_alert_id
       AND alert.location_id = worker_scope.location_id
       AND alert.reading_id = reading.id
       AND alert.sensor_device_id = device.id
       AND alert.alert_rule_id = rule.id
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
        RAISE EXCEPTION 'actuation configuration source, alert, or rule does not match signed scope'
            USING ERRCODE = '42501';
    END IF;
    RETURN COALESCE(is_enabled, FALSE);
END;
$$;

ALTER FUNCTION kokonut_security.publish_sensor_alert_event(
    UUID, UUID, UUID, UUID, UUID, UUID
) OWNER TO kokonut_anomaly_event_owner;
REVOKE ALL ON FUNCTION kokonut_security.publish_sensor_alert_event(
    UUID, UUID, UUID, UUID, UUID, UUID
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.publish_sensor_alert_event(
    UUID, UUID, UUID, UUID, UUID, UUID
) TO kokonut_worker_execution;

ALTER FUNCTION kokonut_security.sensor_alert_actuation_enabled(
    UUID, UUID, UUID, UUID, UUID, UUID
) OWNER TO kokonut_anomaly_actuation_owner;
REVOKE ALL ON FUNCTION kokonut_security.sensor_alert_actuation_enabled(
    UUID, UUID, UUID, UUID, UUID, UUID
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.sensor_alert_actuation_enabled(
    UUID, UUID, UUID, UUID, UUID, UUID
) TO kokonut_worker_execution;

DO $$
DECLARE
    table_name TEXT;
    policy_name TEXT;
    worker_role TEXT;
BEGIN
    FOREACH worker_role IN ARRAY ARRAY[
        'kokonut_anomaly_event_owner', 'kokonut_anomaly_actuation_owner',
        'kokonut_anomaly_claim_owner', 'kokonut_anomaly_notification_owner',
        'kokonut_anomaly_effect_owner', 'kokonut_anomaly_read_owner'
    ] LOOP
        FOREACH table_name IN ARRAY ARRAY[
            'platform_event', 'sensor_anomaly_effect', 'sensor_alert',
            'sensor_reading', 'sensor_device', 'alert_rule', 'sensor_type',
            'location'
        ] LOOP
            policy_name := worker_role || '_' || table_name || '_select';
            IF EXISTS (
                SELECT 1 FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'public'
                  AND relation.relname = table_name
                  AND relation.relrowsecurity
            ) AND NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = table_name
                  AND policyname = policy_name
            ) THEN
                EXECUTE format(
                    'CREATE POLICY %I ON public.%I FOR SELECT TO %I USING (true)',
                    policy_name, table_name, worker_role
                );
            END IF;
        END LOOP;
    END LOOP;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'platform_event'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'platform_event'
          AND policyname = 'anomaly_event_owner_event_insert'
    ) THEN
        CREATE POLICY anomaly_event_owner_event_insert
            ON public.platform_event FOR INSERT TO kokonut_anomaly_event_owner
            WITH CHECK (
                event_type = 'sensor_alert'
                AND payload ->> 'location_id' = (
                    SELECT scope.location_id::TEXT
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                )
            );
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_anomaly_effect'
          AND relation.relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public' AND tablename = 'sensor_anomaly_effect'
              AND policyname = 'anomaly_effect_owner_insert'
        ) THEN
            CREATE POLICY anomaly_effect_owner_insert
                ON public.sensor_anomaly_effect FOR INSERT
                TO kokonut_anomaly_effect_owner
                WITH CHECK (location_id = (
                    SELECT scope.location_id FROM kokonut_security.current_worker_scope(
                        'sensor_reading', 'process'
                    ) AS scope
                ));
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public' AND tablename = 'sensor_anomaly_effect'
              AND policyname = 'anomaly_effect_owner_update'
        ) THEN
            CREATE POLICY anomaly_effect_owner_update
                ON public.sensor_anomaly_effect FOR UPDATE
                TO kokonut_anomaly_effect_owner
                USING (location_id = (
                    SELECT scope.location_id FROM kokonut_security.current_worker_scope(
                        'sensor_reading', 'process'
                    ) AS scope
                ))
                WITH CHECK (location_id = (
                    SELECT scope.location_id FROM kokonut_security.current_worker_scope(
                        'sensor_reading', 'process'
                    ) AS scope
                ));
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_alert'
          AND relation.relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies WHERE schemaname = 'public'
              AND tablename = 'sensor_alert'
              AND policyname = 'anomaly_claim_owner_update'
        ) THEN
            CREATE POLICY anomaly_claim_owner_update ON public.sensor_alert
                FOR UPDATE TO kokonut_anomaly_claim_owner
                USING (location_id = (SELECT scope.location_id
                    FROM kokonut_security.current_worker_scope(
                        'sensor_reading', 'process'
                    ) AS scope))
                WITH CHECK (location_id = (SELECT scope.location_id
                    FROM kokonut_security.current_worker_scope(
                        'sensor_reading', 'process'
                    ) AS scope));
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'notification_outbox'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public'
          AND tablename = 'notification_outbox'
          AND policyname = 'anomaly_notification_owner_select'
    ) THEN
        CREATE POLICY anomaly_notification_owner_select
            ON public.notification_outbox FOR SELECT
            TO kokonut_anomaly_notification_owner USING (
                location_id = (SELECT scope.location_id
                    FROM kokonut_security.current_worker_scope(
                        'sensor_reading', 'process'
                    ) AS scope)
            );
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'mrv_claim'
          AND relation.relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies WHERE schemaname = 'public'
              AND tablename = 'mrv_claim' AND policyname = 'anomaly_claim_owner_select'
        ) THEN
            CREATE POLICY anomaly_claim_owner_select ON public.mrv_claim
                FOR SELECT TO kokonut_anomaly_claim_owner USING (
                    location_id = (SELECT scope.location_id
                        FROM kokonut_security.current_worker_scope(
                            'sensor_reading', 'process'
                        ) AS scope)
                );
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies WHERE schemaname = 'public'
              AND tablename = 'mrv_claim' AND policyname = 'anomaly_claim_owner_insert'
        ) THEN
            CREATE POLICY anomaly_claim_owner_insert ON public.mrv_claim
                FOR INSERT TO kokonut_anomaly_claim_owner WITH CHECK (
                    location_id = (SELECT scope.location_id
                        FROM kokonut_security.current_worker_scope(
                            'sensor_reading', 'process'
                        ) AS scope)
                );
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies WHERE schemaname = 'public'
              AND tablename = 'mrv_claim' AND policyname = 'anomaly_claim_owner_update'
        ) THEN
            CREATE POLICY anomaly_claim_owner_update ON public.mrv_claim
                FOR UPDATE TO kokonut_anomaly_claim_owner
                USING (location_id = (SELECT scope.location_id
                    FROM kokonut_security.current_worker_scope(
                        'sensor_reading', 'process'
                    ) AS scope))
                WITH CHECK (location_id = (SELECT scope.location_id
                    FROM kokonut_security.current_worker_scope(
                        'sensor_reading', 'process'
                    ) AS scope));
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'notification_outbox'
          AND relation.relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies WHERE schemaname = 'public'
              AND tablename = 'notification_outbox'
              AND policyname = 'anomaly_notification_owner_insert'
        ) THEN
            CREATE POLICY anomaly_notification_owner_insert
                ON public.notification_outbox FOR INSERT
                TO kokonut_anomaly_notification_owner WITH CHECK (
                    location_id = (SELECT scope.location_id
                        FROM kokonut_security.current_worker_scope(
                            'sensor_reading', 'process'
                        ) AS scope)
                );
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'actuation_log'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public'
          AND tablename = 'actuation_log'
          AND policyname = 'anomaly_actuation_owner_select'
    ) THEN
        CREATE POLICY anomaly_actuation_owner_select ON public.actuation_log
            FOR SELECT TO kokonut_anomaly_actuation_owner USING (
                location_id = (SELECT scope.location_id
                    FROM kokonut_security.current_worker_scope(
                        'sensor_reading', 'process'
                    ) AS scope)
            );
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'actuation_log'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public'
          AND tablename = 'actuation_log'
          AND policyname = 'anomaly_actuation_owner_insert'
    ) THEN
        CREATE POLICY anomaly_actuation_owner_insert ON public.actuation_log
            FOR INSERT TO kokonut_anomaly_actuation_owner WITH CHECK (
                location_id = (SELECT scope.location_id
                    FROM kokonut_security.current_worker_scope(
                        'sensor_reading', 'process'
                    ) AS scope)
            );
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.sensor_alert_actuation_enabled(
            UUID, UUID, UUID, UUID, UUID, UUID
        ) FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.publish_sensor_alert_event(
            UUID, UUID, UUID, UUID, UUID, UUID
        ) FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.sensor_alert_actuation_enabled(
            UUID, UUID, UUID, UUID, UUID, UUID
        ) FROM kokonut_operator_auth;
        REVOKE ALL ON FUNCTION kokonut_security.publish_sensor_alert_event(
            UUID, UUID, UUID, UUID, UUID, UUID
        ) FROM kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_anomaly_event_owner, kokonut_anomaly_actuation_owner;

COMMENT ON FUNCTION kokonut_security.publish_sensor_alert_event(
    UUID, UUID, UUID, UUID, UUID, UUID
) IS
    'Publishes one canonical sensor_alert event enriched with the same context used by idempotent notification intents; validates a matching alert_created receipt and signed location.';
COMMENT ON FUNCTION kokonut_security.sensor_alert_actuation_enabled(
    UUID, UUID, UUID, UUID, UUID, UUID
) IS
    'Returns only whether a linked sensor alert has a complete, enabled actuator configuration under signed worker scope; does not reveal or execute the command.';

COMMIT;
