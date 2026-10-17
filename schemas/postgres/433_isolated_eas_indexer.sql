-- Isolate scheduled EAS indexing behind one global worker login and bounded
-- database functions. EAS attestations and tracked wallet records are global
-- protocol data, so this worker deliberately has no location tenant context.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_eas_indexer_owner') THEN
        CREATE ROLE kokonut_eas_indexer_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_eas_indexer_owner'
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'EAS indexer function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_eas_indexer_login') THEN
        CREATE ROLE kokonut_eas_indexer_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_eas_indexer_login'
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'EAS indexer login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN ('kokonut_eas_indexer_owner', 'kokonut_eas_indexer_login')
            OR member_role.rolname IN ('kokonut_eas_indexer_owner', 'kokonut_eas_indexer_login')
    ) THEN
        RAISE EXCEPTION 'EAS indexer roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_eas_indexer_login;
GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_eas_indexer_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_eas_indexer_owner;

GRANT SELECT (id, address, chain, is_active) ON public.wallet_profile TO kokonut_eas_indexer_owner;
GRANT SELECT (id, schema_uid) ON public.attestation_schema TO kokonut_eas_indexer_owner;
GRANT INSERT (schema_uid, name, schema_text, chain, active)
    ON public.attestation_schema TO kokonut_eas_indexer_owner;
GRANT SELECT (id, attestation_uid) ON public.attestation_record TO kokonut_eas_indexer_owner;
GRANT INSERT (
    schema_id, attestation_uid, subject_type, claim_data, status, tx_hash, chain, attested_at
) ON public.attestation_record TO kokonut_eas_indexer_owner;
GRANT SELECT (chain, wallet_id, last_attestation_time) ON public.eas_indexer_cursor
    TO kokonut_eas_indexer_owner;
GRANT INSERT (chain, wallet_id, last_attestation_time) ON public.eas_indexer_cursor
    TO kokonut_eas_indexer_owner;
GRANT UPDATE (last_attestation_time, updated_at) ON public.eas_indexer_cursor
    TO kokonut_eas_indexer_owner;
GRANT SELECT (id, chain, indexer_type, metadata) ON public.chain_indexer_status
    TO kokonut_eas_indexer_owner;
GRANT INSERT (chain, indexer_type, last_synced_at, status, error_message, metadata)
    ON public.chain_indexer_status TO kokonut_eas_indexer_owner;
GRANT UPDATE (last_synced_at, status, error_message, metadata, updated_at)
    ON public.chain_indexer_status TO kokonut_eas_indexer_owner;
-- PostgreSQL requires relation-level privileges for the ON CONFLICT upsert
-- on this small global control table. The NOLOGIN owner is reachable only
-- through the fixed chain/status function; the worker login has no table ACL.
GRANT SELECT, INSERT, UPDATE ON public.chain_indexer_status TO kokonut_eas_indexer_owner;
GRANT INSERT (
    source_system, source_table, source_id, target_table, target_id, operation,
    payload_hash, status, error_message, rows_affected, processing_time_ms, processor_version
) ON public.ingestion_log TO kokonut_eas_indexer_owner;
GRANT SELECT (
    id, event_key, source_table, source_id, target_table, columns, rows, payload_hash
) ON public.clickhouse_outbox TO kokonut_eas_indexer_owner;
GRANT INSERT (event_key, source_table, source_id, target_table, columns, rows, payload_hash)
    ON public.clickhouse_outbox TO kokonut_eas_indexer_owner;
GRANT UPDATE (updated_at) ON public.clickhouse_outbox TO kokonut_eas_indexer_owner;

DO $$
DECLARE
    target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'wallet_profile', 'attestation_schema', 'attestation_record',
        'eas_indexer_cursor', 'chain_indexer_status', 'ingestion_log', 'clickhouse_outbox'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = target_table
               AND policyname = 'eas_indexer_owner_function_access'
        ) THEN
            EXECUTE format(
                'CREATE POLICY eas_indexer_owner_function_access ON public.%I '
                || 'FOR ALL TO kokonut_eas_indexer_owner USING (true) WITH CHECK (true)',
                target_table
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.acquire_eas_indexer_chain_lock(
    requested_chain TEXT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_eas_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN ('celo', 'optimism', 'base') THEN
        RAISE EXCEPTION 'EAS chain lock is not authorized' USING ERRCODE = '42501';
    END IF;
    PERFORM pg_advisory_lock(hashtextextended('kokonut:eas-indexer:' || requested_chain, 0));
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.release_eas_indexer_chain_lock(
    requested_chain TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    released BOOLEAN;
BEGIN
    IF session_user <> 'kokonut_eas_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN ('celo', 'optimism', 'base') THEN
        RAISE EXCEPTION 'EAS chain lock is not authorized' USING ERRCODE = '42501';
    END IF;
    released := pg_advisory_unlock(
        hashtextextended('kokonut:eas-indexer:' || requested_chain, 0)
    );
    IF NOT released THEN
        RAISE EXCEPTION 'EAS chain lock is not held by this connection'
            USING ERRCODE = '55000';
    END IF;
    RETURN released;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_eas_indexer_recipients(
    requested_chain TEXT
)
RETURNS TABLE(wallet_id UUID, recipient_address TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_eas_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN ('celo', 'optimism', 'base') THEN
        RAISE EXCEPTION 'EAS recipient query is not authorized' USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT wallet.id, wallet.address::TEXT
      FROM public.wallet_profile AS wallet
     WHERE wallet.is_active IS TRUE
       AND lower(wallet.chain) = requested_chain
       AND NULLIF(btrim(wallet.address), '') IS NOT NULL
     ORDER BY wallet.id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.read_eas_indexer_cursor(
    requested_chain TEXT,
    requested_wallet_id UUID
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    cursor_value BIGINT;
BEGIN
    IF session_user <> 'kokonut_eas_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN ('celo', 'optimism', 'base')
       OR requested_wallet_id IS NULL THEN
        RAISE EXCEPTION 'EAS cursor query is not authorized' USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.wallet_profile AS wallet
         WHERE wallet.id = requested_wallet_id
           AND wallet.is_active IS TRUE AND lower(wallet.chain) = requested_chain
    ) THEN
        RAISE EXCEPTION 'EAS recipient is not active on the requested chain'
            USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.eas_indexer_cursor (chain, wallet_id, last_attestation_time)
    VALUES (requested_chain, requested_wallet_id, 0)
    ON CONFLICT (chain, wallet_id) DO NOTHING;
    SELECT cursor.last_attestation_time INTO cursor_value
      FROM public.eas_indexer_cursor AS cursor
     WHERE cursor.chain = requested_chain AND cursor.wallet_id = requested_wallet_id
     FOR UPDATE;
    RETURN cursor_value;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_eas_indexer_page(
    requested_chain TEXT,
    requested_wallet_id UUID,
    requested_page JSONB
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    wallet_address TEXT;
    page_item JSONB;
    attestation JSONB;
    v_attestation_uid TEXT;
    v_schema_uid TEXT;
    schema_text TEXT;
    schema_id UUID;
    payload_hash TEXT;
    attestation_time BIGINT;
    attested_timestamp TIMESTAMPTZ;
    was_revoked BOOLEAN;
    lifecycle_status TEXT;
    record_id UUID;
    outbox_id UUID;
    inserted_count INTEGER := 0;
    projection_columns JSONB := jsonb_build_array(
        'timestamp', 'attestation_uid', 'schema_uid', 'chain', 'attester',
        'recipient', 'subject_type', 'status', 'revoked', 'metadata'
    );
    projection_row JSONB;
BEGIN
    IF session_user <> 'kokonut_eas_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN ('celo', 'optimism', 'base')
       OR requested_wallet_id IS NULL
       OR jsonb_typeof(requested_page) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'EAS page request is invalid or unauthorized'
            USING ERRCODE = '42501';
    END IF;
    IF jsonb_array_length(requested_page) > 100 THEN
        RAISE EXCEPTION 'EAS page exceeds the accepted row limit' USING ERRCODE = '22023';
    END IF;
    IF octet_length(requested_page::TEXT) > 5242880 THEN
        RAISE EXCEPTION 'EAS page exceeds the accepted payload size' USING ERRCODE = '22023';
    END IF;
    SELECT wallet.address INTO wallet_address
      FROM public.wallet_profile AS wallet
     WHERE wallet.id = requested_wallet_id
       AND wallet.is_active IS TRUE AND lower(wallet.chain) = requested_chain;
    IF wallet_address IS NULL THEN
        RAISE EXCEPTION 'EAS recipient is not active on the requested chain'
            USING ERRCODE = '42501';
    END IF;

    FOR page_item IN SELECT value FROM jsonb_array_elements(requested_page)
    LOOP
        IF jsonb_typeof(page_item) IS DISTINCT FROM 'object'
           OR page_item - ARRAY['attestation', 'payload_hash'] <> '{}'::JSONB
           OR jsonb_typeof(page_item -> 'attestation') IS DISTINCT FROM 'object'
           OR jsonb_typeof(page_item -> 'payload_hash') IS DISTINCT FROM 'string' THEN
            RAISE EXCEPTION 'EAS page item shape is invalid' USING ERRCODE = '22023';
        END IF;
        attestation := page_item -> 'attestation';
        payload_hash := page_item ->> 'payload_hash';
        v_attestation_uid := attestation ->> 'id';
        v_schema_uid := attestation #>> '{schema,id}';
        schema_text := COALESCE(attestation #>> '{schema,schema}', '');
        IF v_attestation_uid IS NULL OR length(v_attestation_uid) NOT BETWEEN 1 AND 66
           OR v_schema_uid IS NULL OR length(v_schema_uid) NOT BETWEEN 1 AND 66
           OR payload_hash IS NULL OR payload_hash !~ '^[0-9a-f]{64}$'
           OR lower(COALESCE(attestation ->> 'recipient', '')) <> lower(wallet_address)
           OR COALESCE(attestation ->> 'time', '') !~ '^[0-9]{1,12}$' THEN
            RAISE EXCEPTION 'EAS attestation identity or timestamp is invalid'
                USING ERRCODE = '22023';
        END IF;
        attestation_time := (attestation ->> 'time')::BIGINT;
        IF attestation_time > 253402300799 THEN
            RAISE EXCEPTION 'EAS attestation timestamp is outside supported bounds'
                USING ERRCODE = '22023';
        END IF;
        attested_timestamp := to_timestamp(attestation_time);
        was_revoked := COALESCE((attestation ->> 'revoked')::BOOLEAN, FALSE);
        lifecycle_status := CASE WHEN was_revoked THEN 'rejected' ELSE 'published' END;

        INSERT INTO public.attestation_schema (schema_uid, name, schema_text, chain, active)
        VALUES (v_schema_uid, 'Schema ' || left(v_schema_uid, 10), schema_text, requested_chain, TRUE)
        ON CONFLICT (schema_uid) DO NOTHING;
        SELECT schema.id INTO schema_id
          FROM public.attestation_schema AS schema
         WHERE schema.schema_uid = v_schema_uid;
        IF schema_id IS NULL THEN
            RAISE EXCEPTION 'EAS schema could not be resolved' USING ERRCODE = '23503';
        END IF;

        INSERT INTO public.attestation_record (
            schema_id, attestation_uid, subject_type, claim_data, status,
            tx_hash, chain, attested_at
        ) VALUES (
            schema_id, v_attestation_uid, 'wallet',
            jsonb_build_object(
                'attester', attestation -> 'attester',
                'recipient', attestation -> 'recipient',
                'data', attestation -> 'data',
                'revocable', attestation -> 'revocable',
                'revoked', attestation -> 'revoked',
                'expiration_time', attestation -> 'expirationTime'
            ),
            lifecycle_status, COALESCE(attestation ->> 'txid', ''), requested_chain,
            attested_timestamp
        ) ON CONFLICT (attestation_uid) DO NOTHING
        RETURNING id INTO record_id;
        IF record_id IS NULL THEN
            CONTINUE;
        END IF;

        projection_row := jsonb_build_array(
            to_char(attested_timestamp AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.MS'),
            v_attestation_uid, v_schema_uid, requested_chain,
            COALESCE(attestation ->> 'attester', ''),
            COALESCE(attestation ->> 'recipient', ''), 'wallet', lifecycle_status,
            was_revoked, '{}'::JSONB
        );
        INSERT INTO public.clickhouse_outbox (
            event_key, source_table, source_id, target_table, columns, rows, payload_hash
        ) VALUES (
            'attestation:attestation_events:' || v_attestation_uid,
            'attestation_record', v_attestation_uid, 'attestation_events',
            projection_columns, jsonb_build_array(projection_row), payload_hash
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
            RAISE EXCEPTION 'EAS projection conflicts with an existing outbox event'
                USING ERRCODE = '23505';
        END IF;
        inserted_count := inserted_count + 1;
    END LOOP;
    RETURN inserted_count;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.advance_eas_indexer_cursor(
    requested_chain TEXT,
    requested_wallet_id UUID,
    requested_time BIGINT
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    cursor_value BIGINT;
BEGIN
    IF session_user <> 'kokonut_eas_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN ('celo', 'optimism', 'base')
       OR requested_wallet_id IS NULL
       OR requested_time IS NULL OR requested_time < 0 OR requested_time > 253402300799
       OR NOT EXISTS (
           SELECT 1 FROM public.wallet_profile AS wallet
            WHERE wallet.id = requested_wallet_id
              AND wallet.is_active IS TRUE AND lower(wallet.chain) = requested_chain
       ) THEN
        RAISE EXCEPTION 'EAS cursor update is invalid or unauthorized'
            USING ERRCODE = '42501';
    END IF;
    UPDATE public.eas_indexer_cursor AS cursor
       SET last_attestation_time = GREATEST(cursor.last_attestation_time, requested_time),
           updated_at = NOW()
     WHERE cursor.chain = requested_chain AND cursor.wallet_id = requested_wallet_id
    RETURNING cursor.last_attestation_time INTO cursor_value;
    IF cursor_value IS NULL THEN
        RAISE EXCEPTION 'EAS cursor row is missing' USING ERRCODE = 'P0002';
    END IF;
    RETURN cursor_value;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.finish_eas_indexer_chain(
    requested_chain TEXT,
    requested_status TEXT,
    requested_error TEXT,
    requested_rows INTEGER,
    requested_processing_time_ms INTEGER,
    requested_payload_hash TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    watermark BIGINT;
BEGIN
    IF session_user <> 'kokonut_eas_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN ('celo', 'optimism', 'base')
       OR requested_status IS NULL
       OR requested_status NOT IN ('healthy', 'error')
       OR requested_rows IS NULL OR requested_rows < 0
       OR requested_processing_time_ms IS NULL
       OR requested_processing_time_ms NOT BETWEEN 0 AND 600000
       OR requested_payload_hash IS NULL
       OR requested_payload_hash !~ '^[0-9a-f]{64}$'
       OR (requested_error IS NOT NULL AND length(requested_error) > 500)
       OR (requested_status = 'healthy' AND requested_error IS NOT NULL)
       OR (requested_status = 'error' AND requested_error IS NULL) THEN
        RAISE EXCEPTION 'EAS chain completion request is invalid or unauthorized'
            USING ERRCODE = '42501';
    END IF;
    SELECT COALESCE(MAX(cursor.last_attestation_time), 0)
      INTO watermark
      FROM public.eas_indexer_cursor AS cursor
     WHERE cursor.chain = requested_chain;

    INSERT INTO public.chain_indexer_status (
        chain, indexer_type, last_synced_at, status, error_message, metadata
    ) VALUES (
        requested_chain, 'eas', NOW(), requested_status, requested_error,
        jsonb_build_object('last_attestation_time', watermark)
    )
    ON CONFLICT (chain, indexer_type) DO UPDATE SET
        last_synced_at = EXCLUDED.last_synced_at,
        status = EXCLUDED.status,
        error_message = EXCLUDED.error_message,
        metadata = COALESCE(public.chain_indexer_status.metadata, '{}'::JSONB)
                   || EXCLUDED.metadata,
        updated_at = NOW();

    INSERT INTO public.ingestion_log (
        source_system, source_table, source_id, target_table, target_id,
        operation, payload_hash, status, error_message, rows_affected,
        processing_time_ms, processor_version
    ) VALUES (
        'eas_api', requested_chain || '_attestations', requested_chain,
        'attestation_record', NULL, 'batch_insert', requested_payload_hash,
        CASE WHEN requested_status = 'error' THEN 'partial' ELSE 'success' END,
        requested_error, requested_rows, requested_processing_time_ms, '1.0.0'
    );
    RETURN watermark;
END;
$$;

ALTER FUNCTION kokonut_security.acquire_eas_indexer_chain_lock(TEXT)
    OWNER TO kokonut_eas_indexer_owner;
ALTER FUNCTION kokonut_security.release_eas_indexer_chain_lock(TEXT)
    OWNER TO kokonut_eas_indexer_owner;
ALTER FUNCTION kokonut_security.list_eas_indexer_recipients(TEXT)
    OWNER TO kokonut_eas_indexer_owner;
ALTER FUNCTION kokonut_security.read_eas_indexer_cursor(TEXT, UUID)
    OWNER TO kokonut_eas_indexer_owner;
ALTER FUNCTION kokonut_security.store_eas_indexer_page(TEXT, UUID, JSONB)
    OWNER TO kokonut_eas_indexer_owner;
ALTER FUNCTION kokonut_security.advance_eas_indexer_cursor(TEXT, UUID, BIGINT)
    OWNER TO kokonut_eas_indexer_owner;
ALTER FUNCTION kokonut_security.finish_eas_indexer_chain(TEXT, TEXT, TEXT, INTEGER, INTEGER, TEXT)
    OWNER TO kokonut_eas_indexer_owner;

REVOKE ALL ON FUNCTION kokonut_security.acquire_eas_indexer_chain_lock(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.release_eas_indexer_chain_lock(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_eas_indexer_recipients(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.read_eas_indexer_cursor(TEXT, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.store_eas_indexer_page(TEXT, UUID, JSONB) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.advance_eas_indexer_cursor(TEXT, UUID, BIGINT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.finish_eas_indexer_chain(TEXT, TEXT, TEXT, INTEGER, INTEGER, TEXT) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION kokonut_security.acquire_eas_indexer_chain_lock(TEXT)
    TO kokonut_eas_indexer_login;
GRANT EXECUTE ON FUNCTION kokonut_security.release_eas_indexer_chain_lock(TEXT)
    TO kokonut_eas_indexer_login;
GRANT EXECUTE ON FUNCTION kokonut_security.list_eas_indexer_recipients(TEXT)
    TO kokonut_eas_indexer_login;
GRANT EXECUTE ON FUNCTION kokonut_security.read_eas_indexer_cursor(TEXT, UUID)
    TO kokonut_eas_indexer_login;
GRANT EXECUTE ON FUNCTION kokonut_security.store_eas_indexer_page(TEXT, UUID, JSONB)
    TO kokonut_eas_indexer_login;
GRANT EXECUTE ON FUNCTION kokonut_security.advance_eas_indexer_cursor(TEXT, UUID, BIGINT)
    TO kokonut_eas_indexer_login;
GRANT EXECUTE ON FUNCTION kokonut_security.finish_eas_indexer_chain(TEXT, TEXT, TEXT, INTEGER, INTEGER, TEXT)
    TO kokonut_eas_indexer_login;

COMMENT ON FUNCTION kokonut_security.store_eas_indexer_page(TEXT, UUID, JSONB) IS
    'Validates and atomically stores one bounded EAS recipient page with its durable ClickHouse projection intents; the isolated EAS login has no direct table grants.';

COMMIT;
