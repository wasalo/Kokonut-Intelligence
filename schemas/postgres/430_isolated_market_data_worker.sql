-- Give global World Bank price ingestion a separate login and one bounded
-- write function. This reference feed is not location-scoped; it must not
-- inherit the application or control-plane database identity.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_market_data_owner'
    ) THEN
        CREATE ROLE kokonut_market_data_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_market_data_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'market-data function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_market_data_login'
    ) THEN
        CREATE ROLE kokonut_market_data_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_market_data_login'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'market-data login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN (
                   'kokonut_market_data_owner', 'kokonut_market_data_login'
               )
            OR member_role.rolname IN (
                   'kokonut_market_data_owner', 'kokonut_market_data_login'
               )
    ) THEN
        RAISE EXCEPTION 'market-data roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_market_data_login;
GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_market_data_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_market_data_owner;

GRANT SELECT (id, name) ON public.crop TO kokonut_market_data_owner;
GRANT SELECT (source, commodity_code, market_name, price_date)
    ON public.price_observation TO kokonut_market_data_owner;
GRANT INSERT (
    crop_id, commodity_code, market_name, price_date, price_per_unit,
    unit, currency, source, source_url, metadata
) ON public.price_observation TO kokonut_market_data_owner;
GRANT INSERT (
    source_system, source_table, source_id, target_table, target_id,
    operation, payload_hash, status, rows_affected, processing_time_ms,
    processor_version
) ON public.ingestion_log TO kokonut_market_data_owner;

-- The login has no direct relation grants. If optional application roles have
-- already been provisioned, remove any earlier broad access to these targets.
DO $$
DECLARE
    role_name TEXT;
    target_table RECORD;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_worker_execution', 'kokonut_market_data_login'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.crop, public.price_observation, '
                || 'public.ingestion_log FROM %I',
                role_name
            );
            FOR target_table IN
                SELECT relation.relname,
                       string_agg(quote_ident(attribute.attname), ', ' ORDER BY attribute.attnum) AS columns
                  FROM pg_class AS relation
                  JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                  JOIN pg_attribute AS attribute ON attribute.attrelid = relation.oid
                 WHERE namespace.nspname = 'public'
                   AND relation.relname IN ('crop', 'price_observation', 'ingestion_log')
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

-- Permit the isolated function owner to operate if application tables later
-- enable forced RLS. The login can reach the owner only through this function.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'crop'
           AND policyname = 'market_data_owner_crop_read'
    ) THEN
        EXECUTE 'CREATE POLICY market_data_owner_crop_read ON public.crop '
            || 'FOR SELECT TO kokonut_market_data_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'price_observation'
           AND policyname = 'market_data_owner_price_conflict_read'
    ) THEN
        EXECUTE 'CREATE POLICY market_data_owner_price_conflict_read ON public.price_observation '
            || 'FOR SELECT TO kokonut_market_data_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'price_observation'
           AND policyname = 'market_data_owner_price_insert'
    ) THEN
        EXECUTE 'CREATE POLICY market_data_owner_price_insert ON public.price_observation '
            || 'FOR INSERT TO kokonut_market_data_owner WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'ingestion_log'
           AND policyname = 'market_data_owner_audit_insert'
    ) THEN
        EXECUTE 'CREATE POLICY market_data_owner_audit_insert ON public.ingestion_log '
            || 'FOR INSERT TO kokonut_market_data_owner WITH CHECK (true)';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_world_bank_market_data(
    requested_records JSONB,
    requested_source_url TEXT,
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
    v_commodity_code TEXT;
    commodity_name TEXT;
    v_price_date DATE;
    v_price_value NUMERIC;
    v_crop_id UUID;
    candidate TEXT;
    normalized_candidate TEXT;
    aliases TEXT[];
    inserted_count INTEGER := 0;
    row_count INTEGER;
    total_rows INTEGER;
BEGIN
    IF session_user <> 'kokonut_market_data_login' THEN
        RAISE EXCEPTION 'market-data ingestion requires its dedicated login'
            USING ERRCODE = '42501';
    END IF;
    IF requested_records IS NULL
       OR jsonb_typeof(requested_records) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'market-data records must be an array'
            USING ERRCODE = '22023';
    END IF;
    total_rows := jsonb_array_length(requested_records);
    IF total_rows NOT BETWEEN 1 AND 20000 THEN
        RAISE EXCEPTION 'market-data batch size is outside the allowed range'
            USING ERRCODE = '22023';
    END IF;
    IF requested_source_url IS NULL
       OR length(requested_source_url) > 255
       OR requested_source_url !~ '^https://[^[:space:]]+$'
       OR requested_payload_hash IS NULL
       OR requested_payload_hash !~ '^[0-9a-f]{64}$'
       OR requested_processing_time_ms IS NULL
       OR requested_processing_time_ms NOT BETWEEN 0 AND 600000 THEN
        RAISE EXCEPTION 'market-data batch metadata is invalid'
            USING ERRCODE = '22023';
    END IF;

    FOR input_row IN SELECT value FROM jsonb_array_elements(requested_records)
    LOOP
        IF jsonb_typeof(input_row) IS DISTINCT FROM 'object'
           OR input_row - ARRAY[
               'commodity_code', 'commodity_name', 'price_date', 'price_per_unit'
           ] <> '{}'::JSONB THEN
            RAISE EXCEPTION 'market-data row shape is invalid'
                USING ERRCODE = '22023';
        END IF;
        IF jsonb_typeof(input_row -> 'commodity_code') IS DISTINCT FROM 'string'
           OR jsonb_typeof(input_row -> 'commodity_name') IS DISTINCT FROM 'string'
           OR jsonb_typeof(input_row -> 'price_date') IS DISTINCT FROM 'string'
           OR jsonb_typeof(input_row -> 'price_per_unit') IS DISTINCT FROM 'number' THEN
            RAISE EXCEPTION 'market-data row contains invalid field types'
                USING ERRCODE = '22023';
        END IF;
        v_commodity_code := input_row ->> 'commodity_code';
        commodity_name := input_row ->> 'commodity_name';
        IF v_commodity_code IS NULL OR v_commodity_code NOT IN (
            'COFFEE', 'COCOA', 'PALM_OIL', 'RICE', 'MAIZE', 'SUGAR', 'TEA', 'BANANA'
        ) OR commodity_name IS NULL
          OR length(btrim(commodity_name)) NOT BETWEEN 1 AND 200 THEN
            RAISE EXCEPTION 'market-data commodity is not supported'
                USING ERRCODE = '22023';
        END IF;
        IF input_row ->> 'price_date' IS NULL
           OR input_row ->> 'price_date' !~ '^\d{4}-\d{2}-01$'
           OR input_row ->> 'price_per_unit' IS NULL THEN
            RAISE EXCEPTION 'market-data date must be the first day of a month'
                USING ERRCODE = '22023';
        END IF;
        BEGIN
            v_price_date := (input_row ->> 'price_date')::DATE;
            v_price_value := (input_row ->> 'price_per_unit')::NUMERIC;
        EXCEPTION WHEN OTHERS THEN
            RAISE EXCEPTION 'market-data row contains an invalid date or price'
                USING ERRCODE = '22023';
        END;
        IF v_price_value IS NULL OR v_price_value <= 0 OR v_price_value > 100000000 THEN
            RAISE EXCEPTION 'market-data price is outside the allowed range'
                USING ERRCODE = '22023';
        END IF;

        aliases := CASE v_commodity_code
            WHEN 'COFFEE' THEN ARRAY['coffee', 'arabica coffee']
            WHEN 'COCOA' THEN ARRAY['cocoa', 'cacao', 'trinitario cacao']
            WHEN 'PALM_OIL' THEN ARRAY['palm oil', 'oil palm', 'palm']
            WHEN 'RICE' THEN ARRAY['rice']
            WHEN 'MAIZE' THEN ARRAY['maize', 'corn']
            WHEN 'SUGAR' THEN ARRAY['sugar', 'sugarcane', 'sugar cane']
            WHEN 'TEA' THEN ARRAY['tea']
            WHEN 'BANANA' THEN ARRAY['banana', 'bananas', 'plantain']
        END;
        v_crop_id := NULL;
        FOREACH candidate IN ARRAY ARRAY[
            replace(v_commodity_code, '_', ' '), commodity_name
        ] || aliases
        LOOP
            normalized_candidate := btrim(regexp_replace(
                lower(candidate), '[^a-z0-9]+', ' ', 'g'
            ));
            SELECT crop.id
              INTO v_crop_id
              FROM public.crop AS crop
             WHERE btrim(regexp_replace(
                       lower(crop.name::TEXT), '[^a-z0-9]+', ' ', 'g'
                   )) = normalized_candidate
                OR btrim(regexp_replace(
                       lower(crop.name::TEXT), '[^a-z0-9]+', ' ', 'g'
                   )) LIKE '%' || normalized_candidate || '%'
                OR normalized_candidate LIKE '%' || btrim(regexp_replace(
                       lower(crop.name::TEXT), '[^a-z0-9]+', ' ', 'g'
                   )) || '%'
             ORDER BY (btrim(regexp_replace(
                           lower(crop.name::TEXT), '[^a-z0-9]+', ' ', 'g'
                       )) = normalized_candidate) DESC, crop.id
             LIMIT 1;
            EXIT WHEN FOUND;
        END LOOP;

        INSERT INTO public.price_observation (
            crop_id, commodity_code, market_name, price_date,
            price_per_unit, unit, currency, source, source_url, metadata
        ) VALUES (
            v_crop_id,
            v_commodity_code,
            'World Bank Pink Sheet',
            v_price_date,
            v_price_value,
            CASE v_commodity_code
                WHEN 'PALM_OIL' THEN 'USD/tonne'
                WHEN 'RICE' THEN 'USD/tonne'
                WHEN 'MAIZE' THEN 'USD/tonne'
                ELSE 'USD/kg'
            END,
            'USD',
            'world_bank_pink_sheet',
            requested_source_url,
            '{"source_type":"live_download"}'::JSONB
        ) ON CONFLICT (source, commodity_code, market_name, price_date) DO NOTHING;
        GET DIAGNOSTICS row_count = ROW_COUNT;
        inserted_count := inserted_count + row_count;
    END LOOP;

    INSERT INTO public.ingestion_log (
        source_system, source_table, source_id, target_table, target_id,
        operation, payload_hash, status, rows_affected, processing_time_ms,
        processor_version
    ) VALUES (
        'world_bank',
        'world_bank_pink_sheet',
        requested_source_url,
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

ALTER FUNCTION kokonut_security.store_world_bank_market_data(JSONB, TEXT, TEXT, INTEGER)
    OWNER TO kokonut_market_data_owner;
REVOKE ALL ON FUNCTION kokonut_security.store_world_bank_market_data(JSONB, TEXT, TEXT, INTEGER)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.store_world_bank_market_data(JSONB, TEXT, TEXT, INTEGER)
    TO kokonut_market_data_login;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_worker_execution'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON FUNCTION kokonut_security.store_world_bank_market_data('
                || 'JSONB, TEXT, TEXT, INTEGER) FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END;
$$;

COMMENT ON FUNCTION kokonut_security.store_world_bank_market_data(JSONB, TEXT, TEXT, INTEGER) IS
    'Validates and persists one bounded World Bank Pink Sheet batch and its ingestion audit; the dedicated login receives no direct relation access.';

COMMIT;
