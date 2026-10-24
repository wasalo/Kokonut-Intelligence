-- Browser operator tenant context must be bound to a live OIDC session and
-- verified tenant-qualified grants, then signed for the current transaction.
-- This migration does not enable RLS on application tables.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_context_owner'
    ) THEN
        CREATE ROLE kokonut_operator_context_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSE
        IF EXISTS (
            SELECT 1
              FROM pg_roles
             WHERE rolname = 'kokonut_operator_context_owner'
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'kokonut_operator_context_owner has unsafe role attributes';
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname = 'kokonut_mobile_context_owner'
           AND NOT rolcanlogin
           AND NOT rolsuper
           AND NOT rolcreatedb
           AND NOT rolcreaterole
           AND NOT rolreplication
           AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'kokonut_mobile_context_owner is missing or has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN (
                   'kokonut_mobile_context_owner', 'kokonut_operator_context_owner'
               )
            OR member_role.rolname IN (
                   'kokonut_mobile_context_owner', 'kokonut_operator_context_owner'
               )
    ) THEN
        RAISE EXCEPTION 'tenant context function owner has role membership';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO PUBLIC;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_operator_context_owner;
GRANT USAGE ON SCHEMA public TO kokonut_operator_context_owner;

GRANT SELECT ON TABLE kokonut_security.mobile_context_hmac_key
    TO kokonut_operator_context_owner;
GRANT SELECT ON TABLE
    public.operator_session,
    public.operator_identity,
    public.operator_scope_grant,
    public.operator_organization_membership,
    public.location_organization_share,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_operator_context_owner;
-- PostgreSQL requires UPDATE privilege to acquire FOR SHARE row locks. These
-- primary-key-only column grants do not permit changing business state.
GRANT UPDATE (id) ON TABLE
    public.operator_session,
    public.operator_identity,
    public.operator_scope_grant,
    public.operator_organization_membership,
    public.location_organization_share,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_operator_context_owner;

DO $$
DECLARE
    target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'operator_session',
        'operator_identity',
        'operator_scope_grant',
        'operator_organization_membership',
        'location_organization_share',
        'location',
        'location_tenant_owner_verification',
        'organization'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public'
               AND tablename = target_table
               AND policyname = 'operator_context_owner_read'
        ) THEN
            EXECUTE format(
                'CREATE POLICY operator_context_owner_read ON public.%I FOR SELECT TO kokonut_operator_context_owner USING (true)',
                target_table
            );
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public'
               AND tablename = target_table
               AND policyname = 'operator_context_owner_lock'
        ) THEN
            EXECUTE format(
                'CREATE POLICY operator_context_owner_lock ON public.%I FOR UPDATE TO kokonut_operator_context_owner USING (true) WITH CHECK (true)',
                target_table
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.set_operator_tenant_context(
    requested_session_token_hash TEXT,
    requested_operator_id UUID,
    requested_location_id UUID,
    requested_resource TEXT,
    requested_action TEXT,
    requested_additional_scopes JSONB DEFAULT '[]'::JSONB
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
    signing_key BYTEA;
    signed_payload JSONB;
    payload_text TEXT;
    signature_text TEXT;
    location_organization_id UUID;
    current_owner_organization_id UUID;
    grant_organization_id UUID;
    resolved_tenant_id UUID;
    row_id UUID;
    session_expires_at TIMESTAMPTZ;
    share_expires_at TIMESTAMPTZ;
    current_scope JSONB;
    scope_record RECORD;
    scope_resource TEXT;
    scope_action TEXT;
    seen_scopes TEXT[] := ARRAY[]::TEXT[];
    scope_key TEXT;
BEGIN
    PERFORM set_config('kokonut.tenant_id', '', TRUE);
    PERFORM set_config('kokonut.location_id', '', TRUE);
    PERFORM set_config('kokonut.actor_id', '', TRUE);
    PERFORM set_config('kokonut.actor_type', '', TRUE);
    PERFORM set_config('kokonut.context_payload', '', TRUE);
    PERFORM set_config('kokonut.context_signature', '', TRUE);

    IF requested_session_token_hash IS NULL
       OR requested_session_token_hash !~ '^[0-9a-f]{64}$'
       OR requested_operator_id IS NULL
       OR requested_location_id IS NULL
       OR requested_resource IS NULL
       OR requested_resource !~ '^[a-z][a-z0-9_]{0,62}$'
       OR requested_action IS NULL
       OR requested_action !~ '^[a-z][a-z0-9_]{0,62}$'
       OR requested_additional_scopes IS NULL THEN
        RAISE EXCEPTION 'operator context arguments are invalid'
            USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(requested_additional_scopes) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'operator additional scopes must be a JSON array'
            USING ERRCODE = '22023';
    END IF;
    IF jsonb_array_length(requested_additional_scopes) > 16 THEN
        RAISE EXCEPTION 'operator additional scopes exceed the limit'
            USING ERRCODE = '22023';
    END IF;

    SELECT session.id, session.expires_at
      INTO row_id, session_expires_at
      FROM public.operator_session AS session
     WHERE session.session_token_hash = requested_session_token_hash
       AND session.operator_id = requested_operator_id
       AND session.revoked_at IS NULL
       AND session.expires_at > clock_timestamp()
     FOR SHARE OF session;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    IF session_expires_at <= clock_timestamp() THEN
        RETURN;
    END IF;

    PERFORM identity.id
      FROM public.operator_identity AS identity
     WHERE identity.id = requested_operator_id
       AND identity.enabled = TRUE
     FOR SHARE OF identity;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT loc.organization_id
      INTO location_organization_id
      FROM public.location AS loc
     WHERE loc.id = requested_location_id
       AND loc.status = 'active'
     FOR SHARE OF loc;
    IF NOT FOUND OR location_organization_id IS NULL THEN
        RETURN;
    END IF;

    SELECT owner.id, owner.organization_id
      INTO row_id, current_owner_organization_id
      FROM public.location_tenant_owner_verification AS owner
     WHERE owner.location_id = requested_location_id
       AND owner.revoked_at IS NULL
       AND owner.organization_id = location_organization_id
     FOR SHARE OF owner;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    PERFORM tenant.id
      FROM public.organization AS tenant
     WHERE tenant.id = current_owner_organization_id
       AND tenant.status = 'active'
     FOR SHARE OF tenant;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    FOR scope_record IN
        SELECT jsonb_build_object(
                   'resource', requested_resource,
                   'action', requested_action
               ) AS scope_json
        UNION ALL
        SELECT scope.value AS scope_json
          FROM jsonb_array_elements(requested_additional_scopes) AS scope(value)
    LOOP
        current_scope := scope_record.scope_json;
        IF jsonb_typeof(current_scope) IS DISTINCT FROM 'object'
           OR (SELECT count(*) FROM jsonb_object_keys(current_scope)) <> 2
           OR jsonb_typeof(current_scope -> 'resource') IS DISTINCT FROM 'string'
           OR jsonb_typeof(current_scope -> 'action') IS DISTINCT FROM 'string' THEN
            RAISE EXCEPTION 'operator additional scopes are invalid'
                USING ERRCODE = '22023';
        END IF;
        scope_resource := current_scope ->> 'resource';
        scope_action := current_scope ->> 'action';
        IF scope_resource !~ '^[a-z][a-z0-9_]{0,62}$'
           OR scope_action !~ '^[a-z][a-z0-9_]{0,62}$' THEN
            RAISE EXCEPTION 'operator additional scopes are invalid'
                USING ERRCODE = '22023';
        END IF;
        scope_key := scope_resource || ':' || scope_action;
        IF scope_key = ANY(seen_scopes) THEN
            RAISE EXCEPTION 'operator scopes must be unique'
                USING ERRCODE = '22023';
        END IF;
        seen_scopes := array_append(seen_scopes, scope_key);

        SELECT grant_row.id, grant_row.organization_id
          INTO row_id, grant_organization_id
          FROM public.operator_scope_grant AS grant_row
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.location_id = requested_location_id
           AND grant_row.resource = scope_resource
           AND grant_row.action = scope_action
           AND grant_row.organization_id IS NOT NULL
           AND grant_row.revoked_at IS NULL
         FOR SHARE OF grant_row;
        IF NOT FOUND OR grant_organization_id IS NULL THEN
            RETURN;
        END IF;

        IF resolved_tenant_id IS NULL THEN
            resolved_tenant_id := grant_organization_id;
        ELSIF resolved_tenant_id IS DISTINCT FROM grant_organization_id THEN
            RETURN;
        END IF;

        PERFORM membership.id
          FROM public.operator_organization_membership AS membership
         WHERE membership.operator_id = requested_operator_id
           AND membership.organization_id = grant_organization_id
           AND membership.revoked_at IS NULL
         FOR SHARE OF membership;
        IF NOT FOUND THEN
            RETURN;
        END IF;

        PERFORM tenant.id
          FROM public.organization AS tenant
         WHERE tenant.id = grant_organization_id
           AND tenant.status = 'active'
         FOR SHARE OF tenant;
        IF NOT FOUND THEN
            RETURN;
        END IF;

        IF grant_organization_id IS DISTINCT FROM current_owner_organization_id THEN
            SELECT share.id, share.expires_at
              INTO row_id, share_expires_at
              FROM public.location_organization_share AS share
             WHERE share.location_id = requested_location_id
               AND share.organization_id = grant_organization_id
               AND share.revoked_at IS NULL
             FOR SHARE OF share;
            IF NOT FOUND OR (share_expires_at IS NOT NULL
                             AND share_expires_at <= clock_timestamp()) THEN
                RETURN;
            END IF;
        END IF;
    END LOOP;

    SELECT key.secret
      INTO STRICT signing_key
      FROM kokonut_security.mobile_context_hmac_key AS key
     WHERE key.key_id = 1;

    signed_payload := jsonb_build_object(
        'backend_pid', pg_backend_pid(),
        'transaction_id', txid_current(),
        'tenant_id', resolved_tenant_id,
        'location_id', requested_location_id,
        'actor_id', requested_operator_id,
        'actor_type', 'operator',
        'nonce', encode(public.gen_random_bytes(16), 'hex')
    );
    payload_text := signed_payload::text;
    signature_text := encode(
        public.hmac(convert_to(payload_text, 'UTF8'), signing_key, 'sha256'),
        'hex'
    );

    PERFORM set_config('kokonut.context_payload', payload_text, TRUE);
    PERFORM set_config('kokonut.context_signature', signature_text, TRUE);
    PERFORM set_config('kokonut.tenant_id', resolved_tenant_id::text, TRUE);
    PERFORM set_config('kokonut.location_id', requested_location_id::text, TRUE);
    PERFORM set_config('kokonut.actor_id', requested_operator_id::text, TRUE);
    PERFORM set_config('kokonut.actor_type', 'operator', TRUE);

    tenant_id := resolved_tenant_id;
    location_id := requested_location_id;
    actor_id := requested_operator_id;
    actor_type := 'operator';
    RETURN NEXT;
END;
$$;

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
       OR signature_text IS NULL
       OR signature_text !~ '^[0-9a-f]{64}$' THEN
        RETURN;
    END IF;

    SELECT key.secret
      INTO signing_key
      FROM kokonut_security.mobile_context_hmac_key AS key
     WHERE key.key_id = 1;
    IF signing_key IS NULL THEN
        RETURN;
    END IF;

    expected_signature := public.hmac(
        convert_to(payload_text, 'UTF8'), signing_key, 'sha256'
    );
    supplied_signature := decode(signature_text, 'hex');
    FOR byte_index IN 0..31 LOOP
        signature_difference := signature_difference |
            (get_byte(expected_signature, byte_index) # get_byte(supplied_signature, byte_index));
    END LOOP;
    IF signature_difference <> 0 THEN
        RETURN;
    END IF;

    BEGIN
        context_payload := payload_text::jsonb;
        active_transaction_id := txid_current_if_assigned();
        IF active_transaction_id IS NULL
           OR context_payload ->> 'backend_pid' IS DISTINCT FROM pg_backend_pid()::text
           OR context_payload ->> 'transaction_id' IS DISTINCT FROM active_transaction_id::text
           OR context_payload ->> 'actor_type' NOT IN ('mobile_device', 'operator')
           OR NULLIF(context_payload ->> 'nonce', '') IS NULL THEN
            RETURN;
        END IF;

        tenant_id := (context_payload ->> 'tenant_id')::uuid;
        location_id := (context_payload ->> 'location_id')::uuid;
        actor_id := (context_payload ->> 'actor_id')::uuid;
        actor_type := context_payload ->> 'actor_type';
    EXCEPTION WHEN OTHERS THEN
        RETURN;
    END;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.set_operator_tenant_context(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
    OWNER TO kokonut_operator_context_owner;
ALTER FUNCTION kokonut_security.current_tenant_context()
    OWNER TO kokonut_mobile_context_owner;
REVOKE ALL ON FUNCTION kokonut_security.set_operator_tenant_context(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.current_tenant_context()
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.set_operator_tenant_context(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
            TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.set_operator_tenant_context(TEXT, UUID, UUID, TEXT, TEXT, JSONB) IS
    'Validates an active OIDC session and tenant-qualified operator scopes against current membership and owner/share state, locks those rows, then signs context for this transaction.';
COMMENT ON FUNCTION kokonut_security.current_tenant_context() IS
    'Returns only a valid database-signed context for this backend and transaction, for mobile_device or operator actors; caller-controlled GUC values alone are never trusted.';

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_operator_context_owner;

COMMIT;
