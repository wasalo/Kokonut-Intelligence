-- Mobile tenant context must be verifiable by PostgreSQL. Ordinary custom
-- GUC values are caller-controlled, so sign the tenant/device/transaction
-- tuple with a database-private key and expose only a validating accessor.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_mobile_context_owner'
    ) THEN
        CREATE ROLE kokonut_mobile_context_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSE
        IF EXISTS (
            SELECT 1
              FROM pg_roles
             WHERE rolname = 'kokonut_mobile_context_owner'
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls)
        ) THEN
            RAISE EXCEPTION 'kokonut_mobile_context_owner has unsafe role attributes';
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname = 'kokonut_mobile_credential_owner'
           AND NOT rolcanlogin
           AND NOT rolsuper
           AND NOT rolcreatedb
           AND NOT rolcreaterole
           AND NOT rolreplication
           AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'kokonut_mobile_credential_owner is missing or has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname IN (
                   'kokonut_mobile_credential_owner', 'kokonut_mobile_context_owner'
               )
            OR member_role.rolname IN (
                   'kokonut_mobile_credential_owner', 'kokonut_mobile_context_owner'
               )
    ) THEN
        RAISE EXCEPTION 'mobile credential/context function owner has role membership';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO PUBLIC;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_mobile_context_owner;
GRANT USAGE ON SCHEMA public TO kokonut_mobile_context_owner;

CREATE TABLE IF NOT EXISTS kokonut_security.mobile_context_hmac_key (
    key_id SMALLINT PRIMARY KEY CHECK (key_id = 1),
    secret BYTEA NOT NULL CHECK (octet_length(secret) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
);

INSERT INTO kokonut_security.mobile_context_hmac_key (key_id, secret)
VALUES (1, public.gen_random_bytes(32))
ON CONFLICT (key_id) DO NOTHING;
REVOKE ALL ON TABLE kokonut_security.mobile_context_hmac_key FROM PUBLIC;
GRANT SELECT ON TABLE kokonut_security.mobile_context_hmac_key
    TO kokonut_mobile_context_owner;

GRANT SELECT ON TABLE
    public.mobile_device,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_mobile_context_owner;
-- PostgreSQL requires UPDATE privilege to lock rows. These column grants only
-- permit row locks; the context function never changes owner/device state.
GRANT UPDATE (id) ON TABLE
    public.mobile_device,
    public.location,
    public.location_tenant_owner_verification,
    public.organization
TO kokonut_mobile_context_owner;

-- These policies are dormant until an operator separately enables RLS. They
-- let only the non-login definer roles inspect credentials/owner rows needed
-- by their fixed functions, including when FORCE ROW LEVEL SECURITY is used.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'mobile_device'
           AND policyname = 'mobile_credential_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_credential_owner_read ON public.mobile_device '
             || 'FOR SELECT TO kokonut_mobile_credential_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'mobile_device'
           AND policyname = 'mobile_credential_owner_insert'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_credential_owner_insert ON public.mobile_device '
             || 'FOR INSERT TO kokonut_mobile_credential_owner WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'mobile_device_enrollment'
           AND policyname = 'mobile_credential_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_credential_owner_read ON public.mobile_device_enrollment '
             || 'FOR SELECT TO kokonut_mobile_credential_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'mobile_device_enrollment'
           AND policyname = 'mobile_credential_owner_update'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_credential_owner_update ON public.mobile_device_enrollment '
             || 'FOR UPDATE TO kokonut_mobile_credential_owner USING (true) WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'location'
           AND policyname = 'mobile_credential_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_credential_owner_read ON public.location '
             || 'FOR SELECT TO kokonut_mobile_credential_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'location_tenant_owner_verification'
           AND policyname = 'mobile_credential_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_credential_owner_read ON public.location_tenant_owner_verification '
             || 'FOR SELECT TO kokonut_mobile_credential_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'organization'
           AND policyname = 'mobile_credential_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_credential_owner_read ON public.organization '
             || 'FOR SELECT TO kokonut_mobile_credential_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'location'
           AND policyname = 'mobile_context_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_context_owner_read ON public.location '
             || 'FOR SELECT TO kokonut_mobile_context_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'location_tenant_owner_verification'
           AND policyname = 'mobile_context_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_context_owner_read ON public.location_tenant_owner_verification '
             || 'FOR SELECT TO kokonut_mobile_context_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'organization'
           AND policyname = 'mobile_context_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_context_owner_read ON public.organization '
             || 'FOR SELECT TO kokonut_mobile_context_owner USING (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'mobile_device'
           AND policyname = 'mobile_context_owner_read'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_context_owner_read ON public.mobile_device '
             || 'FOR SELECT TO kokonut_mobile_context_owner USING (true)';
    END IF;

    -- SELECT ... FOR SHARE is subject to UPDATE policies as well as SELECT
    -- policies when RLS is forced. The roles have UPDATE privileges only on
    -- immutable primary-key columns, solely to acquire these row locks.
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'mobile_device'
           AND policyname = 'mobile_context_owner_lock'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_context_owner_lock ON public.mobile_device '
             || 'FOR UPDATE TO kokonut_mobile_context_owner USING (true) WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'location'
           AND policyname = 'mobile_context_owner_lock'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_context_owner_lock ON public.location '
             || 'FOR UPDATE TO kokonut_mobile_context_owner USING (true) WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'location_tenant_owner_verification'
           AND policyname = 'mobile_context_owner_lock'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_context_owner_lock ON public.location_tenant_owner_verification '
             || 'FOR UPDATE TO kokonut_mobile_context_owner USING (true) WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'organization'
           AND policyname = 'mobile_context_owner_lock'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_context_owner_lock ON public.organization '
             || 'FOR UPDATE TO kokonut_mobile_context_owner USING (true) WITH CHECK (true)';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'location'
           AND policyname = 'mobile_credential_owner_lock'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_credential_owner_lock ON public.location '
             || 'FOR UPDATE TO kokonut_mobile_credential_owner USING (true) WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'location_tenant_owner_verification'
           AND policyname = 'mobile_credential_owner_lock'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_credential_owner_lock ON public.location_tenant_owner_verification '
             || 'FOR UPDATE TO kokonut_mobile_credential_owner USING (true) WITH CHECK (true)';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'organization'
           AND policyname = 'mobile_credential_owner_lock'
    ) THEN
        EXECUTE 'CREATE POLICY mobile_credential_owner_lock ON public.organization '
             || 'FOR UPDATE TO kokonut_mobile_credential_owner USING (true) WITH CHECK (true)';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.set_mobile_device_context(
    requested_token_hash TEXT,
    requested_device_id TEXT,
    requested_location_id UUID
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
    context_row RECORD;
    signing_key BYTEA;
    signed_payload JSONB;
    payload_text TEXT;
    signature_text TEXT;
BEGIN
    PERFORM set_config('kokonut.tenant_id', '', TRUE);
    PERFORM set_config('kokonut.location_id', '', TRUE);
    PERFORM set_config('kokonut.actor_id', '', TRUE);
    PERFORM set_config('kokonut.actor_type', '', TRUE);
    PERFORM set_config('kokonut.context_payload', '', TRUE);
    PERFORM set_config('kokonut.context_signature', '', TRUE);

    IF requested_token_hash IS NULL
       OR requested_token_hash !~ '^[0-9a-f]{64}$'
       OR requested_device_id IS NULL
       OR requested_device_id <> btrim(requested_device_id)
       OR length(requested_device_id) NOT BETWEEN 1 AND 200
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'mobile context arguments are invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT device.tenant_organization_id,
           device.location_id,
           device.id,
           location.organization_id
      INTO context_row
      FROM public.mobile_device AS device
      JOIN public.location AS location
        ON location.id = device.location_id
      JOIN public.location_tenant_owner_verification AS owner
        ON owner.location_id = location.id
       AND owner.organization_id = location.organization_id
       AND owner.revoked_at IS NULL
      JOIN public.organization AS tenant
        ON tenant.id = owner.organization_id
       AND tenant.status = 'active'
     WHERE device.device_token_hash = requested_token_hash
       AND device.device_id = requested_device_id
       AND device.location_id = requested_location_id
       AND device.status = 'active'
       AND device.tenant_organization_id = location.organization_id
       AND location.status = 'active'
     FOR SHARE OF device, location, owner, tenant;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT key.secret
      INTO STRICT signing_key
      FROM kokonut_security.mobile_context_hmac_key AS key
     WHERE key.key_id = 1;

    signed_payload := jsonb_build_object(
        'backend_pid', pg_backend_pid(),
        'transaction_id', txid_current(),
        'tenant_id', context_row.tenant_organization_id,
        'location_id', context_row.location_id,
        'actor_id', context_row.id,
        'actor_type', 'mobile_device',
        'nonce', encode(public.gen_random_bytes(16), 'hex')
    );
    payload_text := signed_payload::text;
    signature_text := encode(
        public.hmac(convert_to(payload_text, 'UTF8'), signing_key, 'sha256'),
        'hex'
    );

    PERFORM set_config('kokonut.context_payload', payload_text, TRUE);
    PERFORM set_config('kokonut.context_signature', signature_text, TRUE);
    -- Keep legacy transaction-local labels for application diagnostics only.
    -- RLS policies must use current_tenant_context(), which verifies the MAC.
    PERFORM set_config('kokonut.tenant_id', context_row.tenant_organization_id::text, TRUE);
    PERFORM set_config('kokonut.location_id', context_row.location_id::text, TRUE);
    PERFORM set_config('kokonut.actor_id', context_row.id::text, TRUE);
    PERFORM set_config('kokonut.actor_type', 'mobile_device', TRUE);

    tenant_id := context_row.tenant_organization_id;
    location_id := context_row.location_id;
    actor_id := context_row.id;
    actor_type := 'mobile_device';
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
    -- Compare a fixed 32-byte MAC without an early-exit text comparison.
    FOR byte_index IN 0..31 LOOP
        signature_difference := signature_difference |
            (get_byte(expected_signature, byte_index) # get_byte(supplied_signature, byte_index));
    END LOOP;
    IF signature_difference <> 0 THEN
        RETURN;
    END IF;

    context_payload := payload_text::jsonb;
    active_transaction_id := txid_current_if_assigned();
    IF active_transaction_id IS NULL
       OR context_payload ->> 'backend_pid' IS DISTINCT FROM pg_backend_pid()::text
       OR context_payload ->> 'transaction_id' IS DISTINCT FROM active_transaction_id::text
       OR context_payload ->> 'actor_type' IS DISTINCT FROM 'mobile_device' THEN
        RETURN;
    END IF;

    tenant_id := (context_payload ->> 'tenant_id')::uuid;
    location_id := (context_payload ->> 'location_id')::uuid;
    actor_id := (context_payload ->> 'actor_id')::uuid;
    actor_type := context_payload ->> 'actor_type';
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.set_mobile_device_context(TEXT, TEXT, UUID)
    OWNER TO kokonut_mobile_context_owner;
ALTER FUNCTION kokonut_security.current_tenant_context()
    OWNER TO kokonut_mobile_context_owner;
REVOKE ALL ON FUNCTION kokonut_security.set_mobile_device_context(TEXT, TEXT, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.current_tenant_context()
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.set_mobile_device_context(TEXT, TEXT, UUID)
    TO PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO PUBLIC;
COMMENT ON FUNCTION kokonut_security.set_mobile_device_context(TEXT, TEXT, UUID) IS
    'Validates the active device bearer-token hash and current owner, then creates a signed context bound to the current backend and transaction.';
COMMENT ON FUNCTION kokonut_security.current_tenant_context() IS
    'Returns only a valid database-signed context for this backend and transaction; caller-controlled GUC values alone are never trusted.';

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_mobile_context_owner;

COMMIT;
