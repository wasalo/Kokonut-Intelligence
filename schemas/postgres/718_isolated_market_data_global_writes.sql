-- Extend the isolated market-data principal to the manual and reference-seed
-- writers. Both operations remain global reference data (location_id IS NULL).
-- The old persisted scheduled-task module remains supported by its existing
-- compatibility entrypoint; this migration does not rewrite task arguments.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_market_data_owner'
           AND NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb
           AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
           AND NOT rolinherit
    ) THEN
        RAISE EXCEPTION 'safe kokonut_market_data_owner role from migration 430 is required';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_market_data_login'
           AND NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb
           AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
           AND NOT rolinherit
    ) THEN
        RAISE EXCEPTION 'safe kokonut_market_data_login role from migration 430 is required';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
    ) THEN
        RAISE EXCEPTION 'kokonut_runtime role is required';
    END IF;
    IF pg_catalog.to_regclass('public.price_observation') IS NULL
       OR pg_catalog.to_regclass('public.crop') IS NULL
       OR pg_catalog.to_regclass('public.ingestion_log') IS NULL THEN
        RAISE EXCEPTION 'market-data tables from migrations 008, 010, and 142 are required';
    END IF;
END;
$$;

-- The function owner needs only the columns used by the two new operations.
-- SELECT(id) is required for the manual INSERT ... RETURNING; it is not exposed
-- to the dedicated login.
GRANT SELECT (id) ON public.price_observation TO kokonut_market_data_owner;
GRANT INSERT (location_id, quality_grade, created_at)
    ON public.price_observation TO kokonut_market_data_owner;

CREATE OR REPLACE FUNCTION kokonut_security.store_manual_market_price(
    requested_crop_name TEXT,
    requested_market_name TEXT,
    requested_price NUMERIC,
    requested_quality_grade TEXT,
    requested_unit TEXT,
    requested_currency TEXT,
    requested_metadata JSONB
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    crop_key UUID;
    inserted_id UUID;
    normalized_crop_name TEXT;
    normalized_market_name TEXT;
    normalized_quality_grade TEXT;
    normalized_unit TEXT;
    normalized_currency TEXT;
BEGIN
    IF session_user <> 'kokonut_market_data_login' THEN
        RAISE EXCEPTION 'manual market-price write requires its dedicated login'
            USING ERRCODE = '42501';
    END IF;

    normalized_crop_name := btrim(requested_crop_name);
    normalized_market_name := btrim(requested_market_name);
    normalized_unit := btrim(requested_unit);
    normalized_currency := btrim(requested_currency);
    normalized_quality_grade := CASE
        WHEN requested_quality_grade IS NULL THEN NULL
        ELSE btrim(requested_quality_grade)
    END;

    IF normalized_crop_name IS NULL
       OR length(normalized_crop_name) NOT BETWEEN 1 AND 200
       OR normalized_market_name IS NULL
       OR length(normalized_market_name) NOT BETWEEN 1 AND 100
       OR requested_price IS NULL
       OR requested_price <= 0
       OR requested_price >= 100000000
       OR normalized_unit IS NULL
       OR length(normalized_unit) NOT BETWEEN 1 AND 50
       OR normalized_currency IS NULL
       OR length(normalized_currency) NOT BETWEEN 1 AND 10
       OR (normalized_quality_grade IS NOT NULL
           AND length(normalized_quality_grade) NOT BETWEEN 1 AND 50)
       OR requested_metadata IS NULL
       OR pg_catalog.jsonb_typeof(requested_metadata) IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length(requested_metadata::TEXT) > 8192 THEN
        RAISE EXCEPTION 'manual market-price input is outside the allowed range'
            USING ERRCODE = '22023';
    END IF;

    SELECT crop.id
      INTO crop_key
      FROM public.crop AS crop
     WHERE crop.name = normalized_crop_name
     ORDER BY crop.id
     LIMIT 1;
    IF crop_key IS NULL THEN
        RAISE EXCEPTION 'manual market-price crop was not found'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.price_observation (
        crop_id, market_name, price_per_unit, price_date, unit, currency,
        source, location_id, quality_grade, metadata, created_at
    ) VALUES (
        crop_key,
        normalized_market_name,
        requested_price,
        (pg_catalog.clock_timestamp() AT TIME ZONE 'UTC')::DATE,
        normalized_unit,
        normalized_currency,
        'manual',
        NULL,
        normalized_quality_grade,
        requested_metadata,
        pg_catalog.clock_timestamp()
    )
    RETURNING id INTO inserted_id;

    RETURN inserted_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_world_bank_seed_market_data(
    requested_records JSONB,
    requested_payload_hash TEXT,
    requested_processing_time_ms INTEGER
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    input_row JSONB;
    commodity_code_value TEXT;
    commodity_name_value TEXT;
    expected_name TEXT;
    expected_unit TEXT;
    price_date_value DATE;
    price_value NUMERIC;
    crop_key UUID;
    candidate TEXT;
    normalized_candidate TEXT;
    aliases TEXT[];
    inserted_count INTEGER := 0;
    row_count INTEGER;
    total_rows INTEGER;
BEGIN
    IF session_user <> 'kokonut_market_data_login' THEN
        RAISE EXCEPTION 'reference market-data seed requires its dedicated login'
            USING ERRCODE = '42501';
    END IF;
    IF requested_records IS NULL
       OR pg_catalog.jsonb_typeof(requested_records) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'reference market-data records must be an array'
            USING ERRCODE = '22023';
    END IF;
    total_rows := pg_catalog.jsonb_array_length(requested_records);
    IF total_rows NOT BETWEEN 1 AND 20000
       OR requested_payload_hash IS NULL
       OR requested_payload_hash !~ '^[0-9a-f]{64}$'
       OR requested_processing_time_ms IS NULL
       OR requested_processing_time_ms NOT BETWEEN 0 AND 600000 THEN
        RAISE EXCEPTION 'reference market-data batch metadata is invalid'
            USING ERRCODE = '22023';
    END IF;

    FOR input_row IN SELECT value FROM pg_catalog.jsonb_array_elements(requested_records)
    LOOP
        IF pg_catalog.jsonb_typeof(input_row) IS DISTINCT FROM 'object'
           OR input_row - ARRAY[
               'commodity_code', 'commodity_name', 'price_date',
               'price_per_unit', 'unit'
           ] <> '{}'::JSONB THEN
            RAISE EXCEPTION 'reference market-data row shape is invalid'
                USING ERRCODE = '22023';
        END IF;
        IF pg_catalog.jsonb_typeof(input_row -> 'commodity_code') IS DISTINCT FROM 'string'
           OR pg_catalog.jsonb_typeof(input_row -> 'commodity_name') IS DISTINCT FROM 'string'
           OR pg_catalog.jsonb_typeof(input_row -> 'price_date') IS DISTINCT FROM 'string'
           OR pg_catalog.jsonb_typeof(input_row -> 'price_per_unit') IS DISTINCT FROM 'number'
           OR pg_catalog.jsonb_typeof(input_row -> 'unit') IS DISTINCT FROM 'string' THEN
            RAISE EXCEPTION 'reference market-data row contains invalid field types'
                USING ERRCODE = '22023';
        END IF;

        commodity_code_value := input_row ->> 'commodity_code';
        commodity_name_value := input_row ->> 'commodity_name';
        expected_name := CASE commodity_code_value
            WHEN 'COFFEE' THEN 'Coffee (Arabica)'
            WHEN 'COCOA' THEN 'Cocoa'
            WHEN 'PALM_OIL' THEN 'Palm Oil'
            WHEN 'RICE' THEN 'Rice'
            WHEN 'MAIZE' THEN 'Maize'
            WHEN 'SUGAR' THEN 'Sugar'
            WHEN 'TEA' THEN 'Tea'
            WHEN 'BANANA' THEN 'Bananas'
            ELSE NULL
        END;
        expected_unit := CASE commodity_code_value
            WHEN 'PALM_OIL' THEN 'USD/tonne'
            WHEN 'RICE' THEN 'USD/tonne'
            WHEN 'MAIZE' THEN 'USD/tonne'
            ELSE 'USD/kg'
        END;
        IF expected_name IS NULL
           OR commodity_name_value IS DISTINCT FROM expected_name
           OR input_row ->> 'unit' IS DISTINCT FROM expected_unit THEN
            RAISE EXCEPTION 'reference market-data commodity is not supported'
                USING ERRCODE = '22023';
        END IF;
        IF input_row ->> 'price_date' IS NULL
           OR input_row ->> 'price_date' !~ '^\d{4}-\d{2}-01$'
           OR input_row ->> 'price_per_unit' IS NULL THEN
            RAISE EXCEPTION 'reference market-data date must be the first day of a month'
                USING ERRCODE = '22023';
        END IF;
        BEGIN
            price_date_value := (input_row ->> 'price_date')::DATE;
            price_value := (input_row ->> 'price_per_unit')::NUMERIC;
        EXCEPTION WHEN OTHERS THEN
            RAISE EXCEPTION 'reference market-data row contains an invalid date or price'
                USING ERRCODE = '22023';
        END;
        IF price_value IS NULL OR price_value <= 0 OR price_value >= 100000000 THEN
            RAISE EXCEPTION 'reference market-data price is outside the allowed range'
                USING ERRCODE = '22023';
        END IF;

        aliases := CASE commodity_code_value
            WHEN 'COFFEE' THEN ARRAY['coffee', 'arabica coffee']
            WHEN 'COCOA' THEN ARRAY['cocoa', 'cacao', 'trinitario cacao']
            WHEN 'PALM_OIL' THEN ARRAY['palm oil', 'oil palm', 'palm']
            WHEN 'RICE' THEN ARRAY['rice']
            WHEN 'MAIZE' THEN ARRAY['maize', 'corn']
            WHEN 'SUGAR' THEN ARRAY['sugar', 'sugarcane', 'sugar cane']
            WHEN 'TEA' THEN ARRAY['tea']
            WHEN 'BANANA' THEN ARRAY['banana', 'bananas', 'plantain']
        END;
        crop_key := NULL;
        FOREACH candidate IN ARRAY ARRAY[
            replace(commodity_code_value, '_', ' '), commodity_name_value
        ] || aliases
        LOOP
            normalized_candidate := btrim(pg_catalog.regexp_replace(
                lower(candidate), '[^a-z0-9]+', ' ', 'g'
            ));
            SELECT crop.id
              INTO crop_key
              FROM public.crop AS crop
             WHERE btrim(pg_catalog.regexp_replace(
                       lower(crop.name::TEXT), '[^a-z0-9]+', ' ', 'g'
                   )) = normalized_candidate
                OR btrim(pg_catalog.regexp_replace(
                       lower(crop.name::TEXT), '[^a-z0-9]+', ' ', 'g'
                   )) LIKE '%' || normalized_candidate || '%'
                OR normalized_candidate LIKE '%' || btrim(pg_catalog.regexp_replace(
                       lower(crop.name::TEXT), '[^a-z0-9]+', ' ', 'g'
                   )) || '%'
             ORDER BY (btrim(pg_catalog.regexp_replace(
                           lower(crop.name::TEXT), '[^a-z0-9]+', ' ', 'g'
                       )) = normalized_candidate) DESC, crop.id
             LIMIT 1;
            EXIT WHEN FOUND;
        END LOOP;

        INSERT INTO public.price_observation (
            crop_id, commodity_code, market_name, price_date,
            price_per_unit, unit, currency, source, source_url, metadata,
            location_id
        ) VALUES (
            crop_key,
            commodity_code_value,
            'World Bank Pink Sheet',
            price_date_value,
            price_value,
            expected_unit,
            'USD',
            'world_bank_pink_sheet_seed',
            'https://www.worldbank.org/en/research/commodity-markets',
            '{"source_type":"seed_data"}'::JSONB,
            NULL
        ) ON CONFLICT (source, commodity_code, market_name, price_date) DO NOTHING;
        GET DIAGNOSTICS row_count = ROW_COUNT;
        inserted_count := inserted_count + row_count;
    END LOOP;

    INSERT INTO public.ingestion_log (
        source_system, source_table, source_id, target_table, target_id,
        operation, payload_hash, status, rows_affected, processing_time_ms,
        processor_version
    ) VALUES (
        'seed',
        'commodity_seed_data',
        'world_bank_pink_sheet_seed',
        'price_observation',
        NULL,
        'insert',
        requested_payload_hash,
        'success',
        inserted_count,
        requested_processing_time_ms,
        '1.0.0'
    );
    RETURN inserted_count;
END;
$$;

ALTER FUNCTION kokonut_security.store_manual_market_price(
    TEXT, TEXT, NUMERIC, TEXT, TEXT, TEXT, JSONB
) OWNER TO kokonut_market_data_owner;
ALTER FUNCTION kokonut_security.store_world_bank_seed_market_data(JSONB, TEXT, INTEGER)
    OWNER TO kokonut_market_data_owner;

REVOKE ALL ON FUNCTION kokonut_security.store_manual_market_price(
    TEXT, TEXT, NUMERIC, TEXT, TEXT, TEXT, JSONB
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.store_world_bank_seed_market_data(JSONB, TEXT, INTEGER)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.store_manual_market_price(
    TEXT, TEXT, NUMERIC, TEXT, TEXT, TEXT, JSONB
) TO kokonut_market_data_login;
GRANT EXECUTE ON FUNCTION kokonut_security.store_world_bank_seed_market_data(JSONB, TEXT, INTEGER)
    TO kokonut_market_data_login;

REVOKE ALL ON FUNCTION kokonut_security.store_manual_market_price(
    TEXT, TEXT, NUMERIC, TEXT, TEXT, TEXT, JSONB
) FROM kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.store_world_bank_seed_market_data(JSONB, TEXT, INTEGER)
    FROM kokonut_runtime;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_worker_execution') THEN
        REVOKE ALL ON FUNCTION kokonut_security.store_manual_market_price(
            TEXT, TEXT, NUMERIC, TEXT, TEXT, TEXT, JSONB
        ) FROM kokonut_worker_execution;
        REVOKE ALL ON FUNCTION kokonut_security.store_world_bank_seed_market_data(JSONB, TEXT, INTEGER)
            FROM kokonut_worker_execution;
    END IF;
END;
$$;

-- Direct runtime SQL loses its write path, while existing readers retain the
-- table SELECT grant. The provisioner reapplies the same DML denial.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE public.price_observation FROM kokonut_runtime;
DO $$
DECLARE
    column_list TEXT;
BEGIN
    SELECT pg_catalog.string_agg(pg_catalog.quote_ident(attname), ', ' ORDER BY attnum)
      INTO column_list
      FROM pg_catalog.pg_attribute
     WHERE attrelid = 'public.price_observation'::REGCLASS
       AND attnum > 0 AND NOT attisdropped;
    EXECUTE pg_catalog.format(
        'REVOKE INSERT (%1$s), UPDATE (%1$s), REFERENCES (%1$s) '
        'ON TABLE public.price_observation FROM kokonut_runtime',
        column_list
    );
END;
$$;
GRANT SELECT ON TABLE public.price_observation TO kokonut_runtime;

COMMENT ON TABLE public.price_observation IS
    'Global and location-scoped price observations. Manual and reference-seed writes use bounded kokonut_security functions; kokonut_runtime is read-only. Existing saved market-data tasks remain compatible through the legacy adapter.';

COMMIT;
