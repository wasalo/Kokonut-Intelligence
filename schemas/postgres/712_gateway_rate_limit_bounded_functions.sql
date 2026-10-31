-- Keep shared Gateway throttling state private to bounded SECURITY DEFINER
-- functions. Runtime callers can consume a bucket but cannot query or mutate
-- bucket rows directly; cleanup has a separate optional maintenance login.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_gateway_rate_limit_owner'
    ) THEN
        CREATE ROLE kokonut_gateway_rate_limit_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_gateway_rate_limit_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Gateway rate-limit function owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_gateway_rate_limit_owner'
            OR member_role.rolname = 'kokonut_gateway_rate_limit_owner'
    ) THEN
        RAISE EXCEPTION 'Gateway rate-limit function owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_gateway_rate_limit_owner;
GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_gateway_rate_limit_owner;
CREATE SCHEMA IF NOT EXISTS kokonut_rate_limit_maintenance
    AUTHORIZATION kokonut_gateway_rate_limit_owner;
ALTER SCHEMA kokonut_rate_limit_maintenance
    OWNER TO kokonut_gateway_rate_limit_owner;
REVOKE ALL ON SCHEMA kokonut_rate_limit_maintenance FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.gateway_rate_bucket
    TO kokonut_gateway_rate_limit_owner;

ALTER TABLE public.gateway_rate_bucket ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gateway_rate_bucket FORCE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public'
           AND tablename = 'gateway_rate_bucket'
           AND policyname = 'gateway_rate_limit_owner_access'
    ) THEN
        EXECUTE 'CREATE POLICY gateway_rate_limit_owner_access '
            || 'ON public.gateway_rate_bucket '
            || 'FOR ALL TO kokonut_gateway_rate_limit_owner '
            || 'USING (true) WITH CHECK (true)';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.consume_gateway_rate_bucket(
    requested_caller_hash TEXT,
    requested_tokens INTEGER,
    consume_tokens BOOLEAN
)
RETURNS TABLE(allowed BOOLEAN, retry_after_seconds INTEGER)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    bucket_tokens DOUBLE PRECISION;
    bucket_updated_at TIMESTAMPTZ;
    now_at TIMESTAMPTZ;
    refilled_tokens DOUBLE PRECISION;
    remaining_tokens DOUBLE PRECISION;
    request_allowed BOOLEAN;
BEGIN
    IF requested_caller_hash IS NULL
       OR requested_caller_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'caller hash must be 64 lowercase hexadecimal characters'
            USING ERRCODE = '22023';
    END IF;
    IF requested_tokens IS NULL OR requested_tokens < 1 OR requested_tokens > 100 THEN
        RAISE EXCEPTION 'requested tokens must be an integer between 1 and 100'
            USING ERRCODE = '22023';
    END IF;
    IF consume_tokens IS NULL THEN
        RAISE EXCEPTION 'consume flag is required'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.gateway_rate_bucket (caller_hash, tokens)
    VALUES (requested_caller_hash, 100)
    ON CONFLICT (caller_hash) DO NOTHING;

    SELECT bucket.tokens, bucket.updated_at
      INTO bucket_tokens, bucket_updated_at
      FROM public.gateway_rate_bucket AS bucket
     WHERE bucket.caller_hash = requested_caller_hash
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'rate-limit bucket could not be locked';
    END IF;

    now_at := pg_catalog.clock_timestamp();
    refilled_tokens := LEAST(
        100.0::DOUBLE PRECISION,
        bucket_tokens + GREATEST(
            0.0::DOUBLE PRECISION,
            EXTRACT(EPOCH FROM (now_at - bucket_updated_at))::DOUBLE PRECISION
        ) * 10.0
    );
    request_allowed := refilled_tokens >= requested_tokens;
    remaining_tokens := CASE
        WHEN consume_tokens AND request_allowed
            THEN refilled_tokens - requested_tokens
        ELSE refilled_tokens
    END;

    UPDATE public.gateway_rate_bucket
       SET tokens = remaining_tokens,
           updated_at = now_at
     WHERE caller_hash = requested_caller_hash;

    RETURN QUERY
    SELECT request_allowed,
           GREATEST(
               1,
               CEIL(
                   GREATEST(
                       0.0::DOUBLE PRECISION,
                       requested_tokens::DOUBLE PRECISION - refilled_tokens
                   ) / 10.0
               )::INTEGER
           );
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_rate_limit_maintenance.cleanup_idle_gateway_rate_buckets(
    requested_limit INTEGER
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    removed_count INTEGER;
BEGIN
    IF requested_limit IS NULL OR requested_limit < 1 OR requested_limit > 1000 THEN
        RAISE EXCEPTION 'cleanup limit must be an integer between 1 and 1000'
            USING ERRCODE = '22023';
    END IF;

    WITH candidates AS (
        SELECT bucket.caller_hash
          FROM public.gateway_rate_bucket AS bucket
         WHERE bucket.updated_at < pg_catalog.clock_timestamp() - INTERVAL '24 hours'
         ORDER BY bucket.updated_at, bucket.caller_hash
         FOR UPDATE SKIP LOCKED
         LIMIT requested_limit
    ), deleted AS (
        DELETE FROM public.gateway_rate_bucket AS bucket
         USING candidates
         WHERE bucket.caller_hash = candidates.caller_hash
         RETURNING 1
    )
    SELECT pg_catalog.count(*)::INTEGER
      INTO removed_count
      FROM deleted;

    RETURN removed_count;
END;
$$;

ALTER FUNCTION kokonut_security.consume_gateway_rate_bucket(TEXT, INTEGER, BOOLEAN)
    OWNER TO kokonut_gateway_rate_limit_owner;
ALTER FUNCTION kokonut_rate_limit_maintenance.cleanup_idle_gateway_rate_buckets(INTEGER)
    OWNER TO kokonut_gateway_rate_limit_owner;

REVOKE ALL ON FUNCTION
    kokonut_security.consume_gateway_rate_bucket(TEXT, INTEGER, BOOLEAN),
    kokonut_rate_limit_maintenance.cleanup_idle_gateway_rate_buckets(INTEGER)
FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE public.gateway_rate_bucket FROM kokonut_runtime;
        GRANT EXECUTE ON FUNCTION
            kokonut_security.consume_gateway_rate_bucket(TEXT, INTEGER, BOOLEAN)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.gateway_rate_bucket FROM kokonut_directus_runtime;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_rate_limit_maintenance_login'
    ) THEN
        GRANT USAGE ON SCHEMA kokonut_rate_limit_maintenance
            TO kokonut_rate_limit_maintenance_login;
        GRANT EXECUTE ON FUNCTION
            kokonut_rate_limit_maintenance.cleanup_idle_gateway_rate_buckets(INTEGER)
            TO kokonut_rate_limit_maintenance_login;
    END IF;
END;
$$;
REVOKE ALL ON TABLE public.gateway_rate_bucket FROM PUBLIC;

INSERT INTO kokonut_security.directus_relation_privilege_policy
    (schema_name, relation_name, access_mode, source_migration)
VALUES
    ('public', 'gateway_rate_bucket', 'no_access',
     '712_gateway_rate_limit_bounded_functions.sql')
ON CONFLICT (schema_name, relation_name) DO UPDATE
    SET access_mode = EXCLUDED.access_mode,
        source_migration = EXCLUDED.source_migration;

COMMENT ON TABLE public.gateway_rate_bucket IS
    'Private shared Gateway throttle state. Read/write access is available only through bounded rate-limit SECURITY DEFINER functions; idle cleanup requires the optional dedicated maintenance login.';

COMMIT;
