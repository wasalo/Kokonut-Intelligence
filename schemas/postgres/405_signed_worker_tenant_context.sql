-- Add a dormant, separately authenticated worker identity for one exact
-- tenant/location/resource/action execution. This migration does not enable
-- application-table RLS or grant access to kokonut_runtime.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_context_owner'
    ) THEN
        CREATE ROLE kokonut_worker_context_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_worker_context_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_worker_context_owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_execution'
    ) THEN
        CREATE ROLE kokonut_worker_execution
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_worker_execution'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_worker_execution has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN (
                   'kokonut_worker_context_owner', 'kokonut_mobile_context_owner'
               )
            OR member_role.rolname IN (
                   'kokonut_worker_context_owner', 'kokonut_mobile_context_owner'
               )
    ) THEN
        RAISE EXCEPTION 'worker and context function owners must not have role memberships';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_worker_execution'
           AND member_role.rolname IN ('kokonut_runtime', 'kokonut_operator_auth')
    ) THEN
        RAISE EXCEPTION 'shared runtime/auth logins cannot inherit worker execution';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO
    kokonut_worker_context_owner,
    kokonut_mobile_context_owner,
    kokonut_worker_execution;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_worker_context_owner;
GRANT USAGE ON SCHEMA public TO kokonut_worker_context_owner;

CREATE TABLE IF NOT EXISTS kokonut_security.worker_principal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    principal_key TEXT NOT NULL UNIQUE
        CHECK (principal_key ~ '^[a-z][a-z0-9_-]{0,62}$'),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    disabled_at TIMESTAMPTZ,
    CHECK ((is_active AND disabled_at IS NULL) OR NOT is_active)
);

CREATE TABLE IF NOT EXISTS kokonut_security.worker_credential (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID NOT NULL REFERENCES kokonut_security.worker_principal(id)
        ON DELETE RESTRICT,
    credential_hash TEXT NOT NULL UNIQUE
        CHECK (credential_hash ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by TEXT,
    revocation_reason TEXT,
    CHECK (
        (revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL)
        OR
        (revoked_at IS NOT NULL AND revoked_by IS NOT NULL
         AND length(btrim(revoked_by)) > 0
         AND revocation_reason IS NOT NULL
         AND length(btrim(revocation_reason)) > 0)
    )
);
CREATE INDEX IF NOT EXISTS idx_worker_credential_active
    ON kokonut_security.worker_credential (credential_hash, worker_id)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS kokonut_security.worker_scope_grant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id UUID NOT NULL REFERENCES kokonut_security.worker_principal(id)
        ON DELETE RESTRICT,
    tenant_id UUID NOT NULL REFERENCES public.organization(id)
        ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id)
        ON DELETE RESTRICT,
    resource TEXT NOT NULL CHECK (resource ~ '^[a-z][a-z0-9_]{0,62}$'),
    action TEXT NOT NULL CHECK (action ~ '^[a-z][a-z0-9_]{0,62}$'),
    granted_by TEXT NOT NULL CHECK (length(btrim(granted_by)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by TEXT,
    revocation_reason TEXT,
    CHECK (
        (revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL)
        OR
        (revoked_at IS NOT NULL AND revoked_by IS NOT NULL
         AND length(btrim(revoked_by)) > 0
         AND revocation_reason IS NOT NULL
         AND length(btrim(revocation_reason)) > 0)
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_worker_scope_grant_active
    ON kokonut_security.worker_scope_grant
       (worker_id, tenant_id, location_id, resource, action)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_worker_scope_grant_lookup
    ON kokonut_security.worker_scope_grant
       (worker_id, location_id, resource, action, tenant_id)
    WHERE revoked_at IS NULL;

REVOKE ALL ON TABLE
    kokonut_security.worker_principal,
    kokonut_security.worker_credential,
    kokonut_security.worker_scope_grant
FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE
            kokonut_security.worker_principal,
            kokonut_security.worker_credential,
            kokonut_security.worker_scope_grant
        FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        REVOKE ALL ON TABLE
            kokonut_security.worker_principal,
            kokonut_security.worker_credential,
            kokonut_security.worker_scope_grant
        FROM kokonut_operator_auth;
    END IF;
END;
$$;

GRANT SELECT ON TABLE
    kokonut_security.worker_principal,
    kokonut_security.worker_credential,
    kokonut_security.worker_scope_grant,
    kokonut_security.mobile_context_hmac_key,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_worker_context_owner;
-- PostgreSQL requires UPDATE privilege to acquire FOR SHARE locks. The
-- function owner receives it only on immutable primary-key columns.
GRANT UPDATE (id) ON TABLE
    kokonut_security.worker_principal,
    kokonut_security.worker_credential,
    kokonut_security.worker_scope_grant,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_worker_context_owner;

DO $$
DECLARE
    target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'location', 'location_tenant_owner_verification', 'organization'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = target_table
               AND policyname = 'worker_context_owner_read'
        ) THEN
            EXECUTE format(
                'CREATE POLICY worker_context_owner_read ON public.%I FOR SELECT TO kokonut_worker_context_owner USING (true)',
                target_table
            );
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public' AND tablename = target_table
               AND policyname = 'worker_context_owner_lock'
        ) THEN
            EXECUTE format(
                'CREATE POLICY worker_context_owner_lock ON public.%I FOR UPDATE TO kokonut_worker_context_owner USING (true) WITH CHECK (true)',
                target_table
            );
        END IF;
    END LOOP;
    FOREACH target_table IN ARRAY ARRAY[
        'worker_principal', 'worker_credential', 'worker_scope_grant'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'kokonut_security' AND tablename = target_table
               AND policyname = 'worker_context_owner_read'
        ) THEN
            EXECUTE format(
                'CREATE POLICY worker_context_owner_read ON kokonut_security.%I FOR SELECT TO kokonut_worker_context_owner USING (true)',
                target_table
            );
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'kokonut_security' AND tablename = target_table
               AND policyname = 'worker_context_owner_lock'
        ) THEN
            EXECUTE format(
                'CREATE POLICY worker_context_owner_lock ON kokonut_security.%I FOR UPDATE TO kokonut_worker_context_owner USING (true) WITH CHECK (true)',
                target_table
            );
        END IF;
    END LOOP;
END;
$$;

ALTER TABLE kokonut_security.worker_principal ENABLE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.worker_principal FORCE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.worker_credential ENABLE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.worker_credential FORCE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.worker_scope_grant ENABLE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.worker_scope_grant FORCE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION kokonut_security.set_worker_tenant_context(
    requested_credential_hash TEXT,
    requested_location_id UUID,
    requested_resource TEXT,
    requested_action TEXT
)
RETURNS TABLE (
    tenant_id UUID,
    location_id UUID,
    actor_id UUID,
    actor_type TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    setting_name TEXT;
    worker_record RECORD;
    resolved_tenant_id UUID;
    resolved_location_id UUID;
    active_grant_id UUID;
    signing_key BYTEA;
    signed_payload JSONB;
    payload_text TEXT;
    signature_text TEXT;
BEGIN
    FOREACH setting_name IN ARRAY ARRAY[
        'kokonut.tenant_id', 'kokonut.location_id', 'kokonut.actor_id',
        'kokonut.actor_type', 'kokonut.context_payload',
        'kokonut.context_signature'
    ] LOOP
        PERFORM set_config(setting_name, '', TRUE);
    END LOOP;

    IF requested_credential_hash IS NULL
       OR requested_credential_hash !~ '^[0-9a-f]{64}$'
       OR requested_location_id IS NULL
       OR requested_resource IS NULL
       OR requested_resource !~ '^[a-z][a-z0-9_]{0,62}$'
       OR requested_action IS NULL
       OR requested_action !~ '^[a-z][a-z0-9_]{0,62}$' THEN
        RETURN;
    END IF;

    SELECT principal.id AS worker_id
      INTO worker_record
      FROM kokonut_security.worker_credential AS credential
      JOIN kokonut_security.worker_principal AS principal
        ON principal.id = credential.worker_id
       AND principal.is_active IS TRUE
       AND principal.disabled_at IS NULL
     WHERE credential.credential_hash = requested_credential_hash
       AND credential.revoked_at IS NULL
       AND (credential.expires_at IS NULL
            OR credential.expires_at > statement_timestamp())
     FOR SHARE OF credential, principal;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT owner.organization_id, loc.id
      INTO resolved_tenant_id, resolved_location_id
      FROM public.location AS loc
      JOIN public.location_tenant_owner_verification AS owner
        ON owner.location_id = loc.id
       AND owner.organization_id = loc.organization_id
       AND owner.revoked_at IS NULL
      JOIN public.organization AS tenant
        ON tenant.id = owner.organization_id
       AND tenant.status = 'active'
     WHERE loc.id = requested_location_id
       AND loc.status = 'active'
     FOR SHARE OF loc, owner, tenant;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT grant_row.id
      INTO active_grant_id
      FROM kokonut_security.worker_scope_grant AS grant_row
     WHERE grant_row.worker_id = worker_record.worker_id
       AND grant_row.tenant_id = resolved_tenant_id
       AND grant_row.location_id = resolved_location_id
       AND grant_row.resource = requested_resource
       AND grant_row.action = requested_action
       AND grant_row.revoked_at IS NULL
       AND (grant_row.expires_at IS NULL
            OR grant_row.expires_at > statement_timestamp())
     FOR SHARE OF grant_row;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT key.secret
      INTO signing_key
      FROM kokonut_security.mobile_context_hmac_key AS key
     WHERE key.key_id = 1;
    IF signing_key IS NULL THEN
        RETURN;
    END IF;

    signed_payload := jsonb_build_object(
        'backend_pid', pg_backend_pid(),
        'transaction_id', txid_current(),
        'tenant_id', resolved_tenant_id,
        'location_id', resolved_location_id,
        'actor_id', worker_record.worker_id,
        'actor_type', 'system_worker',
        'resource', requested_resource,
        'action', requested_action,
        'nonce', encode(public.gen_random_bytes(16), 'hex')
    );
    payload_text := signed_payload::text;
    signature_text := encode(
        public.hmac(convert_to(payload_text, 'UTF8'), signing_key, 'sha256'),
        'hex'
    );

    PERFORM set_config('kokonut.context_payload', payload_text, TRUE);
    PERFORM set_config('kokonut.context_signature', signature_text, TRUE);
    PERFORM set_config('kokonut.tenant_id', resolved_tenant_id::TEXT, TRUE);
    PERFORM set_config('kokonut.location_id', resolved_location_id::TEXT, TRUE);
    PERFORM set_config('kokonut.actor_id', worker_record.worker_id::TEXT, TRUE);
    PERFORM set_config('kokonut.actor_type', 'system_worker', TRUE);

    tenant_id := resolved_tenant_id;
    location_id := resolved_location_id;
    actor_id := worker_record.worker_id;
    actor_type := 'system_worker';
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.set_worker_tenant_context(TEXT, UUID, TEXT, TEXT)
    OWNER TO kokonut_worker_context_owner;
REVOKE ALL ON FUNCTION kokonut_security.set_worker_tenant_context(TEXT, UUID, TEXT, TEXT)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.set_worker_tenant_context(TEXT, UUID, TEXT, TEXT)
    TO kokonut_worker_execution;

CREATE OR REPLACE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE (
    tenant_id UUID,
    location_id UUID,
    actor_id UUID,
    actor_type TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    payload_text TEXT;
    signature_text TEXT;
    signing_key BYTEA;
    context_payload JSONB;
    expected_signature BYTEA;
    supplied_signature BYTEA;
    signature_difference INTEGER := 0;
    byte_index INTEGER;
    active_transaction_id BIGINT;
BEGIN
    payload_text := current_setting('kokonut.context_payload', TRUE);
    signature_text := current_setting('kokonut.context_signature', TRUE);
    IF payload_text IS NULL OR payload_text = ''
       OR signature_text IS NULL OR signature_text !~ '^[0-9a-f]{64}$' THEN
        RETURN;
    END IF;

    SELECT key.secret INTO signing_key
      FROM kokonut_security.mobile_context_hmac_key AS key
     WHERE key.key_id = 1;
    IF signing_key IS NULL THEN
        RETURN;
    END IF;

    expected_signature := public.hmac(convert_to(payload_text, 'UTF8'), signing_key, 'sha256');
    supplied_signature := decode(signature_text, 'hex');
    FOR byte_index IN 0..31 LOOP
        signature_difference := signature_difference |
            (get_byte(expected_signature, byte_index) # get_byte(supplied_signature, byte_index));
    END LOOP;
    IF signature_difference <> 0 THEN
        RETURN;
    END IF;

    BEGIN
        context_payload := payload_text::JSONB;
        active_transaction_id := txid_current_if_assigned();
        IF active_transaction_id IS NULL
           OR context_payload ->> 'backend_pid' IS DISTINCT FROM pg_backend_pid()::TEXT
           OR context_payload ->> 'transaction_id' IS DISTINCT FROM active_transaction_id::TEXT
           OR context_payload ->> 'actor_type' NOT IN (
               'mobile_device', 'operator', 'gateway_api_key',
               'gateway_capability', 'system_worker'
           )
           OR NULLIF(context_payload ->> 'nonce', '') IS NULL THEN
            RETURN;
        END IF;

        tenant_id := (context_payload ->> 'tenant_id')::UUID;
        location_id := (context_payload ->> 'location_id')::UUID;
        actor_id := (context_payload ->> 'actor_id')::UUID;
        actor_type := context_payload ->> 'actor_type';
    EXCEPTION WHEN OTHERS THEN
        RETURN;
    END;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.current_worker_scope(
    requested_resource TEXT,
    requested_action TEXT
)
RETURNS TABLE (
    tenant_id UUID,
    location_id UUID,
    actor_id UUID,
    resource TEXT,
    action TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    validated_context RECORD;
    context_payload JSONB;
    payload_text TEXT;
BEGIN
    IF requested_resource IS NULL
       OR requested_resource !~ '^[a-z][a-z0-9_]{0,62}$'
       OR requested_action IS NULL
       OR requested_action !~ '^[a-z][a-z0-9_]{0,62}$' THEN
        RETURN;
    END IF;

    SELECT context.tenant_id, context.location_id, context.actor_id, context.actor_type
      INTO validated_context
      FROM kokonut_security.current_tenant_context() AS context;
    IF NOT FOUND OR validated_context.actor_type <> 'system_worker' THEN
        RETURN;
    END IF;

    payload_text := current_setting('kokonut.context_payload', TRUE);
    BEGIN
        context_payload := payload_text::JSONB;
    EXCEPTION WHEN OTHERS THEN
        RETURN;
    END;
    IF context_payload ->> 'resource' IS DISTINCT FROM requested_resource
       OR context_payload ->> 'action' IS DISTINCT FROM requested_action
       OR context_payload ->> 'actor_id' IS DISTINCT FROM validated_context.actor_id::TEXT
       OR context_payload ->> 'tenant_id' IS DISTINCT FROM validated_context.tenant_id::TEXT
       OR context_payload ->> 'location_id' IS DISTINCT FROM validated_context.location_id::TEXT THEN
        RETURN;
    END IF;

    tenant_id := validated_context.tenant_id;
    location_id := validated_context.location_id;
    actor_id := validated_context.actor_id;
    resource := requested_resource;
    action := requested_action;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.current_tenant_context()
    OWNER TO kokonut_mobile_context_owner;
ALTER FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    OWNER TO kokonut_worker_context_owner;
REVOKE ALL ON FUNCTION kokonut_security.current_tenant_context() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context() TO PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT) TO PUBLIC;

COMMENT ON TABLE kokonut_security.worker_credential IS
    'High-entropy worker credential SHA-256 digests only; raw credentials remain in the deployment secret provider.';
COMMENT ON TABLE kokonut_security.worker_scope_grant IS
    'Exact, expiring or revocable system-worker authorization bound to the currently verified tenant and one location/resource/action.';
COMMENT ON FUNCTION kokonut_security.set_worker_tenant_context(TEXT, UUID, TEXT, TEXT) IS
    'Validates a worker credential, exact grant, active location, organization, and current owner under row locks, then signs transaction-bound system_worker context.';
COMMENT ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT) IS
    'Returns scope only when the existing HMAC-verified transaction context is a system_worker with the exact signed resource/action.';
COMMENT ON FUNCTION kokonut_security.current_tenant_context() IS
    'Returns only a valid database-signed context for this backend and transaction, including database-verified system_worker contexts.';

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_worker_context_owner;

COMMIT;
