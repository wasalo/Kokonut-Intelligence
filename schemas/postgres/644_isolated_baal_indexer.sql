-- Isolate the read-only Baal event indexer behind a dedicated login and a
-- fixed SECURITY DEFINER contract. Event writes, outbox-free projections, and
-- the Baal cursor remain committed on the indexer's existing batch connection.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_baal_indexer_owner') THEN
        CREATE ROLE kokonut_baal_indexer_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_baal_indexer_owner'
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Baal indexer function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_baal_indexer_login') THEN
        CREATE ROLE kokonut_baal_indexer_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_baal_indexer_login'
          AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
               OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Baal indexer login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN ('kokonut_baal_indexer_owner', 'kokonut_baal_indexer_login')
            OR member_role.rolname IN ('kokonut_baal_indexer_owner', 'kokonut_baal_indexer_login')
    ) THEN
        RAISE EXCEPTION 'Baal indexer roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_baal_indexer_login;
GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_baal_indexer_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_baal_indexer_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_baal_indexer_login;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_baal_indexer_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_baal_indexer_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_baal_indexer_login;
REVOKE CREATE ON SCHEMA public FROM kokonut_baal_indexer_login;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_baal_indexer_login;

GRANT SELECT (id, address, chain) ON public.wallet_profile TO kokonut_baal_indexer_owner;
GRANT SELECT (id, slug) ON public.protocol TO kokonut_baal_indexer_owner;
GRANT SELECT (
    chain, indexer_type, last_synced_block, last_synced_at, status,
    error_message, metadata, updated_at
),
      INSERT (chain, indexer_type, last_synced_block, last_synced_at, status, error_message, metadata),
      UPDATE (last_synced_block, last_synced_at, status, error_message, metadata, updated_at)
    ON public.chain_indexer_status TO kokonut_baal_indexer_owner;
GRANT SELECT (chain, event_type, tx_hash) ON public.governance_event TO kokonut_baal_indexer_owner;
GRANT INSERT (
    wallet_id, protocol_id, chain, event_type, proposal_id, proposal_title,
    vote_choice, amount, token, tx_hash, block_number, block_timestamp, metadata
) ON public.governance_event TO kokonut_baal_indexer_owner;

DO $$
DECLARE target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'wallet_profile', 'protocol', 'chain_indexer_status', 'governance_event'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = target_table
               AND policyname = 'baal_indexer_owner_function_access'
        ) THEN
            EXECUTE format(
                'CREATE POLICY baal_indexer_owner_function_access ON public.%I '
                || 'FOR ALL TO kokonut_baal_indexer_owner USING (true) WITH CHECK (true)',
                target_table
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.acquire_baal_indexer_lock()
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_baal_indexer_login' THEN
        RAISE EXCEPTION 'Baal indexer lock is not authorized' USING ERRCODE = '42501';
    END IF;
    PERFORM pg_advisory_lock(hashtextextended('kokonut:baal-indexer', 0));
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.release_baal_indexer_lock()
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE released BOOLEAN;
BEGIN
    IF session_user <> 'kokonut_baal_indexer_login' THEN
        RAISE EXCEPTION 'Baal indexer unlock is not authorized' USING ERRCODE = '42501';
    END IF;
    released := pg_advisory_unlock(hashtextextended('kokonut:baal-indexer', 0));
    IF NOT released THEN
        RAISE EXCEPTION 'Baal indexer lock is not held by this connection' USING ERRCODE = '55000';
    END IF;
    RETURN released;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.read_baal_indexer_cursor()
RETURNS TABLE(last_synced_block BIGINT, metadata JSONB)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_baal_indexer_login' THEN
        RAISE EXCEPTION 'Baal cursor read is not authorized' USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT status.last_synced_block, COALESCE(status.metadata, '{}'::jsonb)
      FROM public.chain_indexer_status AS status
     WHERE status.chain = 'gnosis' AND status.indexer_type = 'baal';
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.resolve_baal_protocol()
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE protocol_id UUID;
BEGIN
    IF session_user <> 'kokonut_baal_indexer_login' THEN
        RAISE EXCEPTION 'Baal protocol lookup is not authorized' USING ERRCODE = '42501';
    END IF;
    SELECT protocol.id INTO protocol_id FROM public.protocol AS protocol
     WHERE protocol.slug = 'kokonut-treasury' LIMIT 1;
    RETURN protocol_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.resolve_baal_wallet(requested_address TEXT)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE wallet_id UUID;
BEGIN
    IF session_user <> 'kokonut_baal_indexer_login'
       OR requested_address IS NULL OR requested_address !~* '^0x[0-9a-f]{40}$' THEN
        RAISE EXCEPTION 'Baal wallet lookup is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    SELECT wallet.id INTO wallet_id FROM public.wallet_profile AS wallet
     WHERE lower(wallet.address) = lower(requested_address) AND wallet.chain = 'gnosis';
    RETURN wallet_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_baal_governance_event(record JSONB)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE wallet_id UUID; protocol_id UUID;
BEGIN
    IF session_user <> 'kokonut_baal_indexer_login'
       OR jsonb_typeof(record) <> 'object'
       OR record->>'chain' IS DISTINCT FROM 'gnosis'
       OR record->>'event_type' IS NULL
       OR record->>'event_type' NOT IN (
           'proposal_created', 'proposal_sponsored', 'vote_cast', 'proposal_processed',
           'proposal_cancelled', 'ragequit', 'governance_config_set', 'shaman_set'
       )
       OR record->>'tx_hash' IS NULL OR record->>'tx_hash' !~* '^0x[0-9a-f]{64}$'
       OR NULLIF(record->>'block_number', '') IS NULL
       OR (record->>'block_number')::BIGINT < 0
       OR NULLIF(record->>'block_timestamp', '') IS NULL
       OR jsonb_typeof(COALESCE(record->'metadata', '{}'::jsonb)) <> 'object'
       OR octet_length(record::TEXT) > 65536
       OR length(COALESCE(record->>'proposal_title', '')) > 500 THEN
        RAISE EXCEPTION 'Baal governance event is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;

    wallet_id := NULLIF(record->>'wallet_id', '')::UUID;
    protocol_id := NULLIF(record->>'protocol_id', '')::UUID;
    IF wallet_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.wallet_profile AS wallet
         WHERE wallet.id = wallet_id AND wallet.chain = 'gnosis'
    ) THEN
        RAISE EXCEPTION 'Baal wallet reference is outside the Gnosis scope' USING ERRCODE = '23514';
    END IF;
    IF protocol_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.protocol AS protocol
         WHERE protocol.id = protocol_id AND protocol.slug = 'kokonut-treasury'
    ) THEN
        RAISE EXCEPTION 'Baal protocol reference is outside the canonical scope' USING ERRCODE = '23514';
    END IF;

    INSERT INTO public.governance_event (
        wallet_id, protocol_id, chain, event_type, proposal_id, proposal_title,
        vote_choice, amount, token, tx_hash, block_number, block_timestamp, metadata
    ) VALUES (
        wallet_id, protocol_id, 'gnosis', record->>'event_type', record->>'proposal_id',
        record->>'proposal_title', record->>'vote_choice',
        NULLIF(record->>'amount', '')::NUMERIC, record->>'token', lower(record->>'tx_hash'),
        (record->>'block_number')::BIGINT, (record->>'block_timestamp')::TIMESTAMPTZ,
        COALESCE(record->'metadata', '{}'::jsonb)
    ) ON CONFLICT (chain, event_type, tx_hash) DO NOTHING;
    RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.update_baal_indexer_status(
    requested_block BIGINT, requested_status TEXT, requested_error TEXT
)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_baal_indexer_login'
       OR requested_block IS NULL OR requested_block < 0
       OR requested_status IS NULL OR requested_status NOT IN ('syncing', 'healthy', 'failed')
       OR length(COALESCE(requested_error, '')) > 256 THEN
        RAISE EXCEPTION 'Baal indexer status is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.chain_indexer_status (
        chain, indexer_type, last_synced_block, last_synced_at,
        status, error_message, metadata
    ) VALUES (
        'gnosis', 'baal', requested_block, NOW(), requested_status, requested_error, '{}'::jsonb
    ) ON CONFLICT (chain, indexer_type) DO UPDATE SET
        last_synced_block = EXCLUDED.last_synced_block,
        last_synced_at = NOW(), status = EXCLUDED.status,
        error_message = EXCLUDED.error_message,
        updated_at = NOW();
END;
$$;

DO $$
DECLARE function_signature TEXT;
BEGIN
    FOREACH function_signature IN ARRAY ARRAY[
        'kokonut_security.acquire_baal_indexer_lock()',
        'kokonut_security.release_baal_indexer_lock()',
        'kokonut_security.read_baal_indexer_cursor()',
        'kokonut_security.resolve_baal_protocol()',
        'kokonut_security.resolve_baal_wallet(text)',
        'kokonut_security.store_baal_governance_event(jsonb)',
        'kokonut_security.update_baal_indexer_status(bigint,text,text)'
    ] LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO kokonut_baal_indexer_owner', function_signature);
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', function_signature);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO kokonut_baal_indexer_login', function_signature);
    END LOOP;
END;
$$;

COMMIT;
