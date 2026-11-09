-- Keep row locks for operator-authorized writes while supporting signed
-- tenant context in explicitly read-only transactions. Read-only authorization
-- is evaluated against the transaction's live session, tenant and grant rows;
-- no application data or grants are modified by this migration.
BEGIN;

DO $$
BEGIN
    IF to_regprocedure('kokonut_security.set_operator_tenant_context_write(text,uuid,uuid,text,text,jsonb)') IS NULL THEN
        IF to_regprocedure('kokonut_security.set_operator_tenant_context(text,uuid,uuid,text,text,jsonb)') IS NULL THEN
            RAISE EXCEPTION 'operator tenant-context function is missing';
        END IF;
        EXECUTE 'ALTER FUNCTION kokonut_security.set_operator_tenant_context(TEXT, UUID, UUID, TEXT, TEXT, JSONB) RENAME TO set_operator_tenant_context_write';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.set_operator_tenant_context_readonly(
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
     ;
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
     ;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT loc.organization_id
      INTO location_organization_id
      FROM public.location AS loc
     WHERE loc.id = requested_location_id
       AND loc.status = 'active'
     ;
    IF NOT FOUND OR location_organization_id IS NULL THEN
        RETURN;
    END IF;

    SELECT owner.id, owner.organization_id
      INTO row_id, current_owner_organization_id
      FROM public.location_tenant_owner_verification AS owner
     WHERE owner.location_id = requested_location_id
       AND owner.revoked_at IS NULL
       AND owner.organization_id = location_organization_id
     ;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    PERFORM tenant.id
      FROM public.organization AS tenant
     WHERE tenant.id = current_owner_organization_id
       AND tenant.status = 'active'
     ;
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
         ;
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
         ;
        IF NOT FOUND THEN
            RETURN;
        END IF;

        PERFORM tenant.id
          FROM public.organization AS tenant
         WHERE tenant.id = grant_organization_id
           AND tenant.status = 'active'
         ;
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
             ;
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

ALTER FUNCTION kokonut_security.set_operator_tenant_context_write(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
    OWNER TO kokonut_operator_context_owner;
ALTER FUNCTION kokonut_security.set_operator_tenant_context_readonly(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
    OWNER TO kokonut_operator_context_owner;
REVOKE ALL ON FUNCTION kokonut_security.set_operator_tenant_context_write(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.set_operator_tenant_context_readonly(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
    FROM PUBLIC;

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
BEGIN
    IF current_setting('transaction_read_only') = 'on' THEN
        RETURN QUERY
        SELECT * FROM kokonut_security.set_operator_tenant_context_readonly(
            requested_session_token_hash,
            requested_operator_id,
            requested_location_id,
            requested_resource,
            requested_action,
            requested_additional_scopes
        );
        RETURN;
    END IF;

    RETURN QUERY
    SELECT * FROM kokonut_security.set_operator_tenant_context_write(
        requested_session_token_hash,
        requested_operator_id,
        requested_location_id,
        requested_resource,
        requested_action,
        requested_additional_scopes
    );
END;
$$;

ALTER FUNCTION kokonut_security.set_operator_tenant_context(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
    OWNER TO kokonut_operator_context_owner;
REVOKE ALL ON FUNCTION kokonut_security.set_operator_tenant_context(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.set_operator_tenant_context_write(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
            FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.set_operator_tenant_context_readonly(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
            FROM kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.set_operator_tenant_context(TEXT, UUID, UUID, TEXT, TEXT, JSONB)
            TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.set_operator_tenant_context(TEXT, UUID, UUID, TEXT, TEXT, JSONB) IS
    'Validates tenant-qualified operator access; retains row locks for write transactions and uses a read-only validation path for read-only transactions.';
COMMENT ON FUNCTION kokonut_security.set_operator_tenant_context_write(TEXT, UUID, UUID, TEXT, TEXT, JSONB) IS
    'Validates current operator session and tenant grants under row locks before signing write-transaction context.';
COMMENT ON FUNCTION kokonut_security.set_operator_tenant_context_readonly(TEXT, UUID, UUID, TEXT, TEXT, JSONB) IS
    'Validates current operator session and tenant grants without row locks for explicitly read-only transactions.';

COMMIT;
