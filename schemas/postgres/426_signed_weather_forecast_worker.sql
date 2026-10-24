-- Bound scheduled weather-forecast ingestion to one signed location grant.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_weather_forecast_owner'
    ) THEN
        CREATE ROLE kokonut_weather_forecast_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_weather_forecast_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_weather_forecast_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_weather_forecast_owner'
            OR member_role.rolname = 'kokonut_weather_forecast_owner'
    ) THEN
        RAISE EXCEPTION 'weather forecast function owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_weather_forecast_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_weather_forecast_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_weather_forecast_owner;

GRANT SELECT (id, name, status, center) ON public.location
    TO kokonut_weather_forecast_owner;
GRANT SELECT (
    location_id, forecast_date, forecast_hour, source, temp_c, temp_min_c,
    temp_max_c, feels_like_c, humidity_pct, precipitation_mm,
    precipitation_prob_pct, rain_3h_mm, wind_speed_kmh,
    wind_direction_deg, wind_gust_kmh, cloud_cover_pct, visibility_km,
    pressure_hpa, uv_index, description, metadata
)
    ON public.weather_forecast TO kokonut_weather_forecast_owner;
GRANT INSERT (
    location_id, source, forecast_date, forecast_hour, temp_c, temp_min_c,
    temp_max_c, feels_like_c, humidity_pct, precipitation_mm,
    precipitation_prob_pct, rain_3h_mm, wind_speed_kmh, wind_direction_deg,
    wind_gust_kmh, cloud_cover_pct, visibility_km, pressure_hpa, uv_index,
    description, metadata
) ON public.weather_forecast TO kokonut_weather_forecast_owner;
GRANT UPDATE (
    temp_c, temp_min_c, temp_max_c, feels_like_c, humidity_pct,
    precipitation_mm, precipitation_prob_pct, rain_3h_mm, wind_speed_kmh,
    wind_direction_deg, wind_gust_kmh, cloud_cover_pct, visibility_km,
    pressure_hpa, uv_index, description, metadata, created_at
) ON public.weather_forecast TO kokonut_weather_forecast_owner;
GRANT INSERT (
    source_system, source_table, source_id, target_table, target_id, operation,
    payload_hash, status, error_message, rows_affected, processing_time_ms,
    processor_version, location_id
) ON public.ingestion_log TO kokonut_weather_forecast_owner;
GRANT SELECT (id, event_key, source_table, source_id, target_table, columns, rows, payload_hash)
    ON public.clickhouse_outbox TO kokonut_weather_forecast_owner;
GRANT INSERT (
    event_key, source_table, source_id, target_table, columns, rows, payload_hash
) ON public.clickhouse_outbox TO kokonut_weather_forecast_owner;
GRANT UPDATE (updated_at) ON public.clickhouse_outbox
    TO kokonut_weather_forecast_owner;

-- Keep the bounded function owner usable after application tables enable
-- forced RLS. These policies do not enable RLS; the no-login owner is reachable
-- only through the signed SECURITY DEFINER functions below.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'location'
           AND policyname = 'weather_forecast_owner_location_read'
    ) THEN
        EXECUTE 'CREATE POLICY weather_forecast_owner_location_read ON public.location '
            || 'FOR SELECT TO kokonut_weather_forecast_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'weather_forecast'
           AND policyname = 'weather_forecast_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY weather_forecast_owner_read ON public.weather_forecast '
            || 'FOR SELECT TO kokonut_weather_forecast_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'weather_forecast'
           AND policyname = 'weather_forecast_owner_insert'
    ) THEN
        EXECUTE 'CREATE POLICY weather_forecast_owner_insert ON public.weather_forecast '
            || 'FOR INSERT TO kokonut_weather_forecast_owner WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'weather_forecast'
           AND policyname = 'weather_forecast_owner_update'
    ) THEN
        EXECUTE 'CREATE POLICY weather_forecast_owner_update ON public.weather_forecast '
            || 'FOR UPDATE TO kokonut_weather_forecast_owner USING (true) WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'ingestion_log'
           AND policyname = 'weather_forecast_owner_audit_insert'
    ) THEN
        EXECUTE 'CREATE POLICY weather_forecast_owner_audit_insert ON public.ingestion_log '
            || 'FOR INSERT TO kokonut_weather_forecast_owner WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'clickhouse_outbox'
           AND policyname = 'weather_forecast_owner_outbox_read'
    ) THEN
        EXECUTE 'CREATE POLICY weather_forecast_owner_outbox_read ON public.clickhouse_outbox '
            || 'FOR SELECT TO kokonut_weather_forecast_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'clickhouse_outbox'
           AND policyname = 'weather_forecast_owner_outbox_insert'
    ) THEN
        EXECUTE 'CREATE POLICY weather_forecast_owner_outbox_insert ON public.clickhouse_outbox '
            || 'FOR INSERT TO kokonut_weather_forecast_owner WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'clickhouse_outbox'
           AND policyname = 'weather_forecast_owner_outbox_update'
    ) THEN
        EXECUTE 'CREATE POLICY weather_forecast_owner_outbox_update ON public.clickhouse_outbox '
            || 'FOR UPDATE TO kokonut_weather_forecast_owner USING (true) WITH CHECK (true)';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.weather_forecast_location(
    requested_location_id UUID
)
RETURNS TABLE(location_id UUID, location_name TEXT, latitude DOUBLE PRECISION,
              longitude DOUBLE PRECISION)
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
          'weather_forecast', 'ingest'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed weather forecast worker scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'weather forecast location differs from signed worker scope'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT location.id, location.name::TEXT,
           public.ST_Y(location.center), public.ST_X(location.center)
      FROM public.location AS location
     WHERE location.id = worker_scope.location_id
       AND location.status = 'active'
       AND location.center IS NOT NULL;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_weather_forecast_batch(
    requested_location_id UUID,
    forecast_rows JSONB,
    projection_rows JSONB,
    projection_hash TEXT,
    provider_source_id TEXT,
    provider_payload_hash TEXT,
    processing_time_ms INTEGER,
    error_text TEXT DEFAULT NULL
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    inserted_rows INTEGER := 0;
    outbox_id UUID;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope(
          'weather_forecast', 'ingest'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed weather forecast worker scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'weather forecast location differs from signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF processing_time_ms IS NULL OR processing_time_ms < 0
       OR processing_time_ms > 600000 THEN
        RAISE EXCEPTION 'weather forecast processing time is outside the allowed range';
    END IF;
    IF provider_source_id IS NULL OR length(provider_source_id) > 255 THEN
        RAISE EXCEPTION 'weather forecast provider source ID is invalid';
    END IF;
    IF jsonb_typeof(forecast_rows) IS DISTINCT FROM 'array'
       OR jsonb_typeof(projection_rows) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'weather forecast batch must contain bounded JSON arrays';
    END IF;
    IF jsonb_array_length(forecast_rows) > 100 THEN
        RAISE EXCEPTION 'weather forecast batch exceeds the 100-row limit';
    END IF;

    IF error_text IS NOT NULL THEN
        IF jsonb_array_length(forecast_rows) <> 0
           OR jsonb_array_length(projection_rows) <> 0
           OR projection_hash IS NOT NULL THEN
            RAISE EXCEPTION 'failed weather fetch cannot include forecast rows';
        END IF;
        INSERT INTO public.ingestion_log (
            source_system, source_table, source_id, target_table, operation,
            payload_hash, status, error_message, rows_affected,
            processing_time_ms, processor_version, location_id
        ) VALUES (
            'openweathermap', 'forecast_api', '', 'weather_forecast', 'insert',
            NULL, 'failed', left(error_text, 2000), 0,
            processing_time_ms, '1.0.0', worker_scope.location_id
        );
        RETURN 0;
    END IF;

    IF provider_payload_hash IS NULL
       OR provider_payload_hash !~ '^[0-9a-f]{64}$'
       OR jsonb_array_length(projection_rows) <> jsonb_array_length(forecast_rows) THEN
        RAISE EXCEPTION 'weather forecast provider or projection payload is invalid';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM jsonb_array_elements(forecast_rows) AS entry(value)
         WHERE entry.value->>'location_id' IS DISTINCT FROM worker_scope.location_id::TEXT
            OR entry.value->>'source' IS DISTINCT FROM 'openweathermap'
            OR (entry.value ? 'metadata'
                AND jsonb_typeof(entry.value->'metadata') NOT IN ('object', 'null'))
    ) THEN
        RAISE EXCEPTION 'weather forecast rows do not match the signed location/source';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM jsonb_array_elements(projection_rows) AS entry(value)
         WHERE jsonb_typeof(entry.value) IS DISTINCT FROM 'array'
    ) THEN
        RAISE EXCEPTION 'weather projection rows must be arrays';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM jsonb_array_elements(projection_rows) AS entry(value)
         WHERE jsonb_array_length(entry.value) <> 10
            OR entry.value->>1 IS DISTINCT FROM worker_scope.location_id::TEXT
            OR entry.value->>2 IS DISTINCT FROM 'openweathermap_forecast'
    ) THEN
        RAISE EXCEPTION 'weather projection row violates its location or column contract';
    END IF;
    IF projection_hash IS NULL OR projection_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'weather projection hash is invalid';
    END IF;

    WITH source_rows AS (
        SELECT *
          FROM jsonb_to_recordset(forecast_rows) AS item(
              location_id TEXT, source TEXT, forecast_date DATE,
              forecast_hour INTEGER, temp_c NUMERIC, temp_min_c NUMERIC,
              temp_max_c NUMERIC, feels_like_c NUMERIC, humidity_pct NUMERIC,
              precipitation_mm NUMERIC, precipitation_prob_pct NUMERIC,
              rain_3h_mm NUMERIC, wind_speed_kmh NUMERIC,
              wind_direction_deg NUMERIC, wind_gust_kmh NUMERIC,
              cloud_cover_pct NUMERIC, visibility_km NUMERIC,
              pressure_hpa NUMERIC, uv_index NUMERIC, description TEXT,
              metadata JSONB
          )
    )
    INSERT INTO public.weather_forecast (
        location_id, source, forecast_date, forecast_hour, temp_c,
        temp_min_c, temp_max_c, feels_like_c, humidity_pct, precipitation_mm,
        precipitation_prob_pct, rain_3h_mm, wind_speed_kmh,
        wind_direction_deg, wind_gust_kmh, cloud_cover_pct, visibility_km,
        pressure_hpa, uv_index, description, metadata
    )
    SELECT source_rows.location_id::UUID, source_rows.source,
           source_rows.forecast_date, source_rows.forecast_hour,
           source_rows.temp_c, source_rows.temp_min_c, source_rows.temp_max_c,
           source_rows.feels_like_c, source_rows.humidity_pct,
           source_rows.precipitation_mm, source_rows.precipitation_prob_pct,
           source_rows.rain_3h_mm, source_rows.wind_speed_kmh,
           source_rows.wind_direction_deg, source_rows.wind_gust_kmh,
           source_rows.cloud_cover_pct, source_rows.visibility_km,
           source_rows.pressure_hpa, source_rows.uv_index,
           source_rows.description, COALESCE(source_rows.metadata, '{}'::JSONB)
      FROM source_rows
     WHERE source_rows.location_id::UUID = worker_scope.location_id
    ON CONFLICT (location_id, forecast_date, forecast_hour, source)
    DO UPDATE SET
        temp_c = EXCLUDED.temp_c,
        temp_min_c = EXCLUDED.temp_min_c,
        temp_max_c = EXCLUDED.temp_max_c,
        feels_like_c = EXCLUDED.feels_like_c,
        humidity_pct = EXCLUDED.humidity_pct,
        precipitation_mm = EXCLUDED.precipitation_mm,
        precipitation_prob_pct = EXCLUDED.precipitation_prob_pct,
        rain_3h_mm = EXCLUDED.rain_3h_mm,
        wind_speed_kmh = EXCLUDED.wind_speed_kmh,
        wind_direction_deg = EXCLUDED.wind_direction_deg,
        wind_gust_kmh = EXCLUDED.wind_gust_kmh,
        cloud_cover_pct = EXCLUDED.cloud_cover_pct,
        visibility_km = EXCLUDED.visibility_km,
        pressure_hpa = EXCLUDED.pressure_hpa,
        uv_index = EXCLUDED.uv_index,
        description = EXCLUDED.description,
        metadata = EXCLUDED.metadata,
        created_at = statement_timestamp();
    GET DIAGNOSTICS inserted_rows = ROW_COUNT;

    IF inserted_rows > 0 THEN
        INSERT INTO public.clickhouse_outbox AS existing_outbox (
            event_key, source_table, source_id, target_table, columns, rows,
            payload_hash
        ) VALUES (
            'weather_forecast:weather_events:' || projection_hash,
            'weather_forecast', projection_hash, 'weather_events',
            '["timestamp","location_id","source","temperature_c","precipitation_mm","humidity_pct","wind_speed_kmh","solar_radiation_wm2","cloud_cover_pct","metadata"]'::JSONB,
            projection_rows, projection_hash
        )
        ON CONFLICT (event_key) DO UPDATE SET updated_at = statement_timestamp()
        WHERE existing_outbox.payload_hash = EXCLUDED.payload_hash
          AND existing_outbox.source_table = EXCLUDED.source_table
          AND existing_outbox.source_id = EXCLUDED.source_id
          AND existing_outbox.target_table = EXCLUDED.target_table
          AND existing_outbox.columns = EXCLUDED.columns
          AND existing_outbox.rows = EXCLUDED.rows
        RETURNING id INTO outbox_id;
        IF outbox_id IS NULL THEN
            RAISE EXCEPTION 'weather forecast outbox key conflicts with a different payload';
        END IF;
    END IF;

    INSERT INTO public.ingestion_log (
        source_system, source_table, source_id, target_table, operation,
        payload_hash, status, rows_affected, processing_time_ms,
        processor_version, location_id
    ) VALUES (
        'openweathermap', 'forecast_api', provider_source_id,
        'weather_forecast', 'insert', provider_payload_hash, 'success',
        inserted_rows, processing_time_ms, '1.0.0', worker_scope.location_id
    );
    RETURN inserted_rows;
END;
$$;

ALTER FUNCTION kokonut_security.weather_forecast_location(UUID)
    OWNER TO kokonut_weather_forecast_owner;
ALTER FUNCTION kokonut_security.store_weather_forecast_batch(
    UUID, JSONB, JSONB, TEXT, TEXT, TEXT, INTEGER, TEXT
) OWNER TO kokonut_weather_forecast_owner;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_weather_forecast_owner;
REVOKE ALL ON FUNCTION kokonut_security.weather_forecast_location(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.store_weather_forecast_batch(
    UUID, JSONB, JSONB, TEXT, TEXT, TEXT, INTEGER, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.weather_forecast_location(UUID)
    TO kokonut_worker_execution;
GRANT EXECUTE ON FUNCTION kokonut_security.store_weather_forecast_batch(
    UUID, JSONB, JSONB, TEXT, TEXT, TEXT, INTEGER, TEXT
) TO kokonut_worker_execution;

COMMENT ON FUNCTION kokonut_security.weather_forecast_location(UUID) IS
    'Returns coordinates only for the active location in the signed weather_forecast/ingest worker transaction.';
COMMENT ON FUNCTION kokonut_security.store_weather_forecast_batch(
    UUID, JSONB, JSONB, TEXT, TEXT, TEXT, INTEGER, TEXT
) IS
    'Atomically upserts one signed location weather forecast batch, its ingestion audit row, and its canonical ClickHouse outbox intent.';

COMMIT;
