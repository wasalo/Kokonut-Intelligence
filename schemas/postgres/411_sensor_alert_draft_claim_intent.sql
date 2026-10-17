-- Create and link one bounded draft MRV claim from a sensor alert.
-- This records provenance only; it never submits, verifies, or publishes claims.

BEGIN;

ALTER TABLE public.mrv_claim
    ADD COLUMN IF NOT EXISTS source_sensor_reading_event_id UUID;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mrv_claim_source_event_alert
    ON public.mrv_claim(source_sensor_reading_event_id, sensor_alert_id)
    WHERE source_sensor_reading_event_id IS NOT NULL
      AND sensor_alert_id IS NOT NULL;

COMMENT ON COLUMN public.mrv_claim.source_sensor_reading_event_id IS
    'sensor_reading event that produced this idempotent sensor draft claim; NULL for legacy claims.';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_anomaly_claim_owner'
    ) THEN
        CREATE ROLE kokonut_anomaly_claim_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname = 'kokonut_anomaly_claim_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_claim_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_anomaly_claim_owner'
            OR member_role.rolname = 'kokonut_anomaly_claim_owner'
    ) THEN
        RAISE EXCEPTION 'kokonut_anomaly_claim_owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_anomaly_claim_owner;
GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_anomaly_claim_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_anomaly_claim_owner;

GRANT SELECT (id, event_type, source_table, source_id, payload)
    ON public.platform_event TO kokonut_anomaly_claim_owner;
GRANT SELECT (location_id, source_reading_id, alert_rule_id, source_event_id,
              outcome, sensor_alert_id)
    ON public.sensor_anomaly_effect TO kokonut_anomaly_claim_owner;
GRANT SELECT (id, sensor_id, location_id, reading_date)
    ON public.sensor_reading TO kokonut_anomaly_claim_owner;
GRANT SELECT (id, location_id, sensor_type_id)
    ON public.sensor_device TO kokonut_anomaly_claim_owner;
GRANT SELECT (id, sensor_type_id, severity, auto_create_claim, claim_type)
    ON public.alert_rule TO kokonut_anomaly_claim_owner;
GRANT SELECT (id, location_id, reading_id, sensor_device_id, alert_rule_id,
              severity, reading_value, threshold_value, claim_id)
    ON public.sensor_alert TO kokonut_anomaly_claim_owner;
GRANT UPDATE (claim_id) ON public.sensor_alert
    TO kokonut_anomaly_claim_owner;
GRANT SELECT (id, location_id, claim_type, claim_date, claim_data, status,
              sensor_device_id, sensor_alert_id, source_readings,
              source_sensor_reading_event_id)
    ON public.mrv_claim TO kokonut_anomaly_claim_owner;
GRANT INSERT (location_id, claim_type, claim_date, claim_data, status,
              sensor_device_id, sensor_alert_id, source_readings,
              source_record_ids, source_sensor_reading_event_id)
    ON public.mrv_claim TO kokonut_anomaly_claim_owner;
GRANT UPDATE (source_sensor_reading_event_id) ON public.mrv_claim
    TO kokonut_anomaly_claim_owner;

REVOKE ALL ON public.mrv_claim FROM kokonut_worker_execution;
REVOKE ALL ON public.sensor_alert FROM kokonut_worker_execution;

CREATE OR REPLACE FUNCTION kokonut_security.create_sensor_alert_draft_claim(
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
    existing_claim RECORD;
    inserted_claim_id UUID;
    linked_rows INTEGER;
    canonical_claim_data JSONB;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_reading', 'process') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'draft claim creation requires a signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'draft claim is outside the signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_source_event_id IS NULL
       OR requested_source_reading_id IS NULL
       OR requested_alert_rule_id IS NULL
       OR requested_sensor_alert_id IS NULL THEN
        RAISE EXCEPTION 'draft claim source and alert identifiers are required'
            USING ERRCODE = '22023';
    END IF;

    SELECT alert.id, alert.location_id, alert.reading_id,
           alert.sensor_device_id, alert.alert_rule_id, alert.severity,
           alert.reading_value, alert.threshold_value, alert.claim_id,
           reading.reading_date, rule.auto_create_claim, rule.claim_type
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
      JOIN public.sensor_alert AS alert
        ON alert.id = effect.sensor_alert_id
       AND alert.location_id = worker_scope.location_id
       AND alert.reading_id = reading.id
       AND alert.sensor_device_id = device.id
       AND alert.alert_rule_id = effect.alert_rule_id
       AND alert.severity = rule.severity
     WHERE effect.source_event_id = requested_source_event_id
       AND effect.source_reading_id = requested_source_reading_id
       AND effect.alert_rule_id = requested_alert_rule_id
       AND effect.location_id = worker_scope.location_id
       AND effect.outcome = 'alert_created'
       AND effect.sensor_alert_id = requested_sensor_alert_id
       AND alert.id = requested_sensor_alert_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'draft claim source, alert, rule, or location does not match signed scope'
            USING ERRCODE = '42501';
    END IF;

    -- Serialize legacy-link adoption and new intent creation for this alert.
    PERFORM pg_advisory_xact_lock(
        hashtextextended(requested_sensor_alert_id::TEXT, 411)
    );

    canonical_claim_data := jsonb_build_object(
        'sensor_device_id', linked_alert.sensor_device_id,
        'alert_id', linked_alert.id,
        'reading_value', linked_alert.reading_value,
        'threshold_value', linked_alert.threshold_value,
        'severity', linked_alert.severity
    );

    SELECT claim.id, claim.location_id, claim.claim_type, claim.claim_date,
           claim.claim_data, claim.status, claim.sensor_device_id,
           claim.sensor_alert_id, claim.source_readings,
           claim.source_sensor_reading_event_id
      INTO existing_claim
      FROM public.mrv_claim AS claim
     WHERE claim.source_sensor_reading_event_id = requested_source_event_id
       AND claim.sensor_alert_id = linked_alert.id;

    IF FOUND THEN
        IF existing_claim.location_id IS DISTINCT FROM worker_scope.location_id
           OR existing_claim.sensor_alert_id IS DISTINCT FROM linked_alert.id
           OR existing_claim.sensor_device_id IS DISTINCT FROM linked_alert.sensor_device_id
           OR existing_claim.source_sensor_reading_event_id IS DISTINCT FROM requested_source_event_id
           OR existing_claim.claim_data ->> 'alert_id' IS DISTINCT FROM linked_alert.id::TEXT
           OR existing_claim.claim_data ->> 'sensor_device_id'
                IS DISTINCT FROM linked_alert.sensor_device_id::TEXT THEN
            RAISE EXCEPTION 'draft claim event identity conflicts with existing content'
                USING ERRCODE = '23505';
        END IF;

        UPDATE public.sensor_alert AS alert
           SET claim_id = existing_claim.id
         WHERE alert.id = linked_alert.id
           AND (alert.claim_id IS NULL OR alert.claim_id = existing_claim.id);
        GET DIAGNOSTICS linked_rows = ROW_COUNT;
        IF linked_rows <> 1 THEN
            RAISE EXCEPTION 'sensor alert is linked to a different claim'
                USING ERRCODE = '23505';
        END IF;
        RETURN existing_claim.id;
    END IF;

    -- The prior handler may already have created a draft and linked it to the
    -- alert before this bounded function is deployed. Adopt only that exact
    -- source-linked claim, attaching the stable reading-event identity without changing
    -- its lifecycle or review fields.
    IF linked_alert.claim_id IS NOT NULL THEN
        SELECT claim.id, claim.location_id, claim.claim_type, claim.claim_data,
               claim.sensor_device_id, claim.sensor_alert_id,
               claim.source_sensor_reading_event_id
          INTO existing_claim
          FROM public.mrv_claim AS claim
         WHERE claim.id = linked_alert.claim_id;
        IF NOT FOUND
           OR existing_claim.location_id IS DISTINCT FROM worker_scope.location_id
           OR existing_claim.sensor_alert_id IS DISTINCT FROM linked_alert.id
           OR existing_claim.sensor_device_id IS DISTINCT FROM linked_alert.sensor_device_id
           OR existing_claim.source_sensor_reading_event_id IS NOT NULL
           OR existing_claim.claim_type IS DISTINCT FROM linked_alert.claim_type
           OR existing_claim.claim_data IS DISTINCT FROM canonical_claim_data
           OR existing_claim.claim_data ->> 'alert_id' IS DISTINCT FROM linked_alert.id::TEXT
           OR existing_claim.claim_data ->> 'sensor_device_id'
                IS DISTINCT FROM linked_alert.sensor_device_id::TEXT THEN
            RAISE EXCEPTION 'existing sensor claim does not match the alert source'
                USING ERRCODE = '23505';
        END IF;
        UPDATE public.mrv_claim AS claim
           SET source_sensor_reading_event_id = requested_source_event_id
         WHERE claim.id = existing_claim.id
           AND claim.source_sensor_reading_event_id IS NULL;
        GET DIAGNOSTICS linked_rows = ROW_COUNT;
        IF linked_rows <> 1 THEN
            RAISE EXCEPTION 'existing sensor claim could not be linked to its source event'
                USING ERRCODE = '23505';
        END IF;
        RETURN existing_claim.id;
    END IF;

    IF linked_alert.auto_create_claim IS DISTINCT FROM TRUE
       OR NULLIF(btrim(linked_alert.claim_type), '') IS NULL THEN
        RAISE EXCEPTION 'alert rule does not permit automatic claim creation'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO public.mrv_claim (
        location_id, claim_type, claim_date, claim_data, status,
        sensor_device_id, sensor_alert_id, source_readings,
        source_record_ids, source_sensor_reading_event_id
    ) VALUES (
        worker_scope.location_id, linked_alert.claim_type,
        linked_alert.reading_date, canonical_claim_data, 'draft',
        linked_alert.sensor_device_id, linked_alert.id,
        ARRAY[requested_source_reading_id],
        ARRAY[requested_source_reading_id], requested_source_event_id
    )
    ON CONFLICT (source_sensor_reading_event_id, sensor_alert_id)
        WHERE source_sensor_reading_event_id IS NOT NULL
          AND sensor_alert_id IS NOT NULL
    DO NOTHING
    RETURNING id INTO inserted_claim_id;

    IF inserted_claim_id IS NULL THEN
        SELECT claim.id, claim.location_id, claim.claim_type, claim.claim_date,
               claim.claim_data, claim.status, claim.sensor_device_id,
               claim.sensor_alert_id, claim.source_readings,
               claim.source_sensor_reading_event_id
          INTO existing_claim
          FROM public.mrv_claim AS claim
         WHERE claim.source_sensor_reading_event_id = requested_source_event_id
           AND claim.sensor_alert_id = linked_alert.id;
        IF NOT FOUND
           OR existing_claim.location_id IS DISTINCT FROM worker_scope.location_id
           OR existing_claim.sensor_alert_id IS DISTINCT FROM linked_alert.id
           OR existing_claim.sensor_device_id IS DISTINCT FROM linked_alert.sensor_device_id
           OR existing_claim.source_sensor_reading_event_id IS DISTINCT FROM requested_source_event_id
           OR existing_claim.claim_data ->> 'alert_id' IS DISTINCT FROM linked_alert.id::TEXT
           OR existing_claim.claim_data ->> 'sensor_device_id'
                IS DISTINCT FROM linked_alert.sensor_device_id::TEXT THEN
            RAISE EXCEPTION 'draft claim event identity conflicts with existing content'
                USING ERRCODE = '23505';
        END IF;
        inserted_claim_id := existing_claim.id;
    END IF;

    UPDATE public.sensor_alert AS alert
       SET claim_id = inserted_claim_id
     WHERE alert.id = linked_alert.id
       AND (alert.claim_id IS NULL OR alert.claim_id = inserted_claim_id);
    GET DIAGNOSTICS linked_rows = ROW_COUNT;
    IF linked_rows <> 1 THEN
        RAISE EXCEPTION 'sensor alert is linked to a different claim'
            USING ERRCODE = '23505';
    END IF;

    RETURN inserted_claim_id;
END;
$$;

ALTER FUNCTION kokonut_security.create_sensor_alert_draft_claim(
    UUID, UUID, UUID, UUID, UUID
) OWNER TO kokonut_anomaly_claim_owner;
REVOKE ALL ON FUNCTION kokonut_security.create_sensor_alert_draft_claim(
    UUID, UUID, UUID, UUID, UUID
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.create_sensor_alert_draft_claim(
    UUID, UUID, UUID, UUID, UUID
) TO kokonut_worker_execution;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_sensor_alert_draft_claim(
            UUID, UUID, UUID, UUID, UUID
        ) FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_sensor_alert_draft_claim(
            UUID, UUID, UUID, UUID, UUID
        ) FROM kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_anomaly_claim_owner;

COMMENT ON FUNCTION kokonut_security.create_sensor_alert_draft_claim(
    UUID, UUID, UUID, UUID, UUID
) IS
    'Creates or adopts one idempotent draft MRV claim from a matching signed-location sensor-reading event and sensor alert; it cannot transition claim lifecycle or edit review and attestation fields.';

COMMIT;
