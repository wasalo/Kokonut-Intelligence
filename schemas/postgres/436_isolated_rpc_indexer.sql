-- Isolate the scheduled RPC wallet snapshot operation behind a dedicated
-- login and bounded functions. This preserves the existing snapshot contract;
-- it does not claim transaction-history or reorg-recovery support.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_rpc_indexer_owner') THEN
        CREATE ROLE kokonut_rpc_indexer_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_rpc_indexer_owner'
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'RPC indexer function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_rpc_indexer_login') THEN
        CREATE ROLE kokonut_rpc_indexer_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_rpc_indexer_login'
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'RPC indexer login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN ('kokonut_rpc_indexer_owner', 'kokonut_rpc_indexer_login')
            OR member_role.rolname IN ('kokonut_rpc_indexer_owner', 'kokonut_rpc_indexer_login')
    ) THEN
        RAISE EXCEPTION 'RPC indexer roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_rpc_indexer_login;
GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_rpc_indexer_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_rpc_indexer_owner;

GRANT SELECT (id, address, chain, label, is_active)
    ON public.wallet_profile TO kokonut_rpc_indexer_owner;
GRANT SELECT (id, wallet_id, chain, tx_hash, block_number, block_timestamp,
              from_address, to_address, value, token, gas_used, gas_price,
              status, activity_type)
    ON public.wallet_activity_event TO kokonut_rpc_indexer_owner;
GRANT INSERT (wallet_id, chain, tx_hash, block_number, block_timestamp,
              from_address, to_address, value, token, gas_used, gas_price,
              status, activity_type)
    ON public.wallet_activity_event TO kokonut_rpc_indexer_owner;
-- SELECT ... FOR UPDATE requires UPDATE on at least one selected relation
-- column. Keep this limited to the immutable primary key used for row locking.
GRANT UPDATE (id) ON public.wallet_activity_event TO kokonut_rpc_indexer_owner;
GRANT SELECT, INSERT, UPDATE ON public.chain_indexer_status
    TO kokonut_rpc_indexer_owner;
GRANT INSERT (
    source_system, source_table, source_id, target_table, target_id,
    operation, payload_hash, status, error_message, rows_affected,
    processing_time_ms, processor_version
) ON public.ingestion_log TO kokonut_rpc_indexer_owner;
GRANT SELECT, INSERT, UPDATE ON public.clickhouse_outbox
    TO kokonut_rpc_indexer_owner;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public'
          AND tablename = 'wallet_profile' AND policyname = 'rpc_indexer_owner_wallet_read'
    ) THEN
        CREATE POLICY rpc_indexer_owner_wallet_read ON public.wallet_profile
            FOR SELECT TO kokonut_rpc_indexer_owner USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public'
          AND tablename = 'wallet_activity_event'
          AND policyname = 'rpc_indexer_owner_activity_access'
    ) THEN
        CREATE POLICY rpc_indexer_owner_activity_access ON public.wallet_activity_event
            FOR ALL TO kokonut_rpc_indexer_owner USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public'
          AND tablename = 'chain_indexer_status'
          AND policyname = 'rpc_indexer_owner_status_access'
    ) THEN
        CREATE POLICY rpc_indexer_owner_status_access ON public.chain_indexer_status
            FOR ALL TO kokonut_rpc_indexer_owner USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public'
          AND tablename = 'ingestion_log'
          AND policyname = 'rpc_indexer_owner_audit_insert'
    ) THEN
        CREATE POLICY rpc_indexer_owner_audit_insert ON public.ingestion_log
            FOR INSERT TO kokonut_rpc_indexer_owner WITH CHECK (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public'
          AND tablename = 'clickhouse_outbox'
          AND policyname = 'rpc_indexer_owner_outbox_access'
    ) THEN
        CREATE POLICY rpc_indexer_owner_outbox_access ON public.clickhouse_outbox
            FOR ALL TO kokonut_rpc_indexer_owner USING (true) WITH CHECK (true);
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.acquire_rpc_indexer_chain_lock(
    requested_chain TEXT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_rpc_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN (
           'ethereum', 'optimism', 'base', 'arbitrum', 'celo', 'celo-alfajores', 'gnosis'
       ) THEN
        RAISE EXCEPTION 'RPC chain lock is not authorized' USING ERRCODE = '42501';
    END IF;
    PERFORM pg_advisory_lock(hashtextextended('kokonut:rpc-indexer:' || requested_chain, 0));
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.release_rpc_indexer_chain_lock(
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
    IF session_user <> 'kokonut_rpc_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN (
           'ethereum', 'optimism', 'base', 'arbitrum', 'celo', 'celo-alfajores', 'gnosis'
       ) THEN
        RAISE EXCEPTION 'RPC chain unlock is not authorized' USING ERRCODE = '42501';
    END IF;
    released := pg_advisory_unlock(
        hashtextextended('kokonut:rpc-indexer:' || requested_chain, 0)
    );
    IF NOT released THEN
        RAISE EXCEPTION 'RPC chain lock is not held by this connection'
            USING ERRCODE = '55000';
    END IF;
    RETURN released;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_rpc_indexer_wallets(
    requested_chain TEXT
)
RETURNS TABLE(wallet_id UUID, address TEXT, label TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_rpc_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN (
           'ethereum', 'optimism', 'base', 'arbitrum', 'celo', 'celo-alfajores', 'gnosis'
       ) THEN
        RAISE EXCEPTION 'RPC wallet query is not authorized' USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT wallet.id, wallet.address::TEXT, wallet.label::TEXT
      FROM public.wallet_profile AS wallet
     WHERE wallet.is_active IS TRUE
       AND lower(wallet.chain) = requested_chain
       AND wallet.address ~ '^0x[0-9a-fA-F]{40}$'
     ORDER BY wallet.id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_rpc_indexer_snapshot(
    requested_chain TEXT,
    requested_wallet_id UUID,
    requested_record JSONB,
    requested_payload_hash TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    wallet_address TEXT;
    v_tx_hash TEXT;
    v_block_number BIGINT;
    v_block_timestamp TIMESTAMPTZ;
    v_value NUMERIC(18,8);
    existing_record RECORD;
    inserted_record BOOLEAN := FALSE;
    event_columns JSONB := jsonb_build_array(
        'timestamp', 'wallet_address', 'chain', 'tx_hash', 'block_number',
        'event_type', 'value', 'token', 'status', 'metadata'
    );
    event_rows JSONB;
    v_outbox_event_key TEXT;
    outbox_id UUID;
BEGIN
    IF session_user <> 'kokonut_rpc_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN (
           'ethereum', 'optimism', 'base', 'arbitrum', 'celo', 'celo-alfajores', 'gnosis'
       )
       OR requested_wallet_id IS NULL
       OR jsonb_typeof(requested_record) IS DISTINCT FROM 'object'
       OR requested_record - ARRAY[
           'wallet_id', 'chain', 'tx_hash', 'block_number', 'block_timestamp',
           'from_address', 'to_address', 'value', 'token', 'gas_used',
           'gas_price', 'status', 'activity_type'
       ] <> '{}'::JSONB
       OR jsonb_typeof(requested_record -> 'block_number') IS DISTINCT FROM 'number'
       OR jsonb_typeof(requested_record -> 'block_timestamp') IS DISTINCT FROM 'string'
       OR jsonb_typeof(requested_record -> 'value') IS DISTINCT FROM 'number'
       OR jsonb_typeof(requested_record -> 'gas_used') IS DISTINCT FROM 'number'
       OR jsonb_typeof(requested_record -> 'gas_price') IS DISTINCT FROM 'number'
       OR requested_payload_hash IS NULL
       OR requested_payload_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'RPC snapshot request is invalid or unauthorized'
            USING ERRCODE = '42501';
    END IF;

    BEGIN
        v_block_number := (requested_record ->> 'block_number')::BIGINT;
        v_block_timestamp := (requested_record ->> 'block_timestamp')::TIMESTAMPTZ;
        v_value := (requested_record ->> 'value')::NUMERIC(18,8);
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'RPC snapshot values are invalid' USING ERRCODE = '22023';
    END;
    v_tx_hash := requested_record ->> 'tx_hash';
    IF requested_record ->> 'wallet_id' IS DISTINCT FROM requested_wallet_id::TEXT
       OR requested_record ->> 'chain' IS DISTINCT FROM requested_chain
       OR v_block_number IS NULL
       OR v_block_number < 0
       OR v_block_timestamp IS NULL
       OR v_value IS NULL
       OR v_value < 0
       OR v_tx_hash IS NULL
       OR v_tx_hash !~ '^0x[0-9a-f]{64}$'
       OR requested_record ->> 'from_address' IS DISTINCT FROM ''
       OR requested_record ->> 'token' IS DISTINCT FROM 'ETH'
       OR requested_record ->> 'status' IS DISTINCT FROM 'success'
       OR requested_record ->> 'activity_type' IS DISTINCT FROM 'balance_check'
       OR COALESCE(requested_record ->> 'gas_used', '') !~ '^0$'
       OR COALESCE(requested_record ->> 'gas_price', '') !~ '^0$' THEN
        RAISE EXCEPTION 'RPC snapshot identity or fields are invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT wallet.address INTO wallet_address
      FROM public.wallet_profile AS wallet
     WHERE wallet.id = requested_wallet_id
       AND wallet.is_active IS TRUE
       AND lower(wallet.chain) = requested_chain;
    IF wallet_address IS NULL
       OR lower(wallet_address) <> lower(COALESCE(requested_record ->> 'to_address', '')) THEN
        RAISE EXCEPTION 'RPC wallet is not active on the requested chain'
            USING ERRCODE = '42501';
    END IF;

    SELECT activity.id, activity.tx_hash, activity.block_number, activity.block_timestamp,
           activity.from_address, activity.to_address, activity.value,
           activity.token, activity.gas_used, activity.gas_price,
           activity.status, activity.activity_type
      INTO existing_record
      FROM public.wallet_activity_event AS activity
     WHERE activity.wallet_id = requested_wallet_id
       AND activity.chain = requested_chain
       AND activity.block_number = v_block_number
       AND activity.activity_type = 'balance_check'
     ORDER BY activity.id
     LIMIT 1
     FOR UPDATE;
    IF FOUND THEN
        IF existing_record.block_number IS DISTINCT FROM v_block_number
           OR (existing_record.tx_hash = v_tx_hash
               AND existing_record.block_timestamp IS DISTINCT FROM v_block_timestamp)
           OR existing_record.from_address IS DISTINCT FROM ''
           OR lower(existing_record.to_address) IS DISTINCT FROM lower(wallet_address)
           OR existing_record.value IS DISTINCT FROM v_value
           OR existing_record.token IS DISTINCT FROM 'ETH'
           OR existing_record.gas_used IS DISTINCT FROM 0
           OR existing_record.gas_price IS DISTINCT FROM 0
           OR existing_record.status IS DISTINCT FROM 'success'
           OR existing_record.activity_type IS DISTINCT FROM 'balance_check' THEN
            RAISE EXCEPTION 'RPC snapshot identity conflicts with existing activity'
                USING ERRCODE = '23505';
        END IF;
        -- Legacy snapshots use a different synthetic tx_hash and wall-clock
        -- timestamp. Reuse the durable activity identity and do not create a
        -- second ClickHouse projection for the same wallet/block snapshot.
        RETURN FALSE;
    ELSE
        INSERT INTO public.wallet_activity_event (
            wallet_id, chain, tx_hash, block_number, block_timestamp,
            from_address, to_address, value, token, gas_used, gas_price,
            status, activity_type
        ) VALUES (
            requested_wallet_id, requested_chain, v_tx_hash, v_block_number,
            v_block_timestamp, '', wallet_address, v_value, 'ETH', 0, 0,
            'success', 'balance_check'
        );
        inserted_record := TRUE;
    END IF;

    v_outbox_event_key := 'rpc:wallet_events:' || requested_wallet_id::TEXT || ':' || v_tx_hash;
    event_rows := jsonb_build_array(jsonb_build_array(
        to_char(v_block_timestamp AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.MS'),
        wallet_address, requested_chain, v_tx_hash, v_block_number,
        'balance_check', v_value, 'ETH', 'success', '{}'::JSONB
    ));
    INSERT INTO public.clickhouse_outbox (
        event_key, source_table, source_id, target_table,
        columns, rows, payload_hash
    ) VALUES (
        v_outbox_event_key, 'wallet_activity_event', v_outbox_event_key, 'wallet_events',
        event_columns, event_rows, requested_payload_hash
    )
    ON CONFLICT (event_key) DO UPDATE SET updated_at = statement_timestamp()
    WHERE public.clickhouse_outbox.source_table = EXCLUDED.source_table
      AND public.clickhouse_outbox.source_id = EXCLUDED.source_id
      AND public.clickhouse_outbox.target_table = EXCLUDED.target_table
      AND public.clickhouse_outbox.columns = EXCLUDED.columns
      AND public.clickhouse_outbox.rows = EXCLUDED.rows
      AND public.clickhouse_outbox.payload_hash = EXCLUDED.payload_hash
    RETURNING id INTO outbox_id;
    IF outbox_id IS NULL THEN
        RAISE EXCEPTION 'RPC snapshot projection conflicts with an existing outbox event'
            USING ERRCODE = '23505';
    END IF;
    RETURN inserted_record;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.finish_rpc_indexer_chain(
    requested_chain TEXT,
    requested_status TEXT,
    requested_error TEXT,
    requested_rows_affected INTEGER,
    requested_last_block BIGINT,
    requested_processing_time_ms INTEGER,
    requested_payload_hash TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_rpc_indexer_login'
       OR requested_chain IS NULL
       OR requested_chain NOT IN (
           'ethereum', 'optimism', 'base', 'arbitrum', 'celo', 'celo-alfajores', 'gnosis'
       )
       OR requested_status IS NULL OR requested_status NOT IN ('healthy', 'error')
       OR requested_rows_affected IS NULL OR requested_rows_affected < 0
       OR (requested_last_block IS NOT NULL AND requested_last_block < 0)
       OR requested_processing_time_ms IS NULL
       OR requested_processing_time_ms NOT BETWEEN 0 AND 600000
       OR requested_payload_hash IS NULL
       OR requested_payload_hash !~ '^[0-9a-f]{64}$'
       OR (requested_error IS NOT NULL AND length(requested_error) > 500)
       OR (requested_status = 'healthy' AND requested_error IS NOT NULL)
       OR (requested_status = 'error' AND requested_error IS NULL) THEN
        RAISE EXCEPTION 'RPC chain completion request is invalid or unauthorized'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO public.chain_indexer_status (
        chain, indexer_type, last_synced_block, last_synced_at,
        status, error_message, metadata
    ) VALUES (
        requested_chain, 'rpc', requested_last_block, NOW(),
        requested_status, requested_error,
        jsonb_build_object('worker', 'isolated', 'snapshots_inserted', requested_rows_affected)
    )
    ON CONFLICT (chain, indexer_type) DO UPDATE SET
        last_synced_block = EXCLUDED.last_synced_block,
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
        'rpc_provider', requested_chain || '_wallet_profile', requested_chain,
        'wallet_activity_event', NULL, 'balance_snapshot', requested_payload_hash,
        CASE WHEN requested_status = 'error' THEN 'partial' ELSE 'success' END,
        requested_error, requested_rows_affected, requested_processing_time_ms, '1.0.0'
    );
    RETURN TRUE;
END;
$$;

ALTER FUNCTION kokonut_security.acquire_rpc_indexer_chain_lock(TEXT)
    OWNER TO kokonut_rpc_indexer_owner;
ALTER FUNCTION kokonut_security.release_rpc_indexer_chain_lock(TEXT)
    OWNER TO kokonut_rpc_indexer_owner;
ALTER FUNCTION kokonut_security.list_rpc_indexer_wallets(TEXT)
    OWNER TO kokonut_rpc_indexer_owner;
ALTER FUNCTION kokonut_security.store_rpc_indexer_snapshot(TEXT, UUID, JSONB, TEXT)
    OWNER TO kokonut_rpc_indexer_owner;
ALTER FUNCTION kokonut_security.finish_rpc_indexer_chain(TEXT, TEXT, TEXT, INTEGER, BIGINT, INTEGER, TEXT)
    OWNER TO kokonut_rpc_indexer_owner;

REVOKE ALL ON FUNCTION kokonut_security.acquire_rpc_indexer_chain_lock(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.release_rpc_indexer_chain_lock(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_rpc_indexer_wallets(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.store_rpc_indexer_snapshot(TEXT, UUID, JSONB, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.finish_rpc_indexer_chain(TEXT, TEXT, TEXT, INTEGER, BIGINT, INTEGER, TEXT) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION kokonut_security.acquire_rpc_indexer_chain_lock(TEXT)
    TO kokonut_rpc_indexer_login;
GRANT EXECUTE ON FUNCTION kokonut_security.release_rpc_indexer_chain_lock(TEXT)
    TO kokonut_rpc_indexer_login;
GRANT EXECUTE ON FUNCTION kokonut_security.list_rpc_indexer_wallets(TEXT)
    TO kokonut_rpc_indexer_login;
GRANT EXECUTE ON FUNCTION kokonut_security.store_rpc_indexer_snapshot(TEXT, UUID, JSONB, TEXT)
    TO kokonut_rpc_indexer_login;
GRANT EXECUTE ON FUNCTION kokonut_security.finish_rpc_indexer_chain(TEXT, TEXT, TEXT, INTEGER, BIGINT, INTEGER, TEXT)
    TO kokonut_rpc_indexer_login;

COMMENT ON FUNCTION kokonut_security.store_rpc_indexer_snapshot(TEXT, UUID, JSONB, TEXT) IS
    'Validates and idempotently stores one RPC balance snapshot with its ClickHouse outbox intent; the dedicated login has no direct table grants.';

COMMIT;
