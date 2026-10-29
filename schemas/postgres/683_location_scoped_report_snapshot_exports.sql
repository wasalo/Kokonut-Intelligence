-- Durable, location-scoped report snapshot export requests. Browser access
-- stays behind signed operator context; the worker receives only bounded
-- lease-fenced functions and never direct table access.

BEGIN;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_report_snapshot_export_owner',
        'kokonut_report_snapshot_export_login'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                role_name
            );
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_report_snapshot_export_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'report snapshot export owner has unsafe role attributes';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_report_snapshot_export_login'
           AND (rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'report snapshot export login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN (
                   'kokonut_report_snapshot_export_owner',
                   'kokonut_report_snapshot_export_login'
               )
            OR member_role.rolname IN (
                   'kokonut_report_snapshot_export_owner',
                   'kokonut_report_snapshot_export_login'
               )
    ) THEN
        RAISE EXCEPTION 'report snapshot export roles must not have role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO
    kokonut_report_snapshot_export_owner,
    kokonut_report_snapshot_export_login;
GRANT USAGE ON SCHEMA public TO kokonut_report_snapshot_export_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_report_snapshot_export_owner;
REVOKE CREATE ON SCHEMA public FROM kokonut_report_snapshot_export_login;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_report_snapshot_export_login;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_report_snapshot_export_login;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_report_snapshot_export_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_report_snapshot_export_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_report_snapshot_export_login;

CREATE TABLE IF NOT EXISTS public.report_snapshot_export_request (
    request_id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES public.report_snapshot(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    requested_by UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    idempotency_key UUID NOT NULL,
    source_snapshot_hash TEXT NOT NULL CHECK (source_snapshot_hash ~ '^[0-9a-f]{64}$'),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'retryable', 'dead_letter', 'completed', 'cancelled')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 8),
    available_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    lease_owner TEXT CHECK (
        lease_owner IS NULL OR lease_owner ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
    ),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    artifact_id UUID,
    artifact_sha256 TEXT CHECK (
        artifact_sha256 IS NULL OR artifact_sha256 ~ '^[0-9a-f]{64}$'
    ),
    artifact_size BIGINT CHECK (artifact_size IS NULL OR artifact_size BETWEEN 1 AND 524288),
    last_error_class TEXT CHECK (
        last_error_class IS NULL OR last_error_class IN (
            'lease_expired', 'source_changed', 'snapshot_invalid',
            'snapshot_too_large', 'serialization_failed',
            'storage_unavailable', 'storage_write_failed', 'worker_timeout'
        )
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT report_snapshot_export_request_idempotency
        UNIQUE (requested_by, idempotency_key),
    CONSTRAINT report_snapshot_export_request_lease_shape CHECK (
        (status = 'processing'
            AND lease_owner IS NOT NULL AND lease_token IS NOT NULL
            AND lease_expires_at IS NOT NULL)
        OR (status <> 'processing'
            AND lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)
    ),
    CONSTRAINT report_snapshot_export_request_artifact_shape CHECK (
        (status = 'completed'
            AND artifact_id IS NOT NULL AND artifact_sha256 IS NOT NULL
            AND artifact_size IS NOT NULL AND completed_at IS NOT NULL)
        OR (status <> 'completed'
            AND artifact_id IS NULL AND artifact_sha256 IS NULL
            AND artifact_size IS NULL AND completed_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS report_snapshot_export_request_claim
    ON public.report_snapshot_export_request (created_at, request_id)
    WHERE status IN ('pending', 'retryable');
CREATE INDEX IF NOT EXISTS report_snapshot_export_request_location_read
    ON public.report_snapshot_export_request (location_id, created_at DESC, request_id DESC);
CREATE INDEX IF NOT EXISTS report_snapshot_export_request_lease
    ON public.report_snapshot_export_request (lease_expires_at, request_id)
    WHERE status = 'processing';

CREATE TABLE IF NOT EXISTS public.report_snapshot_export_attempt (
    attempt_id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    request_id UUID NOT NULL
        REFERENCES public.report_snapshot_export_request(request_id) ON DELETE RESTRICT,
    attempt_count INTEGER NOT NULL CHECK (attempt_count BETWEEN 1 AND 8),
    event_kind TEXT NOT NULL CHECK (
        event_kind IN ('claimed', 'lease_expired', 'completed', 'retryable', 'dead_letter')
    ),
    worker_id TEXT NOT NULL
        CHECK (worker_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'),
    error_class TEXT CHECK (
        error_class IS NULL OR error_class IN (
            'lease_expired', 'source_changed', 'snapshot_invalid',
            'snapshot_too_large', 'serialization_failed',
            'storage_unavailable', 'storage_write_failed', 'worker_timeout'
        )
    ),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);
CREATE INDEX IF NOT EXISTS report_snapshot_export_attempt_request
    ON public.report_snapshot_export_attempt (request_id, attempt_count, occurred_at);

ALTER TABLE public.report_snapshot_export_request ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.report_snapshot_export_request FORCE ROW LEVEL SECURITY;
ALTER TABLE public.report_snapshot_export_attempt ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.report_snapshot_export_attempt FORCE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'report_snapshot_export_request'
           AND policyname = 'report_snapshot_export_owner_access'
    ) THEN
        CREATE POLICY report_snapshot_export_owner_access
            ON public.report_snapshot_export_request FOR ALL
            TO kokonut_report_snapshot_export_owner USING (TRUE) WITH CHECK (TRUE);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'report_snapshot_export_attempt'
           AND policyname = 'report_snapshot_export_attempt_owner_access'
    ) THEN
        CREATE POLICY report_snapshot_export_attempt_owner_access
            ON public.report_snapshot_export_attempt FOR ALL
            TO kokonut_report_snapshot_export_owner USING (TRUE) WITH CHECK (TRUE);
    END IF;
END;
$$;

REVOKE ALL ON TABLE
    public.report_snapshot_export_request,
    public.report_snapshot_export_attempt
FROM PUBLIC, kokonut_report_snapshot_export_login;
DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.report_snapshot_export_request, public.report_snapshot_export_attempt FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END;
$$;

GRANT SELECT ON TABLE public.report_snapshot_export_request,
    public.report_snapshot_export_attempt TO kokonut_report_snapshot_export_owner;
GRANT INSERT, UPDATE ON TABLE public.report_snapshot_export_request
    TO kokonut_report_snapshot_export_owner;
GRANT INSERT ON TABLE public.report_snapshot_export_attempt
    TO kokonut_report_snapshot_export_owner;
GRANT SELECT ON TABLE
    public.report_snapshot,
    public.location,
    public.operator_identity,
    public.operator_scope_grant,
    public.operator_organization_membership,
    public.location_organization_share,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_report_snapshot_export_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_report_snapshot_export_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_report_snapshot_export_owner;
DO $$
DECLARE table_name TEXT;
        policy_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'report_snapshot', 'location', 'operator_identity', 'operator_scope_grant',
        'operator_organization_membership', 'location_organization_share',
        'location_tenant_owner_verification', 'organization'
    ] LOOP
        policy_name := 'report_export_' || table_name || '_select';
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_class AS relation
            JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname = 'public' AND relation.relname = table_name
              AND relation.relrowsecurity
        ) AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies AS policy
             WHERE policy.schemaname = 'public' AND policy.tablename = table_name
               AND policy.policyname = policy_name
        ) THEN
            EXECUTE pg_catalog.format(
                'CREATE POLICY %I ON public.%I FOR SELECT TO kokonut_report_snapshot_export_owner USING (TRUE)',
                policy_name, table_name
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.request_report_snapshot_export(
    requested_location_id UUID,
    requested_snapshot_id UUID,
    requested_idempotency_key UUID
)
RETURNS TABLE (request_id UUID, status TEXT, created_at TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    source_hash TEXT;
    existing public.report_snapshot_export_request%ROWTYPE;
BEGIN
    IF SESSION_USER <> 'kokonut_runtime'
       OR requested_location_id IS NULL OR requested_snapshot_id IS NULL
       OR requested_idempotency_key IS NULL THEN
        RAISE EXCEPTION 'report snapshot export request is not authorized'
            USING ERRCODE = '42501';
    END IF;
    SELECT context.tenant_id, context.location_id, context.actor_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.tenant_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR NOT public.operator_scope_grant_allows(
           context_record.actor_id, 'report_snapshot_export', 'create', requested_location_id
       ) THEN
        RAISE EXCEPTION 'report snapshot export requires signed location create scope'
            USING ERRCODE = '42501';
    END IF;

    SELECT snapshot.snapshot_hash
      INTO source_hash
      FROM public.report_snapshot AS snapshot
     WHERE snapshot.id = requested_snapshot_id
       AND snapshot.location_id = requested_location_id
       AND snapshot.status IN ('verified', 'published')
       AND snapshot.snapshot_hash ~ '^[0-9a-f]{64}$';
    IF source_hash IS NULL THEN
        RETURN;
    END IF;

    SELECT request.* INTO existing
      FROM public.report_snapshot_export_request AS request
     WHERE request.requested_by = context_record.actor_id
       AND request.idempotency_key = requested_idempotency_key
     FOR UPDATE;
    IF FOUND THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.snapshot_id IS DISTINCT FROM requested_snapshot_id
           OR existing.source_snapshot_hash IS DISTINCT FROM source_hash THEN
            RAISE EXCEPTION 'report snapshot export idempotency key was reused for different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN QUERY SELECT existing.request_id, existing.status, existing.created_at;
        RETURN;
    END IF;

    INSERT INTO public.report_snapshot_export_request (
        snapshot_id, location_id, requested_by, idempotency_key,
        source_snapshot_hash
    ) VALUES (
        requested_snapshot_id, requested_location_id, context_record.actor_id,
        requested_idempotency_key, source_hash
    ) ON CONFLICT (requested_by, idempotency_key) DO NOTHING
    RETURNING * INTO existing;
    IF NOT FOUND THEN
        SELECT request.* INTO existing
          FROM public.report_snapshot_export_request AS request
         WHERE request.requested_by = context_record.actor_id
           AND request.idempotency_key = requested_idempotency_key;
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.snapshot_id IS DISTINCT FROM requested_snapshot_id
           OR existing.source_snapshot_hash IS DISTINCT FROM source_hash THEN
            RAISE EXCEPTION 'report snapshot export idempotency key was reused for different input'
                USING ERRCODE = '23505';
        END IF;
    END IF;
    RETURN QUERY SELECT existing.request_id, existing.status, existing.created_at;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_report_snapshot_exports(
    requested_location_id UUID,
    requested_limit INTEGER
)
RETURNS TABLE (
    request_id UUID, snapshot_id UUID, location_id UUID, status TEXT,
    attempt_count INTEGER, artifact_size BIGINT, created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, last_error_class TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD;
BEGIN
    IF SESSION_USER <> 'kokonut_runtime' OR requested_location_id IS NULL
       OR requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50 THEN
        RAISE EXCEPTION 'report snapshot export list request is invalid'
            USING ERRCODE = '42501';
    END IF;
    SELECT context.tenant_id, context.location_id, context.actor_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.tenant_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR NOT public.operator_scope_grant_allows(
           context_record.actor_id, 'report_snapshot_export', 'read', requested_location_id
       ) THEN
        RAISE EXCEPTION 'report snapshot export list requires signed location read scope'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT request.request_id, request.snapshot_id, request.location_id,
           request.status, request.attempt_count, request.artifact_size,
           request.created_at, request.updated_at, request.completed_at,
           request.last_error_class
      FROM public.report_snapshot_export_request AS request
     WHERE request.location_id = requested_location_id
     ORDER BY request.created_at DESC, request.request_id DESC
     LIMIT requested_limit;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_report_snapshot_export(
    requested_location_id UUID,
    requested_request_id UUID
)
RETURNS TABLE (
    request_id UUID, snapshot_id UUID, location_id UUID, status TEXT,
    attempt_count INTEGER, artifact_size BIGINT, created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, last_error_class TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD;
BEGIN
    IF SESSION_USER <> 'kokonut_runtime' OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'report snapshot export detail request is invalid'
            USING ERRCODE = '42501';
    END IF;
    SELECT context.tenant_id, context.location_id, context.actor_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.tenant_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR NOT public.operator_scope_grant_allows(
           context_record.actor_id, 'report_snapshot_export', 'read', requested_location_id
       ) THEN
        RAISE EXCEPTION 'report snapshot export detail requires signed location read scope'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT request.request_id, request.snapshot_id, request.location_id,
           request.status, request.attempt_count, request.artifact_size,
           request.created_at, request.updated_at, request.completed_at,
           request.last_error_class
      FROM public.report_snapshot_export_request AS request
     WHERE request.request_id = requested_request_id
       AND request.location_id = requested_location_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.authorize_report_snapshot_export_download(
    requested_location_id UUID,
    requested_request_id UUID
)
RETURNS TABLE (artifact_id UUID, artifact_sha256 TEXT, artifact_size BIGINT)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD;
        request_record RECORD;
BEGIN
    IF SESSION_USER <> 'kokonut_runtime' OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'report snapshot export download request is invalid'
            USING ERRCODE = '42501';
    END IF;
    SELECT context.tenant_id, context.location_id, context.actor_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.tenant_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR NOT public.operator_scope_grant_allows(
           context_record.actor_id, 'report_snapshot_export', 'download', requested_location_id
       ) THEN
        RAISE EXCEPTION 'report snapshot export download requires signed location download scope'
            USING ERRCODE = '42501';
    END IF;
    SELECT request.* INTO request_record
      FROM public.report_snapshot_export_request AS request
      JOIN public.report_snapshot AS snapshot
        ON snapshot.id = request.snapshot_id
       AND snapshot.location_id = request.location_id
       AND snapshot.status IN ('verified', 'published')
       AND snapshot.snapshot_hash = request.source_snapshot_hash
      JOIN public.operator_identity AS requester
        ON requester.id = request.requested_by AND requester.enabled
     WHERE request.request_id = requested_request_id
       AND request.location_id = requested_location_id
       AND request.status = 'completed'
       AND public.operator_scope_grant_allows(
           request.requested_by, 'report_snapshot_export', 'create', requested_location_id
       );
    IF NOT FOUND THEN
        RETURN;
    END IF;
    RETURN QUERY SELECT request_record.artifact_id,
                        request_record.artifact_sha256,
                        request_record.artifact_size;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.claim_report_snapshot_export_batch(
    requested_worker_id TEXT,
    requested_limit INTEGER,
    requested_lease_seconds INTEGER
)
RETURNS TABLE (
    request_id UUID, snapshot_id UUID, location_id UUID,
    requested_by UUID, attempt_count INTEGER, lease_token UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF SESSION_USER <> 'kokonut_report_snapshot_export_login'
       OR requested_worker_id IS NULL
       OR requested_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
       OR requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 25
       OR requested_lease_seconds IS NULL OR requested_lease_seconds NOT BETWEEN 30 AND 900 THEN
        RAISE EXCEPTION 'report snapshot export claim is not authorized'
            USING ERRCODE = '42501';
    END IF;

    WITH expired AS MATERIALIZED (
        SELECT request.request_id, request.attempt_count, request.lease_owner
          FROM public.report_snapshot_export_request AS request
         WHERE request.status = 'processing'
           AND request.lease_expires_at <= pg_catalog.clock_timestamp()
         ORDER BY request.lease_expires_at, request.request_id
         LIMIT requested_limit
         FOR UPDATE SKIP LOCKED
    ), recovered AS (
        UPDATE public.report_snapshot_export_request AS request
           SET status = CASE WHEN request.attempt_count >= 8 THEN 'dead_letter' ELSE 'retryable' END,
               lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
               last_error_class = 'lease_expired',
               available_at = pg_catalog.clock_timestamp(),
               updated_at = pg_catalog.clock_timestamp()
          FROM expired
         WHERE request.request_id = expired.request_id
        RETURNING request.request_id, request.attempt_count, expired.lease_owner
    )
    INSERT INTO public.report_snapshot_export_attempt (
        request_id, attempt_count, event_kind, worker_id, error_class
    )
    SELECT recovered.request_id, recovered.attempt_count, 'lease_expired',
           recovered.lease_owner, 'lease_expired'
      FROM recovered;

    RETURN QUERY
    WITH candidates AS MATERIALIZED (
        SELECT request.request_id
          FROM public.report_snapshot_export_request AS request
         WHERE request.status IN ('pending', 'retryable')
           AND request.attempt_count < 8
           AND request.available_at <= pg_catalog.clock_timestamp()
         ORDER BY request.created_at, request.request_id
         LIMIT requested_limit
         FOR UPDATE SKIP LOCKED
    ), claimed AS (
        UPDATE public.report_snapshot_export_request AS request
           SET status = 'processing', attempt_count = request.attempt_count + 1,
               lease_owner = requested_worker_id,
               lease_token = pg_catalog.gen_random_uuid(),
               lease_expires_at = pg_catalog.clock_timestamp()
                   + pg_catalog.make_interval(secs => requested_lease_seconds),
               updated_at = pg_catalog.clock_timestamp(), last_error_class = NULL
          FROM candidates
         WHERE request.request_id = candidates.request_id
        RETURNING request.request_id, request.snapshot_id, request.location_id,
                  request.requested_by, request.attempt_count, request.lease_token
    ), logged AS (
        INSERT INTO public.report_snapshot_export_attempt (
            request_id, attempt_count, event_kind, worker_id
        )
        SELECT claimed.request_id, claimed.attempt_count, 'claimed', requested_worker_id
          FROM claimed
        RETURNING report_snapshot_export_attempt.request_id
    )
    SELECT claimed.request_id, claimed.snapshot_id, claimed.location_id,
           claimed.requested_by, claimed.attempt_count, claimed.lease_token
      FROM claimed
      JOIN logged USING (request_id)
     ORDER BY claimed.request_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.read_report_snapshot_export_source(
    requested_request_id UUID,
    requested_worker_id TEXT,
    requested_lease_token UUID
)
RETURNS TABLE (
    id UUID, location_id UUID, report_name TEXT, report_type TEXT,
    status TEXT, period_start DATE, period_end DATE,
    snapshot_hash TEXT, report_data JSONB
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE request_record RECORD;
BEGIN
    IF SESSION_USER <> 'kokonut_report_snapshot_export_login'
       OR requested_request_id IS NULL OR requested_lease_token IS NULL
       OR requested_worker_id IS NULL
       OR requested_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$' THEN
        RAISE EXCEPTION 'report snapshot export source read is not authorized'
            USING ERRCODE = '42501';
    END IF;
    SELECT request.request_id, request.snapshot_id, request.location_id,
           request.requested_by, request.source_snapshot_hash
      INTO request_record
      FROM public.report_snapshot_export_request AS request
     WHERE request.request_id = requested_request_id
       AND request.status = 'processing'
       AND request.lease_owner = requested_worker_id
       AND request.lease_token = requested_lease_token
       AND request.lease_expires_at > pg_catalog.clock_timestamp();
    IF NOT FOUND THEN RETURN; END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM public.operator_identity AS requester
         WHERE requester.id = request_record.requested_by
           AND requester.enabled
           AND public.operator_scope_grant_allows(
               requester.id, 'report_snapshot_export', 'create', request_record.location_id
           )
    ) THEN
        RETURN;
    END IF;
    RETURN QUERY
    SELECT snapshot.id, snapshot.location_id, snapshot.report_name::TEXT,
           snapshot.report_type::TEXT, snapshot.status::TEXT,
           snapshot.period_start, snapshot.period_end, snapshot.snapshot_hash::TEXT,
           snapshot.report_data
      FROM public.report_snapshot AS snapshot
      JOIN public.report_snapshot_export_request AS request
        ON request.snapshot_id = snapshot.id
       AND request.location_id = snapshot.location_id
       AND request.source_snapshot_hash = snapshot.snapshot_hash
       AND request.request_id = request_record.request_id
       AND request.status = 'processing'
       AND request.lease_owner = requested_worker_id
       AND request.lease_token = requested_lease_token
       AND request.lease_expires_at > pg_catalog.clock_timestamp()
     WHERE snapshot.id = request_record.snapshot_id
       AND snapshot.location_id = request_record.location_id
       AND snapshot.status IN ('verified', 'published')
       AND pg_catalog.octet_length(snapshot.report_data::TEXT) <= 524288;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.finish_report_snapshot_export_attempt(
    requested_request_id UUID,
    requested_worker_id TEXT,
    requested_lease_token UUID,
    requested_success BOOLEAN,
    requested_error_class TEXT,
    requested_retry_delay_seconds INTEGER,
    requested_artifact_id UUID,
    requested_artifact_sha256 TEXT,
    requested_artifact_size BIGINT
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE request_record RECORD;
        final_status TEXT;
        final_error_class TEXT;
BEGIN
    IF SESSION_USER <> 'kokonut_report_snapshot_export_login'
       OR requested_request_id IS NULL OR requested_lease_token IS NULL
       OR requested_worker_id IS NULL
       OR requested_worker_id !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'
       OR requested_success IS NULL
       OR requested_retry_delay_seconds IS NULL
       OR requested_retry_delay_seconds NOT BETWEEN 0 AND 3600
       OR (requested_success AND (
           requested_error_class IS NOT NULL OR requested_artifact_id IS NULL
           OR requested_artifact_sha256 IS NULL
           OR requested_artifact_sha256 !~ '^[0-9a-f]{64}$'
           OR requested_artifact_size IS NULL
           OR requested_artifact_size NOT BETWEEN 1 AND 524288
       ))
       OR (NOT requested_success AND (
           requested_error_class IS NULL
           OR requested_error_class NOT IN (
               'lease_expired', 'source_changed', 'snapshot_invalid',
               'snapshot_too_large', 'serialization_failed',
               'storage_unavailable', 'storage_write_failed', 'worker_timeout'
           )
           OR requested_artifact_id IS NOT NULL
           OR requested_artifact_sha256 IS NOT NULL
           OR requested_artifact_size IS NOT NULL
       )) THEN
        RAISE EXCEPTION 'report snapshot export completion is invalid'
            USING ERRCODE = '42501';
    END IF;

    SELECT request.request_id, request.snapshot_id, request.location_id,
           request.requested_by, request.source_snapshot_hash,
           request.attempt_count
      INTO request_record
      FROM public.report_snapshot_export_request AS request
     WHERE request.request_id = requested_request_id
       AND request.status = 'processing'
       AND request.lease_owner = requested_worker_id
       AND request.lease_token = requested_lease_token
       AND request.lease_expires_at > pg_catalog.clock_timestamp()
     FOR UPDATE;
    IF NOT FOUND THEN RETURN 'lease_lost'; END IF;

    IF requested_success AND NOT EXISTS (
        SELECT 1
          FROM public.report_snapshot AS snapshot
          JOIN public.operator_identity AS requester
            ON requester.id = request_record.requested_by AND requester.enabled
         WHERE snapshot.id = request_record.snapshot_id
           AND snapshot.location_id = request_record.location_id
           AND snapshot.status IN ('verified', 'published')
           AND snapshot.snapshot_hash = request_record.source_snapshot_hash
           AND public.operator_scope_grant_allows(
               requester.id, 'report_snapshot_export', 'create', request_record.location_id
           )
    ) THEN
        final_status := 'dead_letter';
        final_error_class := 'source_changed';
    ELSIF requested_success THEN
        final_status := 'completed';
        final_error_class := NULL;
    ELSE
        final_status := CASE
            WHEN requested_error_class IN (
                'source_changed', 'snapshot_invalid', 'snapshot_too_large',
                'serialization_failed'
            ) OR request_record.attempt_count >= 8 THEN 'dead_letter'
            ELSE 'retryable'
        END;
        final_error_class := requested_error_class;
    END IF;

    UPDATE public.report_snapshot_export_request AS request
       SET status = final_status,
           lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
           available_at = CASE WHEN final_status = 'retryable'
                               THEN pg_catalog.clock_timestamp()
                                    + pg_catalog.make_interval(secs => requested_retry_delay_seconds)
                               ELSE request.available_at END,
           artifact_id = CASE WHEN final_status = 'completed' THEN requested_artifact_id ELSE NULL END,
           artifact_sha256 = CASE WHEN final_status = 'completed' THEN requested_artifact_sha256 ELSE NULL END,
           artifact_size = CASE WHEN final_status = 'completed' THEN requested_artifact_size ELSE NULL END,
           completed_at = CASE WHEN final_status = 'completed' THEN pg_catalog.clock_timestamp() ELSE NULL END,
           last_error_class = final_error_class,
           updated_at = pg_catalog.clock_timestamp()
     WHERE request.request_id = requested_request_id;

    INSERT INTO public.report_snapshot_export_attempt (
        request_id, attempt_count, event_kind, worker_id, error_class
    ) VALUES (
        requested_request_id, request_record.attempt_count,
        final_status, requested_worker_id, final_error_class
    );
    RETURN final_status;
END;
$$;

ALTER FUNCTION kokonut_security.request_report_snapshot_export(UUID, UUID, UUID)
    OWNER TO kokonut_report_snapshot_export_owner;
ALTER FUNCTION kokonut_security.list_report_snapshot_exports(UUID, INTEGER)
    OWNER TO kokonut_report_snapshot_export_owner;
ALTER FUNCTION kokonut_security.get_report_snapshot_export(UUID, UUID)
    OWNER TO kokonut_report_snapshot_export_owner;
ALTER FUNCTION kokonut_security.authorize_report_snapshot_export_download(UUID, UUID)
    OWNER TO kokonut_report_snapshot_export_owner;
ALTER FUNCTION kokonut_security.claim_report_snapshot_export_batch(TEXT, INTEGER, INTEGER)
    OWNER TO kokonut_report_snapshot_export_owner;
ALTER FUNCTION kokonut_security.read_report_snapshot_export_source(UUID, TEXT, UUID)
    OWNER TO kokonut_report_snapshot_export_owner;
ALTER FUNCTION kokonut_security.finish_report_snapshot_export_attempt(
    UUID, TEXT, UUID, BOOLEAN, TEXT, INTEGER, UUID, TEXT, BIGINT
) OWNER TO kokonut_report_snapshot_export_owner;

REVOKE ALL ON FUNCTION kokonut_security.request_report_snapshot_export(UUID, UUID, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_report_snapshot_exports(UUID, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_report_snapshot_export(UUID, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.authorize_report_snapshot_export_download(UUID, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.claim_report_snapshot_export_batch(TEXT, INTEGER, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.read_report_snapshot_export_source(UUID, TEXT, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.finish_report_snapshot_export_attempt(
    UUID, TEXT, UUID, BOOLEAN, TEXT, INTEGER, UUID, TEXT, BIGINT
) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION kokonut_security.claim_report_snapshot_export_batch(TEXT, INTEGER, INTEGER)
    TO kokonut_report_snapshot_export_login;
GRANT EXECUTE ON FUNCTION kokonut_security.read_report_snapshot_export_source(UUID, TEXT, UUID)
    TO kokonut_report_snapshot_export_login;
GRANT EXECUTE ON FUNCTION kokonut_security.finish_report_snapshot_export_attempt(
    UUID, TEXT, UUID, BOOLEAN, TEXT, INTEGER, UUID, TEXT, BIGINT
) TO kokonut_report_snapshot_export_login;

DO $$
DECLARE function_signature TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION
            kokonut_security.request_report_snapshot_export(UUID, UUID, UUID),
            kokonut_security.list_report_snapshot_exports(UUID, INTEGER),
            kokonut_security.get_report_snapshot_export(UUID, UUID),
            kokonut_security.authorize_report_snapshot_export_download(UUID, UUID)
        TO kokonut_runtime;
        REVOKE ALL ON FUNCTION
            kokonut_security.claim_report_snapshot_export_batch(TEXT, INTEGER, INTEGER),
            kokonut_security.read_report_snapshot_export_source(UUID, TEXT, UUID),
            kokonut_security.finish_report_snapshot_export_attempt(
                UUID, TEXT, UUID, BOOLEAN, TEXT, INTEGER, UUID, TEXT, BIGINT
            )
        FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        FOREACH function_signature IN ARRAY ARRAY[
            'kokonut_security.request_report_snapshot_export(uuid,uuid,uuid)',
            'kokonut_security.list_report_snapshot_exports(uuid,integer)',
            'kokonut_security.get_report_snapshot_export(uuid,uuid)',
            'kokonut_security.authorize_report_snapshot_export_download(uuid,uuid)',
            'kokonut_security.claim_report_snapshot_export_batch(text,integer,integer)',
            'kokonut_security.read_report_snapshot_export_source(uuid,text,uuid)',
            'kokonut_security.finish_report_snapshot_export_attempt(uuid,text,uuid,boolean,text,integer,uuid,text,bigint)'
        ] LOOP
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON FUNCTION %s FROM kokonut_directus_runtime',
                function_signature
            );
        END LOOP;
    END IF;
END;
$$;

COMMIT;
