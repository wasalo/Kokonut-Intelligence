BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_capability_owner') THEN
        EXECUTE 'CREATE ROLE kokonut_operator_capability_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_clickhouse_outbox_operator_owner') THEN
        EXECUTE 'CREATE ROLE kokonut_clickhouse_outbox_operator_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_clickhouse_outbox_operator_login') THEN
        EXECUTE 'CREATE ROLE kokonut_clickhouse_outbox_operator_login NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname IN ('kokonut_operator_capability_owner', 'kokonut_clickhouse_outbox_operator_owner')
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'ClickHouse outbox function-owner roles must remain non-login and unprivileged';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = 'kokonut_clickhouse_outbox_operator_login'
          AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'ClickHouse outbox operator login must remain a non-inheriting bounded login';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_auth_members m
        JOIN pg_roles role ON role.oid = m.roleid
        JOIN pg_roles member ON member.oid = m.member
        WHERE role.rolname IN (
            'kokonut_operator_capability_owner',
            'kokonut_clickhouse_outbox_operator_owner',
            'kokonut_clickhouse_outbox_operator_login'
        )
           OR member.rolname IN (
            'kokonut_operator_capability_owner',
            'kokonut_clickhouse_outbox_operator_owner',
            'kokonut_clickhouse_outbox_operator_login'
        )
    ) THEN
        RAISE EXCEPTION 'ClickHouse outbox operator roles may not have or receive role memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM kokonut_clickhouse_outbox_operator_login;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_clickhouse_outbox_operator_login;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_clickhouse_outbox_operator_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_clickhouse_outbox_operator_login;
REVOKE ALL ON ALL TABLES IN SCHEMA kokonut_security FROM kokonut_clickhouse_outbox_operator_login;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA kokonut_security FROM kokonut_clickhouse_outbox_operator_login;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_clickhouse_outbox_operator_login;
GRANT USAGE, CREATE ON SCHEMA kokonut_security TO kokonut_operator_capability_owner;
GRANT USAGE, CREATE ON SCHEMA kokonut_security TO kokonut_clickhouse_outbox_operator_owner;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_clickhouse_outbox_operator_login;
GRANT USAGE ON SCHEMA public TO kokonut_operator_capability_owner;
GRANT USAGE ON SCHEMA public TO kokonut_clickhouse_outbox_operator_owner;

CREATE TABLE kokonut_security.operator_global_capability (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    capability_code TEXT NOT NULL CHECK (
        capability_code IN (
            'clickhouse_outbox:read',
            'clickhouse_outbox:replay',
            'clickhouse_outbox:resolve',
            'clickhouse_outbox:discard'
        )
    ),
    granted_by_db_role TEXT NOT NULL,
    approved_by TEXT NOT NULL CHECK (length(btrim(approved_by)) BETWEEN 1 AND 255),
    grant_reason TEXT NOT NULL CHECK (length(btrim(grant_reason)) BETWEEN 1 AND 2000),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    revoked_at TIMESTAMPTZ,
    revoked_by_db_role TEXT,
    revoked_by TEXT,
    revoke_reason TEXT,
    CONSTRAINT operator_global_capability_revocation_fields_consistent CHECK (
        (revoked_at IS NULL AND revoked_by_db_role IS NULL AND revoked_by IS NULL AND revoke_reason IS NULL)
        OR
        (revoked_at IS NOT NULL AND revoked_by_db_role IS NOT NULL AND revoked_by IS NOT NULL AND revoke_reason IS NOT NULL)
    )
);
ALTER TABLE kokonut_security.operator_global_capability OWNER TO kokonut_operator_capability_owner;
CREATE UNIQUE INDEX operator_global_capability_one_active
    ON kokonut_security.operator_global_capability (operator_id, capability_code)
    WHERE revoked_at IS NULL;

CREATE TABLE kokonut_security.operator_global_capability_audit (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    capability_id UUID NOT NULL REFERENCES kokonut_security.operator_global_capability(id) ON DELETE RESTRICT,
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    capability_code TEXT NOT NULL CHECK (
        capability_code IN (
            'clickhouse_outbox:read',
            'clickhouse_outbox:replay',
            'clickhouse_outbox:resolve',
            'clickhouse_outbox:discard'
        )
    ),
    action TEXT NOT NULL CHECK (action IN ('granted', 'revoked')),
    actor_db_role TEXT NOT NULL,
    approved_by TEXT NOT NULL CHECK (length(btrim(approved_by)) BETWEEN 1 AND 255),
    reason TEXT NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 2000),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);
ALTER TABLE kokonut_security.operator_global_capability_audit OWNER TO kokonut_operator_capability_owner;
REVOKE ALL ON TABLE kokonut_security.operator_global_capability FROM PUBLIC;
REVOKE ALL ON TABLE kokonut_security.operator_global_capability_audit FROM PUBLIC;
ALTER TABLE kokonut_security.operator_global_capability ENABLE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.operator_global_capability FORCE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.operator_global_capability_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.operator_global_capability_audit FORCE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'kokonut_security'
          AND tablename = 'operator_global_capability'
          AND policyname = 'operator_capability_owner_all'
    ) THEN
        CREATE POLICY operator_capability_owner_all
            ON kokonut_security.operator_global_capability
            FOR ALL TO kokonut_operator_capability_owner
            USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'kokonut_security'
          AND tablename = 'operator_global_capability'
          AND policyname = 'outbox_operator_owner_read'
    ) THEN
        CREATE POLICY outbox_operator_owner_read
            ON kokonut_security.operator_global_capability
            FOR SELECT TO kokonut_clickhouse_outbox_operator_owner
            USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'kokonut_security'
          AND tablename = 'operator_global_capability_audit'
          AND policyname = 'operator_capability_audit_owner_all'
    ) THEN
        CREATE POLICY operator_capability_audit_owner_all
            ON kokonut_security.operator_global_capability_audit
            FOR ALL TO kokonut_operator_capability_owner
            USING (true) WITH CHECK (true);
    END IF;
END;
$$;

ALTER TABLE public.clickhouse_outbox_operator_audit
    ADD COLUMN IF NOT EXISTS operator_id UUID REFERENCES public.operator_identity(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS clickhouse_outbox_operator_audit_operator
    ON public.clickhouse_outbox_operator_audit(operator_id, created_at DESC)
    WHERE operator_id IS NOT NULL;
REVOKE ALL ON TABLE public.clickhouse_outbox_operator_audit FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'operator_identity'
          AND relation.relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = 'operator_identity'
              AND policyname = 'clickhouse_outbox_operator_identity_read'
        ) THEN
            CREATE POLICY clickhouse_outbox_operator_identity_read
                ON public.operator_identity
                FOR SELECT TO kokonut_clickhouse_outbox_operator_owner
                USING (true);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = 'operator_identity'
              AND policyname = 'clickhouse_outbox_capability_owner_identity_read'
        ) THEN
            CREATE POLICY clickhouse_outbox_capability_owner_identity_read
                ON public.operator_identity
                FOR SELECT TO kokonut_operator_capability_owner
                USING (true);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = 'operator_identity'
              AND policyname = 'clickhouse_outbox_operator_identity_lock'
        ) THEN
            CREATE POLICY clickhouse_outbox_operator_identity_lock
                ON public.operator_identity
                FOR UPDATE TO kokonut_clickhouse_outbox_operator_owner
                USING (true) WITH CHECK (true);
        END IF;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'operator_session'
          AND relation.relrowsecurity
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = 'operator_session'
              AND policyname = 'clickhouse_outbox_operator_session_read'
        ) THEN
            CREATE POLICY clickhouse_outbox_operator_session_read
                ON public.operator_session
                FOR SELECT TO kokonut_clickhouse_outbox_operator_owner
                USING (true);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = 'operator_session'
              AND policyname = 'clickhouse_outbox_operator_session_lock'
        ) THEN
            CREATE POLICY clickhouse_outbox_operator_session_lock
                ON public.operator_session
                FOR UPDATE TO kokonut_clickhouse_outbox_operator_owner
                USING (true) WITH CHECK (true);
        END IF;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'clickhouse_outbox'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'clickhouse_outbox'
          AND policyname = 'clickhouse_outbox_operator_owner_all'
    ) THEN
        CREATE POLICY clickhouse_outbox_operator_owner_all
            ON public.clickhouse_outbox
            FOR ALL TO kokonut_clickhouse_outbox_operator_owner
            USING (true) WITH CHECK (true);
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'clickhouse_outbox_operator_audit'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'clickhouse_outbox_operator_audit'
          AND policyname = 'clickhouse_outbox_operator_audit_insert'
    ) THEN
        CREATE POLICY clickhouse_outbox_operator_audit_insert
            ON public.clickhouse_outbox_operator_audit
            FOR INSERT TO kokonut_clickhouse_outbox_operator_owner
            WITH CHECK (true);
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA kokonut_security TO kokonut_clickhouse_outbox_operator_owner;
GRANT SELECT ON TABLE kokonut_security.operator_global_capability
    TO kokonut_clickhouse_outbox_operator_owner;
GRANT SELECT ON TABLE public.operator_identity
    TO kokonut_operator_capability_owner;
GRANT SELECT, UPDATE (enabled, updated_at) ON TABLE public.operator_identity
    TO kokonut_clickhouse_outbox_operator_owner;
GRANT SELECT, UPDATE (last_seen_at, revoked_at) ON TABLE public.operator_session
    TO kokonut_clickhouse_outbox_operator_owner;
GRANT SELECT ON TABLE public.clickhouse_outbox
    TO kokonut_clickhouse_outbox_operator_owner;
GRANT UPDATE (status, attempt_count, available_at, last_error, lease_owner, lease_token, lease_expires_at, updated_at)
    ON TABLE public.clickhouse_outbox TO kokonut_clickhouse_outbox_operator_owner;
GRANT INSERT (outbox_id, event_key, action, actor, reason, prior_attempt_count, payload_hash, operator_id)
    ON TABLE public.clickhouse_outbox_operator_audit TO kokonut_clickhouse_outbox_operator_owner;

CREATE OR REPLACE FUNCTION kokonut_security.resolve_clickhouse_outbox_operator_session(
    requested_session_token_hash TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    resolved_operator_id UUID;
BEGIN
    IF requested_session_token_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'operator session proof is invalid' USING ERRCODE = '42501';
    END IF;
    SELECT operator_session.operator_id
    INTO resolved_operator_id
    FROM public.operator_session AS operator_session
    JOIN public.operator_identity AS operator_identity
      ON operator_identity.id = operator_session.operator_id
    WHERE btrim(operator_session.session_token_hash) = requested_session_token_hash
      AND operator_session.revoked_at IS NULL
      AND operator_session.expires_at > pg_catalog.clock_timestamp()
      AND operator_identity.enabled
    FOR UPDATE OF operator_session, operator_identity;
    IF resolved_operator_id IS NULL THEN
        RAISE EXCEPTION 'operator session is not active' USING ERRCODE = '42501';
    END IF;
    RETURN resolved_operator_id;
END;
$$;
ALTER FUNCTION kokonut_security.resolve_clickhouse_outbox_operator_session(TEXT)
    OWNER TO kokonut_clickhouse_outbox_operator_owner;
REVOKE ALL ON FUNCTION kokonut_security.resolve_clickhouse_outbox_operator_session(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.resolve_clickhouse_outbox_operator_session(TEXT)
    TO kokonut_clickhouse_outbox_operator_owner, kokonut_operator_capability_owner;

CREATE OR REPLACE FUNCTION kokonut_security.operator_global_capability_allows(
    requested_session_token_hash TEXT,
    requested_capability_code TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    resolved_operator_id UUID;
BEGIN
    IF requested_capability_code NOT IN (
        'clickhouse_outbox:read',
        'clickhouse_outbox:replay',
        'clickhouse_outbox:resolve',
        'clickhouse_outbox:discard'
    ) THEN
        RETURN FALSE;
    END IF;
    resolved_operator_id := kokonut_security.resolve_clickhouse_outbox_operator_session(
        requested_session_token_hash
    );
    RETURN EXISTS (
        SELECT 1
        FROM kokonut_security.operator_global_capability capability
        WHERE capability.operator_id = resolved_operator_id
          AND capability.capability_code = requested_capability_code
          AND capability.revoked_at IS NULL
    );
END;
$$;
ALTER FUNCTION kokonut_security.operator_global_capability_allows(TEXT, TEXT)
    OWNER TO kokonut_operator_capability_owner;
REVOKE ALL ON FUNCTION kokonut_security.operator_global_capability_allows(TEXT, TEXT) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.operator_global_capability_allows(TEXT, TEXT) TO kokonut_operator_auth';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.grant_operator_global_capability(
    requested_operator_id UUID,
    requested_capability_code TEXT,
    requested_approved_by TEXT,
    requested_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    granted_id UUID;
BEGIN
    IF session_user IN ('kokonut_runtime', 'kokonut_operator_auth', 'kokonut_clickhouse_outbox_operator_login') THEN
        RAISE EXCEPTION 'DBA-approved capability provisioning is required' USING ERRCODE = '42501';
    END IF;
    IF requested_capability_code NOT IN (
        'clickhouse_outbox:read',
        'clickhouse_outbox:replay',
        'clickhouse_outbox:resolve',
        'clickhouse_outbox:discard'
    ) OR btrim(coalesce(requested_approved_by, '')) = '' OR btrim(coalesce(requested_reason, '')) = '' THEN
        RAISE EXCEPTION 'capability, approver, and reason are required' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.operator_identity
        WHERE id = requested_operator_id AND enabled
    ) THEN
        RAISE EXCEPTION 'enabled operator identity is required' USING ERRCODE = '22023';
    END IF;
    INSERT INTO kokonut_security.operator_global_capability (
        operator_id, capability_code, granted_by_db_role, approved_by, grant_reason
    ) VALUES (
        requested_operator_id,
        requested_capability_code,
        session_user::TEXT,
        btrim(requested_approved_by),
        btrim(requested_reason)
    )
    RETURNING id INTO granted_id;
    INSERT INTO kokonut_security.operator_global_capability_audit (
        capability_id, operator_id, capability_code, action, actor_db_role, approved_by, reason
    ) VALUES (
        granted_id,
        requested_operator_id,
        requested_capability_code,
        'granted',
        session_user::TEXT,
        btrim(requested_approved_by),
        btrim(requested_reason)
    );
    RETURN granted_id;
END;
$$;
ALTER FUNCTION kokonut_security.grant_operator_global_capability(UUID, TEXT, TEXT, TEXT)
    OWNER TO kokonut_operator_capability_owner;
REVOKE ALL ON FUNCTION kokonut_security.grant_operator_global_capability(UUID, TEXT, TEXT, TEXT) FROM PUBLIC;

CREATE OR REPLACE FUNCTION kokonut_security.revoke_operator_global_capability(
    requested_capability_id UUID,
    requested_approved_by TEXT,
    requested_reason TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    revoked_row RECORD;
BEGIN
    IF session_user IN ('kokonut_runtime', 'kokonut_operator_auth', 'kokonut_clickhouse_outbox_operator_login') THEN
        RAISE EXCEPTION 'DBA-approved capability provisioning is required' USING ERRCODE = '42501';
    END IF;
    IF btrim(coalesce(requested_approved_by, '')) = '' OR btrim(coalesce(requested_reason, '')) = '' THEN
        RAISE EXCEPTION 'approver and reason are required' USING ERRCODE = '22023';
    END IF;
    UPDATE kokonut_security.operator_global_capability
    SET revoked_at = pg_catalog.clock_timestamp(),
        revoked_by_db_role = session_user::TEXT,
        revoked_by = btrim(requested_approved_by),
        revoke_reason = btrim(requested_reason)
    WHERE id = requested_capability_id AND revoked_at IS NULL
    RETURNING operator_id, capability_code INTO revoked_row;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'active operator capability was not found' USING ERRCODE = 'P0002';
    END IF;
    INSERT INTO kokonut_security.operator_global_capability_audit (
        capability_id, operator_id, capability_code, action, actor_db_role, approved_by, reason
    ) VALUES (
        requested_capability_id,
        revoked_row.operator_id,
        revoked_row.capability_code,
        'revoked',
        session_user::TEXT,
        btrim(requested_approved_by),
        btrim(requested_reason)
    );
    RETURN TRUE;
END;
$$;
ALTER FUNCTION kokonut_security.revoke_operator_global_capability(UUID, TEXT, TEXT)
    OWNER TO kokonut_operator_capability_owner;
REVOKE ALL ON FUNCTION kokonut_security.revoke_operator_global_capability(UUID, TEXT, TEXT) FROM PUBLIC;

CREATE OR REPLACE FUNCTION kokonut_security.list_clickhouse_outbox_operator_dead_letters(
    requested_session_token_hash TEXT,
    requested_limit INTEGER
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    resolved_operator_id UUID;
    can_replay BOOLEAN;
    can_resolve BOOLEAN;
    can_discard BOOLEAN;
    items JSONB;
BEGIN
    IF session_user <> 'kokonut_clickhouse_outbox_operator_login' THEN
        RAISE EXCEPTION 'ClickHouse outbox operator identity required' USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit < 1 OR requested_limit > 100 THEN
        RAISE EXCEPTION 'limit must be between 1 and 100' USING ERRCODE = '22023';
    END IF;
    resolved_operator_id := kokonut_security.resolve_clickhouse_outbox_operator_session(requested_session_token_hash);
    IF NOT EXISTS (
        SELECT 1 FROM kokonut_security.operator_global_capability
        WHERE operator_global_capability.operator_id = resolved_operator_id
          AND operator_global_capability.capability_code = 'clickhouse_outbox:read'
          AND operator_global_capability.revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'ClickHouse outbox read capability required' USING ERRCODE = '42501';
    END IF;
    SELECT EXISTS (
        SELECT 1 FROM kokonut_security.operator_global_capability
        WHERE operator_global_capability.operator_id = resolved_operator_id
          AND operator_global_capability.capability_code = 'clickhouse_outbox:replay'
          AND operator_global_capability.revoked_at IS NULL
    ), EXISTS (
        SELECT 1 FROM kokonut_security.operator_global_capability
        WHERE operator_global_capability.operator_id = resolved_operator_id
          AND operator_global_capability.capability_code = 'clickhouse_outbox:resolve'
          AND operator_global_capability.revoked_at IS NULL
    ), EXISTS (
        SELECT 1 FROM kokonut_security.operator_global_capability
        WHERE operator_global_capability.operator_id = resolved_operator_id
          AND operator_global_capability.capability_code = 'clickhouse_outbox:discard'
          AND operator_global_capability.revoked_at IS NULL
    ) INTO can_replay, can_resolve, can_discard;
    SELECT coalesce(
        jsonb_agg(
            jsonb_build_object(
                'id', queue_row.id,
                'target_table', queue_row.target_table,
                'attempt_count', queue_row.attempt_count,
                'created_at', queue_row.created_at,
                'updated_at', queue_row.updated_at
            ) ORDER BY queue_row.updated_at DESC, queue_row.id
        ),
        '[]'::jsonb
    ) INTO items
    FROM (
        SELECT id, target_table, attempt_count, created_at, updated_at
        FROM public.clickhouse_outbox
        WHERE status = 'dead_letter'
        ORDER BY updated_at DESC, id
        LIMIT requested_limit
    ) AS queue_row;
    RETURN jsonb_build_object(
        'items', items,
        'capabilities', jsonb_build_object(
            'replay', can_replay,
            'resolve', can_resolve,
            'discard', can_discard
        )
    );
END;
$$;
ALTER FUNCTION kokonut_security.list_clickhouse_outbox_operator_dead_letters(TEXT, INTEGER)
    OWNER TO kokonut_clickhouse_outbox_operator_owner;
REVOKE ALL ON FUNCTION kokonut_security.list_clickhouse_outbox_operator_dead_letters(TEXT, INTEGER) FROM PUBLIC;

CREATE OR REPLACE FUNCTION kokonut_security.transition_clickhouse_outbox_operator_dead_letter(
    requested_session_token_hash TEXT,
    requested_outbox_id UUID,
    requested_action TEXT,
    requested_reason TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    resolved_operator_id UUID;
    required_capability TEXT;
    audit_action TEXT;
    new_status TEXT;
    outbox_row RECORD;
BEGIN
    IF session_user <> 'kokonut_clickhouse_outbox_operator_login' THEN
        RAISE EXCEPTION 'ClickHouse outbox operator identity required' USING ERRCODE = '42501';
    END IF;
    IF requested_action IS NULL
       OR requested_action NOT IN ('replay', 'resolve', 'discard')
       OR btrim(coalesce(requested_reason, '')) = ''
       OR length(btrim(requested_reason)) > 2000 THEN
        RAISE EXCEPTION 'action and reason are invalid' USING ERRCODE = '22023';
    END IF;
    resolved_operator_id := kokonut_security.resolve_clickhouse_outbox_operator_session(requested_session_token_hash);
    required_capability := CASE requested_action
        WHEN 'replay' THEN 'clickhouse_outbox:replay'
        WHEN 'resolve' THEN 'clickhouse_outbox:resolve'
        ELSE 'clickhouse_outbox:discard'
    END;
    IF NOT EXISTS (
        SELECT 1 FROM kokonut_security.operator_global_capability
        WHERE operator_global_capability.operator_id = resolved_operator_id
          AND operator_global_capability.capability_code = required_capability
          AND operator_global_capability.revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'ClickHouse outbox capability required' USING ERRCODE = '42501';
    END IF;
    SELECT id, event_key, payload_hash, attempt_count
    INTO outbox_row
    FROM public.clickhouse_outbox
    WHERE id = requested_outbox_id AND status = 'dead_letter'
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'dead-letter row not found' USING ERRCODE = 'P0002';
    END IF;
    audit_action := CASE requested_action
        WHEN 'replay' THEN 'replayed'
        WHEN 'resolve' THEN 'resolved'
        WHEN 'discard' THEN 'discarded'
    END;
    new_status := CASE requested_action
        WHEN 'replay' THEN 'pending'
        WHEN 'resolve' THEN 'resolved'
        WHEN 'discard' THEN 'discarded'
    END;
    UPDATE public.clickhouse_outbox
    SET status = new_status,
        attempt_count = CASE WHEN requested_action = 'replay' THEN 0 ELSE attempt_count END,
        available_at = pg_catalog.clock_timestamp(),
        updated_at = pg_catalog.clock_timestamp(),
        last_error = CASE WHEN requested_action = 'replay' THEN NULL ELSE last_error END,
        lease_owner = NULL,
        lease_token = NULL,
        lease_expires_at = NULL
    WHERE id = requested_outbox_id AND status = 'dead_letter';
    INSERT INTO public.clickhouse_outbox_operator_audit (
        outbox_id,
        event_key,
        action,
        actor,
        reason,
        prior_attempt_count,
        payload_hash,
        operator_id
    ) VALUES (
        outbox_row.id,
        outbox_row.event_key,
        audit_action,
        'operator:' || resolved_operator_id::TEXT,
        btrim(requested_reason),
        outbox_row.attempt_count,
        outbox_row.payload_hash,
        resolved_operator_id
    );
    RETURN jsonb_build_object(
        'id', outbox_row.id,
        'action', audit_action,
        'status', new_status
    );
END;
$$;
ALTER FUNCTION kokonut_security.transition_clickhouse_outbox_operator_dead_letter(TEXT, UUID, TEXT, TEXT)
    OWNER TO kokonut_clickhouse_outbox_operator_owner;
REVOKE ALL ON FUNCTION kokonut_security.transition_clickhouse_outbox_operator_dead_letter(TEXT, UUID, TEXT, TEXT) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION kokonut_security.list_clickhouse_outbox_operator_dead_letters(TEXT, INTEGER)
    TO kokonut_clickhouse_outbox_operator_login;
GRANT EXECUTE ON FUNCTION kokonut_security.transition_clickhouse_outbox_operator_dead_letter(TEXT, UUID, TEXT, TEXT)
    TO kokonut_clickhouse_outbox_operator_login;

DO $$
DECLARE
    column_name TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE public.clickhouse_outbox FROM kokonut_runtime';
        FOR column_name IN
            SELECT attribute.attname
            FROM pg_catalog.pg_attribute AS attribute
            WHERE attribute.attrelid = 'public.clickhouse_outbox'::regclass
              AND attribute.attnum > 0
              AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE UPDATE (%I) ON TABLE public.clickhouse_outbox FROM kokonut_runtime',
                column_name
            );
        END LOOP;
        EXECUTE 'GRANT SELECT, INSERT ON TABLE public.clickhouse_outbox TO kokonut_runtime';
        EXECUTE 'GRANT UPDATE (updated_at) ON TABLE public.clickhouse_outbox TO kokonut_runtime';
        EXECUTE 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE public.clickhouse_outbox_operator_audit FROM kokonut_runtime';
    END IF;
END;
$$;

COMMIT;
