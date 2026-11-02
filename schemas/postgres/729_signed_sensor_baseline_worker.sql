-- Move environmental-baseline alerts behind exact-location signed worker
-- functions. Alert, event, and notification intent writes share the worker's
-- transaction; a retry for the same baseline/latest reading reuses its receipt.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_sensor_baseline_owner'
    ) THEN
        CREATE ROLE kokonut_sensor_baseline_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_sensor_baseline_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_sensor_baseline_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_sensor_baseline_owner'
            OR member_role.rolname = 'kokonut_sensor_baseline_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_sensor_baseline_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_sensor_baseline_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_sensor_baseline_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_sensor_baseline_owner;

GRANT SELECT (id, location_id, metric_name, baseline_value, unit, created_at)
    ON public.environmental_baseline TO kokonut_sensor_baseline_owner;
GRANT SELECT (id, location_id, sensor_id, sensor_type, value, created_at)
    ON public.sensor_reading TO kokonut_sensor_baseline_owner;
GRANT SELECT (id, name, location_id, sensor_type_id)
    ON public.sensor_device TO kokonut_sensor_baseline_owner;
GRANT SELECT (id, name) ON public.sensor_type
    TO kokonut_sensor_baseline_owner;
GRANT SELECT (id, name, sensor_type_id, metric, enabled, created_at)
    ON public.alert_rule TO kokonut_sensor_baseline_owner;
GRANT SELECT (id, name) ON public.location
    TO kokonut_sensor_baseline_owner;
GRANT SELECT (id, location_id, reading_id, sensor_device_id, alert_rule_id,
              severity, message, reading_value, threshold_value, triggered_at,
              claim_id)
    ON public.sensor_alert TO kokonut_sensor_baseline_owner;
GRANT INSERT (id, location_id, sensor_device_id, alert_rule_id, reading_id,
              severity, status, message, reading_value, threshold_value,
              triggered_at, metadata)
    ON public.sensor_alert TO kokonut_sensor_baseline_owner;
GRANT SELECT (id, event_type, source_table, source_id, payload, priority)
    ON public.platform_event TO kokonut_sensor_baseline_owner;
GRANT INSERT (id, event_type, source_table, source_id, payload, priority,
              status, max_retries)
    ON public.platform_event TO kokonut_sensor_baseline_owner;
GRANT SELECT (source_event_id, event_type, channel, destination_key, payload,
              location_id)
    ON public.notification_outbox TO kokonut_sensor_baseline_owner;
GRANT INSERT (source_event_id, event_type, channel, destination_key, payload,
              location_id)
    ON public.notification_outbox TO kokonut_sensor_baseline_owner;

CREATE TABLE IF NOT EXISTS kokonut_security.sensor_baseline_alert_effect (
    baseline_id UUID NOT NULL,
    location_id UUID NOT NULL,
    reading_id UUID NOT NULL,
    sensor_alert_id UUID NOT NULL,
    alert_event_id UUID NOT NULL,
    alert_rule_id UUID NOT NULL,
    sensor_device_id UUID NOT NULL,
    severity TEXT NOT NULL CHECK (severity = 'warning'),
    message TEXT NOT NULL,
    reading_value NUMERIC NOT NULL,
    threshold_value NUMERIC NOT NULL,
    sample_count INTEGER NOT NULL CHECK (sample_count BETWEEN 1 AND 10),
    triggered_at TIMESTAMPTZ NOT NULL,
    sensor_name TEXT,
    sensor_type TEXT NOT NULL,
    location_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (baseline_id, reading_id)
);

ALTER TABLE kokonut_security.sensor_baseline_alert_effect
    OWNER TO kokonut_sensor_baseline_owner;
ALTER TABLE kokonut_security.sensor_baseline_alert_effect
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.sensor_baseline_alert_effect
    FORCE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'kokonut_security'
           AND tablename = 'sensor_baseline_alert_effect'
           AND policyname = 'sensor_baseline_effect_owner_scope'
    ) THEN
        CREATE POLICY sensor_baseline_effect_owner_scope
            ON kokonut_security.sensor_baseline_alert_effect
            FOR ALL TO kokonut_sensor_baseline_owner
            USING (
                location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                )
            )
            WITH CHECK (
                location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                )
            );
    END IF;
END;
$$;
GRANT SELECT, INSERT ON kokonut_security.sensor_baseline_alert_effect
    TO kokonut_sensor_baseline_owner;
REVOKE ALL ON kokonut_security.sensor_baseline_alert_effect
    FROM PUBLIC, kokonut_worker_execution;

-- Respect installations that already protect one or more source/effect tables
-- with RLS. These policies are only for the isolated, membership-free owner;
-- all tenant filters remain independently enforced inside the functions.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'environmental_baseline'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public'
           AND tablename = 'environmental_baseline'
           AND policyname = 'sensor_baseline_owner_select'
    ) THEN
        CREATE POLICY sensor_baseline_owner_select
            ON public.environmental_baseline FOR SELECT
            TO kokonut_sensor_baseline_owner
            USING (location_id = (
                SELECT scope.location_id
                  FROM kokonut_security.current_worker_scope(
                      'sensor_reading', 'process'
                  ) AS scope
            ));
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_reading'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'sensor_reading'
           AND policyname = 'sensor_baseline_owner_select'
    ) THEN
        CREATE POLICY sensor_baseline_owner_select
            ON public.sensor_reading FOR SELECT
            TO kokonut_sensor_baseline_owner
            USING (location_id = (
                SELECT scope.location_id
                  FROM kokonut_security.current_worker_scope(
                      'sensor_reading', 'process'
                  ) AS scope
            ));
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_device'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'sensor_device'
           AND policyname = 'sensor_baseline_owner_select'
    ) THEN
        CREATE POLICY sensor_baseline_owner_select
            ON public.sensor_device FOR SELECT
            TO kokonut_sensor_baseline_owner
            USING (location_id = (
                SELECT scope.location_id
                  FROM kokonut_security.current_worker_scope(
                      'sensor_reading', 'process'
                  ) AS scope
            ));
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_type'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'sensor_type'
           AND policyname = 'sensor_baseline_owner_select'
    ) THEN
        CREATE POLICY sensor_baseline_owner_select
            ON public.sensor_type FOR SELECT
            TO kokonut_sensor_baseline_owner
            USING (EXISTS (
                SELECT 1 FROM public.sensor_device AS device
                 WHERE device.sensor_type_id = sensor_type.id
                   AND device.location_id = (
                       SELECT scope.location_id
                         FROM kokonut_security.current_worker_scope(
                             'sensor_reading', 'process'
                         ) AS scope
                   )
            ));
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'alert_rule'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'alert_rule'
           AND policyname = 'sensor_baseline_owner_select'
    ) THEN
        CREATE POLICY sensor_baseline_owner_select
            ON public.alert_rule FOR SELECT
            TO kokonut_sensor_baseline_owner
            USING (EXISTS (
                SELECT 1
                  FROM public.sensor_device AS device
                 WHERE device.sensor_type_id = alert_rule.sensor_type_id
                   AND device.location_id = (
                       SELECT scope.location_id
                         FROM kokonut_security.current_worker_scope(
                             'sensor_reading', 'process'
                         ) AS scope
                   )
            ));
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'location'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'location'
           AND policyname = 'sensor_baseline_owner_select'
    ) THEN
        CREATE POLICY sensor_baseline_owner_select
            ON public.location FOR SELECT
            TO kokonut_sensor_baseline_owner
            USING (id = (
                SELECT scope.location_id
                  FROM kokonut_security.current_worker_scope(
                      'sensor_reading', 'process'
                  ) AS scope
            ));
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'sensor_alert'
          AND relation.relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname = 'public' AND tablename = 'sensor_alert'
               AND policyname = 'sensor_baseline_owner_select'
        ) THEN
            CREATE POLICY sensor_baseline_owner_select
                ON public.sensor_alert FOR SELECT
                TO kokonut_sensor_baseline_owner
                USING (location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                ));
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname = 'public' AND tablename = 'sensor_alert'
               AND policyname = 'sensor_baseline_owner_insert'
        ) THEN
            CREATE POLICY sensor_baseline_owner_insert
                ON public.sensor_alert FOR INSERT
                TO kokonut_sensor_baseline_owner
                WITH CHECK (location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                ));
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'platform_event'
          AND relation.relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname = 'public' AND tablename = 'platform_event'
               AND policyname = 'sensor_baseline_owner_select'
        ) THEN
            CREATE POLICY sensor_baseline_owner_select
                ON public.platform_event FOR SELECT
                TO kokonut_sensor_baseline_owner
                USING (payload ->> 'location_id' = (
                    SELECT scope.location_id::TEXT
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                ));
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname = 'public' AND tablename = 'platform_event'
               AND policyname = 'sensor_baseline_owner_insert'
        ) THEN
            CREATE POLICY sensor_baseline_owner_insert
                ON public.platform_event FOR INSERT
                TO kokonut_sensor_baseline_owner
                WITH CHECK (payload ->> 'location_id' = (
                    SELECT scope.location_id::TEXT
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                ));
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'notification_outbox'
          AND relation.relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname = 'public' AND tablename = 'notification_outbox'
               AND policyname = 'sensor_baseline_owner_select'
        ) THEN
            CREATE POLICY sensor_baseline_owner_select
                ON public.notification_outbox FOR SELECT
                TO kokonut_sensor_baseline_owner
                USING (location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                ));
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname = 'public' AND tablename = 'notification_outbox'
               AND policyname = 'sensor_baseline_owner_insert'
        ) THEN
            CREATE POLICY sensor_baseline_owner_insert
                ON public.notification_outbox FOR INSERT
                TO kokonut_sensor_baseline_owner
                WITH CHECK (location_id = (
                    SELECT scope.location_id
                      FROM kokonut_security.current_worker_scope(
                          'sensor_reading', 'process'
                      ) AS scope
                ));
        END IF;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.evaluate_sensor_baselines(
    requested_location_id UUID
)
RETURNS TABLE (
    baseline_id UUID,
    outcome TEXT,
    sensor_alert_id UUID,
    alert_event_id UUID,
    reading_id UUID,
    alert_rule_id UUID,
    sensor_device_id UUID,
    severity TEXT,
    message TEXT,
    reading_value NUMERIC,
    threshold_value NUMERIC,
    sample_count INTEGER,
    triggered_at TIMESTAMPTZ,
    sensor_name TEXT,
    sensor_type TEXT,
    location_name TEXT,
    location_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    signed_location_id UUID;
    baseline RECORD;
    sample RECORD;
    selected_device RECORD;
    selected_rule RECORD;
    prior_effect RECORD;
    deviation NUMERIC;
    direction TEXT;
    unit_text TEXT;
    formatted_value TEXT;
    formatted_baseline TEXT;
    formatted_deviation TEXT;
    event_payload JSONB;
    now_utc TIMESTAMPTZ;
BEGIN
    SELECT scope.location_id
      INTO signed_location_id
      FROM kokonut_security.current_worker_scope(
          'sensor_reading', 'process'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'baseline check requires a signed sensor-reading worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM signed_location_id THEN
        RAISE EXCEPTION 'baseline check is outside the signed worker location'
            USING ERRCODE = '42501';
    END IF;

    now_utc := clock_timestamp();
    FOR baseline IN
        SELECT source.id, source.location_id, source.metric_name,
               source.baseline_value, source.unit
          FROM public.environmental_baseline AS source
         WHERE source.location_id = signed_location_id
           AND source.metric_name = ANY (ARRAY[
               'soil_moisture', 'air_temperature', 'humidity',
               'soil_temperature', 'rainfall'
           ]::TEXT[])
         ORDER BY source.created_at, source.id
    LOOP
        baseline_id := baseline.id;
        location_id := signed_location_id;
        outcome := NULL;
        sensor_alert_id := NULL;
        alert_event_id := NULL;
        reading_id := NULL;
        alert_rule_id := NULL;
        sensor_device_id := NULL;
        severity := NULL;
        message := NULL;
        reading_value := NULL;
        threshold_value := NULL;
        sample_count := 0;
        triggered_at := NULL;
        sensor_name := NULL;
        sensor_type := baseline.metric_name;
        location_name := NULL;

        SELECT COUNT(*)::INTEGER AS sample_count,
               AVG(reading.value) AS average_value,
               (ARRAY_AGG(reading.id ORDER BY reading.created_at DESC, reading.id DESC))[1]
                   AS latest_reading_id,
               (ARRAY_AGG(reading.sensor_id ORDER BY reading.created_at DESC, reading.id DESC))[1]
                   AS latest_sensor_id
          INTO sample
          FROM (
              SELECT source.id, source.sensor_id, source.value, source.created_at
                FROM public.sensor_reading AS source
                JOIN public.sensor_device AS source_device
                  ON source_device.id = source.sensor_id
                 AND source_device.location_id = source.location_id
                JOIN public.sensor_type AS source_type
                  ON source_type.id = source_device.sensor_type_id
                 AND source_type.name = source.sensor_type
               WHERE source_type.name = baseline.metric_name
                 AND source.location_id = signed_location_id
                 AND source.created_at >= now_utc - INTERVAL '24 hours'
               ORDER BY source.created_at DESC, source.id DESC
               LIMIT 10
          ) AS reading;

        sample_count := COALESCE(sample.sample_count, 0);
        reading_id := sample.latest_reading_id;

        IF sample.latest_reading_id IS NOT NULL THEN
            PERFORM pg_catalog.pg_advisory_xact_lock(
                pg_catalog.hashtextextended(
                    baseline.id::TEXT || ':' || sample.latest_reading_id::TEXT,
                    0
                )
            );
        END IF;

        -- A committed effect is the exact retry receipt. Return its original
        -- result before reevaluating mutable baseline/rule/device state.
        IF sample.latest_reading_id IS NOT NULL THEN
            SELECT effect.*
              INTO prior_effect
              FROM kokonut_security.sensor_baseline_alert_effect AS effect
             WHERE effect.baseline_id = baseline.id
               AND effect.reading_id = sample.latest_reading_id;
            IF FOUND THEN
                outcome := 'alert_replayed';
                sensor_alert_id := prior_effect.sensor_alert_id;
                alert_event_id := prior_effect.alert_event_id;
                reading_id := prior_effect.reading_id;
                alert_rule_id := prior_effect.alert_rule_id;
                sensor_device_id := prior_effect.sensor_device_id;
                severity := prior_effect.severity;
                message := prior_effect.message;
                reading_value := prior_effect.reading_value;
                threshold_value := prior_effect.threshold_value;
                sample_count := prior_effect.sample_count;
                triggered_at := prior_effect.triggered_at;
                sensor_name := prior_effect.sensor_name;
                sensor_type := prior_effect.sensor_type;
                location_name := prior_effect.location_name;
                RETURN NEXT;
                CONTINUE;
            END IF;
        ELSE
            -- Preserve a committed result for a delayed retry even after its
            -- source reading falls outside the rolling 24-hour evaluation
            -- window. A newer in-window reading takes precedence above.
            SELECT effect.*
              INTO prior_effect
              FROM kokonut_security.sensor_baseline_alert_effect AS effect
             WHERE effect.baseline_id = baseline.id
             ORDER BY effect.triggered_at DESC,
                      effect.created_at DESC,
                      effect.reading_id DESC
             LIMIT 1;
            IF FOUND THEN
                outcome := 'alert_replayed';
                sensor_alert_id := prior_effect.sensor_alert_id;
                alert_event_id := prior_effect.alert_event_id;
                reading_id := prior_effect.reading_id;
                alert_rule_id := prior_effect.alert_rule_id;
                sensor_device_id := prior_effect.sensor_device_id;
                severity := prior_effect.severity;
                message := prior_effect.message;
                reading_value := prior_effect.reading_value;
                threshold_value := prior_effect.threshold_value;
                sample_count := prior_effect.sample_count;
                triggered_at := prior_effect.triggered_at;
                sensor_name := prior_effect.sensor_name;
                sensor_type := prior_effect.sensor_type;
                location_name := prior_effect.location_name;
                RETURN NEXT;
                CONTINUE;
            END IF;
        END IF;

        IF baseline.baseline_value IS NULL THEN
            outcome := 'baseline_unavailable';
        ELSIF baseline.baseline_value = 0 THEN
            outcome := 'baseline_zero';
        ELSIF sample.sample_count = 0 OR sample.average_value IS NULL THEN
            outcome := 'no_readings';
        ELSE
            deviation := ABS(sample.average_value - baseline.baseline_value)
                         / ABS(baseline.baseline_value);
            IF deviation <= 0.30 THEN
                outcome := 'below_threshold';
            ELSE
                SELECT device.id, device.name, device.sensor_type_id
                  INTO selected_device
                  FROM public.sensor_device AS device
                 WHERE device.id = sample.latest_sensor_id
                   AND device.location_id = signed_location_id;
                IF NOT FOUND THEN
                    outcome := 'missing_device';
                ELSE
                    SELECT candidate.id, candidate.name
                      INTO selected_rule
                      FROM public.sensor_type AS kind
                      JOIN public.alert_rule AS candidate
                        ON candidate.sensor_type_id = kind.id
                     WHERE kind.name = baseline.metric_name
                       AND candidate.metric = 'value'
                       AND candidate.enabled = TRUE
                     ORDER BY candidate.created_at, candidate.id
                     LIMIT 1;
                    IF NOT FOUND THEN
                        outcome := 'missing_rule';
                    ELSE
                        -- Different baseline rows can resolve to the same
                        -- device/rule. Serialize their cooldown check so two
                        -- concurrent runs cannot both create an alert.
                        PERFORM pg_catalog.pg_advisory_xact_lock(
                            pg_catalog.hashtextextended(
                                'sensor-baseline-cooldown:'
                                || signed_location_id::TEXT || ':'
                                || selected_device.id::TEXT || ':' || selected_rule.id::TEXT,
                                0
                            )
                        );
                        IF EXISTS (
                            SELECT 1
                              FROM public.sensor_alert AS recent
                             WHERE recent.alert_rule_id = selected_rule.id
                               AND recent.sensor_device_id = selected_device.id
                               AND recent.location_id = signed_location_id
                               AND recent.triggered_at >
                                   now_utc - INTERVAL '120 minutes'
                             ORDER BY recent.triggered_at DESC, recent.id DESC
                             LIMIT 1
                        ) THEN
                            outcome := 'cooldown';
                        ELSE
                            location_name := (
                                SELECT farm.name
                                  FROM public.location AS farm
                                 WHERE farm.id = signed_location_id
                            );
                            unit_text := COALESCE(baseline.unit, 'None');
                            direction := CASE
                                WHEN sample.average_value > baseline.baseline_value
                                    THEN 'above'
                                ELSE 'below'
                            END;
                            formatted_value := TO_CHAR(
                                sample.average_value,
                                'FM999999999990.00'
                            );
                            formatted_baseline := TO_CHAR(
                                baseline.baseline_value,
                                'FM999999999990.00'
                            );
                            formatted_deviation := TO_CHAR(
                                ROUND(deviation * 100),
                                'FM999999999990'
                            );
                            message := 'Baseline deviation: '
                                || baseline.metric_name || ' '
                                || formatted_value || unit_text || ' is '
                                || direction || ' baseline '
                                || formatted_baseline || unit_text || ' ('
                                || formatted_deviation || '% deviation)';
                            severity := 'warning';
                            reading_value := sample.average_value;
                            threshold_value := baseline.baseline_value;
                            sensor_device_id := selected_device.id;
                            alert_rule_id := selected_rule.id;
                            sensor_name := selected_device.name;
                            triggered_at := now_utc;
                            sensor_alert_id := gen_random_uuid();
                            alert_event_id := gen_random_uuid();

                            INSERT INTO public.sensor_alert (
                                id, location_id, sensor_device_id, alert_rule_id,
                                reading_id, severity, status, message,
                                reading_value, threshold_value, triggered_at,
                                metadata
                            ) VALUES (
                                sensor_alert_id, signed_location_id, selected_device.id,
                                selected_rule.id, sample.latest_reading_id, severity,
                                'open', message, sample.average_value,
                                baseline.baseline_value, now_utc,
                                jsonb_build_object(
                                    'source', 'environmental_baseline',
                                    'baseline_id', baseline.id,
                                    'sample_count', sample.sample_count
                                )
                            );

                            event_payload := jsonb_build_object(
                                'alert_id', sensor_alert_id,
                                'sensor_device_id', selected_device.id,
                                'sensor_id', sample.latest_sensor_id,
                                'severity', severity,
                                'rule_name', 'baseline_deviation',
                                'reading_value', sample.average_value,
                                'threshold_value', baseline.baseline_value,
                                'message', message,
                                'location_id', signed_location_id
                            );
                            INSERT INTO public.platform_event (
                                id, event_type, source_table, source_id,
                                payload, priority, status, max_retries
                            ) VALUES (
                                alert_event_id, 'sensor_alert', 'sensor_alert',
                                sensor_alert_id, event_payload, 'normal',
                                'pending', 3
                            );

                            INSERT INTO kokonut_security.sensor_baseline_alert_effect (
                                baseline_id, location_id, reading_id,
                                sensor_alert_id, alert_event_id, alert_rule_id,
                                sensor_device_id, severity, message, reading_value,
                                threshold_value, sample_count, triggered_at,
                                sensor_name, sensor_type, location_name
                            ) VALUES (
                                baseline.id, signed_location_id,
                                sample.latest_reading_id, sensor_alert_id,
                                alert_event_id, selected_rule.id, selected_device.id, severity,
                                message, sample.average_value,
                                baseline.baseline_value, sample.sample_count,
                                now_utc, selected_device.name, baseline.metric_name,
                                location_name
                            );
                            outcome := 'alert_created';
                        END IF;
                    END IF;
                END IF;
            END IF;
        END IF;
        RETURN NEXT;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.enqueue_sensor_baseline_notification_intent(
    requested_alert_event_id UUID,
    requested_baseline_id UUID,
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
    signed_location_id UUID;
    linked_effect RECORD;
    alert_event RECORD;
    expected_payload JSONB;
    allowed_keys TEXT[];
    required_keys TEXT[];
    was_inserted BOOLEAN := FALSE;
    existing_intent RECORD;
BEGIN
    SELECT scope.location_id
      INTO signed_location_id
      FROM kokonut_security.current_worker_scope(
          'sensor_reading', 'process'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'baseline notification requires signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM signed_location_id THEN
        RAISE EXCEPTION 'baseline notification is outside signed location scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_alert_event_id IS NULL
       OR requested_baseline_id IS NULL
       OR requested_sensor_alert_id IS NULL THEN
        RAISE EXCEPTION 'baseline notification identifiers are required'
            USING ERRCODE = '22023';
    END IF;
    IF requested_channel IS NULL
       OR requested_channel NOT IN ('webhook', 'directus', 'email')
       OR requested_destination_key IS DISTINCT FROM 'primary' THEN
        RAISE EXCEPTION 'notification destination is not allowed'
            USING ERRCODE = '22023';
    END IF;
    IF requested_payload IS NULL
       OR jsonb_typeof(requested_payload) IS DISTINCT FROM 'object'
       OR octet_length(requested_payload::TEXT) > 16384 THEN
        RAISE EXCEPTION 'notification payload must be an object no larger than 16 KiB'
            USING ERRCODE = '22023';
    END IF;

    SELECT effect.*
      INTO linked_effect
      FROM kokonut_security.sensor_baseline_alert_effect AS effect
     WHERE effect.baseline_id = requested_baseline_id
       AND effect.sensor_alert_id = requested_sensor_alert_id
       AND effect.alert_event_id = requested_alert_event_id
       AND effect.location_id = signed_location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'baseline notification source does not match signed scope'
            USING ERRCODE = '42501';
    END IF;

    SELECT event.event_type, event.source_table, event.source_id,
           event.payload, event.priority
      INTO alert_event
      FROM public.platform_event AS event
     WHERE event.id = requested_alert_event_id;
    IF NOT FOUND
       OR alert_event.event_type IS DISTINCT FROM 'sensor_alert'
       OR alert_event.source_table IS DISTINCT FROM 'sensor_alert'
       OR alert_event.source_id IS DISTINCT FROM requested_sensor_alert_id
       OR alert_event.payload ->> 'alert_id'
            IS DISTINCT FROM requested_sensor_alert_id::TEXT
       OR alert_event.payload ->> 'location_id'
            IS DISTINCT FROM signed_location_id::TEXT THEN
        RAISE EXCEPTION 'baseline alert event does not match its receipt'
            USING ERRCODE = '42501';
    END IF;

    IF requested_channel = 'webhook' THEN
        allowed_keys := ARRAY[
            'text', 'alert_id', 'severity', 'message', 'sensor_device_id',
            'sensor_name', 'sensor_type', 'location_id', 'location_name',
            'reading_value', 'threshold_value', 'triggered_at', 'claim_id'
        ];
        required_keys := allowed_keys;
        expected_payload := jsonb_build_object(
            'text', '[WARNING] ' || linked_effect.message,
            'alert_id', requested_sensor_alert_id,
            'severity', 'warning',
            'message', linked_effect.message,
            'sensor_device_id', linked_effect.sensor_device_id,
            'sensor_name', linked_effect.sensor_name,
            'sensor_type', linked_effect.sensor_type,
            'location_id', signed_location_id,
            'location_name', linked_effect.location_name,
            'reading_value', linked_effect.reading_value,
            'threshold_value', linked_effect.threshold_value,
            'triggered_at', requested_payload -> 'triggered_at',
            'claim_id', NULL
        );
    ELSIF requested_channel = 'directus' THEN
        allowed_keys := ARRAY['subject', 'message', 'type', 'recipient', 'status'];
        required_keys := allowed_keys;
        expected_payload := jsonb_build_object(
            'subject', 'Sensor Alert: ' || COALESCE(linked_effect.sensor_name, 'Unknown'),
            'message', linked_effect.message,
            'type', 'warning',
            'recipient', 'role:00000000-0000-0000-0000-000000000006',
            'status', 'unread'
        );
    ELSE
        allowed_keys := ARRAY['subject', 'body'];
        required_keys := allowed_keys;
        expected_payload := NULL;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM jsonb_object_keys(requested_payload) AS payload_key(key)
         WHERE payload_key.key <> ALL (allowed_keys)
    ) OR NOT (requested_payload ?& required_keys) THEN
        RAISE EXCEPTION 'notification payload contains unsupported or missing fields'
            USING ERRCODE = '22023';
    END IF;

    IF requested_channel = 'webhook' THEN
        IF requested_payload ->> 'text' IS DISTINCT FROM
               '[WARNING] ' || linked_effect.message
           OR requested_payload ->> 'alert_id' IS DISTINCT FROM
               requested_sensor_alert_id::TEXT
           OR requested_payload ->> 'severity' IS DISTINCT FROM 'warning'
           OR requested_payload ->> 'message' IS DISTINCT FROM linked_effect.message
           OR requested_payload ->> 'sensor_device_id' IS DISTINCT FROM
               linked_effect.sensor_device_id::TEXT
           OR requested_payload ->> 'sensor_name' IS DISTINCT FROM
               linked_effect.sensor_name
           OR requested_payload ->> 'sensor_type' IS DISTINCT FROM
               linked_effect.sensor_type
           OR requested_payload ->> 'location_id' IS DISTINCT FROM
               signed_location_id::TEXT
           OR requested_payload ->> 'location_name' IS DISTINCT FROM
               linked_effect.location_name
           OR (requested_payload ->> 'reading_value')::NUMERIC
                IS DISTINCT FROM linked_effect.reading_value
           OR (requested_payload ->> 'threshold_value')::NUMERIC
                IS DISTINCT FROM linked_effect.threshold_value
           OR (requested_payload ->> 'triggered_at')::TIMESTAMPTZ
                IS DISTINCT FROM linked_effect.triggered_at
           OR requested_payload -> 'claim_id' IS DISTINCT FROM 'null'::JSONB THEN
            RAISE EXCEPTION 'webhook notification does not match the baseline alert'
                USING ERRCODE = '42501';
        END IF;
    ELSIF requested_channel = 'directus' THEN
        IF requested_payload IS DISTINCT FROM expected_payload THEN
            RAISE EXCEPTION 'Directus notification does not match the baseline alert'
                USING ERRCODE = '42501';
        END IF;
    ELSE
        IF requested_payload ->> 'subject' IS DISTINCT FROM
               '[WARNING] Sensor Alert: '
                   || COALESCE(linked_effect.sensor_name, 'Unknown')
           OR requested_payload ->> 'body' IS NULL
           OR position(linked_effect.message IN requested_payload ->> 'body') = 0
           OR position(('Alert ID: ' || requested_sensor_alert_id::TEXT)
                       IN requested_payload ->> 'body') = 0 THEN
            RAISE EXCEPTION 'email notification does not match the baseline alert'
                USING ERRCODE = '42501';
        END IF;
    END IF;

    INSERT INTO public.notification_outbox (
        source_event_id, event_type, channel, destination_key, payload,
        location_id
    ) VALUES (
        requested_alert_event_id, 'sensor_alert', requested_channel,
        requested_destination_key, requested_payload, signed_location_id
    )
    ON CONFLICT (source_event_id, channel, destination_key) DO NOTHING
    RETURNING TRUE INTO was_inserted;

    IF COALESCE(was_inserted, FALSE) THEN
        RETURN TRUE;
    END IF;

    SELECT outbox.event_type, outbox.payload, outbox.location_id
      INTO existing_intent
      FROM public.notification_outbox AS outbox
     WHERE outbox.source_event_id = requested_alert_event_id
       AND outbox.channel = requested_channel
       AND outbox.destination_key = requested_destination_key;
    IF NOT FOUND
       OR existing_intent.event_type IS DISTINCT FROM 'sensor_alert'
       OR existing_intent.payload IS DISTINCT FROM requested_payload
       OR existing_intent.location_id IS DISTINCT FROM signed_location_id THEN
        RAISE EXCEPTION 'notification identity conflicts with existing content'
            USING ERRCODE = '23505';
    END IF;
    RETURN FALSE;
END;
$$;

ALTER FUNCTION kokonut_security.evaluate_sensor_baselines(UUID)
    OWNER TO kokonut_sensor_baseline_owner;
ALTER FUNCTION kokonut_security.enqueue_sensor_baseline_notification_intent(
    UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
) OWNER TO kokonut_sensor_baseline_owner;

REVOKE ALL ON FUNCTION kokonut_security.evaluate_sensor_baselines(UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.enqueue_sensor_baseline_notification_intent(
    UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.evaluate_sensor_baselines(UUID)
    TO kokonut_worker_execution;
GRANT EXECUTE ON FUNCTION kokonut_security.enqueue_sensor_baseline_notification_intent(
    UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
) TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        REVOKE ALL ON FUNCTION kokonut_security.evaluate_sensor_baselines(UUID)
            FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.enqueue_sensor_baseline_notification_intent(
            UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
        ) FROM kokonut_runtime;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_operator_auth'
    ) THEN
        REVOKE ALL ON FUNCTION kokonut_security.evaluate_sensor_baselines(UUID)
            FROM kokonut_operator_auth;
        REVOKE ALL ON FUNCTION kokonut_security.enqueue_sensor_baseline_notification_intent(
            UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
        ) FROM kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_sensor_baseline_owner;

COMMENT ON TABLE kokonut_security.sensor_baseline_alert_effect IS
    'Private idempotency receipt for environmental-baseline alerts; keyed by the baseline and latest source reading.';
COMMENT ON FUNCTION kokonut_security.evaluate_sensor_baselines(UUID) IS
    'Evaluates active environmental baselines for one signed sensor-reading location and atomically creates a warning alert plus sensor_alert event; exact baseline/reading retries return the stored alert.';
COMMENT ON FUNCTION kokonut_security.enqueue_sensor_baseline_notification_intent(
    UUID, UUID, UUID, UUID, TEXT, TEXT, JSONB
) IS
    'Enqueues one allowlisted notification intent only for a sensor-baseline alert receipt and event in the current signed location; exact retries are idempotent.';

COMMIT;
