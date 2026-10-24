-- Put device-token revocation behind a fixed database function so the shared
-- runtime role cannot directly change device status or credential material.
-- The function revalidates the exact Gateway/operator revoke scope inside the
-- write transaction and remains safe under forced RLS.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_mobile_device_revoke_owner'
    ) THEN
        CREATE ROLE kokonut_mobile_device_revoke_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname = 'kokonut_mobile_device_revoke_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'mobile device revoke function owner has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_mobile_device_revoke_owner'
            OR member_role.rolname = 'kokonut_mobile_device_revoke_owner'
    ) THEN
        RAISE EXCEPTION 'mobile device revoke function owner must not have role membership';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_mobile_device_revoke_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.set_gateway_tenant_context(
    TEXT, TEXT, UUID, TEXT, TEXT
) TO kokonut_mobile_device_revoke_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.set_operator_tenant_context(
    TEXT, UUID, UUID, TEXT, TEXT, JSONB
) TO kokonut_mobile_device_revoke_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_mobile_device_revoke_owner;

GRANT SELECT (device_id, location_id, tenant_organization_id, status)
    ON TABLE public.mobile_device TO kokonut_mobile_device_revoke_owner;
GRANT UPDATE (status, device_token_hash, revoked_at, updated_at)
    ON TABLE public.mobile_device TO kokonut_mobile_device_revoke_owner;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public'
           AND tablename = 'mobile_device'
           AND policyname = 'mobile_device_revoke_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_device_revoke_owner_read ON public.mobile_device '
             || 'FOR SELECT TO kokonut_mobile_device_revoke_owner USING ('
             || 'EXISTS (SELECT 1 FROM kokonut_security.current_tenant_context() AS context '
             || 'WHERE context.tenant_id = mobile_device.tenant_organization_id '
             || 'AND context.location_id = mobile_device.location_id '
             || 'AND context.actor_type IN (''operator'', ''gateway_api_key'', ''gateway_capability'')))';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public'
           AND tablename = 'mobile_device'
           AND policyname = 'mobile_device_revoke_owner_update'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_device_revoke_owner_update ON public.mobile_device '
             || 'FOR UPDATE TO kokonut_mobile_device_revoke_owner USING ('
             || 'EXISTS (SELECT 1 FROM kokonut_security.current_tenant_context() AS context '
             || 'WHERE context.tenant_id = mobile_device.tenant_organization_id '
             || 'AND context.location_id = mobile_device.location_id '
             || 'AND context.actor_type IN (''operator'', ''gateway_api_key'', ''gateway_capability''))) '
             || 'WITH CHECK (EXISTS (SELECT 1 FROM kokonut_security.current_tenant_context() AS context '
             || 'WHERE context.tenant_id = mobile_device.tenant_organization_id '
             || 'AND context.location_id = mobile_device.location_id '
             || 'AND context.actor_type IN (''operator'', ''gateway_api_key'', ''gateway_capability'')))';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.revoke_mobile_device(
    requested_location_id UUID,
    requested_device_id TEXT,
    requested_gateway_credential_type TEXT,
    requested_gateway_credential_hash TEXT,
    requested_operator_id UUID,
    requested_operator_session_token_hash TEXT
)
RETURNS TABLE (result TEXT, device_id TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    resolved_tenant_id UUID;
    resolved_location_id UUID;
    resolved_actor_type TEXT;
    expected_actor_type TEXT;
    revoked_device_id TEXT;
BEGIN
    IF requested_location_id IS NULL
       OR requested_device_id IS NULL
       OR requested_device_id <> btrim(requested_device_id)
       OR length(requested_device_id) NOT BETWEEN 1 AND 200 THEN
        RETURN QUERY SELECT 'denied'::TEXT, NULL::TEXT;
        RETURN;
    END IF;

    IF requested_gateway_credential_type IN ('api_key', 'capability_token')
       AND requested_gateway_credential_hash ~ '^[0-9a-f]{64}$'
       AND requested_operator_id IS NULL
       AND requested_operator_session_token_hash IS NULL THEN
        expected_actor_type := CASE requested_gateway_credential_type
            WHEN 'api_key' THEN 'gateway_api_key'
            ELSE 'gateway_capability'
        END;
        PERFORM 1
          FROM kokonut_security.set_gateway_tenant_context(
              requested_gateway_credential_type,
              requested_gateway_credential_hash,
              requested_location_id,
              'mobile_device',
              'revoke'
          );
    ELSIF requested_gateway_credential_type IS NULL
       AND requested_gateway_credential_hash IS NULL
       AND requested_operator_id IS NOT NULL
       AND requested_operator_session_token_hash ~ '^[0-9a-f]{64}$' THEN
        expected_actor_type := 'operator';
        PERFORM 1
          FROM kokonut_security.set_operator_tenant_context(
              requested_operator_session_token_hash,
              requested_operator_id,
              requested_location_id,
              'mobile_device',
              'revoke',
              '[]'::JSONB
          );
    ELSE
        RETURN QUERY SELECT 'denied'::TEXT, NULL::TEXT;
        RETURN;
    END IF;

    SELECT context.tenant_id, context.location_id, context.actor_type
      INTO resolved_tenant_id, resolved_location_id, resolved_actor_type
      FROM kokonut_security.current_tenant_context() AS context;
    IF NOT FOUND
       OR resolved_tenant_id IS NULL
       OR resolved_location_id IS DISTINCT FROM requested_location_id
       OR resolved_actor_type IS DISTINCT FROM expected_actor_type THEN
        RETURN QUERY SELECT 'denied'::TEXT, NULL::TEXT;
        RETURN;
    END IF;

    UPDATE public.mobile_device AS device
       SET status = 'revoked',
           device_token_hash = NULL,
           revoked_at = statement_timestamp(),
           updated_at = statement_timestamp()
     WHERE device.device_id = requested_device_id
       AND device.location_id = resolved_location_id
       AND device.tenant_organization_id = resolved_tenant_id
       AND device.status = 'active'
    RETURNING device.device_id INTO revoked_device_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT 'not_found'::TEXT, NULL::TEXT;
        RETURN;
    END IF;

    RETURN QUERY SELECT 'revoked'::TEXT, revoked_device_id;
END;
$$;

ALTER FUNCTION kokonut_security.revoke_mobile_device(
    UUID, TEXT, TEXT, TEXT, UUID, TEXT
) OWNER TO kokonut_mobile_device_revoke_owner;
REVOKE ALL ON FUNCTION kokonut_security.revoke_mobile_device(
    UUID, TEXT, TEXT, TEXT, UUID, TEXT
) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.revoke_mobile_device(
            UUID, TEXT, TEXT, TEXT, UUID, TEXT
        ) TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.revoke_mobile_device(
    UUID, TEXT, TEXT, TEXT, UUID, TEXT
) IS
    'Revokes one active Field Collector device after revalidating an exact mobile_device:revoke location grant in this transaction. Returns only revoked, not_found, or denied and never exposes token material.';

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_mobile_device_revoke_owner;

COMMIT;
