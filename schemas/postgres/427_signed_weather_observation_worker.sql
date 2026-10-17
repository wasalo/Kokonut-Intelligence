-- Bound scheduled current-weather ingestion to one signed location grant.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_weather_observation_owner'
    ) THEN
        CREATE ROLE kokonut_weather_observation_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_weather_observation_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_weather_observation_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_weather_observation_owner'
            OR member_role.rolname = 'kokonut_weather_observation_owner'
    ) THEN
        RAISE EXCEPTION 'weather observation function owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA kokonut_security, public
    TO kokonut_weather_observation_owner;
GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_weather_observation_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_weather_observation_owner;

GRANT SELECT (id, status, center) ON public.location
    TO kokonut_weather_observation_owner;
GRANT INSERT (
    id, location_id, observation_date, observation_time, source,
    temperature_c, precipitation_mm, humidity_pct, wind_speed_kmh,
    wind_direction_deg, pressure_hpa, visibility_km, cloud_cover_pct, metadata
) ON public.weather_observation TO kokonut_weather_observation_owner;
GRANT INSERT (
    source_system, source_table, source_id, target_table, target_id, operation,
    payload_hash, status, error_message, rows_affected, processing_time_ms,
    processor_version, location_id
) ON public.ingestion_log TO kokonut_weather_observation_owner;
GRANT INSERT (
    event_key, source_table, source_id, target_table, columns, rows, payload_hash
) ON public.clickhouse_outbox TO kokonut_weather_observation_owner;
GRANT SELECT (
    id, event_key, source_table, source_id, target_table, columns, rows, payload_hash
) ON public.clickhouse_outbox TO kokonut_weather_observation_owner;
GRANT UPDATE (updated_at) ON public.clickhouse_outbox
    TO kokonut_weather_observation_owner;

CREATE TABLE IF NOT EXISTS kokonut_security.weather_observation_worker_receipt (
    location_id UUID NOT NULL,
    provider_payload_hash TEXT NOT NULL
        CHECK (provider_payload_hash ~ '^[0-9a-f]{64}$'),
    observation_id UUID NOT NULL
        REFERENCES public.weather_observation(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY (location_id, provider_payload_hash),
    UNIQUE (observation_id)
);
ALTER TABLE kokonut_security.weather_observation_worker_receipt
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.weather_observation_worker_receipt
    FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS weather_observation_receipt_owner
    ON kokonut_security.weather_observation_worker_receipt;
CREATE POLICY weather_observation_receipt_owner
    ON kokonut_security.weather_observation_worker_receipt
    FOR ALL TO kokonut_weather_observation_owner
    USING (true) WITH CHECK (true);
GRANT SELECT, INSERT ON kokonut_security.weather_observation_worker_receipt
    TO kokonut_weather_observation_owner;
REVOKE ALL ON kokonut_security.weather_observation_worker_receipt
    FROM PUBLIC, kokonut_worker_execution, kokonut_runtime;
DO $$
BEGIN
    -- The dedicated worker login is optional deployment configuration. A
    -- clean schema bootstrap must not require it to exist before migrations;
    -- if it has already been provisioned, remove any direct receipt access.
    IF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_login'
    ) THEN
        EXECUTE 'REVOKE ALL ON kokonut_security.weather_observation_worker_receipt '
            || 'FROM kokonut_worker_login';
    END IF;
END;
$$;

-- These narrowly scoped policies allow the no-login function owner to continue
-- working if application tables later enable forced RLS. It is reachable only
-- through the signed SECURITY DEFINER functions below.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'location'
           AND policyname = 'weather_observation_owner_location_read'
    ) THEN
        EXECUTE 'CREATE POLICY weather_observation_owner_location_read ON public.location '
            || 'FOR SELECT TO kokonut_weather_observation_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'weather_observation'
           AND policyname = 'weather_observation_owner_insert'
    ) THEN
        EXECUTE 'CREATE POLICY weather_observation_owner_insert ON public.weather_observation '
            || 'FOR INSERT TO kokonut_weather_observation_owner WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'ingestion_log'
           AND policyname = 'weather_observation_owner_audit_insert'
    ) THEN
        EXECUTE 'CREATE POLICY weather_observation_owner_audit_insert ON public.ingestion_log '
            || 'FOR INSERT TO kokonut_weather_observation_owner WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'clickhouse_outbox'
           AND policyname = 'weather_observation_owner_outbox_insert'
    ) THEN
        EXECUTE 'CREATE POLICY weather_observation_owner_outbox_insert ON public.clickhouse_outbox '
            || 'FOR INSERT TO kokonut_weather_observation_owner WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'clickhouse_outbox'
           AND policyname = 'weather_observation_owner_outbox_read'
    ) THEN
        EXECUTE 'CREATE POLICY weather_observation_owner_outbox_read ON public.clickhouse_outbox '
            || 'FOR SELECT TO kokonut_weather_observation_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'clickhouse_outbox'
           AND policyname = 'weather_observation_owner_outbox_update'
    ) THEN
        EXECUTE 'CREATE POLICY weather_observation_owner_outbox_update ON public.clickhouse_outbox '
            || 'FOR UPDATE TO kokonut_weather_observation_owner USING (true) WITH CHECK (true)';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.weather_observation_location(
    requested_location_id UUID
)
RETURNS TABLE(latitude DOUBLE PRECISION, longitude DOUBLE PRECISION)
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
          'weather_observation', 'ingest'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed current-weather worker scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'current-weather location differs from signed worker scope'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT public.ST_Y(location.center), public.ST_X(location.center)
      FROM public.location AS location
     WHERE location.id = worker_scope.location_id
       AND location.status = 'active'
       AND location.center IS NOT NULL;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_weather_observation(
    requested_location_id UUID,
    observation_row JSONB,
    projection_rows JSONB,
    projection_hash TEXT,
    provider_source_id TEXT,
    requested_provider_payload_hash TEXT,
    processing_time_ms INTEGER,
    error_text TEXT DEFAULT NULL
)
RETURNS TABLE(observation_id UUID, inserted BOOLEAN)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    parsed_record RECORD;
    saved_observation_id UUID;
    existing_observation_id UUID;
    outbox_id UUID;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope(
          'weather_observation', 'ingest'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed current-weather worker scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'current-weather location differs from signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF processing_time_ms IS NULL OR processing_time_ms < 0
       OR processing_time_ms > 600000 THEN
        RAISE EXCEPTION 'current-weather processing time is outside the allowed range';
    END IF;

    IF error_text IS NOT NULL THEN
        IF observation_row IS NOT NULL
           OR projection_hash IS NOT NULL
       OR requested_provider_payload_hash IS NOT NULL THEN
            RAISE EXCEPTION 'failed weather fetch cannot include observation or projection rows';
        END IF;
        IF jsonb_typeof(projection_rows) IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'failed weather fetch must use an empty projection array';
        END IF;
        IF jsonb_array_length(projection_rows) <> 0 THEN
            RAISE EXCEPTION 'failed weather fetch cannot include observation or projection rows';
        END IF;
        INSERT INTO public.ingestion_log (
            source_system, source_table, source_id, target_table, operation,
            payload_hash, status, error_message, rows_affected,
            processing_time_ms, processor_version, location_id
        ) VALUES (
            'openweathermap', 'weather_api', '', 'weather_observation', 'insert',
            NULL, 'failed', left(error_text, 2000), 0,
            processing_time_ms, '1.0.0', worker_scope.location_id
        );
        observation_id := NULL;
        inserted := FALSE;
        RETURN NEXT;
        RETURN;
    END IF;

    IF jsonb_typeof(observation_row) IS DISTINCT FROM 'object'
       OR jsonb_typeof(projection_rows) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'current-weather payload is invalid';
    END IF;
    IF jsonb_array_length(projection_rows) <> 1
       OR provider_source_id IS NULL
       OR length(btrim(provider_source_id)) = 0
       OR length(provider_source_id) > 255
       OR requested_provider_payload_hash IS NULL
       OR requested_provider_payload_hash !~ '^[0-9a-f]{64}$'
       OR projection_hash IS NULL
       OR projection_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'current-weather payload is invalid';
    END IF;

    SELECT * INTO parsed_record
      FROM jsonb_to_record(observation_row) AS item(
          location_id UUID, observation_date DATE, observation_time TIME,
          source TEXT, temperature_c NUMERIC, humidity_pct NUMERIC,
          precipitation_mm NUMERIC, wind_speed_kmh NUMERIC,
          wind_direction_deg NUMERIC, pressure_hpa NUMERIC,
          visibility_km NUMERIC, cloud_cover_pct NUMERIC, metadata JSONB
      );
    IF parsed_record.location_id IS DISTINCT FROM worker_scope.location_id
       OR parsed_record.source IS DISTINCT FROM 'openweathermap'
       OR parsed_record.observation_date IS NULL
       OR parsed_record.metadata IS NULL
       OR jsonb_typeof(parsed_record.metadata) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'current-weather record violates signed location/source contract';
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements(projection_rows) AS entry(value)
         WHERE jsonb_typeof(entry.value) IS DISTINCT FROM 'array'
            OR jsonb_array_length(entry.value) <> 10
            OR entry.value->>1 IS DISTINCT FROM worker_scope.location_id::TEXT
            OR entry.value->>2 IS DISTINCT FROM 'openweathermap'
    ) THEN
        RAISE EXCEPTION 'current-weather projection row violates location/column contract';
    END IF;

    -- Serialize concurrent retries for the same provider response. If a process
    -- committed before losing its scheduler acknowledgement, the receipt makes
    -- the retry a no-op across all four effects below.
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            worker_scope.location_id::TEXT || ':' || requested_provider_payload_hash, 0
        )
    );
    SELECT receipt.observation_id
      INTO existing_observation_id
      FROM kokonut_security.weather_observation_worker_receipt AS receipt
     WHERE receipt.location_id = worker_scope.location_id
       AND receipt.provider_payload_hash = requested_provider_payload_hash;
    IF FOUND THEN
        observation_id := existing_observation_id;
        inserted := FALSE;
        RETURN NEXT;
        RETURN;
    END IF;

    saved_observation_id := public.gen_random_uuid();
    INSERT INTO public.weather_observation (
        id, location_id, observation_date, observation_time, source,
        temperature_c, precipitation_mm, humidity_pct, wind_speed_kmh,
        wind_direction_deg, pressure_hpa, visibility_km, cloud_cover_pct, metadata
    ) VALUES (
        saved_observation_id, worker_scope.location_id,
        parsed_record.observation_date, parsed_record.observation_time,
        parsed_record.source, parsed_record.temperature_c,
        parsed_record.precipitation_mm, parsed_record.humidity_pct,
        parsed_record.wind_speed_kmh, parsed_record.wind_direction_deg,
        parsed_record.pressure_hpa, parsed_record.visibility_km,
        parsed_record.cloud_cover_pct, parsed_record.metadata
    );

    INSERT INTO public.ingestion_log (
        source_system, source_table, source_id, target_table, target_id,
        operation, payload_hash, status, rows_affected, processing_time_ms,
        processor_version, location_id
    ) VALUES (
        'openweathermap', 'weather_api', provider_source_id,
        'weather_observation', saved_observation_id, 'insert',
        requested_provider_payload_hash, 'success', 1, processing_time_ms,
        '1.0.0', worker_scope.location_id
    );

    INSERT INTO public.clickhouse_outbox AS existing_outbox (
        event_key, source_table, source_id, target_table, columns, rows, payload_hash
    ) VALUES (
        'weather:weather_events:' || projection_hash,
        'weather_observation', projection_hash, 'weather_events',
        '["timestamp","location_id","source","temperature_c","precipitation_mm","humidity_pct","wind_speed_kmh","solar_radiation_wm2","cloud_cover_pct","metadata"]'::JSONB,
        projection_rows, projection_hash
    ) ON CONFLICT (event_key) DO UPDATE
       SET updated_at = statement_timestamp()
     WHERE existing_outbox.payload_hash = EXCLUDED.payload_hash
       AND existing_outbox.source_table = EXCLUDED.source_table
       AND existing_outbox.source_id = EXCLUDED.source_id
       AND existing_outbox.target_table = EXCLUDED.target_table
       AND existing_outbox.columns = EXCLUDED.columns
       AND existing_outbox.rows = EXCLUDED.rows
    RETURNING id INTO outbox_id;
    IF outbox_id IS NULL THEN
        RAISE EXCEPTION 'current-weather outbox key conflicts with a different payload';
    END IF;

    INSERT INTO kokonut_security.weather_observation_worker_receipt (
        location_id, provider_payload_hash, observation_id
    ) VALUES (
        worker_scope.location_id, requested_provider_payload_hash, saved_observation_id
    );

    observation_id := saved_observation_id;
    inserted := TRUE;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.weather_observation_location(UUID)
    OWNER TO kokonut_weather_observation_owner;
ALTER FUNCTION kokonut_security.store_weather_observation(
    UUID, JSONB, JSONB, TEXT, TEXT, TEXT, INTEGER, TEXT
) OWNER TO kokonut_weather_observation_owner;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_weather_observation_owner;
REVOKE ALL ON FUNCTION kokonut_security.weather_observation_location(UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.store_weather_observation(
    UUID, JSONB, JSONB, TEXT, TEXT, TEXT, INTEGER, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.weather_observation_location(UUID)
    TO kokonut_worker_execution;
GRANT EXECUTE ON FUNCTION kokonut_security.store_weather_observation(
    UUID, JSONB, JSONB, TEXT, TEXT, TEXT, INTEGER, TEXT
) TO kokonut_worker_execution;

COMMENT ON FUNCTION kokonut_security.weather_observation_location(UUID) IS
    'Returns coordinates only for the active location in the signed weather_observation/ingest worker transaction.';
COMMENT ON FUNCTION kokonut_security.store_weather_observation(
    UUID, JSONB, JSONB, TEXT, TEXT, TEXT, INTEGER, TEXT
) IS
    'Atomically inserts one signed current-weather observation, its ingestion audit, ClickHouse outbox intent, and an idempotency receipt.';

COMMIT;
