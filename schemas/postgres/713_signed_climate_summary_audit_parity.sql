-- Preserve the legacy climate audit digest and zero-valued success timing
-- while routing all summary writes through the signed climate function owner.
-- Migration 429 remains immutable; this migration adds a compatible v2 entrypoint.

BEGIN;

ALTER TABLE public.ingestion_log
    ADD COLUMN IF NOT EXISTS execution_duration_ms INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.ingestion_log'::regclass
           AND conname = 'ingestion_log_execution_duration_ms_check'
    ) THEN
        ALTER TABLE public.ingestion_log
            ADD CONSTRAINT ingestion_log_execution_duration_ms_check
            CHECK (execution_duration_ms IS NULL
                   OR execution_duration_ms BETWEEN 0 AND 600000);
    END IF;
END;
$$;

GRANT INSERT (execution_duration_ms) ON public.ingestion_log
    TO kokonut_climate_owner;

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
       AND location.status = 'active';
    IF NOT FOUND THEN
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

CREATE OR REPLACE FUNCTION kokonut_security.store_climate_summary_v2(
    requested_location_id UUID,
    requested_source_key TEXT,
    climate_summary JSONB,
    legacy_audit_payload TEXT,
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
    audit_payload_json JSONB;
    expected_audit_payload JSONB;
    audit_keys TEXT[];
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
        IF climate_summary IS NOT NULL OR legacy_audit_payload IS NOT NULL
           OR length(btrim(error_text)) = 0 THEN
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
            processing_time_ms, execution_duration_ms, processor_version, location_id
        ) VALUES (
            source_system, source_table, provider_source_id, target_table,
            'upsert', 'failed', left(error_text, 2000), 0,
            processing_time_ms, processing_time_ms, '1.0.0', worker_scope.location_id
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

    IF legacy_audit_payload IS NULL THEN
        RAISE EXCEPTION 'climate legacy audit payload is required';
    END IF;
    BEGIN
        audit_payload_json := legacy_audit_payload::JSONB;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'climate legacy audit payload is invalid';
    END;
    IF jsonb_typeof(audit_payload_json) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'climate legacy audit payload must be an object';
    END IF;
    CASE requested_source_key
        WHEN 'worldclim' THEN
            expected_audit_payload := metadata_json->'estimated_bioclimatic_variables';
        WHEN 'era5_land' THEN
            expected_audit_payload := jsonb_build_object(
                'soil_moisture_6m_volume_fraction', values_json->'soil_moisture_6m',
                'mean_temp_6m_c', values_json->'mean_temp_6m',
                'max_temp_6m_c', values_json->'max_temp_6m',
                'min_temp_6m_c', values_json->'min_temp_6m',
                'precipitation_6m_mm', values_json->'precipitation_6m'
            );
        WHEN 'modis_lst' THEN
            expected_audit_payload := jsonb_build_object(
                'lst_day_mean_6m_c', values_json->'lst_day_mean_6m',
                'lst_night_mean_6m_c', values_json->'lst_night_mean_6m'
            );
        WHEN 'smap_moisture' THEN
            expected_audit_payload := jsonb_build_object(
                'soil_moisture_6m_volume_fraction', values_json->'soil_moisture_6m'
            );
        WHEN 'sentinel1_sar' THEN
            expected_audit_payload := jsonb_build_object(
                'vh_median_6m_db', values_json->'vh_median_6m',
                'vv_median_6m_db', values_json->'vv_median_6m'
            );
    END CASE;
    IF requested_source_key = 'worldclim' THEN
        SELECT array_agg(item.key ORDER BY item.key COLLATE "C")
          INTO audit_keys
          FROM jsonb_object_keys(expected_audit_payload) AS item(key);
        IF audit_keys IS DISTINCT FROM ARRAY[
            'bio_1', 'bio_10', 'bio_11', 'bio_12', 'bio_13', 'bio_14',
            'bio_15', 'bio_16', 'bio_17', 'bio_18', 'bio_19', 'bio_2',
            'bio_3', 'bio_4', 'bio_5', 'bio_6', 'bio_7', 'bio_8', 'bio_9'
        ] THEN
            RAISE EXCEPTION 'WorldClim audit payload fields do not match the legacy contract';
        END IF;
        IF EXISTS (
            SELECT 1 FROM jsonb_each(expected_audit_payload) AS item(key, value)
             WHERE jsonb_typeof(item.value) NOT IN ('number', 'null')
        ) OR expected_audit_payload->'bio_1' IS DISTINCT FROM values_json->'bio1_mean_annual_temp'
          OR expected_audit_payload->'bio_4' IS DISTINCT FROM values_json->'bio4_temp_seasonality'
          OR expected_audit_payload->'bio_5' IS DISTINCT FROM values_json->'bio5_max_temp_warmest_month'
          OR expected_audit_payload->'bio_6' IS DISTINCT FROM values_json->'bio6_min_temp_coldest_month'
          OR expected_audit_payload->'bio_7' IS DISTINCT FROM values_json->'temp_range'
          OR expected_audit_payload->'bio_12' IS DISTINCT FROM values_json->'bio12_annual_precipitation'
          OR expected_audit_payload->'bio_15' IS DISTINCT FROM values_json->'bio15_precip_seasonality'
          OR expected_audit_payload->'bio_16' IS DISTINCT FROM values_json->'bio16_precip_wettest_quarter'
          OR expected_audit_payload->'bio_17' IS DISTINCT FROM values_json->'bio17_precip_driest_quarter' THEN
            RAISE EXCEPTION 'WorldClim audit payload does not match the stored summary';
        END IF;
    END IF;
    IF expected_audit_payload IS NULL
       OR audit_payload_json IS DISTINCT FROM expected_audit_payload THEN
        RAISE EXCEPTION 'climate legacy audit payload does not match the validated summary';
    END IF;
    payload_hash := encode(
        public.digest(convert_to(legacy_audit_payload, 'UTF8'), 'sha256'), 'hex'
    );
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
        execution_duration_ms, processor_version, location_id
    ) VALUES (
        source_system, source_table, provider_source_id, target_table,
        summary_id, 'upsert', payload_hash, 'success', 1,
        0, processing_time_ms, '1.0.0', worker_scope.location_id
    );
    RETURN summary_id;
END;
$$;

ALTER FUNCTION kokonut_security.store_climate_summary_v2(
    UUID, TEXT, JSONB, TEXT, INTEGER, TEXT
) OWNER TO kokonut_climate_owner;
REVOKE ALL ON FUNCTION kokonut_security.store_climate_summary_v2(
    UUID, TEXT, JSONB, TEXT, INTEGER, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.store_climate_summary_v2(
    UUID, TEXT, JSONB, TEXT, INTEGER, TEXT
) TO kokonut_worker_execution;

COMMENT ON FUNCTION kokonut_security.store_climate_summary_v2(
    UUID, TEXT, JSONB, TEXT, INTEGER, TEXT
) IS
    'Atomically upserts one validated climate summary and audit within a signed location scope, preserving the legacy Python payload digest and recording elapsed duration separately.';

DO $$
DECLARE
    target_table TEXT;
    target_column TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'worldclim_climate',
        'ncep_weather_summary',
        'modis_lst_summary',
        'smap_soil_moisture',
        'sentinel1_sar_summary'
    ] LOOP
        EXECUTE format(
            'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
            || 'ON TABLE public.%I FROM kokonut_runtime',
            target_table
        );
        FOR target_column IN
            SELECT attribute.attname
              FROM pg_attribute AS attribute
             WHERE attribute.attrelid = format('public.%I', target_table)::regclass
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE format(
                'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                || 'ON TABLE public.%2$I FROM kokonut_runtime',
                target_column, target_table
            );
        END LOOP;
    END LOOP;
END;
$$;

COMMIT;
