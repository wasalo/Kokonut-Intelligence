-- One-time, pseudonymous Delphi participant invite issuance and revocation.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_invite'
    ) THEN
        CREATE ROLE kokonut_delphi_invite
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_invite'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) OR EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_delphi_invite'
            OR member_role.rolname = 'kokonut_delphi_invite'
    ) THEN
        RAISE EXCEPTION 'Delphi invite role must remain isolated and non-login';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_participant_invite (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    consent_notice_id UUID NOT NULL
        REFERENCES kokonut_security.delphi_consent_notice(id) ON DELETE RESTRICT,
    consent_notice_version TEXT NOT NULL,
    consent_notice_digest BYTEA NOT NULL
        CHECK (pg_catalog.octet_length(consent_notice_digest) = 32),
    token_digest BYTEA NOT NULL UNIQUE CHECK (pg_catalog.octet_length(token_digest) = 32),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
    created_by UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_by UUID REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    revoked_at TIMESTAMPTZ,
    revoke_reason_code TEXT CHECK (revoke_reason_code IN (
        'sent_to_wrong_recipient', 'token_exposed', 'study_cancelled',
        'notice_replaced', 'other'
    )),
    accepted_at TIMESTAMPTZ,
    CHECK (expires_at > created_at),
    CHECK (
        (status = 'pending' AND revoked_by IS NULL AND revoked_at IS NULL
         AND revoke_reason_code IS NULL AND accepted_at IS NULL)
        OR (status = 'revoked' AND revoked_by IS NOT NULL AND revoked_at IS NOT NULL
            AND revoke_reason_code IS NOT NULL AND accepted_at IS NULL)
        OR (status = 'accepted' AND revoked_by IS NULL AND revoked_at IS NULL
            AND revoke_reason_code IS NULL AND accepted_at IS NOT NULL)
        OR (status = 'expired' AND revoked_by IS NULL AND revoked_at IS NULL
            AND revoke_reason_code IS NULL AND accepted_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_delphi_participant_invite_location_study
    ON kokonut_security.delphi_participant_invite(location_id, study_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_delphi_participant_invite_pending_expiry
    ON kokonut_security.delphi_participant_invite(expires_at, id)
    WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_participant_invite_request (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    invite_id UUID NOT NULL UNIQUE
        REFERENCES kokonut_security.delphi_participant_invite(id) ON DELETE RESTRICT,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_participant_invite_revocation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    invite_id UUID NOT NULL UNIQUE
        REFERENCES kokonut_security.delphi_participant_invite(id) ON DELETE RESTRICT,
    reason_code TEXT NOT NULL CHECK (reason_code IN (
        'sent_to_wrong_recipient', 'token_exposed', 'study_cancelled',
        'notice_replaced', 'other'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_invite_receipt_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi invite receipts are append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_participant_invite_request_immutable
    ON kokonut_security.delphi_participant_invite_request;
CREATE TRIGGER trg_delphi_participant_invite_request_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_participant_invite_request
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_invite_receipt_mutation();
DROP TRIGGER IF EXISTS trg_delphi_participant_invite_revocation_immutable
    ON kokonut_security.delphi_participant_invite_revocation;
CREATE TRIGGER trg_delphi_participant_invite_revocation_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_participant_invite_revocation
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_invite_receipt_mutation();

CREATE OR REPLACE FUNCTION kokonut_security.guard_delphi_participant_invite_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF ROW(NEW.id, NEW.location_id, NEW.study_id, NEW.consent_notice_id,
           NEW.consent_notice_version, NEW.consent_notice_digest,
           NEW.token_digest, NEW.created_by, NEW.created_at, NEW.expires_at)
       IS DISTINCT FROM
       ROW(OLD.id, OLD.location_id, OLD.study_id, OLD.consent_notice_id,
           OLD.consent_notice_version, OLD.consent_notice_digest,
           OLD.token_digest, OLD.created_by, OLD.created_at, OLD.expires_at) THEN
        RAISE EXCEPTION 'Delphi invite content is immutable';
    END IF;
    IF OLD.status = 'pending'
       AND NEW.status = 'revoked'
       AND NEW.revoked_by IS NOT NULL
       AND NEW.revoked_at IS NOT NULL
       AND NEW.revoke_reason_code IS NOT NULL
       AND NEW.accepted_at IS NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Delphi invite permits only independent revoke or acceptance transitions';
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_participant_invite_content_immutable
    ON kokonut_security.delphi_participant_invite;
CREATE TRIGGER trg_delphi_participant_invite_content_immutable
    BEFORE UPDATE ON kokonut_security.delphi_participant_invite
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.guard_delphi_participant_invite_update();

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_participant_invite_delete()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi invite history cannot be deleted';
    RETURN NULL;
END;
$$;
DROP TRIGGER IF EXISTS trg_delphi_participant_invite_no_delete
    ON kokonut_security.delphi_participant_invite;
CREATE TRIGGER trg_delphi_participant_invite_no_delete
    BEFORE DELETE ON kokonut_security.delphi_participant_invite
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_participant_invite_delete();

ALTER TABLE kokonut_security.delphi_participant_invite OWNER TO kokonut_delphi_invite;
ALTER TABLE kokonut_security.delphi_participant_invite_request OWNER TO kokonut_delphi_invite;
ALTER TABLE kokonut_security.delphi_participant_invite_revocation OWNER TO kokonut_delphi_invite;
REVOKE ALL ON TABLE kokonut_security.delphi_participant_invite,
    kokonut_security.delphi_participant_invite_request,
    kokonut_security.delphi_participant_invite_revocation FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_delphi_invite;
GRANT SELECT ON TABLE public.operator_scope_grant TO kokonut_delphi_invite;
GRANT SELECT (id, location_id, status) ON TABLE public.delphi_study
    TO kokonut_delphi_invite;
GRANT UPDATE (id) ON TABLE public.delphi_study TO kokonut_delphi_invite;
GRANT SELECT (id, location_id, study_id, version, notice_digest, status)
    ON TABLE kokonut_security.delphi_consent_notice TO kokonut_delphi_invite;
GRANT UPDATE (id) ON TABLE kokonut_security.delphi_consent_notice
    TO kokonut_delphi_invite;
GRANT SELECT, INSERT ON TABLE kokonut_security.delphi_participant_invite_request,
    kokonut_security.delphi_participant_invite_revocation TO kokonut_delphi_invite;
GRANT SELECT, INSERT ON TABLE kokonut_security.delphi_participant_invite
    TO kokonut_delphi_invite;
GRANT UPDATE (status, revoked_by, revoked_at, revoke_reason_code)
    ON TABLE kokonut_security.delphi_participant_invite TO kokonut_delphi_invite;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_delphi_invite;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_delphi_invite;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_delphi_invite;
GRANT EXECUTE ON FUNCTION public.gen_random_bytes(INTEGER)
    TO kokonut_delphi_invite;

CREATE OR REPLACE FUNCTION kokonut_security.issue_location_delphi_participant_invite(
    requested_location_id UUID,
    requested_study_id UUID,
    requested_lifetime_seconds INTEGER,
    requested_request_id UUID
)
RETURNS TABLE (
    invite_id UUID,
    location_id UUID,
    study_id UUID,
    consent_notice_id UUID,
    consent_notice_version TEXT,
    consent_notice_digest TEXT,
    invite_token TEXT,
    expires_at TIMESTAMPTZ,
    status TEXT,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    study_record RECORD;
    notice_record RECORD;
    prior_record RECORD;
    payload_digest BYTEA;
    token_value TEXT;
    new_invite_id UUID;
    expiry TIMESTAMPTZ;
    active_invite_count INTEGER;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_study_id IS NULL THEN
        RAISE EXCEPTION 'Delphi invite requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'invite', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi invite requires a current location invite grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_request_id IS NULL
       OR requested_lifetime_seconds IS NULL
       OR requested_lifetime_seconds NOT BETWEEN 3600 AND 2592000 THEN
        RAISE EXCEPTION 'Delphi invite request or expiry is invalid'
            USING ERRCODE = '22023';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0));
    payload_digest := public.digest(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'study_id', requested_study_id,
            'lifetime_seconds', requested_lifetime_seconds
        )::TEXT, 'UTF8'), 'sha256');
    SELECT request.location_id, request.study_id, request.invite_id, request.payload_digest
      INTO prior_record
      FROM kokonut_security.delphi_participant_invite_request AS request
     WHERE request.operator_id = context_record.actor_id
       AND request.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_record.location_id IS DISTINCT FROM requested_location_id
           OR prior_record.study_id IS DISTINCT FROM requested_study_id
           OR prior_record.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Delphi invite request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        SELECT invite.id, invite.consent_notice_id, invite.consent_notice_version,
               invite.consent_notice_digest, invite.expires_at, invite.status
          INTO prior_record
          FROM kokonut_security.delphi_participant_invite AS invite
         WHERE invite.id = prior_record.invite_id;
        invite_id := prior_record.id;
        location_id := requested_location_id;
        study_id := requested_study_id;
        consent_notice_id := prior_record.consent_notice_id;
        consent_notice_version := prior_record.consent_notice_version;
        consent_notice_digest := pg_catalog.encode(prior_record.consent_notice_digest, 'hex');
        invite_token := NULL;
        expires_at := prior_record.expires_at;
        status := prior_record.status;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT study.id, study.location_id, study.status
      INTO study_record
      FROM public.delphi_study AS study
     WHERE study.id = requested_study_id
       AND study.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi study is unavailable for this location'
            USING ERRCODE = '42501';
    END IF;
    IF study_record.status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Delphi invites may be issued only for draft studies'
            USING ERRCODE = '55000';
    END IF;

    SELECT notice.id, notice.version, notice.notice_digest
      INTO notice_record
      FROM kokonut_security.delphi_consent_notice AS notice
     WHERE notice.study_id = requested_study_id
       AND notice.location_id = requested_location_id
       AND notice.status = 'approved'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'A currently approved participant notice is required'
            USING ERRCODE = '55000';
    END IF;

    SELECT count(*)::INTEGER INTO active_invite_count
      FROM kokonut_security.delphi_participant_invite AS invite
     WHERE invite.study_id = requested_study_id
       AND invite.status = 'pending'
       AND invite.expires_at > pg_catalog.clock_timestamp();
    IF active_invite_count >= 500 THEN
        RAISE EXCEPTION 'Delphi study has reached its active invite limit'
            USING ERRCODE = '54000';
    END IF;

    token_value := pg_catalog.encode(public.gen_random_bytes(32), 'hex');
    expiry := pg_catalog.clock_timestamp()
        + pg_catalog.make_interval(secs => requested_lifetime_seconds);
    INSERT INTO kokonut_security.delphi_participant_invite (
        location_id, study_id, consent_notice_id, consent_notice_version,
        consent_notice_digest, token_digest, created_by, expires_at
    ) VALUES (
        requested_location_id, requested_study_id, notice_record.id,
        notice_record.version, notice_record.notice_digest,
        public.digest(pg_catalog.convert_to(token_value, 'UTF8'), 'sha256'),
        context_record.actor_id, expiry
    ) RETURNING id INTO new_invite_id;
    INSERT INTO kokonut_security.delphi_participant_invite_request (
        operator_id, request_id, location_id, study_id, invite_id, payload_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_study_id, new_invite_id, payload_digest
    );
    invite_id := new_invite_id;
    location_id := requested_location_id;
    study_id := requested_study_id;
    consent_notice_id := notice_record.id;
    consent_notice_version := notice_record.version;
    consent_notice_digest := pg_catalog.encode(notice_record.notice_digest, 'hex');
    invite_token := token_value;
    expires_at := expiry;
    status := 'pending';
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.revoke_location_delphi_participant_invite(
    requested_location_id UUID,
    requested_invite_id UUID,
    requested_request_id UUID,
    requested_reason_code TEXT
)
RETURNS TABLE (
    invite_id UUID,
    study_id UUID,
    status TEXT,
    revoked_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    prior_record RECORD;
    invite_record RECORD;
    new_revocation_id UUID;
    revoke_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_invite_id IS NULL THEN
        RAISE EXCEPTION 'Delphi invite revoke requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'invite_revoke', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi invite revoke requires a current location revoke grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_request_id IS NULL OR requested_reason_code IS NULL
       OR requested_reason_code NOT IN (
           'sent_to_wrong_recipient', 'token_exposed', 'study_cancelled',
           'notice_replaced', 'other'
       ) THEN
        RAISE EXCEPTION 'Delphi invite revoke request is invalid'
            USING ERRCODE = '22023';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0));
    SELECT item.id, item.invite_id, item.study_id, item.location_id,
           item.reason_code, item.created_at
      INTO prior_record
      FROM kokonut_security.delphi_participant_invite_revocation AS item
     WHERE item.operator_id = context_record.actor_id
       AND item.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_record.location_id IS DISTINCT FROM requested_location_id
           OR prior_record.invite_id IS DISTINCT FROM requested_invite_id
           OR prior_record.reason_code IS DISTINCT FROM requested_reason_code THEN
            RAISE EXCEPTION 'Delphi invite revoke request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        invite_id := prior_record.invite_id;
        study_id := prior_record.study_id;
        status := 'revoked';
        revoked_at := prior_record.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT invite.id, invite.study_id, invite.status, invite.expires_at
      INTO invite_record
      FROM kokonut_security.delphi_participant_invite AS invite
     WHERE invite.id = requested_invite_id
       AND invite.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi invite is unavailable for this location'
            USING ERRCODE = '42501';
    END IF;
    IF invite_record.status IS DISTINCT FROM 'pending'
       OR invite_record.expires_at <= pg_catalog.clock_timestamp() THEN
        RAISE EXCEPTION 'Only pending, unexpired Delphi invites can be revoked'
            USING ERRCODE = '55000';
    END IF;
    revoke_time := pg_catalog.clock_timestamp();
    UPDATE kokonut_security.delphi_participant_invite AS invite
       SET status = 'revoked', revoked_by = context_record.actor_id,
           revoked_at = revoke_time, revoke_reason_code = requested_reason_code
     WHERE invite.id = requested_invite_id;
    INSERT INTO kokonut_security.delphi_participant_invite_revocation (
        operator_id, request_id, location_id, study_id, invite_id,
        reason_code, created_at
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        invite_record.study_id, requested_invite_id, requested_reason_code, revoke_time
    ) RETURNING id INTO new_revocation_id;
    invite_id := requested_invite_id;
    study_id := invite_record.study_id;
    status := 'revoked';
    revoked_at := revoke_time;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.prevent_delphi_invite_receipt_mutation()
    OWNER TO kokonut_delphi_invite;
ALTER FUNCTION kokonut_security.guard_delphi_participant_invite_update()
    OWNER TO kokonut_delphi_invite;
ALTER FUNCTION kokonut_security.prevent_delphi_participant_invite_delete()
    OWNER TO kokonut_delphi_invite;
ALTER FUNCTION kokonut_security.issue_location_delphi_participant_invite(UUID, UUID, INTEGER, UUID)
    OWNER TO kokonut_delphi_invite;
ALTER FUNCTION kokonut_security.revoke_location_delphi_participant_invite(UUID, UUID, UUID, TEXT)
    OWNER TO kokonut_delphi_invite;
REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_invite_receipt_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.guard_delphi_participant_invite_update() FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_participant_invite_delete() FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.issue_location_delphi_participant_invite(UUID, UUID, INTEGER, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.revoke_location_delphi_participant_invite(UUID, UUID, UUID, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.issue_location_delphi_participant_invite(
            UUID, UUID, INTEGER, UUID
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.revoke_location_delphi_participant_invite(
            UUID, UUID, UUID, TEXT
        ) TO kokonut_runtime;
        REVOKE ALL ON TABLE kokonut_security.delphi_participant_invite,
            kokonut_security.delphi_participant_invite_request,
            kokonut_security.delphi_participant_invite_revocation FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_participant_invite,
            kokonut_security.delphi_participant_invite_request,
            kokonut_security.delphi_participant_invite_revocation FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.issue_location_delphi_participant_invite(
            UUID, UUID, INTEGER, UUID
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.revoke_location_delphi_participant_invite(
            UUID, UUID, UUID, TEXT
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE kokonut_security.delphi_participant_invite IS
'Pseudonymous single-use Delphi invite bound to the exact study and approved notice digest; only the token digest is persisted.';
COMMENT ON FUNCTION kokonut_security.issue_location_delphi_participant_invite(UUID, UUID, INTEGER, UUID) IS
'Issue one expiring participant invite under exact location delphi:invite; retries do not reveal the one-time secret again.';
COMMENT ON FUNCTION kokonut_security.revoke_location_delphi_participant_invite(UUID, UUID, UUID, TEXT) IS
'Revoke one pending invite under exact location delphi:invite_revoke with append-only reason-code audit.';

COMMIT;
