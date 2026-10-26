-- Isolate the scheduled global freshness sweep behind bounded functions.
-- The job intentionally checks both location-scoped and network-wide sources;
-- it does not claim a farm tenant context.  Its dedicated login receives no
-- direct table or sequence access.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_freshness_owner') THEN
        CREATE ROLE kokonut_freshness_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_freshness_owner'
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'freshness function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_freshness_login') THEN
        CREATE ROLE kokonut_freshness_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_freshness_login'
          AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
               OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'freshness login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN ('kokonut_freshness_owner', 'kokonut_freshness_login')
            OR member_role.rolname IN ('kokonut_freshness_owner', 'kokonut_freshness_login')
    ) THEN
        RAISE EXCEPTION 'freshness roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_freshness_login;
GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_freshness_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_freshness_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_freshness_login;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_freshness_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_freshness_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_freshness_login;
REVOKE CREATE ON SCHEMA public FROM kokonut_freshness_login;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_freshness_login;

GRANT SELECT (
    id, source_system, is_active, location_scoped, stale_threshold_minutes,
    critical_threshold_minutes, alert_cooldown_minutes, escalation_cooldown_minutes
) ON public.data_freshness_config TO kokonut_freshness_owner;
GRANT SELECT (id) ON public.location TO kokonut_freshness_owner;
GRANT SELECT (location_id, observation_date) ON public.weather_observation TO kokonut_freshness_owner;
GRANT SELECT (sensor_id, created_at) ON public.sensor_reading TO kokonut_freshness_owner;
GRANT SELECT (id, location_id) ON public.sensor_device TO kokonut_freshness_owner;
GRANT SELECT (location_id, observation_date) ON public.remote_sensing_observation TO kokonut_freshness_owner;
GRANT SELECT (location_id, observation_date) ON public.price_observation TO kokonut_freshness_owner;
GRANT SELECT (attested_at) ON public.attestation_record TO kokonut_freshness_owner;
GRANT SELECT (block_timestamp) ON public.wallet_activity_event TO kokonut_freshness_owner;
GRANT SELECT (block_timestamp) ON public.governance_event TO kokonut_freshness_owner;
GRANT INSERT (
    config_id, source_system, location_id, last_data_at, gap_minutes, status,
    alert_sent, alert_channel, metadata
) ON public.data_freshness_check TO kokonut_freshness_owner;
GRANT SELECT (id, source_system, location_id, status),
    UPDATE (alert_sent, alert_channel) ON public.data_freshness_check TO kokonut_freshness_owner;
GRANT SELECT (
    id, source_system, location_id, current_status, last_event_status, last_event_at,
    alert_count, escalation_count, recovery_count
), INSERT (source_system, location_id, current_status),
   UPDATE (
       current_status, last_event_type, last_event_status, last_event_at,
       alert_count, escalation_count, recovery_count, updated_at
   ) ON public.data_freshness_alert_state TO kokonut_freshness_owner;
GRANT INSERT (
    state_id, check_id, source_system, location_id, event_type,
    previous_status, status, gap_minutes, created_at
) ON public.data_freshness_alert_history TO kokonut_freshness_owner;
GRANT SELECT (id, source_system, location_id, event_type, status)
    ON public.data_freshness_alert_history TO kokonut_freshness_owner;
GRANT SELECT (id, event_type, source_table, source_id, payload, priority), INSERT (
    id, event_type, source_table, source_id, payload, priority, status, max_retries, metadata
) ON public.platform_event TO kokonut_freshness_owner;

DO $$
DECLARE target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'data_freshness_config', 'location', 'weather_observation', 'sensor_reading',
        'sensor_device', 'remote_sensing_observation', 'price_observation',
        'attestation_record', 'wallet_activity_event', 'governance_event',
        'data_freshness_check', 'data_freshness_alert_state',
        'data_freshness_alert_history', 'platform_event'
    ] LOOP
        IF EXISTS (
            SELECT 1 FROM pg_class relation
            JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname = 'public' AND relation.relname = target_table
              AND relation.relrowsecurity
        ) AND NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = target_table
               AND policyname = 'freshness_owner_function_access'
        ) THEN
            EXECUTE format(
                'CREATE POLICY freshness_owner_function_access ON public.%I '
                || 'FOR ALL TO kokonut_freshness_owner USING (true) WITH CHECK (true)',
                target_table
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_freshness_configs(requested_source TEXT DEFAULT NULL)
RETURNS TABLE (
    id UUID, source_system TEXT, stale_threshold_minutes INTEGER,
    critical_threshold_minutes INTEGER, location_scoped BOOLEAN,
    alert_cooldown_minutes INTEGER, escalation_cooldown_minutes INTEGER
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_freshness_login'
       OR (requested_source IS NOT NULL AND length(requested_source) > 100) THEN
        RAISE EXCEPTION 'freshness config read is not authorized' USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT config.id, config.source_system::TEXT, config.stale_threshold_minutes,
           config.critical_threshold_minutes, COALESCE(config.location_scoped, FALSE),
           config.alert_cooldown_minutes, config.escalation_cooldown_minutes
      FROM public.data_freshness_config AS config
     WHERE config.is_active = TRUE
       AND (requested_source IS NULL OR config.source_system = requested_source)
     ORDER BY config.source_system, config.id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_freshness_locations()
RETURNS TABLE (location_id UUID)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_freshness_login' THEN
        RAISE EXCEPTION 'freshness location list is not authorized' USING ERRCODE = '42501';
    END IF;
    RETURN QUERY SELECT location.id FROM public.location AS location ORDER BY location.id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.read_freshness_data_at(
    requested_source TEXT, requested_location_scoped BOOLEAN, requested_location UUID
)
RETURNS TIMESTAMPTZ
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE
    configured_scope BOOLEAN;
    latest_at TIMESTAMPTZ;
BEGIN
    IF session_user <> 'kokonut_freshness_login' THEN
        RAISE EXCEPTION 'freshness data read is not authorized' USING ERRCODE = '42501';
    END IF;
    SELECT COALESCE(config.location_scoped, FALSE) INTO configured_scope
      FROM public.data_freshness_config AS config
     WHERE config.source_system = requested_source AND config.is_active = TRUE;
    IF NOT FOUND OR configured_scope IS DISTINCT FROM requested_location_scoped
       OR (requested_location_scoped AND requested_location IS NULL)
       OR (NOT requested_location_scoped AND requested_location IS NOT NULL) THEN
        RAISE EXCEPTION 'freshness scope is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;

    IF requested_source = 'weather' THEN
        SELECT max(observation.observation_date) INTO latest_at
          FROM public.weather_observation AS observation
         WHERE NOT requested_location_scoped OR observation.location_id = requested_location;
    ELSIF requested_source = 'sensors' THEN
        SELECT max(reading.created_at) INTO latest_at
          FROM public.sensor_reading AS reading
          JOIN public.sensor_device AS device ON device.id = reading.sensor_id
         WHERE NOT requested_location_scoped OR device.location_id = requested_location;
    ELSIF requested_source = 'remote_sensing' THEN
        SELECT max(observation.observation_date) INTO latest_at
          FROM public.remote_sensing_observation AS observation
         WHERE NOT requested_location_scoped OR observation.location_id = requested_location;
    ELSIF requested_source = 'market_data' THEN
        SELECT max(observation.observation_date) INTO latest_at
          FROM public.price_observation AS observation
         WHERE NOT requested_location_scoped OR observation.location_id = requested_location;
    ELSIF requested_source = 'eas_indexer' THEN
        SELECT max(record.attested_at) INTO latest_at
          FROM public.attestation_record AS record;
    ELSIF requested_source = 'rpc_indexer' THEN
        SELECT max(event.block_timestamp) INTO latest_at
          FROM public.wallet_activity_event AS event;
    ELSIF requested_source = 'gnosis_indexer' THEN
        SELECT max(event.block_timestamp) INTO latest_at
          FROM public.governance_event AS event;
    ELSE
        RAISE EXCEPTION 'unsupported freshness source' USING ERRCODE = '22023';
    END IF;
    RETURN latest_at;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.create_freshness_check(
    requested_config UUID, requested_source TEXT, requested_location UUID,
    requested_last_data_at TIMESTAMPTZ, requested_gap INTEGER, requested_status TEXT,
    requested_alert_sent BOOLEAN, requested_alert_channel TEXT, requested_metadata JSONB
)
RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE
    check_id UUID;
    scope_is_location BOOLEAN;
BEGIN
    IF session_user <> 'kokonut_freshness_login'
       OR requested_status NOT IN ('fresh', 'stale', 'critical', 'no_data', 'error')
       OR (requested_gap IS NOT NULL AND requested_gap < 0)
       OR requested_alert_sent IS DISTINCT FROM FALSE
       OR requested_alert_channel IS NOT NULL
       OR jsonb_typeof(COALESCE(requested_metadata, '{}'::jsonb)) <> 'object'
       OR octet_length(COALESCE(requested_metadata, '{}'::jsonb)::TEXT) > 8192 THEN
        RAISE EXCEPTION 'freshness check is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    SELECT COALESCE(config.location_scoped, FALSE) INTO scope_is_location
      FROM public.data_freshness_config AS config
     WHERE config.id = requested_config AND config.source_system = requested_source
       AND config.is_active = TRUE;
    IF NOT FOUND OR (scope_is_location AND requested_location IS NULL)
       OR (NOT scope_is_location AND requested_location IS NOT NULL) THEN
        RAISE EXCEPTION 'freshness check scope is invalid' USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.data_freshness_check (
        config_id, source_system, location_id, last_data_at, gap_minutes, status,
        alert_sent, alert_channel, metadata
    ) VALUES (
        requested_config, requested_source, requested_location, requested_last_data_at,
        requested_gap, requested_status, FALSE, NULL, COALESCE(requested_metadata, '{}'::jsonb)
    ) RETURNING id INTO check_id;
    RETURN check_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_freshness_alert_state(
    requested_source TEXT, requested_location UUID
)
RETURNS TABLE (id UUID, current_status TEXT, last_event_status TEXT, last_event_at TIMESTAMPTZ)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE
    scope_is_location BOOLEAN;
    selected_state_id UUID;
BEGIN
    IF session_user <> 'kokonut_freshness_login' THEN
        RAISE EXCEPTION 'freshness alert state read is not authorized' USING ERRCODE = '42501';
    END IF;
    SELECT COALESCE(config.location_scoped, FALSE) INTO scope_is_location
      FROM public.data_freshness_config AS config
     WHERE config.source_system = requested_source AND config.is_active = TRUE;
    IF NOT FOUND OR (scope_is_location AND requested_location IS NULL)
       OR (NOT scope_is_location AND requested_location IS NOT NULL) THEN
        RAISE EXCEPTION 'freshness alert scope is invalid' USING ERRCODE = '42501';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(
        'kokonut:freshness:' || requested_source || ':' || COALESCE(requested_location::TEXT, 'global'), 0
    ));
    SELECT state.id INTO selected_state_id
      FROM public.data_freshness_alert_state AS state
     WHERE state.source_system = requested_source
       AND state.location_id IS NOT DISTINCT FROM requested_location
     FOR UPDATE;
    IF NOT FOUND THEN
        INSERT INTO public.data_freshness_alert_state (source_system, location_id, current_status)
        VALUES (requested_source, requested_location, 'no_data')
        ON CONFLICT DO NOTHING;
        SELECT state.id INTO selected_state_id
          FROM public.data_freshness_alert_state AS state
         WHERE state.source_system = requested_source
           AND state.location_id IS NOT DISTINCT FROM requested_location
         FOR UPDATE;
    END IF;
    RETURN QUERY
    SELECT state.id, state.current_status::TEXT, state.last_event_status::TEXT, state.last_event_at
      FROM public.data_freshness_alert_state AS state
     WHERE state.id = selected_state_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.record_freshness_alert_event(
    requested_state UUID, requested_check UUID, requested_source TEXT,
    requested_location UUID, requested_event_type TEXT, requested_previous_status TEXT,
    requested_status TEXT, requested_gap INTEGER, requested_at TIMESTAMPTZ
)
RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE
    alert_id UUID;
BEGIN
    IF session_user <> 'kokonut_freshness_login'
       OR requested_event_type NOT IN ('alert', 'escalation', 'recovery')
       OR requested_status NOT IN ('fresh', 'stale', 'critical')
       OR (requested_gap IS NOT NULL AND requested_gap < 0)
       OR requested_at IS NULL
       OR (requested_event_type = 'escalation' AND
           (requested_previous_status IS DISTINCT FROM 'stale' OR requested_status <> 'critical'))
       OR (requested_event_type = 'recovery' AND
           (requested_previous_status NOT IN ('stale', 'critical') OR requested_status <> 'fresh'))
       OR (requested_event_type = 'alert' AND requested_status NOT IN ('stale', 'critical')) THEN
        RAISE EXCEPTION 'freshness alert transition is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.data_freshness_alert_state AS state
         WHERE state.id = requested_state AND state.source_system = requested_source
           AND state.location_id IS NOT DISTINCT FROM requested_location
           AND state.current_status IS NOT DISTINCT FROM requested_previous_status
    ) OR NOT EXISTS (
        SELECT 1 FROM public.data_freshness_check AS check_row
         WHERE check_row.id = requested_check AND check_row.source_system = requested_source
           AND check_row.location_id IS NOT DISTINCT FROM requested_location
           AND check_row.status = requested_status
    ) THEN
        RAISE EXCEPTION 'freshness alert source rows do not match' USING ERRCODE = '23514';
    END IF;
    INSERT INTO public.data_freshness_alert_history (
        state_id, check_id, source_system, location_id, event_type,
        previous_status, status, gap_minutes, created_at
    ) VALUES (
        requested_state, requested_check, requested_source, requested_location,
        requested_event_type, requested_previous_status, requested_status,
        requested_gap, requested_at
    ) RETURNING id INTO alert_id;
    UPDATE public.data_freshness_alert_state AS state
       SET current_status = requested_status,
           last_event_type = requested_event_type,
           last_event_status = requested_status,
           last_event_at = requested_at,
           alert_count = state.alert_count + CASE WHEN requested_event_type = 'alert' THEN 1 ELSE 0 END,
           escalation_count = state.escalation_count + CASE WHEN requested_event_type = 'escalation' THEN 1 ELSE 0 END,
           recovery_count = state.recovery_count + CASE WHEN requested_event_type = 'recovery' THEN 1 ELSE 0 END,
           updated_at = requested_at
     WHERE state.id = requested_state;
    RETURN alert_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.update_freshness_alert_state(
    requested_state UUID, requested_status TEXT, requested_at TIMESTAMPTZ
)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_freshness_login'
       OR requested_status NOT IN ('fresh', 'stale', 'critical', 'no_data')
       OR requested_at IS NULL THEN
        RAISE EXCEPTION 'freshness alert state update is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    UPDATE public.data_freshness_alert_state
       SET current_status = requested_status, updated_at = requested_at
     WHERE id = requested_state;
    IF NOT FOUND THEN RAISE EXCEPTION 'freshness alert state does not exist' USING ERRCODE = '23503'; END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.update_freshness_check_alert(
    requested_check UUID, requested_alert_sent BOOLEAN, requested_channel TEXT
)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_freshness_login'
       OR requested_alert_sent IS DISTINCT FROM FALSE
       OR requested_channel IS NOT NULL AND requested_channel <> 'event_bus' THEN
        RAISE EXCEPTION 'freshness check alert update is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    UPDATE public.data_freshness_check
       SET alert_sent = FALSE, alert_channel = requested_channel
     WHERE id = requested_check;
    IF NOT FOUND THEN RAISE EXCEPTION 'freshness check does not exist' USING ERRCODE = '23503'; END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.enqueue_freshness_event(
    requested_alert UUID, requested_payload JSONB, requested_priority TEXT
)
RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE
    alert_row RECORD;
BEGIN
    IF session_user <> 'kokonut_freshness_login'
       OR jsonb_typeof(requested_payload) <> 'object'
       OR octet_length(requested_payload::TEXT) > 16384
       OR requested_payload->>'alert_id' IS DISTINCT FROM requested_alert::TEXT
       OR requested_payload->>'event_type' NOT IN ('alert', 'escalation', 'recovery')
       OR requested_priority NOT IN ('high', 'normal') THEN
        RAISE EXCEPTION 'freshness event is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    SELECT history.id, history.source_system, history.location_id,
           history.event_type, history.status
      INTO alert_row
      FROM public.data_freshness_alert_history AS history
     WHERE history.id = requested_alert;
    IF NOT FOUND
       OR requested_payload->>'source_system' IS DISTINCT FROM alert_row.source_system
       OR requested_payload->>'event_type' IS DISTINCT FROM alert_row.event_type
       OR requested_payload->>'status' IS DISTINCT FROM alert_row.status
       OR requested_payload->>'location_id' IS DISTINCT FROM alert_row.location_id::TEXT
       OR COALESCE(length(requested_payload->>'message'), 0) > 4096 THEN
        RAISE EXCEPTION 'freshness event does not match its alert' USING ERRCODE = '23514';
    END IF;
    INSERT INTO public.platform_event (
        id, event_type, source_table, source_id, payload, priority, status, max_retries, metadata
    ) VALUES (
        requested_alert, 'data_stale', 'data_freshness_alert_history', requested_alert,
        requested_payload, requested_priority, 'pending', 3, NULL
    ) ON CONFLICT (id) DO NOTHING;
    IF NOT FOUND AND NOT EXISTS (
        SELECT 1 FROM public.platform_event AS event
         WHERE event.id = requested_alert AND event.event_type = 'data_stale'
           AND event.source_table = 'data_freshness_alert_history'
           AND event.source_id = requested_alert AND event.payload = requested_payload
           AND event.priority = requested_priority
    ) THEN
        RAISE EXCEPTION 'freshness event retry conflicts with existing event' USING ERRCODE = '23505';
    END IF;
    RETURN requested_alert;
END;
$$;

DO $$
DECLARE function_signature TEXT;
BEGIN
    FOREACH function_signature IN ARRAY ARRAY[
        'kokonut_security.list_freshness_configs(text)',
        'kokonut_security.list_freshness_locations()',
        'kokonut_security.read_freshness_data_at(text,boolean,uuid)',
        'kokonut_security.create_freshness_check(uuid,text,uuid,timestamp with time zone,integer,text,boolean,text,jsonb)',
        'kokonut_security.get_freshness_alert_state(text,uuid)',
        'kokonut_security.record_freshness_alert_event(uuid,uuid,text,uuid,text,text,text,integer,timestamp with time zone)',
        'kokonut_security.update_freshness_alert_state(uuid,text,timestamp with time zone)',
        'kokonut_security.update_freshness_check_alert(uuid,boolean,text)',
        'kokonut_security.enqueue_freshness_event(uuid,jsonb,text)'
    ] LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO kokonut_freshness_owner', function_signature);
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', function_signature);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO kokonut_freshness_login', function_signature);
    END LOOP;
END;
$$;

COMMIT;
