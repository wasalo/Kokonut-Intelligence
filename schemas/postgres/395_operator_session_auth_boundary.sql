-- Keep opaque browser-session hashes outside the general application role.
-- A dedicated operator-auth login receives explicit execution grants for these functions.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_operator_auth_owner'
    ) THEN
        CREATE ROLE kokonut_operator_auth_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSE
        IF EXISTS (
            SELECT 1
              FROM pg_roles
             WHERE rolname = 'kokonut_operator_auth_owner'
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'kokonut_operator_auth_owner has unsafe role attributes';
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_operator_auth_owner'
            OR member_role.rolname = 'kokonut_operator_auth_owner'
    ) THEN
        RAISE EXCEPTION 'operator auth function owner has role membership';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO PUBLIC;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_operator_auth_owner;
GRANT USAGE ON SCHEMA public TO kokonut_operator_auth_owner;

GRANT SELECT ON TABLE public.operator_identity TO kokonut_operator_auth_owner;
GRANT UPDATE (display_name, email, updated_at)
    ON TABLE public.operator_identity TO kokonut_operator_auth_owner;
GRANT SELECT, INSERT ON TABLE public.operator_session TO kokonut_operator_auth_owner;
GRANT UPDATE (last_seen_at, revoked_at)
    ON TABLE public.operator_session TO kokonut_operator_auth_owner;

-- These policies are dormant unless a later migration enables RLS on the
-- identity/session tables. They keep the function owner usable under FORCE RLS.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'operator_identity'
           AND policyname = 'operator_auth_owner_read'
    ) THEN
        CREATE POLICY operator_auth_owner_read ON public.operator_identity
            FOR SELECT TO kokonut_operator_auth_owner USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'operator_identity'
           AND policyname = 'operator_auth_owner_update'
    ) THEN
        CREATE POLICY operator_auth_owner_update ON public.operator_identity
            FOR UPDATE TO kokonut_operator_auth_owner
            USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'operator_session'
           AND policyname = 'operator_auth_owner_read'
    ) THEN
        CREATE POLICY operator_auth_owner_read ON public.operator_session
            FOR SELECT TO kokonut_operator_auth_owner USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'operator_session'
           AND policyname = 'operator_auth_owner_insert'
    ) THEN
        CREATE POLICY operator_auth_owner_insert ON public.operator_session
            FOR INSERT TO kokonut_operator_auth_owner WITH CHECK (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public' AND tablename = 'operator_session'
           AND policyname = 'operator_auth_owner_update'
    ) THEN
        CREATE POLICY operator_auth_owner_update ON public.operator_session
            FOR UPDATE TO kokonut_operator_auth_owner
            USING (true) WITH CHECK (true);
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.create_operator_session(
    requested_issuer TEXT,
    requested_subject TEXT,
    requested_display_name TEXT,
    requested_email TEXT,
    requested_session_token_hash TEXT,
    requested_csrf_token_hash TEXT,
    requested_expires_at TIMESTAMPTZ
)
RETURNS TABLE (
    session_id UUID,
    operator_id UUID,
    issuer TEXT,
    subject TEXT,
    display_name TEXT,
    email TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    identity_row RECORD;
BEGIN
    IF requested_issuer IS NULL
       OR requested_issuer !~ '^https://[^/?#]+(/[^?#]*)?$'
       OR requested_subject IS NULL
       OR length(requested_subject) NOT BETWEEN 1 AND 255
       OR requested_display_name IS NOT NULL
          AND length(requested_display_name) > 200
       OR requested_email IS NOT NULL AND length(requested_email) > 200
       OR requested_session_token_hash IS NULL
       OR requested_session_token_hash !~ '^[0-9a-f]{64}$'
       OR requested_csrf_token_hash IS NULL
       OR requested_csrf_token_hash !~ '^[0-9a-f]{64}$'
       OR requested_expires_at IS NULL
       OR requested_expires_at <= clock_timestamp()
       OR requested_expires_at > clock_timestamp() + INTERVAL '12 hours' THEN
        RAISE EXCEPTION 'operator session arguments are invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT identity.id, identity.issuer, identity.subject,
           identity.display_name, identity.email
      INTO identity_row
      FROM public.operator_identity AS identity
     WHERE identity.issuer = requested_issuer
       AND identity.subject = requested_subject
       AND identity.enabled = TRUE
     FOR UPDATE OF identity;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    UPDATE public.operator_identity AS identity
       SET display_name = COALESCE(requested_display_name, identity.display_name),
           email = COALESCE(requested_email, identity.email),
           updated_at = clock_timestamp()
     WHERE identity.id = identity_row.id
     RETURNING identity.id, identity.issuer, identity.subject,
               identity.display_name, identity.email
          INTO identity_row;

    INSERT INTO public.operator_session (
        operator_id, session_token_hash, csrf_token_hash, expires_at
    ) VALUES (
        identity_row.id, requested_session_token_hash,
        requested_csrf_token_hash, requested_expires_at
    ) RETURNING id INTO session_id;

    operator_id := identity_row.id;
    issuer := identity_row.issuer;
    subject := identity_row.subject;
    display_name := identity_row.display_name;
    email := identity_row.email;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.authenticate_operator_session(
    requested_session_token_hash TEXT
)
RETURNS TABLE (
    session_id UUID,
    csrf_token_hash TEXT,
    operator_id UUID,
    issuer TEXT,
    subject TEXT,
    display_name TEXT,
    email TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    session_row RECORD;
BEGIN
    IF requested_session_token_hash IS NULL
       OR requested_session_token_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'operator session hash is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT session.id AS session_id,
           session.operator_id AS operator_id,
           session.csrf_token_hash AS csrf_token_hash,
           identity.issuer AS issuer,
           identity.subject AS subject,
           identity.display_name AS display_name,
           identity.email AS email
      INTO session_row
      FROM public.operator_session AS session
      JOIN public.operator_identity AS identity
        ON identity.id = session.operator_id
     WHERE session.session_token_hash = requested_session_token_hash
       AND session.revoked_at IS NULL
       AND session.expires_at > clock_timestamp()
       AND identity.enabled = TRUE
     FOR UPDATE OF session, identity;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    UPDATE public.operator_session AS session
       SET last_seen_at = clock_timestamp()
     WHERE session.id = session_row.session_id;

    session_id := session_row.session_id;
    csrf_token_hash := btrim(session_row.csrf_token_hash);
    operator_id := session_row.operator_id;
    issuer := session_row.issuer;
    subject := session_row.subject;
    display_name := session_row.display_name;
    email := session_row.email;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.revoke_operator_session(
    requested_session_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    changed INTEGER;
BEGIN
    IF requested_session_id IS NULL THEN
        RETURN FALSE;
    END IF;
    UPDATE public.operator_session AS session
       SET revoked_at = clock_timestamp()
     WHERE session.id = requested_session_id
       AND session.revoked_at IS NULL;
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END;
$$;

ALTER FUNCTION kokonut_security.create_operator_session(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) OWNER TO kokonut_operator_auth_owner;
ALTER FUNCTION kokonut_security.authenticate_operator_session(TEXT)
    OWNER TO kokonut_operator_auth_owner;
ALTER FUNCTION kokonut_security.revoke_operator_session(UUID)
    OWNER TO kokonut_operator_auth_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_operator_auth_owner;

REVOKE ALL ON FUNCTION kokonut_security.create_operator_session(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.authenticate_operator_session(TEXT)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.revoke_operator_session(UUID)
    FROM PUBLIC;

COMMIT;
