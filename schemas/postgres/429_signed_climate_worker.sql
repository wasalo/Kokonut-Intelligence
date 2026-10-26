-- Give scheduled climate refresh a dedicated signed identity. The function
-- owner, rather than the login or worker execution role, receives narrow
-- access to canonical location-level climate summaries and ingestion audit.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_climate_owner'
    ) THEN
        CREATE ROLE kokonut_climate_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_climate_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_climate_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_climate_owner'
            OR member_role.rolname = 'kokonut_climate_owner'
    ) THEN
        RAISE EXCEPTION 'climate function owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_climate_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_climate_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_climate_owner;

GRANT SELECT (id, status, center, latitude, longitude) ON public.location
    TO kokonut_climate_owner;
GRANT SELECT (id, location_id) ON public.farm TO kokonut_climate_owner;
GRANT SELECT (farm_id, boundary) ON public.plot TO kokonut_climate_owner;

GRANT SELECT (
    id, location_id, plot_id, bio1_mean_annual_temp, bio4_temp_seasonality,
    bio5_max_temp_warmest_month, bio6_min_temp_coldest_month,
    bio12_annual_precipitation, bio15_precip_seasonality,
    bio16_precip_wettest_quarter, bio17_precip_driest_quarter,
    temp_range, source, resolution_m, metadata, updated_at
) ON public.worldclim_climate TO kokonut_climate_owner;
GRANT INSERT (
    id, location_id, plot_id, bio1_mean_annual_temp, bio4_temp_seasonality,
    bio5_max_temp_warmest_month, bio6_min_temp_coldest_month,
    bio12_annual_precipitation, bio15_precip_seasonality,
    bio16_precip_wettest_quarter, bio17_precip_driest_quarter, temp_range,
    source, resolution_m, metadata
) ON public.worldclim_climate TO kokonut_climate_owner;
GRANT UPDATE (
    bio1_mean_annual_temp, bio4_temp_seasonality,
    bio5_max_temp_warmest_month, bio6_min_temp_coldest_month,
    bio12_annual_precipitation, bio15_precip_seasonality,
    bio16_precip_wettest_quarter, bio17_precip_driest_quarter, temp_range,
    source, resolution_m, metadata, updated_at
) ON public.worldclim_climate TO kokonut_climate_owner;

GRANT SELECT (
    id, location_id, plot_id, target_date, source, resolution_m,
    soil_moisture_6m, mean_temp_6m, max_temp_6m, min_temp_6m,
    precipitation_6m, metadata, updated_at
) ON public.ncep_weather_summary TO kokonut_climate_owner;
GRANT INSERT (
    id, location_id, plot_id, target_date, source, resolution_m,
    soil_moisture_6m, mean_temp_6m, max_temp_6m, min_temp_6m,
    precipitation_6m, metadata
) ON public.ncep_weather_summary TO kokonut_climate_owner;
GRANT UPDATE (
    resolution_m, soil_moisture_6m, mean_temp_6m, max_temp_6m,
    min_temp_6m, precipitation_6m, metadata, updated_at
) ON public.ncep_weather_summary TO kokonut_climate_owner;

GRANT SELECT (
    id, location_id, plot_id, target_date, source, resolution_m,
    lst_day_mean_6m, lst_night_mean_6m, metadata, updated_at
) ON public.modis_lst_summary TO kokonut_climate_owner;
GRANT INSERT (
    id, location_id, plot_id, target_date, source, resolution_m,
    lst_day_mean_6m, lst_night_mean_6m, metadata
) ON public.modis_lst_summary TO kokonut_climate_owner;
GRANT UPDATE (
    resolution_m, lst_day_mean_6m, lst_night_mean_6m, metadata, updated_at
) ON public.modis_lst_summary TO kokonut_climate_owner;

GRANT SELECT (
    id, location_id, plot_id, target_date, source, resolution_m,
    soil_moisture_6m, metadata, updated_at
) ON public.smap_soil_moisture TO kokonut_climate_owner;
GRANT INSERT (
    id, location_id, plot_id, target_date, source, resolution_m,
    soil_moisture_6m, metadata
) ON public.smap_soil_moisture TO kokonut_climate_owner;
GRANT UPDATE (
    resolution_m, soil_moisture_6m, metadata, updated_at
) ON public.smap_soil_moisture TO kokonut_climate_owner;

GRANT SELECT (
    id, location_id, plot_id, target_date, source, resolution_m,
    vh_median_6m, vv_median_6m, metadata, updated_at
) ON public.sentinel1_sar_summary TO kokonut_climate_owner;
GRANT INSERT (
    id, location_id, plot_id, target_date, source, resolution_m,
    vh_median_6m, vv_median_6m, metadata
) ON public.sentinel1_sar_summary TO kokonut_climate_owner;
GRANT UPDATE (
    resolution_m, vh_median_6m, vv_median_6m, metadata, updated_at
) ON public.sentinel1_sar_summary TO kokonut_climate_owner;

GRANT INSERT (
    source_system, source_table, source_id, target_table, target_id,
    operation, payload_hash, status, error_message, rows_affected,
    processing_time_ms, processor_version, location_id
) ON public.ingestion_log TO kokonut_climate_owner;

-- The runtime login is not a climate writer. The security-definer owner has
-- only the table/column privileges above and remains protected by forced RLS.
REVOKE ALL ON TABLE
    public.worldclim_climate,
    public.ncep_weather_summary,
    public.modis_lst_summary,
    public.smap_soil_moisture,
    public.sentinel1_sar_summary,
    public.ingestion_log
FROM kokonut_worker_execution;

DO $$
DECLARE
    target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'location', 'farm', 'plot',
        'worldclim_climate', 'ncep_weather_summary', 'modis_lst_summary',
        'smap_soil_moisture', 'sentinel1_sar_summary', 'ingestion_log'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public'
               AND tablename = target_table
               AND policyname = 'climate_owner_scoped_function_access'
        ) THEN
            EXECUTE format(
                'CREATE POLICY climate_owner_scoped_function_access ON public.%I '
                || 'FOR ALL TO kokonut_climate_owner USING (true) WITH CHECK (true)',
                target_table
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.climate_location(
    requested_location_id UUID
)
RETURNS TABLE(
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    west DOUBLE PRECISION,
    south DOUBLE PRECISION,
    east DOUBLE PRECISION,
    north DOUBLE PRECISION
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    location_latitude DOUBLE PRECISION;
    location_longitude DOUBLE PRECISION;
    bounds RECORD;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('climate', 'ingest') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed climate worker scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'climate location differs from signed worker scope'
            USING ERRCODE = '42501';
    END IF;

    SELECT COALESCE(public.ST_Y(location.center), location.latitude),
           COALESCE(public.ST_X(location.center), location.longitude)
      INTO location_latitude, location_longitude
      FROM public.location AS location
     WHERE location.id = worker_scope.location_id
       AND location.status = 'active'
       AND (location.center IS NOT NULL
            OR (location.latitude IS NOT NULL AND location.longitude IS NOT NULL));
    IF location_latitude IS NULL OR location_longitude IS NULL THEN
        RETURN;
    END IF;

    SELECT public.ST_XMin(public.ST_Extent(plot.boundary))::DOUBLE PRECISION AS west,
           public.ST_YMin(public.ST_Extent(plot.boundary))::DOUBLE PRECISION AS south,
           public.ST_XMax(public.ST_Extent(plot.boundary))::DOUBLE PRECISION AS east,
           public.ST_YMax(public.ST_Extent(plot.boundary))::DOUBLE PRECISION AS north
      INTO bounds
      FROM public.plot AS plot
      JOIN public.farm AS farm ON farm.id = plot.farm_id
     WHERE farm.location_id = worker_scope.location_id
       AND plot.boundary IS NOT NULL;

    latitude := location_latitude;
    longitude := location_longitude;
    west := COALESCE(bounds.west, location_longitude - 0.05);
    south := COALESCE(bounds.south, location_latitude - 0.05);
    east := COALESCE(bounds.east, location_longitude + 0.05);
    north := COALESCE(bounds.north, location_latitude + 0.05);
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_climate_summary(
    requested_location_id UUID,
    requested_source_key TEXT,
    climate_summary JSONB,
    processing_time_ms INTEGER,
    error_text TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    values_json JSONB;
    metadata_json JSONB;
    summary_id UUID;
    record_source TEXT;
    source_system TEXT;
    source_table TEXT;
    provider_source_id TEXT;
    target_table TEXT;
    summary_date DATE;
    resolution INTEGER;
    expected_keys TEXT[];
    actual_keys TEXT[];
    payload_hash TEXT;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('climate', 'ingest') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed climate worker scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'climate location differs from signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_source_key NOT IN (
        'worldclim', 'era5_land', 'modis_lst', 'smap_moisture', 'sentinel1_sar'
    ) THEN
        RAISE EXCEPTION 'climate source is not supported';
    END IF;
    IF processing_time_ms IS NULL OR processing_time_ms < 0
       OR processing_time_ms > 600000 THEN
        RAISE EXCEPTION 'climate processing time is outside the allowed range';
    END IF;

    IF error_text IS NOT NULL THEN
        IF climate_summary IS NOT NULL OR length(btrim(error_text)) = 0 THEN
            RAISE EXCEPTION 'failed climate source cannot include a summary';
        END IF;
        CASE requested_source_key
            WHEN 'worldclim' THEN
                source_system := 'latitude_proxy'; source_table := 'worldclim_climate';
                provider_source_id := 'latitude_proxy_v1'; target_table := 'worldclim_climate';
            WHEN 'era5_land' THEN
                source_system := 'gee_api'; source_table := 'era5_land';
                provider_source_id := 'ECMWF/ERA5_LAND/DAILY_AGGR'; target_table := 'ncep_weather_summary';
            WHEN 'modis_lst' THEN
                source_system := 'gee_api'; source_table := 'modis_lst';
                provider_source_id := 'MODIS/061/MOD11A2'; target_table := 'modis_lst_summary';
            WHEN 'smap_moisture' THEN
                source_system := 'gee_api'; source_table := 'smap_soil_moisture';
                provider_source_id := 'NASA/SMAP/SPL3SMP_E/006'; target_table := 'smap_soil_moisture';
            WHEN 'sentinel1_sar' THEN
                source_system := 'gee_api'; source_table := 'sentinel1_sar';
                provider_source_id := 'COPERNICUS/S1_GRD'; target_table := 'sentinel1_sar_summary';
        END CASE;
        INSERT INTO public.ingestion_log (
            source_system, source_table, source_id, target_table,
            operation, status, error_message, rows_affected,
            processing_time_ms, processor_version, location_id
        ) VALUES (
            source_system, source_table, provider_source_id, target_table,
            'upsert', 'failed', left(error_text, 2000), 0,
            processing_time_ms, '1.0.0', worker_scope.location_id
        );
        RETURN NULL;
    END IF;

    IF jsonb_typeof(climate_summary) IS DISTINCT FROM 'object'
       OR climate_summary->>'source_key' IS DISTINCT FROM requested_source_key
       OR jsonb_typeof(climate_summary->'values') IS DISTINCT FROM 'object'
       OR jsonb_typeof(climate_summary->'metadata') IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'climate summary payload is invalid';
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_object_keys(climate_summary) AS item(key)
         WHERE item.key <> ALL (ARRAY[
             'source_key', 'source_table', 'source_id', 'target_table',
             'target_date', 'resolution_m', 'values', 'metadata'
         ])
    ) THEN
        RAISE EXCEPTION 'climate summary contains unsupported fields';
    END IF;
    values_json := climate_summary->'values';
    metadata_json := climate_summary->'metadata';
    SELECT array_agg(item.key ORDER BY item.key COLLATE "C")
      INTO actual_keys
      FROM jsonb_object_keys(values_json) AS item(key);

    CASE requested_source_key
        WHEN 'worldclim' THEN
            expected_keys := ARRAY[
                'bio12_annual_precipitation',
                'bio15_precip_seasonality', 'bio16_precip_wettest_quarter',
                'bio17_precip_driest_quarter', 'bio1_mean_annual_temp',
                'bio4_temp_seasonality',
                'bio5_max_temp_warmest_month', 'bio6_min_temp_coldest_month',
                'temp_range'
            ];
            source_system := 'latitude_proxy'; source_table := 'worldclim_climate';
            provider_source_id := 'latitude_proxy_v1'; target_table := 'worldclim_climate';
            record_source := 'latitude_proxy_v1'; resolution := NULL;
            summary_date := NULL;
        WHEN 'era5_land' THEN
            expected_keys := ARRAY[
                'max_temp_6m', 'mean_temp_6m', 'min_temp_6m',
                'precipitation_6m', 'soil_moisture_6m'
            ];
            source_system := 'gee_api'; source_table := 'era5_land';
            provider_source_id := 'ECMWF/ERA5_LAND/DAILY_AGGR'; target_table := 'ncep_weather_summary';
            record_source := 'era5_land_daily_aggr'; resolution := 11132;
        WHEN 'modis_lst' THEN
            expected_keys := ARRAY['lst_day_mean_6m', 'lst_night_mean_6m'];
            source_system := 'gee_api'; source_table := 'modis_lst';
            provider_source_id := 'MODIS/061/MOD11A2'; target_table := 'modis_lst_summary';
            record_source := 'modis_mod11a2_v061'; resolution := 1000;
        WHEN 'smap_moisture' THEN
            expected_keys := ARRAY['soil_moisture_6m'];
            source_system := 'gee_api'; source_table := 'smap_soil_moisture';
            provider_source_id := 'NASA/SMAP/SPL3SMP_E/006'; target_table := 'smap_soil_moisture';
            record_source := 'smap_l3_enhanced_9km_v006'; resolution := 9000;
        WHEN 'sentinel1_sar' THEN
            expected_keys := ARRAY['vh_median_6m', 'vv_median_6m'];
            source_system := 'gee_api'; source_table := 'sentinel1_sar';
            provider_source_id := 'COPERNICUS/S1_GRD'; target_table := 'sentinel1_sar_summary';
            record_source := 'sentinel1_grd'; resolution := 10;
    END CASE;

    IF actual_keys IS DISTINCT FROM expected_keys THEN
        RAISE EXCEPTION 'climate summary fields do not match the % source contract (actual %, expected %)',
            requested_source_key, actual_keys, expected_keys;
    END IF;
    IF EXISTS (
        SELECT 1
          FROM jsonb_each(values_json) AS item(key, value)
         WHERE jsonb_typeof(item.value) NOT IN ('number', 'null')
    ) THEN
        RAISE EXCEPTION 'climate summary values must be numeric or null';
    END IF;
    IF requested_source_key = 'worldclim' THEN
        IF climate_summary->'target_date' IS DISTINCT FROM 'null'::JSONB
           OR climate_summary->'resolution_m' IS DISTINCT FROM 'null'::JSONB THEN
            RAISE EXCEPTION 'WorldClim proxy must not claim a target date or resolution';
        END IF;
    ELSE
        IF climate_summary->>'resolution_m' IS DISTINCT FROM resolution::TEXT
           OR climate_summary->>'target_date' IS NULL THEN
            RAISE EXCEPTION 'climate summary date or resolution violates the source contract';
        END IF;
            summary_date := (climate_summary->>'target_date')::DATE;
    END IF;

    payload_hash := encode(public.digest(convert_to(climate_summary::TEXT, 'UTF8'), 'sha256'), 'hex');
    CASE requested_source_key
        WHEN 'worldclim' THEN
            INSERT INTO public.worldclim_climate (
                id, location_id, plot_id, bio1_mean_annual_temp,
                bio4_temp_seasonality, bio5_max_temp_warmest_month,
                bio6_min_temp_coldest_month, bio12_annual_precipitation,
                bio15_precip_seasonality, bio16_precip_wettest_quarter,
                bio17_precip_driest_quarter, temp_range, source, resolution_m, metadata
            ) VALUES (
                gen_random_uuid(), worker_scope.location_id, NULL,
                (values_json->>'bio1_mean_annual_temp')::NUMERIC,
                (values_json->>'bio4_temp_seasonality')::NUMERIC,
                (values_json->>'bio5_max_temp_warmest_month')::NUMERIC,
                (values_json->>'bio6_min_temp_coldest_month')::NUMERIC,
                (values_json->>'bio12_annual_precipitation')::NUMERIC,
                (values_json->>'bio15_precip_seasonality')::NUMERIC,
                (values_json->>'bio16_precip_wettest_quarter')::NUMERIC,
                (values_json->>'bio17_precip_driest_quarter')::NUMERIC,
                (values_json->>'temp_range')::NUMERIC,
                record_source, resolution, metadata_json
            ) ON CONFLICT (location_id) WHERE plot_id IS NULL DO UPDATE SET
                bio1_mean_annual_temp = EXCLUDED.bio1_mean_annual_temp,
                bio4_temp_seasonality = EXCLUDED.bio4_temp_seasonality,
                bio5_max_temp_warmest_month = EXCLUDED.bio5_max_temp_warmest_month,
                bio6_min_temp_coldest_month = EXCLUDED.bio6_min_temp_coldest_month,
                bio12_annual_precipitation = EXCLUDED.bio12_annual_precipitation,
                bio15_precip_seasonality = EXCLUDED.bio15_precip_seasonality,
                bio16_precip_wettest_quarter = EXCLUDED.bio16_precip_wettest_quarter,
                bio17_precip_driest_quarter = EXCLUDED.bio17_precip_driest_quarter,
                temp_range = EXCLUDED.temp_range,
                source = EXCLUDED.source, resolution_m = EXCLUDED.resolution_m,
                metadata = EXCLUDED.metadata, updated_at = statement_timestamp()
            RETURNING id INTO summary_id;
        WHEN 'era5_land' THEN
            INSERT INTO public.ncep_weather_summary (
                id, location_id, plot_id, target_date, source, resolution_m,
                soil_moisture_6m, mean_temp_6m, max_temp_6m, min_temp_6m,
                precipitation_6m, metadata
            ) VALUES (
                gen_random_uuid(), worker_scope.location_id, NULL, summary_date,
                record_source, resolution,
                (values_json->>'soil_moisture_6m')::NUMERIC,
                (values_json->>'mean_temp_6m')::NUMERIC,
                (values_json->>'max_temp_6m')::NUMERIC,
                (values_json->>'min_temp_6m')::NUMERIC,
                (values_json->>'precipitation_6m')::NUMERIC, metadata_json
            ) ON CONFLICT (location_id, target_date, source)
                WHERE plot_id IS NULL AND source IS NOT NULL
            DO UPDATE SET resolution_m = EXCLUDED.resolution_m,
                soil_moisture_6m = EXCLUDED.soil_moisture_6m,
                mean_temp_6m = EXCLUDED.mean_temp_6m,
                max_temp_6m = EXCLUDED.max_temp_6m,
                min_temp_6m = EXCLUDED.min_temp_6m,
                precipitation_6m = EXCLUDED.precipitation_6m,
                metadata = EXCLUDED.metadata, updated_at = statement_timestamp()
            RETURNING id INTO summary_id;
        WHEN 'modis_lst' THEN
            INSERT INTO public.modis_lst_summary (
                id, location_id, plot_id, target_date, source, resolution_m,
                lst_day_mean_6m, lst_night_mean_6m, metadata
            ) VALUES (
                gen_random_uuid(), worker_scope.location_id, NULL, summary_date,
                record_source, resolution,
                (values_json->>'lst_day_mean_6m')::NUMERIC,
                (values_json->>'lst_night_mean_6m')::NUMERIC, metadata_json
            ) ON CONFLICT (location_id, target_date, source)
                WHERE plot_id IS NULL AND source IS NOT NULL
            DO UPDATE SET resolution_m = EXCLUDED.resolution_m,
                lst_day_mean_6m = EXCLUDED.lst_day_mean_6m,
                lst_night_mean_6m = EXCLUDED.lst_night_mean_6m,
                metadata = EXCLUDED.metadata, updated_at = statement_timestamp()
            RETURNING id INTO summary_id;
        WHEN 'smap_moisture' THEN
            INSERT INTO public.smap_soil_moisture (
                id, location_id, plot_id, target_date, source, resolution_m,
                soil_moisture_6m, metadata
            ) VALUES (
                gen_random_uuid(), worker_scope.location_id, NULL, summary_date,
                record_source, resolution,
                (values_json->>'soil_moisture_6m')::NUMERIC, metadata_json
            ) ON CONFLICT (location_id, target_date, source)
                WHERE plot_id IS NULL AND source IS NOT NULL
            DO UPDATE SET resolution_m = EXCLUDED.resolution_m,
                soil_moisture_6m = EXCLUDED.soil_moisture_6m,
                metadata = EXCLUDED.metadata, updated_at = statement_timestamp()
            RETURNING id INTO summary_id;
        WHEN 'sentinel1_sar' THEN
            INSERT INTO public.sentinel1_sar_summary (
                id, location_id, plot_id, target_date, source, resolution_m,
                vh_median_6m, vv_median_6m, metadata
            ) VALUES (
                gen_random_uuid(), worker_scope.location_id, NULL, summary_date,
                record_source, resolution,
                (values_json->>'vh_median_6m')::NUMERIC,
                (values_json->>'vv_median_6m')::NUMERIC, metadata_json
            ) ON CONFLICT (location_id, target_date, source)
                WHERE plot_id IS NULL AND source IS NOT NULL
            DO UPDATE SET resolution_m = EXCLUDED.resolution_m,
                vh_median_6m = EXCLUDED.vh_median_6m,
                vv_median_6m = EXCLUDED.vv_median_6m,
                metadata = EXCLUDED.metadata, updated_at = statement_timestamp()
            RETURNING id INTO summary_id;
    END CASE;

    INSERT INTO public.ingestion_log (
        source_system, source_table, source_id, target_table, target_id,
        operation, payload_hash, status, rows_affected, processing_time_ms,
        processor_version, location_id
    ) VALUES (
        source_system, source_table, provider_source_id, target_table,
        summary_id, 'upsert', payload_hash, 'success', 1,
        processing_time_ms, '1.0.0', worker_scope.location_id
    );
    RETURN summary_id;
END;
$$;

ALTER FUNCTION kokonut_security.climate_location(UUID)
    OWNER TO kokonut_climate_owner;
ALTER FUNCTION kokonut_security.store_climate_summary(UUID, TEXT, JSONB, INTEGER, TEXT)
    OWNER TO kokonut_climate_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_climate_owner;
REVOKE ALL ON FUNCTION kokonut_security.climate_location(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.store_climate_summary(UUID, TEXT, JSONB, INTEGER, TEXT)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.climate_location(UUID)
    TO kokonut_worker_execution;
GRANT EXECUTE ON FUNCTION kokonut_security.store_climate_summary(UUID, TEXT, JSONB, INTEGER, TEXT)
    TO kokonut_worker_execution;

COMMENT ON FUNCTION kokonut_security.climate_location(UUID) IS
    'Returns an active location point and plot-derived/fallback bbox only for a signed climate/ingest worker scope.';
COMMENT ON FUNCTION kokonut_security.store_climate_summary(UUID, TEXT, JSONB, INTEGER, TEXT) IS
    'Atomically upserts one whitelisted canonical climate summary and its ingestion audit within a signed climate/ingest location scope.';

COMMIT;
