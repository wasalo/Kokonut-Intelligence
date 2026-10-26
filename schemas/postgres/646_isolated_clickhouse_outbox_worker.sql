-- Give the ClickHouse projection dispatcher a dedicated login and only two
-- bounded SECURITY DEFINER functions. The legacy operator CLI remains on its
-- existing runtime identity for reconciliation and dead-letter actions.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_clickhouse_outbox_owner') THEN
        CREATE ROLE kokonut_clickhouse_outbox_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_clickhouse_outbox_owner'
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'ClickHouse outbox function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_clickhouse_outbox_login') THEN
        CREATE ROLE kokonut_clickhouse_outbox_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_clickhouse_outbox_login'
          AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
               OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'ClickHouse outbox login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN ('kokonut_clickhouse_outbox_owner', 'kokonut_clickhouse_outbox_login')
            OR member_role.rolname IN ('kokonut_clickhouse_outbox_owner', 'kokonut_clickhouse_outbox_login')
    ) THEN
        RAISE EXCEPTION 'ClickHouse outbox roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_clickhouse_outbox_login;
GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_clickhouse_outbox_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_clickhouse_outbox_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_clickhouse_outbox_login;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_clickhouse_outbox_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_clickhouse_outbox_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_clickhouse_outbox_login;
REVOKE CREATE ON SCHEMA public FROM kokonut_clickhouse_outbox_login;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_clickhouse_outbox_login;

GRANT SELECT (
    id, event_key, source_table, source_id, target_table, columns, rows,
    payload_hash, status, attempt_count, available_at, lease_owner,
    lease_token, lease_expires_at, last_error, created_at, delivered_at
) ON public.clickhouse_outbox TO kokonut_clickhouse_outbox_owner;
GRANT UPDATE (
    status, attempt_count, available_at, lease_owner, lease_token,
    lease_expires_at, last_error, delivered_at, updated_at
) ON public.clickhouse_outbox TO kokonut_clickhouse_outbox_owner;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relname = 'clickhouse_outbox'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'clickhouse_outbox'
           AND policyname = 'clickhouse_outbox_owner_function_access'
    ) THEN
        EXECUTE 'CREATE POLICY clickhouse_outbox_owner_function_access '
            || 'ON public.clickhouse_outbox FOR ALL TO kokonut_clickhouse_outbox_owner '
            || 'USING (true) WITH CHECK (true)';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.claim_clickhouse_outbox_batch(
    requested_worker_id TEXT, requested_limit INTEGER
)
RETURNS TABLE (
    id UUID, event_key VARCHAR, source_table VARCHAR, source_id VARCHAR,
    target_table VARCHAR, columns JSONB, rows JSONB, payload_hash VARCHAR,
    attempt_count INTEGER, lease_token UUID
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
BEGIN
    IF session_user <> 'kokonut_clickhouse_outbox_login'
       OR requested_worker_id IS NULL
       OR requested_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
       OR requested_limit IS NULL OR requested_limit < 1 OR requested_limit > 100 THEN
        RAISE EXCEPTION 'ClickHouse outbox claim is not authorized' USING ERRCODE = '42501';
    END IF;

    WITH expired AS (
        SELECT outbox.id
          FROM public.clickhouse_outbox AS outbox
         WHERE outbox.status = 'processing' AND outbox.lease_expires_at < NOW()
         ORDER BY outbox.lease_expires_at, outbox.id
         LIMIT requested_limit
         FOR UPDATE SKIP LOCKED
    )
    UPDATE public.clickhouse_outbox AS outbox
       SET status = CASE WHEN outbox.attempt_count >= 8 THEN 'dead_letter' ELSE 'retryable' END,
           lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
           available_at = NOW(), updated_at = NOW(),
           last_error = COALESCE(outbox.last_error, 'delivery lease expired')
      FROM expired
     WHERE outbox.id = expired.id;

    RETURN QUERY
    WITH candidates AS (
        SELECT outbox.id
          FROM public.clickhouse_outbox AS outbox
         WHERE outbox.status IN ('pending', 'retryable')
           AND outbox.available_at <= NOW()
         ORDER BY outbox.created_at, outbox.id
         LIMIT requested_limit
         FOR UPDATE SKIP LOCKED
    )
    UPDATE public.clickhouse_outbox AS outbox
       SET status = 'processing', attempt_count = outbox.attempt_count + 1,
           lease_owner = requested_worker_id,
           lease_token = gen_random_uuid(),
           lease_expires_at = NOW() + INTERVAL '300 seconds',
           updated_at = NOW()
      FROM candidates
     WHERE outbox.id = candidates.id
    RETURNING outbox.id, outbox.event_key, outbox.source_table, outbox.source_id,
              outbox.target_table, outbox.columns, outbox.rows, outbox.payload_hash,
              outbox.attempt_count, outbox.lease_token;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.finish_clickhouse_outbox_delivery(
    requested_id UUID, requested_worker_id TEXT, requested_lease_token UUID,
    requested_success BOOLEAN, requested_error TEXT,
    requested_retry_delay_seconds INTEGER, requested_permanent_failure BOOLEAN
)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE changed INTEGER;
BEGIN
    IF session_user <> 'kokonut_clickhouse_outbox_login'
       OR requested_id IS NULL OR requested_lease_token IS NULL
       OR requested_worker_id IS NULL
       OR requested_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
       OR requested_success IS NULL OR requested_permanent_failure IS NULL
       OR (requested_success AND requested_permanent_failure)
       OR requested_retry_delay_seconds IS NULL
       OR requested_retry_delay_seconds < 0 OR requested_retry_delay_seconds > 3600
       OR (NOT requested_success AND (requested_error IS NULL OR length(requested_error) > 1000)) THEN
        RAISE EXCEPTION 'ClickHouse outbox completion is not authorized' USING ERRCODE = '42501';
    END IF;

    UPDATE public.clickhouse_outbox AS outbox
       SET status = CASE WHEN requested_success THEN 'succeeded'
                         WHEN requested_permanent_failure OR outbox.attempt_count >= 8 THEN 'dead_letter'
                         ELSE 'retryable' END,
           available_at = CASE WHEN requested_success THEN outbox.available_at
                               ELSE NOW() + make_interval(secs => requested_retry_delay_seconds) END,
           delivered_at = CASE WHEN requested_success THEN NOW() ELSE outbox.delivered_at END,
           last_error = requested_error,
           lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
           updated_at = NOW()
     WHERE outbox.id = requested_id AND outbox.status = 'processing'
       AND outbox.lease_owner = requested_worker_id
       AND outbox.lease_token = requested_lease_token
       AND outbox.lease_expires_at > NOW();
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END;
$$;

ALTER FUNCTION kokonut_security.claim_clickhouse_outbox_batch(TEXT, INTEGER)
    OWNER TO kokonut_clickhouse_outbox_owner;
ALTER FUNCTION kokonut_security.finish_clickhouse_outbox_delivery(
    UUID, TEXT, UUID, BOOLEAN, TEXT, INTEGER, BOOLEAN
) OWNER TO kokonut_clickhouse_outbox_owner;
REVOKE ALL ON FUNCTION kokonut_security.claim_clickhouse_outbox_batch(TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.finish_clickhouse_outbox_delivery(
    UUID, TEXT, UUID, BOOLEAN, TEXT, INTEGER, BOOLEAN
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.claim_clickhouse_outbox_batch(TEXT, INTEGER)
    TO kokonut_clickhouse_outbox_login;
GRANT EXECUTE ON FUNCTION kokonut_security.finish_clickhouse_outbox_delivery(
    UUID, TEXT, UUID, BOOLEAN, TEXT, INTEGER, BOOLEAN
) TO kokonut_clickhouse_outbox_login;

COMMIT;
