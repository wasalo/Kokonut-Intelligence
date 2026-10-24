-- Bind Gateway credential authorization to a database-verified location scope in
-- the same transaction as protected reads/writes. This does not enable RLS.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_gateway_context_owner'
    ) THEN
        CREATE ROLE kokonut_gateway_context_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_gateway_context_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_gateway_context_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_gateway_context_owner'
            OR member_role.rolname = 'kokonut_gateway_context_owner'
    ) THEN
        RAISE EXCEPTION 'Gateway context function owner must not have role membership';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO PUBLIC;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_gateway_context_owner;
GRANT USAGE ON SCHEMA public TO kokonut_gateway_context_owner;

-- One stored identity per API-key digest is required for unambiguous database
-- authorization. Fail the transaction if historic rows conflict so no partial
-- migration state is committed.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM public.api_key
         GROUP BY key_hash
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'migration 396 requires duplicate API-key hashes to be resolved before retrying';
    END IF;
END;
$$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_api_key_key_hash_396
    ON public.api_key (key_hash);

GRANT SELECT ON kokonut_security.mobile_context_hmac_key,
    public.api_key,
    public.capability_token,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_gateway_context_owner;
-- PostgreSQL requires UPDATE privilege to take row locks. The definer only
-- locks these primary keys and cannot mutate business or credential state.
GRANT UPDATE (key_id) ON kokonut_security.mobile_context_hmac_key
    TO kokonut_gateway_context_owner;
GRANT UPDATE (id) ON TABLE
    public.api_key,
    public.capability_token,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_gateway_context_owner;

DO $$
DECLARE
    target_table TEXT;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'api_key',
        'capability_token',
        'location',
        'location_tenant_owner_verification',
        'organization'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public'
               AND tablename = target_table
               AND policyname = 'gateway_context_owner_read'
        ) THEN
            EXECUTE format(
                'CREATE POLICY gateway_context_owner_read ON public.%I FOR SELECT TO kokonut_gateway_context_owner USING (true)',
                target_table
            );
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE schemaname = 'public'
               AND tablename = target_table
               AND policyname = 'gateway_context_owner_lock'
        ) THEN
            EXECUTE format(
                'CREATE POLICY gateway_context_owner_lock ON public.%I FOR UPDATE TO kokonut_gateway_context_owner USING (true) WITH CHECK (true)',
                target_table
            );
        END IF;
    END LOOP;
END;
$$;

-- API-key credentials may be inserted/rotated by an administrative principal,
-- never by the application runtime role. gRPC may still read these reviewed
-- columns for authentication; all future columns remain denied by default.
DO $$
DECLARE
    target_column TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL PRIVILEGES ON TABLE public.api_key FROM kokonut_runtime;
        FOR target_column IN
            SELECT attname
              FROM pg_attribute
             WHERE attrelid = 'public.api_key'::regclass
               AND attnum > 0
               AND NOT attisdropped
        LOOP
            EXECUTE format(
                'REVOKE SELECT (%I), INSERT (%I), UPDATE (%I) ON TABLE public.api_key FROM kokonut_runtime',
                target_column, target_column, target_column
            );
        END LOOP;
        GRANT SELECT (id, key_hash, key_prefix, role_id, scopes, expires_at, is_active)
            ON TABLE public.api_key TO kokonut_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.set_gateway_tenant_context(
    requested_credential_type TEXT,
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
    matched_key_id UUID;
    resolved_tenant_id UUID;
    resolved_location_id UUID;
    matched_rows INTEGER := 0;
    key_row RECORD;
    resolved_actor_type TEXT;
    signing_key BYTEA;
    context_payload TEXT;
    context_signature TEXT;
BEGIN
    FOREACH setting_name IN ARRAY ARRAY[
        'kokonut.tenant_id',
        'kokonut.location_id',
        'kokonut.actor_id',
        'kokonut.actor_type',
        'kokonut.context_payload',
        'kokonut.context_signature'
    ] LOOP
        PERFORM set_config(setting_name, '', TRUE);
    END LOOP;

    IF requested_credential_type IS NULL
       OR requested_credential_type NOT IN ('api_key', 'capability_token')
       OR requested_credential_hash IS NULL
       OR requested_credential_hash !~ '^[0-9a-f]{64}$'
       OR requested_location_id IS NULL
       OR requested_resource IS NULL
       OR requested_resource !~ '^[a-z][a-z0-9_]{0,62}$'
       OR requested_action IS NULL
       OR requested_action !~ '^[a-z][a-z0-9_]{0,62}$' THEN
        RETURN;
    END IF;

    -- Require one active credential with an exact resource:action:location
    -- grant. Wildcard and location-free grants do not establish tenant
    -- context. Lock credentials and ownership rows so revocation/transfer
    -- serializes with this transaction.
    IF requested_credential_type = 'api_key' THEN
        FOR key_row IN
            SELECT credential.id AS credential_id,
                   owner.organization_id AS tenant_id,
                   loc.id AS location_id
              FROM public.api_key AS credential
              JOIN public.location AS loc
                ON loc.id = requested_location_id
               AND loc.status = 'active'
              JOIN public.location_tenant_owner_verification AS owner
                ON owner.location_id = loc.id
               AND owner.organization_id = loc.organization_id
               AND owner.revoked_at IS NULL
              JOIN public.organization AS tenant
                ON tenant.id = owner.organization_id
               AND tenant.status = 'active'
             WHERE credential.key_hash = requested_credential_hash
               AND credential.is_active IS TRUE
               AND (credential.expires_at IS NULL
                    OR credential.expires_at > statement_timestamp())
               AND format(
                       '%s:%s:%s', requested_resource, requested_action,
                       requested_location_id::text
                   ) = ANY(COALESCE(credential.scopes, ARRAY[]::TEXT[]))
             ORDER BY credential.id
             LIMIT 2
             FOR SHARE OF credential, loc, owner, tenant
        LOOP
            matched_rows := matched_rows + 1;
            matched_key_id := key_row.credential_id;
            resolved_tenant_id := key_row.tenant_id;
            resolved_location_id := key_row.location_id;
        END LOOP;
        resolved_actor_type := 'gateway_api_key';
    ELSE
        FOR key_row IN
            SELECT credential.id AS credential_id,
                   owner.organization_id AS tenant_id,
                   loc.id AS location_id
              FROM public.capability_token AS credential
              JOIN public.location AS loc
                ON loc.id = requested_location_id
               AND loc.status = 'active'
              JOIN public.location_tenant_owner_verification AS owner
                ON owner.location_id = loc.id
               AND owner.organization_id = loc.organization_id
               AND owner.revoked_at IS NULL
              JOIN public.organization AS tenant
                ON tenant.id = owner.organization_id
               AND tenant.status = 'active'
             WHERE credential.token_hash = requested_credential_hash
               AND credential.revoked IS FALSE
               AND credential.expires_at > statement_timestamp()
               AND (credential.max_usage IS NULL OR credential.max_usage = 0
                    OR credential.usage_count <= credential.max_usage)
               AND EXISTS (
                   SELECT 1
                     FROM jsonb_array_elements(
                         CASE WHEN jsonb_typeof(credential.capabilities) = 'array'
                              THEN credential.capabilities ELSE '[]'::JSONB END
                     ) AS capability(value)
                    WHERE capability.value ->> 'resource' = requested_resource
                      AND capability.value ->> 'action' = requested_action
                      AND capability.value ->> 'location_id' = requested_location_id::text
               )
             ORDER BY credential.id
             LIMIT 2
             FOR SHARE OF credential, loc, owner, tenant
        LOOP
            matched_rows := matched_rows + 1;
            matched_key_id := key_row.credential_id;
            resolved_tenant_id := key_row.tenant_id;
            resolved_location_id := key_row.location_id;
        END LOOP;
        resolved_actor_type := 'gateway_capability';
    END IF;

    IF matched_rows <> 1 THEN
        RETURN;
    END IF;

    SELECT key.secret
      INTO signing_key
      FROM kokonut_security.mobile_context_hmac_key AS key
     WHERE key.key_id = 1;
    IF signing_key IS NULL THEN
        RETURN;
    END IF;

    context_payload := jsonb_build_object(
        'tenant_id', resolved_tenant_id,
        'location_id', resolved_location_id,
        'actor_id', matched_key_id,
        'actor_type', resolved_actor_type,
        'backend_pid', pg_backend_pid(),
        'transaction_id', txid_current(),
        'nonce', encode(public.gen_random_bytes(16), 'hex')
    )::TEXT;
    context_signature := encode(
        public.hmac(convert_to(context_payload, 'UTF8'), signing_key, 'sha256'),
        'hex'
    );

    PERFORM set_config('kokonut.context_payload', context_payload, TRUE);
    PERFORM set_config('kokonut.context_signature', context_signature, TRUE);
    PERFORM set_config('kokonut.tenant_id', resolved_tenant_id::TEXT, TRUE);
    PERFORM set_config('kokonut.location_id', resolved_location_id::TEXT, TRUE);
    PERFORM set_config('kokonut.actor_id', matched_key_id::TEXT, TRUE);
    PERFORM set_config('kokonut.actor_type', resolved_actor_type, TRUE);

    tenant_id := resolved_tenant_id;
    location_id := resolved_location_id;
    actor_id := matched_key_id;
    actor_type := resolved_actor_type;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.set_gateway_tenant_context(TEXT, TEXT, UUID, TEXT, TEXT)
    OWNER TO kokonut_gateway_context_owner;
REVOKE ALL ON FUNCTION kokonut_security.set_gateway_tenant_context(TEXT, TEXT, UUID, TEXT, TEXT)
    FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.set_gateway_tenant_context(TEXT, TEXT, UUID, TEXT, TEXT)
            TO kokonut_runtime;
    END IF;
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
           OR context_payload ->> 'backend_pid' IS DISTINCT FROM pg_backend_pid()::TEXT
           OR context_payload ->> 'transaction_id' IS DISTINCT FROM active_transaction_id::TEXT
           OR context_payload ->> 'actor_type' NOT IN (
               'mobile_device', 'operator', 'gateway_api_key', 'gateway_capability'
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

ALTER FUNCTION kokonut_security.current_tenant_context()
    OWNER TO kokonut_mobile_context_owner;
REVOKE ALL ON FUNCTION kokonut_security.current_tenant_context() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context() TO PUBLIC;

COMMENT ON FUNCTION kokonut_security.set_gateway_tenant_context(TEXT, TEXT, UUID, TEXT, TEXT) IS
    'Validates one active API key or capability token and its exact location/resource/action scope, locks current owner rows, then signs tenant context for this transaction.';
COMMENT ON FUNCTION kokonut_security.current_tenant_context() IS
    'Returns only a valid database-signed context for this backend and transaction, for mobile_device, operator, or database-verified Gateway credentials.';

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_gateway_context_owner;

COMMIT;
