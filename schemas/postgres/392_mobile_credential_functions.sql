-- Keep bearer-credential resolution and one-time redemption behind narrow
-- database functions so those paths can later run under forced RLS without
-- broad no-context reads from the application role.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_mobile_credential_owner'
    ) THEN
        CREATE ROLE kokonut_mobile_credential_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSE
        IF EXISTS (
            SELECT 1
              FROM pg_roles
             WHERE rolname = 'kokonut_mobile_credential_owner'
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls)
        ) THEN
            RAISE EXCEPTION 'kokonut_mobile_credential_owner has unsafe role attributes';
        END IF;
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO PUBLIC;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_mobile_credential_owner;

GRANT USAGE ON SCHEMA public TO kokonut_mobile_credential_owner;
GRANT SELECT ON TABLE
    public.mobile_device,
    public.mobile_device_enrollment,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_mobile_credential_owner;
-- PostgreSQL requires UPDATE privilege to take row locks. Column-level grants
-- on immutable primary keys allow the owner check to lock transfer rows without
-- granting the function role update access to owner, organization, or location
-- state.
GRANT UPDATE (id) ON TABLE
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_mobile_credential_owner;
GRANT INSERT ON TABLE public.mobile_device TO kokonut_mobile_credential_owner;
GRANT UPDATE (used_at, consumed_device_id)
    ON TABLE public.mobile_device_enrollment
    TO kokonut_mobile_credential_owner;

-- Credential redemption runs with a deliberately restricted search_path. The
-- existing tenant-binding trigger must therefore qualify its relation names
-- instead of inheriting the caller's search_path, which is limited to
-- pg_catalog inside the credential functions below.
CREATE OR REPLACE FUNCTION public.guard_mobile_tenant_binding()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND (
        NEW.location_id IS DISTINCT FROM OLD.location_id
        OR NEW.tenant_organization_id IS DISTINCT FROM OLD.tenant_organization_id
    ) THEN
        RAISE EXCEPTION 'mobile device and enrollment tenant bindings are immutable';
    END IF;

    IF TG_OP = 'INSERT' AND NEW.tenant_organization_id IS NOT NULL THEN
        PERFORM 1
          FROM public.location AS loc
          JOIN public.location_tenant_owner_verification AS owner
            ON owner.location_id = loc.id
           AND owner.organization_id = loc.organization_id
           AND owner.revoked_at IS NULL
          JOIN public.organization AS tenant
            ON tenant.id = owner.organization_id
           AND tenant.status = 'active'
         WHERE loc.id = NEW.location_id
           AND loc.status = 'active'
           AND owner.organization_id = NEW.tenant_organization_id
         FOR SHARE OF loc, owner, tenant;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'mobile enrollment must match the current verified location owner';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.guard_mobile_tenant_binding() IS
    'Requires new Field Collector device/enrollment bindings to match the current verified owner, makes bindings immutable, and uses a fixed search path with schema-qualified relations.';

CREATE OR REPLACE FUNCTION kokonut_security.resolve_mobile_device_token(
    requested_token_hash TEXT
)
RETURNS TABLE (
    device_id TEXT,
    user_id TEXT,
    location_id TEXT,
    owner_binding_current BOOLEAN
)
LANGUAGE SQL
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    SELECT device.device_id::text,
           device.user_id::text,
           device.location_id::text,
           COALESCE(
               device.tenant_organization_id IS NOT NULL
               AND location.status = 'active'
               AND device.tenant_organization_id = location.organization_id
               AND owner.id IS NOT NULL
               AND tenant.status = 'active',
               FALSE
           ) AS owner_binding_current
      FROM public.mobile_device AS device
      LEFT JOIN public.location AS location
        ON location.id = device.location_id
      LEFT JOIN public.location_tenant_owner_verification AS owner
        ON owner.location_id = location.id
       AND owner.organization_id = location.organization_id
       AND owner.revoked_at IS NULL
      LEFT JOIN public.organization AS tenant
        ON tenant.id = owner.organization_id
     WHERE device.device_token_hash = requested_token_hash
       AND device.status = 'active'
     LIMIT 1
$$;

ALTER FUNCTION kokonut_security.resolve_mobile_device_token(TEXT)
    OWNER TO kokonut_mobile_credential_owner;
REVOKE ALL ON FUNCTION kokonut_security.resolve_mobile_device_token(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.resolve_mobile_device_token(TEXT) TO PUBLIC;
COMMENT ON FUNCTION kokonut_security.resolve_mobile_device_token(TEXT) IS
    'Resolves one presented device-token hash to minimal device identity and current-owner state; never returns token material or collection payloads.';

CREATE OR REPLACE FUNCTION kokonut_security.redeem_mobile_enrollment(
    requested_code_hash TEXT,
    requested_device_id TEXT,
    requested_device_name TEXT,
    requested_device_type TEXT,
    requested_os TEXT,
    requested_os_version TEXT,
    requested_app_version TEXT,
    requested_device_token_hash TEXT
)
RETURNS TABLE (
    result TEXT,
    registered_location_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    enrollment_row RECORD;
    current_owner_id UUID;
    inserted_device_id TEXT;
    consumed_enrollment_id UUID;
BEGIN
    IF requested_code_hash IS NULL
       OR requested_code_hash !~ '^[0-9a-f]{64}$'
       OR requested_device_token_hash IS NULL
       OR requested_device_token_hash !~ '^[0-9a-f]{64}$'
       OR requested_device_id IS NULL
       OR requested_device_id <> btrim(requested_device_id)
       OR length(requested_device_id) NOT BETWEEN 1 AND 200
       OR (requested_device_name IS NOT NULL AND length(requested_device_name) > 300)
       OR requested_device_type IS NULL
       OR btrim(requested_device_type) = ''
       OR length(requested_device_type) NOT BETWEEN 1 AND 100
       OR (requested_os IS NOT NULL AND length(requested_os) > 100)
       OR (requested_os_version IS NOT NULL AND length(requested_os_version) > 50)
       OR (requested_app_version IS NOT NULL AND length(requested_app_version) > 50) THEN
        RAISE EXCEPTION 'mobile enrollment arguments are invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT enrollment.id,
           enrollment.user_id,
           enrollment.location_id,
           enrollment.tenant_organization_id
      INTO enrollment_row
      FROM public.mobile_device_enrollment AS enrollment
     WHERE enrollment.code_hash = requested_code_hash
       AND enrollment.used_at IS NULL
       AND enrollment.revoked_at IS NULL
       AND enrollment.expires_at > statement_timestamp()
     FOR UPDATE;

    IF NOT FOUND THEN
        result := 'invalid';
        registered_location_id := NULL;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT location.organization_id
      INTO current_owner_id
      FROM public.location AS location
      JOIN public.location_tenant_owner_verification AS owner
        ON owner.location_id = location.id
       AND owner.organization_id = location.organization_id
       AND owner.revoked_at IS NULL
      JOIN public.organization AS tenant
        ON tenant.id = owner.organization_id
       AND tenant.status = 'active'
     WHERE location.id = enrollment_row.location_id
       AND location.status = 'active'
     FOR SHARE OF location, owner, tenant;

    IF NOT FOUND
       OR enrollment_row.tenant_organization_id IS NULL
       OR enrollment_row.tenant_organization_id IS DISTINCT FROM current_owner_id THEN
        result := 'owner_changed';
        registered_location_id := NULL;
        RETURN NEXT;
        RETURN;
    END IF;

    INSERT INTO public.mobile_device (
        device_id, device_name, device_type, os, os_version,
        app_version, user_id, location_id, tenant_organization_id,
        device_token_hash, has_camera, has_gps, has_offline,
        status, last_seen_at
    ) VALUES (
        requested_device_id, requested_device_name, requested_device_type,
        requested_os, requested_os_version, requested_app_version,
        enrollment_row.user_id, enrollment_row.location_id, current_owner_id,
        requested_device_token_hash, TRUE, TRUE, TRUE, 'active', statement_timestamp()
    )
    ON CONFLICT (device_id) DO NOTHING
    RETURNING mobile_device.device_id INTO inserted_device_id;

    IF inserted_device_id IS NULL THEN
        result := 'device_conflict';
        registered_location_id := NULL;
        RETURN NEXT;
        RETURN;
    END IF;

    UPDATE public.mobile_device_enrollment AS enrollment
       SET used_at = statement_timestamp(),
           consumed_device_id = requested_device_id
     WHERE enrollment.id = enrollment_row.id
       AND enrollment.used_at IS NULL
       AND enrollment.revoked_at IS NULL
    RETURNING enrollment.id INTO consumed_enrollment_id;

    IF consumed_enrollment_id IS NULL THEN
        RAISE EXCEPTION 'mobile enrollment was consumed concurrently'
            USING ERRCODE = '40001';
    END IF;

    result := 'registered';
    registered_location_id := enrollment_row.location_id;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.redeem_mobile_enrollment(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) OWNER TO kokonut_mobile_credential_owner;
REVOKE ALL ON FUNCTION kokonut_security.redeem_mobile_enrollment(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.redeem_mobile_enrollment(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) TO PUBLIC;
COMMENT ON FUNCTION kokonut_security.redeem_mobile_enrollment(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) IS
    'Atomically redeems one high-entropy enrollment-code hash, checks the current verified owner, registers one device, and consumes the code.';

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_mobile_credential_owner;

COMMIT;
