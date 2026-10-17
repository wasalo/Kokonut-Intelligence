-- Route native scheduled remote-sensing ingestion through a dedicated signed
-- location identity. Legacy/manual provider adapters remain available.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_remote_sensing_owner') THEN
        CREATE ROLE kokonut_remote_sensing_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_remote_sensing_owner'
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
               OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'remote-sensing function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_remote_sensing_login') THEN
        CREATE ROLE kokonut_remote_sensing_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_remote_sensing_login'
          AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
               OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'remote-sensing worker login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_remote_sensing_owner'
            OR member_role.rolname = 'kokonut_remote_sensing_owner'
            OR (member_role.rolname = 'kokonut_remote_sensing_login'
                AND (granted_role.rolname <> 'kokonut_worker_execution'
                     OR membership.admin_option OR membership.inherit_option
                     OR NOT membership.set_option))
    ) THEN
        RAISE EXCEPTION 'remote-sensing worker role membership is unexpected';
    END IF;
END;
$$;

GRANT kokonut_worker_execution TO kokonut_remote_sensing_login
    WITH INHERIT FALSE, SET TRUE;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_remote_sensing_login;
GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_remote_sensing_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_remote_sensing_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_remote_sensing_owner;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_remote_sensing_owner;

GRANT SELECT ON public.remote_sensing_job TO kokonut_remote_sensing_owner;
GRANT UPDATE (
    status, last_run_at, last_run_status, next_run_at, observations_fetched,
    attempt_count, lease_owner, lease_expires_at, last_error_class, last_error, updated_at
) ON public.remote_sensing_job TO kokonut_remote_sensing_owner;
GRANT SELECT (id, farm_id, boundary) ON public.plot TO kokonut_remote_sensing_owner;
GRANT SELECT (id, location_id) ON public.farm TO kokonut_remote_sensing_owner;
GRANT SELECT ON public.remote_sensing_observation TO kokonut_remote_sensing_owner;
GRANT INSERT (
    plot_id, location_id, observation_date, source, ndvi, ndre, evi, savi,
    canopy_cover_pct, canopy_height_m,
    cloud_cover_pct, metadata, ndwi, msavi, satvi, bsi, nbr2, ndti, lswi, brightness_index,
    tc_brightness, tc_greenness, tc_wetness, band_blue, band_green, band_red,
    band_nir, band_swir1, band_swir2, source_system, source_id, source_raw,
    schema_version
) ON public.remote_sensing_observation TO kokonut_remote_sensing_owner;
GRANT INSERT (
    job_id, provider, attempt_number, outcome, retryable, observations,
    error_message, started_at, finished_at, fallback_used, metadata
) ON public.remote_sensing_provider_attempt TO kokonut_remote_sensing_owner;
GRANT INSERT (
    source_system, source_table, source_id, target_table, target_id, operation,
    payload_hash, status, error_message, rows_affected, processor_version, location_id
) ON public.ingestion_log TO kokonut_remote_sensing_owner;
GRANT SELECT (
    id, event_key, source_table, source_id, target_table, columns, rows, payload_hash
) ON public.clickhouse_outbox TO kokonut_remote_sensing_owner;
GRANT INSERT (
    event_key, source_table, source_id, target_table, columns, rows, payload_hash
) ON public.clickhouse_outbox TO kokonut_remote_sensing_owner;
GRANT UPDATE (updated_at) ON public.clickhouse_outbox TO kokonut_remote_sensing_owner;

-- Future forced-RLS deployments keep these security-definer operations usable.
-- This migration deliberately does not enable RLS on shared application tables.
DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'remote_sensing_job', 'remote_sensing_observation',
        'remote_sensing_provider_attempt', 'farm', 'plot', 'ingestion_log',
        'clickhouse_outbox'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = table_name
               AND policyname = 'remote_sensing_owner_bounded_access'
        ) THEN
            EXECUTE format(
                'CREATE POLICY remote_sensing_owner_bounded_access ON public.%I '
                || 'FOR ALL TO kokonut_remote_sensing_owner USING (true) WITH CHECK (true)',
                table_name
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.claim_remote_sensing_job(
    requested_location_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    claimed public.remote_sensing_job%ROWTYPE;
    bounds RECORD;
BEGIN
    IF session_user <> 'kokonut_remote_sensing_login' THEN
        RAISE EXCEPTION 'remote-sensing claim requires its dedicated login'
            USING ERRCODE = '42501';
    END IF;
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('remote_sensing', 'run') AS scope;
    IF NOT FOUND OR requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'signed remote-sensing location scope is required'
            USING ERRCODE = '42501';
    END IF;

    SELECT job.* INTO claimed
      FROM public.remote_sensing_job AS job
     WHERE job.location_id = worker_scope.location_id
       AND job.provider IN ('gee', 'copernicus')
       AND job.status = 'active'
       AND (job.next_run_at IS NULL OR job.next_run_at <= statement_timestamp())
       AND (job.lease_expires_at IS NULL OR job.lease_expires_at <= statement_timestamp())
       AND (job.plot_id IS NULL OR EXISTS (
           SELECT 1 FROM public.plot AS plot
           JOIN public.farm AS farm ON farm.id = plot.farm_id
           WHERE plot.id = job.plot_id AND farm.location_id = worker_scope.location_id
       ))
     ORDER BY job.next_run_at NULLS FIRST, job.id
     LIMIT 1
     FOR UPDATE SKIP LOCKED;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    UPDATE public.remote_sensing_job AS job
       SET lease_owner = 'remote-sensing-' || pg_catalog.gen_random_uuid()::TEXT,
           lease_expires_at = statement_timestamp() + INTERVAL '30 minutes',
           attempt_count = COALESCE(job.attempt_count, 0) + 1,
           updated_at = statement_timestamp()
     WHERE job.id = claimed.id
     RETURNING job.* INTO claimed;

    IF claimed.bbox IS NOT NULL THEN
        SELECT public.ST_XMin(public.ST_Extent(claimed.bbox))::DOUBLE PRECISION AS west,
               public.ST_YMin(public.ST_Extent(claimed.bbox))::DOUBLE PRECISION AS south,
               public.ST_XMax(public.ST_Extent(claimed.bbox))::DOUBLE PRECISION AS east,
               public.ST_YMax(public.ST_Extent(claimed.bbox))::DOUBLE PRECISION AS north
          INTO bounds;
    ELSE
        SELECT public.ST_XMin(public.ST_Extent(plot.boundary))::DOUBLE PRECISION AS west,
               public.ST_YMin(public.ST_Extent(plot.boundary))::DOUBLE PRECISION AS south,
               public.ST_XMax(public.ST_Extent(plot.boundary))::DOUBLE PRECISION AS east,
               public.ST_YMax(public.ST_Extent(plot.boundary))::DOUBLE PRECISION AS north
          INTO bounds
          FROM public.plot AS plot
          JOIN public.farm AS farm ON farm.id = plot.farm_id
         WHERE farm.location_id = worker_scope.location_id
           AND plot.boundary IS NOT NULL
           AND (claimed.plot_id IS NULL OR plot.id = claimed.plot_id);
    END IF;

    RETURN jsonb_build_object(
        'id', claimed.id,
        'location_id', claimed.location_id,
        'plot_id', claimed.plot_id,
        'provider', claimed.provider,
        'cadence_days', claimed.cadence_days,
        'cloud_max_pct', claimed.cloud_max_pct,
        'metadata', COALESCE(claimed.metadata, '{}'::JSONB),
        'lease_owner', claimed.lease_owner,
        'attempt_count', claimed.attempt_count,
        'bbox', CASE WHEN bounds.west IS NULL THEN NULL ELSE jsonb_build_object(
            'west', bounds.west, 'south', bounds.south,
            'east', bounds.east, 'north', bounds.north
        ) END
    );
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.finish_remote_sensing_job(
    requested_job_id UUID,
    requested_location_id UUID,
    requested_lease_owner TEXT,
    requested_attempts JSONB,
    requested_observations JSONB
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    job_row public.remote_sensing_job%ROWTYPE;
    attempt_item JSONB;
    observation_item JSONB;
    observation_row public.remote_sensing_observation%ROWTYPE;
    attempt_index INTEGER := 0;
    attempt_base INTEGER;
    record_count INTEGER;
    attempt_started_at TIMESTAMPTZ;
    attempt_finished_at TIMESTAMPTZ;
    written_count INTEGER := 0;
    record_plot_id UUID;
    record_source TEXT;
    record_source_system TEXT;
    record_source_id TEXT;
    record_metadata JSONB;
    record_date DATE;
    outcome TEXT;
    final_attempt JSONB;
    error_text TEXT;
    projection_columns JSONB;
    projection_row JSONB;
    projection_hash TEXT;
    outbox_id UUID;
    created BOOLEAN;
BEGIN
    IF session_user <> 'kokonut_remote_sensing_login' THEN
        RAISE EXCEPTION 'remote-sensing persistence requires its dedicated login'
            USING ERRCODE = '42501';
    END IF;
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('remote_sensing', 'run') AS scope;
    IF NOT FOUND OR requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'signed remote-sensing location scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_job_id IS NULL OR requested_lease_owner IS NULL
       OR length(requested_lease_owner) > 150
       OR jsonb_typeof(requested_attempts) IS DISTINCT FROM 'array'
       OR jsonb_array_length(requested_attempts) NOT BETWEEN 1 AND 2
       OR jsonb_typeof(requested_observations) IS DISTINCT FROM 'array'
       OR jsonb_array_length(requested_observations) > 5
       OR octet_length(requested_attempts::TEXT || requested_observations::TEXT) > 1048576 THEN
        RAISE EXCEPTION 'remote-sensing result batch is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT job.* INTO job_row
      FROM public.remote_sensing_job AS job
     WHERE job.id = requested_job_id
       AND job.location_id = worker_scope.location_id
       AND job.lease_owner = requested_lease_owner
       AND job.lease_expires_at > statement_timestamp()
     FOR UPDATE;
    IF NOT FOUND OR job_row.status <> 'active'
       OR job_row.attempt_count < 1 THEN
        RAISE EXCEPTION 'remote-sensing lease is absent, expired, or outside signed scope'
            USING ERRCODE = '42501';
    END IF;
    IF job_row.plot_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.plot AS plot
        JOIN public.farm AS farm ON farm.id = plot.farm_id
        WHERE plot.id = job_row.plot_id AND farm.location_id = worker_scope.location_id
    ) THEN
        RAISE EXCEPTION 'remote-sensing plot is outside signed location scope'
            USING ERRCODE = '42501';
    END IF;

    final_attempt := requested_attempts -> (jsonb_array_length(requested_attempts) - 1);
    outcome := final_attempt ->> 'outcome';
    IF outcome IS NULL OR outcome NOT IN ('success', 'no_data', 'retryable', 'non_retryable')
       OR jsonb_array_length(requested_observations) > 0
          AND outcome NOT IN ('success') THEN
        RAISE EXCEPTION 'remote-sensing final outcome is invalid'
            USING ERRCODE = '22023';
    END IF;
    record_count := jsonb_array_length(requested_observations);
    IF record_count <> COALESCE((final_attempt ->> 'observations')::INTEGER, -1)
       OR (outcome = 'no_data' AND record_count <> 0)
       OR (outcome IN ('retryable', 'non_retryable') AND record_count <> 0) THEN
        RAISE EXCEPTION 'remote-sensing result count does not match its final attempt'
            USING ERRCODE = '22023';
    END IF;

    attempt_base := (job_row.attempt_count - 1) * 2;
    FOR attempt_item IN SELECT value FROM jsonb_array_elements(requested_attempts)
    LOOP
        attempt_index := attempt_index + 1;
        IF jsonb_typeof(attempt_item) IS DISTINCT FROM 'object'
           OR attempt_item - ARRAY[
               'provider', 'outcome', 'retryable', 'observations', 'message',
               'fallback_used', 'metadata', 'started_at', 'finished_at'
           ] <> '{}'::JSONB
           OR attempt_item ->> 'provider' IS NULL
           OR attempt_item ->> 'provider' NOT IN ('gee', 'copernicus')
           OR attempt_item ->> 'outcome' IS NULL
           OR attempt_item ->> 'outcome' NOT IN ('success', 'no_data', 'retryable', 'non_retryable')
           OR jsonb_typeof(attempt_item -> 'retryable') IS DISTINCT FROM 'boolean'
           OR jsonb_typeof(attempt_item -> 'observations') IS DISTINCT FROM 'number'
           OR (attempt_item ->> 'observations')::INTEGER NOT BETWEEN 0 AND 5
           OR jsonb_typeof(attempt_item -> 'fallback_used') IS DISTINCT FROM 'boolean'
           OR jsonb_typeof(attempt_item -> 'started_at') IS DISTINCT FROM 'string'
           OR jsonb_typeof(attempt_item -> 'finished_at') IS DISTINCT FROM 'string'
           OR (attempt_index = 1 AND (attempt_item ->> 'provider') <> job_row.provider)
           OR (attempt_index = 1 AND (attempt_item ->> 'fallback_used')::BOOLEAN)
           OR (attempt_index = 2 AND NOT (attempt_item ->> 'fallback_used')::BOOLEAN)
           OR (attempt_index = 2 AND (attempt_item ->> 'provider') = job_row.provider)
           OR COALESCE(jsonb_typeof(attempt_item -> 'metadata'), 'object') <> 'object'
        THEN
            RAISE EXCEPTION 'remote-sensing provider attempt is invalid'
                USING ERRCODE = '22023';
        END IF;
        IF (attempt_item ->> 'retryable')::BOOLEAN
           IS DISTINCT FROM ((attempt_item ->> 'outcome') = 'retryable') THEN
            RAISE EXCEPTION 'remote-sensing retry flag conflicts with its outcome'
                USING ERRCODE = '22023';
        END IF;
        attempt_started_at := (attempt_item ->> 'started_at')::TIMESTAMPTZ;
        attempt_finished_at := (attempt_item ->> 'finished_at')::TIMESTAMPTZ;
        IF attempt_finished_at < attempt_started_at
           OR attempt_finished_at > statement_timestamp() + INTERVAL '5 seconds'
           OR attempt_started_at < statement_timestamp() - INTERVAL '35 minutes' THEN
            RAISE EXCEPTION 'remote-sensing attempt timestamps are outside the active lease window'
                USING ERRCODE = '22023';
        END IF;
        INSERT INTO public.remote_sensing_provider_attempt (
            job_id, provider, attempt_number, outcome, retryable, observations,
            error_message, started_at, finished_at, fallback_used, metadata
        ) VALUES (
            job_row.id, attempt_item ->> 'provider', attempt_base + attempt_index,
            attempt_item ->> 'outcome', (attempt_item ->> 'retryable')::BOOLEAN,
            (attempt_item ->> 'observations')::INTEGER,
            NULLIF(left(attempt_item ->> 'message', 2000), ''),
            attempt_started_at, attempt_finished_at,
            (attempt_item ->> 'fallback_used')::BOOLEAN,
            COALESCE(attempt_item -> 'metadata', '{}'::JSONB)
        );
    END LOOP;
    IF (requested_attempts -> 0 ->> 'provider') <> job_row.provider
       OR (jsonb_array_length(requested_attempts) = 2
           AND (requested_attempts -> 0 ->> 'outcome') <> 'retryable') THEN
        RAISE EXCEPTION 'remote-sensing fallback sequence is invalid'
            USING ERRCODE = '22023';
    END IF;

    FOR observation_item IN SELECT value FROM jsonb_array_elements(requested_observations)
    LOOP
        IF jsonb_typeof(observation_item) IS DISTINCT FROM 'object'
           OR observation_item - ARRAY[
               'plot_id', 'location_id', 'observation_date', 'source', 'ndvi', 'ndre',
               'evi', 'savi', 'canopy_cover_pct', 'canopy_height_m', 'ndwi',
               'cloud_cover_pct', 'satvi', 'bsi', 'nbr2', 'ndti', 'lswi',
               'brightness_index', 'tc_brightness', 'tc_greenness', 'tc_wetness',
               'band_blue', 'band_green', 'band_red', 'band_nir', 'band_swir1',
               'band_swir2', 'source_system', 'source_id', 'metadata'
           ] <> '{}'::JSONB
           OR observation_item ->> 'location_id' IS DISTINCT FROM worker_scope.location_id::TEXT
           OR NULLIF(observation_item ->> 'source_id', '') IS NULL
           OR length(observation_item ->> 'source_id') > 255
           OR observation_item ->> 'source' IS DISTINCT FROM 'sentinel-2'
           OR observation_item ->> 'source_system' IS NULL
           OR observation_item ->> 'source_system' NOT IN ('gee_api', 'copernicus_api')
           OR jsonb_typeof(observation_item -> 'metadata') IS DISTINCT FROM 'object'
        THEN
            RAISE EXCEPTION 'remote-sensing observation is outside the accepted record contract'
                USING ERRCODE = '22023';
        END IF;
        record_plot_id := NULLIF(observation_item ->> 'plot_id', '')::UUID;
        IF record_plot_id IS DISTINCT FROM job_row.plot_id THEN
            RAISE EXCEPTION 'remote-sensing observation plot differs from its job'
                USING ERRCODE = '42501';
        END IF;
        record_source := observation_item ->> 'source';
        record_source_system := observation_item ->> 'source_system';
        record_source_id := observation_item ->> 'source_id';
        IF ((final_attempt ->> 'provider') = 'gee' AND record_source_system <> 'gee_api')
           OR ((final_attempt ->> 'provider') = 'copernicus'
               AND record_source_system <> 'copernicus_api') THEN
            RAISE EXCEPTION 'remote-sensing record source differs from its final provider'
                USING ERRCODE = '22023';
        END IF;
        record_date := (observation_item ->> 'observation_date')::DATE;
        record_metadata := observation_item -> 'metadata';

        INSERT INTO public.remote_sensing_observation (
            plot_id, location_id, observation_date, source, ndvi, ndre, evi, savi,
            canopy_cover_pct, canopy_height_m,
            cloud_cover_pct, metadata, ndwi, msavi, satvi, bsi, nbr2, ndti, lswi,
            brightness_index, tc_brightness, tc_greenness, tc_wetness,
            band_blue, band_green, band_red, band_nir, band_swir1, band_swir2,
            source_system, source_id, source_raw, schema_version
        ) VALUES (
            record_plot_id, worker_scope.location_id, record_date, record_source,
            NULLIF(observation_item ->> 'ndvi', '')::NUMERIC,
            NULLIF(observation_item ->> 'ndre', '')::NUMERIC,
            NULLIF(observation_item ->> 'evi', '')::NUMERIC,
            NULLIF(observation_item ->> 'savi', '')::NUMERIC,
            NULLIF(observation_item ->> 'canopy_cover_pct', '')::NUMERIC,
            NULLIF(observation_item ->> 'canopy_height_m', '')::NUMERIC,
            NULLIF(observation_item ->> 'cloud_cover_pct', '')::NUMERIC,
            record_metadata,
            NULLIF(observation_item ->> 'ndwi', '')::NUMERIC,
            NULLIF(observation_item ->> 'msavi', '')::NUMERIC,
            NULLIF(observation_item ->> 'satvi', '')::NUMERIC,
            NULLIF(observation_item ->> 'bsi', '')::NUMERIC,
            NULLIF(observation_item ->> 'nbr2', '')::NUMERIC,
            NULLIF(observation_item ->> 'ndti', '')::NUMERIC,
            NULLIF(observation_item ->> 'lswi', '')::NUMERIC,
            NULLIF(observation_item ->> 'brightness_index', '')::NUMERIC,
            NULLIF(observation_item ->> 'tc_brightness', '')::NUMERIC,
            NULLIF(observation_item ->> 'tc_greenness', '')::NUMERIC,
            NULLIF(observation_item ->> 'tc_wetness', '')::NUMERIC,
            NULLIF(observation_item ->> 'band_blue', '')::NUMERIC,
            NULLIF(observation_item ->> 'band_green', '')::NUMERIC,
            NULLIF(observation_item ->> 'band_red', '')::NUMERIC,
            NULLIF(observation_item ->> 'band_nir', '')::NUMERIC,
            NULLIF(observation_item ->> 'band_swir1', '')::NUMERIC,
            NULLIF(observation_item ->> 'band_swir2', '')::NUMERIC,
            record_source_system, record_source_id, observation_item, 'remote-sensing-v1'
        )
        ON CONFLICT (source_system, source_id) WHERE source_id IS NOT NULL DO NOTHING
        RETURNING * INTO observation_row;
        created := FOUND;
        IF NOT created THEN
            SELECT observation.* INTO observation_row
              FROM public.remote_sensing_observation AS observation
             WHERE observation.source_system = record_source_system
               AND observation.source_id = record_source_id;
            IF NOT FOUND OR observation_row.location_id IS DISTINCT FROM worker_scope.location_id
               OR observation_row.plot_id IS DISTINCT FROM job_row.plot_id THEN
                RAISE EXCEPTION 'remote-sensing replay identity belongs to another scope'
                    USING ERRCODE = '23505';
            END IF;
        ELSE
            IF record_source_system = 'gee_api' THEN
                projection_columns := jsonb_build_array(
                    'timestamp', 'observation_id', 'location_id', 'plot_id', 'source',
                    'ndvi', 'ndre', 'evi', 'savi', 'canopy_cover_pct', 'ndwi',
                    'cloud_cover_pct', 'msavi', 'satvi', 'bsi', 'nbr2', 'ndti', 'lswi',
                    'brightness_index', 'tc_brightness', 'tc_greenness', 'tc_wetness',
                    'band_blue', 'band_green', 'band_red', 'band_nir', 'band_swir1',
                    'band_swir2', 'source_system', 'metadata'
                );
                projection_row := jsonb_build_array(
                    observation_row.observation_date::TEXT || ' 00:00:00.000',
                    observation_row.id::TEXT, worker_scope.location_id::TEXT,
                    COALESCE(observation_row.plot_id::TEXT, ''), observation_row.source,
                    observation_row.ndvi, observation_row.ndre, observation_row.evi,
                    observation_row.savi, observation_row.canopy_cover_pct,
                    observation_row.ndwi, observation_row.cloud_cover_pct, NULL,
                    observation_row.satvi, observation_row.bsi, observation_row.nbr2,
                    observation_row.ndti, observation_row.lswi,
                    observation_row.brightness_index, observation_row.tc_brightness,
                    observation_row.tc_greenness, observation_row.tc_wetness,
                    observation_row.band_blue, observation_row.band_green,
                    observation_row.band_red, observation_row.band_nir,
                    observation_row.band_swir1, observation_row.band_swir2,
                    record_source_system, '{}'::JSONB
                );
            ELSE
                projection_columns := jsonb_build_array(
                    'timestamp', 'observation_id', 'location_id', 'plot_id', 'source',
                    'cloud_cover_pct', 'source_system', 'metadata'
                );
                projection_row := jsonb_build_array(
                    observation_row.observation_date::TEXT || ' 00:00:00.000',
                    observation_row.id::TEXT, worker_scope.location_id::TEXT,
                    COALESCE(observation_row.plot_id::TEXT, ''), observation_row.source,
                    observation_row.cloud_cover_pct, record_source_system, '{}'::JSONB
                );
            END IF;
            projection_hash := encode(public.digest(
                convert_to(projection_row::TEXT, 'UTF8'), 'sha256'
            ), 'hex');
            outbox_id := NULL;
            INSERT INTO public.clickhouse_outbox (
                event_key, source_table, source_id, target_table, columns, rows, payload_hash
            ) VALUES (
                'remote_sensing:remote_sensing_events:' || observation_row.id::TEXT,
                'remote_sensing_observation', observation_row.id::TEXT,
                'remote_sensing_events', projection_columns,
                jsonb_build_array(projection_row), projection_hash
            )
            ON CONFLICT (event_key) DO UPDATE SET updated_at = statement_timestamp()
            WHERE public.clickhouse_outbox.payload_hash = EXCLUDED.payload_hash
              AND public.clickhouse_outbox.source_table = EXCLUDED.source_table
              AND public.clickhouse_outbox.source_id = EXCLUDED.source_id
              AND public.clickhouse_outbox.target_table = EXCLUDED.target_table
              AND public.clickhouse_outbox.columns = EXCLUDED.columns
              AND public.clickhouse_outbox.rows = EXCLUDED.rows
            RETURNING id INTO outbox_id;
            IF outbox_id IS NULL THEN
                RAISE EXCEPTION 'remote-sensing projection conflicts with an existing outbox event'
                    USING ERRCODE = '23505';
            END IF;
            INSERT INTO public.ingestion_log (
                source_system, source_table, source_id, target_table, target_id,
                operation, payload_hash, status, rows_affected, processor_version, location_id
            ) VALUES (
                record_source_system,
                CASE record_source_system WHEN 'gee_api' THEN 'sentinel2' ELSE 'sentinel2_product' END,
                record_source_id, 'remote_sensing_observation', observation_row.id,
                'insert', encode(public.digest(convert_to(observation_item::TEXT, 'UTF8'), 'sha256'), 'hex'),
                'success', 1, 'remote-sensing-v1', worker_scope.location_id
            );
            written_count := written_count + 1;
        END IF;
    END LOOP;

    error_text := NULLIF(left(final_attempt ->> 'message', 2000), '');
    UPDATE public.remote_sensing_job
       SET status = CASE WHEN outcome = 'non_retryable' THEN 'error' ELSE 'active' END,
           last_run_at = statement_timestamp(),
           last_run_status = CASE WHEN outcome IN ('success', 'no_data') THEN 'success' ELSE 'error' END,
           observations_fetched = COALESCE(observations_fetched, 0)
               + (final_attempt ->> 'observations')::INTEGER,
           next_run_at = CASE
               WHEN outcome = 'retryable' THEN statement_timestamp() + INTERVAL '15 minutes'
               ELSE statement_timestamp() + make_interval(days => cadence_days)
           END,
           lease_owner = NULL,
           lease_expires_at = NULL,
           last_error_class = CASE WHEN outcome IN ('success', 'no_data') THEN NULL ELSE outcome END,
           last_error = CASE WHEN outcome IN ('success', 'no_data') THEN NULL ELSE error_text END,
           updated_at = statement_timestamp()
     WHERE id = job_row.id AND location_id = worker_scope.location_id
       AND lease_owner = requested_lease_owner;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'remote-sensing lease changed before completion'
            USING ERRCODE = '40001';
    END IF;
    RETURN written_count;
END;
$$;

ALTER FUNCTION kokonut_security.claim_remote_sensing_job(UUID)
    OWNER TO kokonut_remote_sensing_owner;
ALTER FUNCTION kokonut_security.finish_remote_sensing_job(UUID, UUID, TEXT, JSONB, JSONB)
    OWNER TO kokonut_remote_sensing_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_remote_sensing_owner;
REVOKE ALL ON FUNCTION kokonut_security.claim_remote_sensing_job(UUID)
    FROM PUBLIC, kokonut_runtime, kokonut_worker_login,
         kokonut_worker_execution, kokonut_remote_sensing_login;
REVOKE ALL ON FUNCTION kokonut_security.finish_remote_sensing_job(UUID, UUID, TEXT, JSONB, JSONB)
    FROM PUBLIC, kokonut_runtime, kokonut_worker_login,
         kokonut_worker_execution, kokonut_remote_sensing_login;
GRANT EXECUTE ON FUNCTION kokonut_security.claim_remote_sensing_job(UUID),
    kokonut_security.finish_remote_sensing_job(UUID, UUID, TEXT, JSONB, JSONB)
    TO kokonut_worker_execution;

DO $$
DECLARE
    role_name TEXT;
    target_table RECORD;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_worker_execution', 'kokonut_remote_sensing_login'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.remote_sensing_job, '
                || 'public.remote_sensing_observation, public.remote_sensing_provider_attempt, '
                || 'public.farm, public.plot, public.ingestion_log, public.clickhouse_outbox FROM %I',
                role_name
            );
            FOR target_table IN
                SELECT relation.relname,
                       string_agg(quote_ident(attribute.attname), ', ' ORDER BY attribute.attnum) AS columns
                  FROM pg_class AS relation
                  JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                  JOIN pg_attribute AS attribute ON attribute.attrelid = relation.oid
                 WHERE namespace.nspname = 'public'
                   AND relation.relname IN (
                       'remote_sensing_job', 'remote_sensing_observation',
                       'remote_sensing_provider_attempt', 'farm', 'plot',
                       'ingestion_log', 'clickhouse_outbox'
                   )
                   AND attribute.attnum > 0 AND NOT attribute.attisdropped
                 GROUP BY relation.relname
            LOOP
                EXECUTE format(
                    'REVOKE ALL (%s) ON TABLE public.%I FROM %I',
                    target_table.columns, target_table.relname, role_name
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

ALTER TABLE public.remote_sensing_observation ALTER COLUMN plot_id DROP NOT NULL;

COMMIT;
