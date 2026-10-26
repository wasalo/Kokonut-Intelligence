-- Isolate legacy Gnosis Moloch indexing behind one dedicated login and a
-- fixed set of SECURITY DEFINER functions. The login cannot access tables.
-- Receipt, projections, outbox intents, and the block cursor remain committed
-- in the indexer's existing per-range transaction.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_gnosis_indexer_owner') THEN
        CREATE ROLE kokonut_gnosis_indexer_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_gnosis_indexer_owner'
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Gnosis indexer function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_gnosis_indexer_login') THEN
        CREATE ROLE kokonut_gnosis_indexer_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_gnosis_indexer_login'
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Gnosis indexer login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN ('kokonut_gnosis_indexer_owner', 'kokonut_gnosis_indexer_login')
            OR member_role.rolname IN ('kokonut_gnosis_indexer_owner', 'kokonut_gnosis_indexer_login')
    ) THEN
        RAISE EXCEPTION 'Gnosis indexer roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_gnosis_indexer_login;
GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_gnosis_indexer_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_gnosis_indexer_owner;

GRANT SELECT (id, address, chain, owner_type, owner_id)
    ON public.wallet_profile TO kokonut_gnosis_indexer_owner;
GRANT SELECT (id, slug) ON public.protocol TO kokonut_gnosis_indexer_owner;
GRANT SELECT, INSERT, UPDATE ON public.chain_indexer_status
    TO kokonut_gnosis_indexer_owner;
GRANT SELECT (chain, transaction_hash, log_index, block_number, block_hash, event_name),
      INSERT (chain, transaction_hash, log_index, block_number, block_hash, event_name)
    ON public.gnosis_event_log_receipt TO kokonut_gnosis_indexer_owner;
-- PostgreSQL requires UPDATE privilege on a selected key column when the
-- function locks an existing receipt row with FOR KEY SHARE.
GRANT UPDATE (transaction_hash)
    ON public.gnosis_event_log_receipt TO kokonut_gnosis_indexer_owner;
GRANT INSERT (
    wallet_id, protocol_id, chain, event_type, proposal_id, proposal_title,
    vote_choice, amount, token, tx_hash, block_number, block_timestamp, metadata
) ON public.governance_event TO kokonut_gnosis_indexer_owner;
GRANT SELECT (id, tx_hash, chain, block_number)
    ON public.governance_event TO kokonut_gnosis_indexer_owner;
GRANT INSERT (
    location_id, wallet_id, chain, event_date, flow_direction, amount, token,
    usd_value, source, tx_hash, block_number, verified, notes
) ON public.treasury_event TO kokonut_gnosis_indexer_owner;
GRANT SELECT (id, tx_hash, chain, block_number)
    ON public.treasury_event TO kokonut_gnosis_indexer_owner;
GRANT INSERT (
    wallet_id, protocol_id, location_id, usage_date, action_type, amount, token,
    tx_hash, chain, block_number, verified, notes
) ON public.digital_lego_usage TO kokonut_gnosis_indexer_owner;
GRANT SELECT (id, tx_hash, chain, block_number, action_type)
    ON public.digital_lego_usage TO kokonut_gnosis_indexer_owner;
GRANT SELECT (id, event_key, source_table, source_id, target_table, columns, rows, payload_hash)
    ON public.clickhouse_outbox TO kokonut_gnosis_indexer_owner;
GRANT INSERT (event_key, source_table, source_id, target_table, columns, rows, payload_hash)
    ON public.clickhouse_outbox TO kokonut_gnosis_indexer_owner;
GRANT UPDATE (updated_at) ON public.clickhouse_outbox TO kokonut_gnosis_indexer_owner;

CREATE INDEX IF NOT EXISTS idx_gnosis_indexer_governance_tx_block
    ON public.governance_event (tx_hash, block_number)
    WHERE chain = 'gnosis' AND tx_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gnosis_indexer_treasury_tx_block
    ON public.treasury_event (tx_hash, block_number)
    WHERE chain = 'gnosis' AND tx_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gnosis_indexer_dlego_tx_block
    ON public.digital_lego_usage (tx_hash, block_number)
    WHERE chain = 'gnosis' AND tx_hash IS NOT NULL;

DO $$
DECLARE
    target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'wallet_profile', 'protocol', 'chain_indexer_status',
        'gnosis_event_log_receipt', 'governance_event', 'treasury_event',
        'digital_lego_usage', 'clickhouse_outbox'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = target_table
               AND policyname = 'gnosis_indexer_owner_function_access'
        ) THEN
            EXECUTE format(
                'CREATE POLICY gnosis_indexer_owner_function_access ON public.%I '
                || 'FOR ALL TO kokonut_gnosis_indexer_owner USING (true) WITH CHECK (true)',
                target_table
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.acquire_gnosis_indexer_lock()
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login' THEN
        RAISE EXCEPTION 'Gnosis indexer lock is not authorized' USING ERRCODE = '42501';
    END IF;
    PERFORM pg_advisory_lock(hashtextextended('kokonut:gnosis-moloch-indexer', 0));
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.release_gnosis_indexer_lock()
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE released BOOLEAN;
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login' THEN
        RAISE EXCEPTION 'Gnosis indexer unlock is not authorized' USING ERRCODE = '42501';
    END IF;
    released := pg_advisory_unlock(hashtextextended('kokonut:gnosis-moloch-indexer', 0));
    IF NOT released THEN
        RAISE EXCEPTION 'Gnosis indexer lock is not held by this connection' USING ERRCODE = '55000';
    END IF;
    RETURN released;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.read_gnosis_indexer_cursor()
RETURNS TABLE(last_synced_block BIGINT, metadata JSONB)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login' THEN
        RAISE EXCEPTION 'Gnosis cursor read is not authorized' USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT status.last_synced_block, COALESCE(status.metadata, '{}'::jsonb)
      FROM public.chain_indexer_status AS status
     WHERE status.chain = 'gnosis' AND status.indexer_type = 'gnosis_moloch';
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.claim_gnosis_event_log(
    requested_chain TEXT, requested_tx_hash TEXT, requested_log_index BIGINT,
    requested_block_number BIGINT, requested_block_hash TEXT, requested_event_name TEXT
)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE inserted_hash TEXT; inserted_block BIGINT; inserted_event TEXT;
        stored_hash TEXT; stored_block BIGINT; stored_event TEXT;
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login'
       OR requested_chain IS DISTINCT FROM 'gnosis'
       OR requested_tx_hash IS NULL OR requested_tx_hash !~ '^0x[0-9a-f]{64}$'
       OR requested_block_hash IS NULL OR requested_block_hash !~ '^0x[0-9a-f]{64}$'
       OR requested_log_index < 0 OR requested_block_number < 0
       OR requested_event_name IS NULL OR requested_event_name NOT IN (
           'SubmitProposal', 'ProcessProposal', 'VoteProposal', 'Ragequit',
           'Trade', 'UpdateDelegate', 'Withdraw', 'CancelProposal'
       ) THEN
        RAISE EXCEPTION 'Gnosis event receipt is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.gnosis_event_log_receipt (
        chain, transaction_hash, log_index, block_number, block_hash, event_name
    ) VALUES (
        requested_chain, requested_tx_hash, requested_log_index,
        requested_block_number, requested_block_hash, requested_event_name
    ) ON CONFLICT (chain, transaction_hash, log_index) DO NOTHING
    RETURNING block_hash, block_number, event_name
         INTO inserted_hash, inserted_block, inserted_event;
    IF FOUND THEN
        RETURN TRUE;
    END IF;
    SELECT receipt.block_hash, receipt.block_number, receipt.event_name
      INTO stored_hash, stored_block, stored_event
      FROM public.gnosis_event_log_receipt AS receipt
     WHERE receipt.chain = requested_chain
       AND receipt.transaction_hash = requested_tx_hash
       AND receipt.log_index = requested_log_index
     FOR KEY SHARE;
    IF (stored_hash, stored_block, stored_event)
       IS DISTINCT FROM (requested_block_hash, requested_block_number, requested_event_name) THEN
        RAISE EXCEPTION 'Gnosis canonical event identity changed' USING ERRCODE = '23514';
    END IF;
    RETURN FALSE;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.resolve_gnosis_wallet(
    requested_address TEXT
)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE wallet_id UUID;
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login'
       OR requested_address IS NULL OR requested_address !~* '^0x[0-9a-f]{40}$' THEN
        RAISE EXCEPTION 'Gnosis wallet lookup is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    SELECT wallet.id INTO wallet_id FROM public.wallet_profile AS wallet
     WHERE lower(wallet.address) = lower(requested_address) AND wallet.chain = 'gnosis';
    RETURN wallet_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.resolve_gnosis_wallet_location(
    requested_wallet_id UUID
)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE location_id UUID;
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login' THEN
        RAISE EXCEPTION 'Gnosis wallet location lookup is unauthorized' USING ERRCODE = '42501';
    END IF;
    SELECT wallet.owner_id INTO location_id FROM public.wallet_profile AS wallet
     WHERE wallet.id = requested_wallet_id AND wallet.owner_type = 'farm';
    RETURN location_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.resolve_gnosis_protocol()
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE protocol_id UUID;
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login' THEN
        RAISE EXCEPTION 'Gnosis protocol lookup is unauthorized' USING ERRCODE = '42501';
    END IF;
    SELECT protocol.id INTO protocol_id FROM public.protocol AS protocol
     WHERE protocol.slug = 'kokonut-treasury' LIMIT 1;
    RETURN protocol_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_gnosis_governance_event(
    record JSONB
)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE event_id UUID;
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login'
       OR jsonb_typeof(record) <> 'object'
       OR record->>'chain' IS DISTINCT FROM 'gnosis'
       OR record->>'event_type' NOT IN (
           'proposal_created', 'proposal_executed', 'proposal_failed', 'vote_cast',
           'ragequit', 'tribute', 'delegate_changed'
       )
       OR record->>'tx_hash' IS NULL OR record->>'tx_hash' !~ '^0x[0-9a-f]{64}$'
       OR record->>'block_number' IS NULL
       OR NOT EXISTS (
           SELECT 1 FROM public.gnosis_event_log_receipt AS receipt
            WHERE receipt.chain = 'gnosis'
              AND receipt.transaction_hash = record->>'tx_hash'
              AND receipt.block_number = (record->>'block_number')::BIGINT
              AND (
                  (receipt.event_name = 'SubmitProposal' AND record->>'event_type' = 'proposal_created')
                  OR (receipt.event_name = 'ProcessProposal' AND record->>'event_type' IN ('proposal_executed', 'proposal_failed'))
                  OR (receipt.event_name = 'VoteProposal' AND record->>'event_type' = 'vote_cast')
                  OR (receipt.event_name = 'Ragequit' AND record->>'event_type' = 'ragequit')
                  OR (receipt.event_name = 'Trade' AND record->>'event_type' = 'tribute')
                  OR (receipt.event_name = 'UpdateDelegate' AND record->>'event_type' = 'delegate_changed')
              )
       ) THEN
        RAISE EXCEPTION 'Gnosis governance event is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.governance_event (
        wallet_id, protocol_id, chain, event_type, proposal_id, proposal_title,
        vote_choice, amount, token, tx_hash, block_number, block_timestamp, metadata
    ) VALUES (
        NULLIF(record->>'wallet_id', '')::UUID,
        NULLIF(record->>'protocol_id', '')::UUID,
        'gnosis', record->>'event_type', record->>'proposal_id',
        record->>'proposal_title', record->>'vote_choice',
        NULLIF(record->>'amount', '')::NUMERIC, record->>'token', record->>'tx_hash',
        NULLIF(record->>'block_number', '')::BIGINT,
        NULLIF(record->>'block_timestamp', '')::TIMESTAMPTZ,
        COALESCE(record->'metadata', '{}'::jsonb)
    ) RETURNING id INTO event_id;
    RETURN event_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_gnosis_treasury_event(
    record JSONB
)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE event_id UUID;
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login'
       OR jsonb_typeof(record) <> 'object'
       OR record->>'chain' IS DISTINCT FROM 'gnosis'
       OR record->>'flow_direction' IS DISTINCT FROM 'outflow'
       OR record->>'tx_hash' IS NULL OR record->>'tx_hash' !~ '^0x[0-9a-f]{64}$'
       OR record->>'block_number' IS NULL
       OR NOT EXISTS (
           SELECT 1 FROM public.gnosis_event_log_receipt AS receipt
            WHERE receipt.chain = 'gnosis'
              AND receipt.transaction_hash = record->>'tx_hash'
              AND receipt.block_number = (record->>'block_number')::BIGINT
              AND receipt.event_name = 'Withdraw'
       ) THEN
        RAISE EXCEPTION 'Gnosis treasury event is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.treasury_event (
        location_id, wallet_id, chain, event_date, flow_direction, amount, token,
        usd_value, source, tx_hash, block_number, verified, notes
    ) VALUES (
        NULLIF(record->>'location_id', '')::UUID,
        NULLIF(record->>'wallet_id', '')::UUID, 'gnosis',
        COALESCE(NULLIF(record->>'event_date', '')::DATE, CURRENT_DATE),
        'outflow', NULLIF(record->>'amount', '')::NUMERIC, record->>'token',
        NULLIF(record->>'usd_value', '')::NUMERIC,
        COALESCE(NULLIF(record->>'source', ''), 'moloch_dao'), record->>'tx_hash',
        NULLIF(record->>'block_number', '')::BIGINT,
        COALESCE((record->>'verified')::BOOLEAN, TRUE), record->>'notes'
    ) RETURNING id INTO event_id;
    RETURN event_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_gnosis_digital_lego_usage(
    record JSONB
)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE usage_id UUID;
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login'
       OR jsonb_typeof(record) <> 'object'
       OR record->>'chain' IS DISTINCT FROM 'gnosis'
       OR record->>'action_type' NOT IN ('vote', 'swap', 'withdraw', 'other')
       OR record->>'tx_hash' IS NULL OR record->>'tx_hash' !~ '^0x[0-9a-f]{64}$'
       OR record->>'block_number' IS NULL
       OR NOT EXISTS (
           SELECT 1 FROM public.gnosis_event_log_receipt AS receipt
            WHERE receipt.chain = 'gnosis'
              AND receipt.transaction_hash = record->>'tx_hash'
              AND receipt.block_number = (record->>'block_number')::BIGINT
              AND (
                  (receipt.event_name IN ('SubmitProposal', 'VoteProposal', 'ProcessProposal', 'CancelProposal') AND record->>'action_type' = 'vote')
                  OR (receipt.event_name = 'Trade' AND record->>'action_type' = 'swap')
                  OR (receipt.event_name IN ('Ragequit', 'Withdraw') AND record->>'action_type' = 'withdraw')
                  OR (receipt.event_name = 'UpdateDelegate' AND record->>'action_type' = 'other')
              )
       ) THEN
        RAISE EXCEPTION 'Gnosis protocol usage is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.digital_lego_usage (
        wallet_id, protocol_id, location_id, usage_date, action_type, amount,
        token, tx_hash, chain, block_number, verified, notes
    ) VALUES (
        NULLIF(record->>'wallet_id', '')::UUID,
        NULLIF(record->>'protocol_id', '')::UUID,
        NULLIF(record->>'location_id', '')::UUID,
        NULLIF(record->>'usage_date', '')::DATE, record->>'action_type',
        NULLIF(record->>'amount', '')::NUMERIC, record->>'token', record->>'tx_hash',
        'gnosis', NULLIF(record->>'block_number', '')::BIGINT,
        COALESCE((record->>'verified')::BOOLEAN, TRUE), record->>'notes'
    ) ON CONFLICT DO NOTHING RETURNING id INTO usage_id;
    RETURN usage_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.enqueue_gnosis_clickhouse(
    requested_event_key TEXT, requested_source_table TEXT, requested_source_id TEXT,
    requested_target_table TEXT, requested_columns JSONB, requested_rows JSONB,
    requested_payload_hash TEXT
)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE outbox_id UUID;
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login'
       OR requested_event_key IS NULL OR requested_source_table IS NULL
       OR requested_source_id IS NULL OR requested_target_table IS NULL
       OR requested_columns IS NULL OR requested_rows IS NULL
       OR requested_payload_hash IS NULL
       OR requested_payload_hash !~ '^[0-9a-f]{64}$'
       OR jsonb_typeof(requested_columns) <> 'array'
       OR jsonb_typeof(requested_rows) <> 'array'
       OR jsonb_array_length(requested_rows) <> 1
       OR jsonb_typeof(requested_rows->0) <> 'array'
       OR requested_source_id !~ '^0x[0-9a-f]{64}$'
       OR NOT (
           (requested_source_table = 'governance_event' AND requested_target_table = 'wallet_events'
             AND requested_event_key LIKE ('governance:wallet_events:' || requested_source_id || ':%')
             AND requested_columns = '["timestamp","wallet_address","chain","tx_hash","block_number","event_type","value","token","status","metadata"]'::jsonb
             AND jsonb_array_length(requested_rows->0) = 10
             AND requested_rows->0->>2 = 'gnosis'
             AND requested_rows->0->>3 = requested_source_id)
           OR
           (requested_source_table = 'treasury_event' AND requested_target_table = 'wallet_events'
             AND requested_event_key LIKE ('governance:wallet_events:' || requested_source_id || ':%')
             AND requested_columns = '["timestamp","wallet_address","chain","tx_hash","block_number","event_type","value","token","status","metadata"]'::jsonb
             AND jsonb_array_length(requested_rows->0) = 10
             AND requested_rows->0->>2 = 'gnosis'
             AND requested_rows->0->>3 = requested_source_id)
           OR
           (requested_source_table = 'digital_lego_usage' AND requested_target_table = 'dlego_events'
             AND requested_event_key LIKE ('governance:dlego_events:' || requested_source_id || ':%')
             AND requested_columns = '["timestamp","wallet_id","protocol_id","location_id","action_type","amount","token","chain","tx_hash","metadata"]'::jsonb
             AND jsonb_array_length(requested_rows->0) = 10
             AND requested_rows->0->>7 = 'gnosis'
             AND requested_rows->0->>8 = requested_source_id)
       ) THEN
        RAISE EXCEPTION 'Gnosis ClickHouse projection is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    IF requested_source_id IS NULL OR requested_source_id !~ '^0x[0-9a-f]{64}$'
       OR NOT (
           (requested_source_table = 'governance_event' AND EXISTS (
               SELECT 1 FROM public.governance_event AS source
                WHERE source.chain = 'gnosis' AND source.tx_hash = requested_source_id
                  AND source.block_number = NULLIF(requested_rows->0->>4, '')::BIGINT
           ))
           OR (requested_source_table = 'treasury_event' AND EXISTS (
               SELECT 1 FROM public.treasury_event AS source
                WHERE source.chain = 'gnosis' AND source.tx_hash = requested_source_id
                  AND source.block_number = NULLIF(requested_rows->0->>4, '')::BIGINT
           ))
           OR (requested_source_table = 'digital_lego_usage' AND EXISTS (
               SELECT 1 FROM public.digital_lego_usage AS source
                WHERE source.chain = 'gnosis' AND source.tx_hash = requested_source_id
                  AND source.action_type = requested_rows->0->>4
           ))
       ) THEN
        RAISE EXCEPTION 'Gnosis projection has no matching canonical source row' USING ERRCODE = '23514';
    END IF;
    INSERT INTO public.clickhouse_outbox (
        event_key, source_table, source_id, target_table, columns, rows, payload_hash
    ) VALUES (
        requested_event_key, requested_source_table, requested_source_id,
        requested_target_table, requested_columns, requested_rows, requested_payload_hash
    ) ON CONFLICT (event_key) DO UPDATE SET updated_at = NOW()
      WHERE public.clickhouse_outbox.payload_hash = EXCLUDED.payload_hash
        AND public.clickhouse_outbox.source_table = EXCLUDED.source_table
        AND public.clickhouse_outbox.source_id = EXCLUDED.source_id
        AND public.clickhouse_outbox.target_table = EXCLUDED.target_table
        AND public.clickhouse_outbox.columns = EXCLUDED.columns
        AND public.clickhouse_outbox.rows = EXCLUDED.rows
    RETURNING id INTO outbox_id;
    IF outbox_id IS NULL THEN
        RAISE EXCEPTION 'Gnosis outbox event conflicts with an existing projection' USING ERRCODE = '23505';
    END IF;
    RETURN outbox_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.update_gnosis_indexer_status(
    requested_block BIGINT, requested_status TEXT, requested_error TEXT,
    requested_metadata JSONB
)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_gnosis_indexer_login'
       OR requested_status IS NULL OR requested_status NOT IN ('syncing', 'healthy', 'error')
       OR requested_block IS NULL OR requested_block < -1
       OR length(COALESCE(requested_error, '')) > 256
       OR jsonb_typeof(COALESCE(requested_metadata, '{}'::jsonb)) <> 'object' THEN
        RAISE EXCEPTION 'Gnosis indexer status is invalid or unauthorized' USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.chain_indexer_status (
        chain, indexer_type, last_synced_block, last_synced_at, status,
        error_message, metadata
    ) VALUES (
        'gnosis', 'gnosis_moloch', requested_block, NOW(),
        requested_status, requested_error, COALESCE(requested_metadata, '{}'::jsonb)
    ) ON CONFLICT (chain, indexer_type) DO UPDATE SET
        last_synced_block = EXCLUDED.last_synced_block,
        last_synced_at = NOW(), status = EXCLUDED.status,
        error_message = EXCLUDED.error_message,
        metadata = COALESCE(public.chain_indexer_status.metadata, '{}'::jsonb)
            || EXCLUDED.metadata,
        updated_at = NOW();
END;
$$;

DO $$
DECLARE function_signature TEXT;
BEGIN
    FOREACH function_signature IN ARRAY ARRAY[
        'kokonut_security.acquire_gnosis_indexer_lock()',
        'kokonut_security.release_gnosis_indexer_lock()',
        'kokonut_security.read_gnosis_indexer_cursor()',
        'kokonut_security.claim_gnosis_event_log(text,text,bigint,bigint,text,text)',
        'kokonut_security.resolve_gnosis_wallet(text)',
        'kokonut_security.resolve_gnosis_wallet_location(uuid)',
        'kokonut_security.resolve_gnosis_protocol()',
        'kokonut_security.store_gnosis_governance_event(jsonb)',
        'kokonut_security.store_gnosis_treasury_event(jsonb)',
        'kokonut_security.store_gnosis_digital_lego_usage(jsonb)',
        'kokonut_security.enqueue_gnosis_clickhouse(text,text,text,text,jsonb,jsonb,text)',
        'kokonut_security.update_gnosis_indexer_status(bigint,text,text,jsonb)'
    ] LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO kokonut_gnosis_indexer_owner', function_signature);
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', function_signature);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO kokonut_gnosis_indexer_login', function_signature);
    END LOOP;
END;
$$;

COMMIT;
