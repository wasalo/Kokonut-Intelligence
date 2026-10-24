-- Database-only backups omit cluster roles and object ACLs. Restore the narrow
-- owners and grants for Field Collector and operator-session SECURITY DEFINER
-- functions before enabling the dedicated runtime logins.
BEGIN;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_mobile_credential_owner',
        'kokonut_mobile_context_owner',
        'kokonut_operator_context_owner',
        'kokonut_operator_auth_owner',
        'kokonut_gateway_context_owner',
        'kokonut_mobile_device_revoke_owner'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                'NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                role_name
            );
        ELSIF EXISTS (
            SELECT 1 FROM pg_roles
             WHERE rolname = role_name
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'security function owner % has unsafe role attributes', role_name;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_auth_members AS membership
              JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
              JOIN pg_roles AS member_role ON member_role.oid = membership.member
             WHERE granted_role.rolname = role_name OR member_role.rolname = role_name
        ) THEN
            RAISE EXCEPTION 'security function owner % has role membership', role_name;
        END IF;
    END LOOP;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security TO
    kokonut_mobile_credential_owner,
    kokonut_mobile_context_owner,
    kokonut_operator_context_owner,
    kokonut_operator_auth_owner,
    kokonut_gateway_context_owner,
    kokonut_mobile_device_revoke_owner;
GRANT CREATE ON SCHEMA kokonut_security TO
    kokonut_mobile_credential_owner,
    kokonut_mobile_context_owner,
    kokonut_operator_context_owner,
    kokonut_operator_auth_owner,
    kokonut_gateway_context_owner,
    kokonut_mobile_device_revoke_owner;

-- Rebuild the exact table and column grants expected by the definer roles.
GRANT SELECT ON TABLE
    public.mobile_device,
    public.mobile_device_enrollment,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_mobile_credential_owner;
GRANT UPDATE (id) ON TABLE
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_mobile_credential_owner;
GRANT INSERT ON TABLE public.mobile_device TO kokonut_mobile_credential_owner;
GRANT UPDATE (used_at, consumed_device_id)
    ON TABLE public.mobile_device_enrollment TO kokonut_mobile_credential_owner;

REVOKE ALL ON TABLE kokonut_security.mobile_context_hmac_key FROM PUBLIC;
GRANT SELECT ON TABLE kokonut_security.mobile_context_hmac_key
    TO kokonut_mobile_context_owner, kokonut_operator_context_owner,
       kokonut_gateway_context_owner;
GRANT SELECT ON TABLE
    public.mobile_device,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_mobile_context_owner;
GRANT UPDATE (id) ON TABLE
    public.mobile_device,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_mobile_context_owner;

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

GRANT SELECT ON TABLE public.operator_identity TO kokonut_operator_auth_owner;
GRANT UPDATE (display_name, email, updated_at)
    ON TABLE public.operator_identity TO kokonut_operator_auth_owner;
GRANT SELECT, INSERT ON TABLE public.operator_session TO kokonut_operator_auth_owner;
GRANT UPDATE (last_seen_at, revoked_at)
    ON TABLE public.operator_session TO kokonut_operator_auth_owner;

GRANT SELECT ON TABLE
    kokonut_security.mobile_context_hmac_key,
    public.api_key,
    public.capability_token,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_gateway_context_owner;
GRANT UPDATE (key_id) ON TABLE kokonut_security.mobile_context_hmac_key
    TO kokonut_gateway_context_owner;
GRANT UPDATE (id) ON TABLE
    public.api_key,
    public.capability_token,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_gateway_context_owner;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_mobile_device_revoke_owner;
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

-- A fresh role set is cluster-global, while function definitions and policy
-- rows are database-local. Rebind restored definer functions to their bounded
-- owners after pg_restore has completed.
ALTER FUNCTION kokonut_security.resolve_mobile_device_token(TEXT)
    OWNER TO kokonut_mobile_credential_owner;
ALTER FUNCTION kokonut_security.redeem_mobile_enrollment(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) OWNER TO kokonut_mobile_credential_owner;
ALTER FUNCTION kokonut_security.set_mobile_device_context(TEXT, TEXT, UUID)
    OWNER TO kokonut_mobile_context_owner;
ALTER FUNCTION kokonut_security.current_tenant_context()
    OWNER TO kokonut_mobile_context_owner;
ALTER FUNCTION kokonut_security.set_operator_tenant_context(
    TEXT, UUID, UUID, TEXT, TEXT, JSONB
) OWNER TO kokonut_operator_context_owner;
ALTER FUNCTION kokonut_security.create_operator_session(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) OWNER TO kokonut_operator_auth_owner;
ALTER FUNCTION kokonut_security.authenticate_operator_session(TEXT)
    OWNER TO kokonut_operator_auth_owner;
ALTER FUNCTION kokonut_security.revoke_operator_session(UUID)
    OWNER TO kokonut_operator_auth_owner;
ALTER FUNCTION kokonut_security.set_gateway_tenant_context(
    TEXT, TEXT, UUID, TEXT, TEXT
) OWNER TO kokonut_gateway_context_owner;
ALTER FUNCTION kokonut_security.revoke_mobile_device(
    UUID, TEXT, TEXT, TEXT, UUID, TEXT
) OWNER TO kokonut_mobile_device_revoke_owner;

-- Preserve the deliberately public bounded entry points while explicitly
-- revoking default PUBLIC execution from privileged context and write methods.
GRANT EXECUTE ON FUNCTION kokonut_security.resolve_mobile_device_token(TEXT) TO PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.redeem_mobile_enrollment(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) TO PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.set_mobile_device_context(TEXT, TEXT, UUID) TO PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context() TO PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.set_operator_tenant_context(
    TEXT, UUID, UUID, TEXT, TEXT, JSONB
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.create_operator_session(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.authenticate_operator_session(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.revoke_operator_session(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.set_gateway_tenant_context(
    TEXT, TEXT, UUID, TEXT, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.revoke_mobile_device(
    UUID, TEXT, TEXT, TEXT, UUID, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.set_operator_tenant_context(
            TEXT, UUID, UUID, TEXT, TEXT, JSONB
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.set_gateway_tenant_context(
            TEXT, TEXT, UUID, TEXT, TEXT
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.revoke_mobile_device(
            UUID, TEXT, TEXT, TEXT, UUID, TEXT
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_operator_auth;
        GRANT EXECUTE ON FUNCTION kokonut_security.create_operator_session(
            TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
        ) TO kokonut_operator_auth;
        GRANT EXECUTE ON FUNCTION kokonut_security.authenticate_operator_session(TEXT)
            TO kokonut_operator_auth;
        GRANT EXECUTE ON FUNCTION kokonut_security.revoke_operator_session(UUID)
            TO kokonut_operator_auth;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM
    kokonut_mobile_credential_owner,
    kokonut_mobile_context_owner,
    kokonut_operator_context_owner,
    kokonut_operator_auth_owner,
    kokonut_gateway_context_owner,
    kokonut_mobile_device_revoke_owner;

COMMIT;
