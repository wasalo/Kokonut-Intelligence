-- One-time invite redemption, pseudonymous consent acceptance, and withdrawal.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_participant'
    ) THEN
        CREATE ROLE kokonut_delphi_participant
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_participant'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) OR EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_delphi_participant'
            OR member_role.rolname = 'kokonut_delphi_participant'
    ) THEN
        RAISE EXCEPTION 'Delphi participant role must remain isolated and non-login';
    END IF;
END;
$$;

ALTER TABLE public.delphi_panel_member
    DROP CONSTRAINT IF EXISTS delphi_panel_member_participant_ref_type_check;
ALTER TABLE public.delphi_panel_member
    DROP CONSTRAINT IF EXISTS chk_delphi_panel_participant_ref_type;
ALTER TABLE public.delphi_panel_member
    ADD CONSTRAINT chk_delphi_panel_participant_ref_type
    CHECK (participant_ref_type IN (
        'farmer_identity', 'stakeholder_group', 'guild_contributor', 'agent',
        'pseudonymous_participant'
    ));

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_participant_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invite_id UUID NOT NULL UNIQUE
        REFERENCES kokonut_security.delphi_participant_invite(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    panel_member_id UUID NOT NULL UNIQUE
        REFERENCES public.delphi_panel_member(id) ON DELETE RESTRICT,
    session_token_digest BYTEA NOT NULL UNIQUE
        CHECK (pg_catalog.octet_length(session_token_digest) = 32),
    csrf_token_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(csrf_token_digest) = 32),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    CHECK (expires_at > created_at),
    CHECK ((status = 'active' AND revoked_at IS NULL)
        OR (status = 'revoked' AND revoked_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_delphi_participant_session_member
    ON kokonut_security.delphi_participant_session(panel_member_id, status, expires_at);

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_participant_consent_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invite_id UUID NOT NULL
        REFERENCES kokonut_security.delphi_participant_invite(id) ON DELETE RESTRICT,
    session_id UUID NOT NULL
        REFERENCES kokonut_security.delphi_participant_session(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    panel_member_id UUID NOT NULL
        REFERENCES public.delphi_panel_member(id) ON DELETE RESTRICT,
    consent_notice_id UUID NOT NULL
        REFERENCES kokonut_security.delphi_consent_notice(id) ON DELETE RESTRICT,
    consent_notice_version TEXT NOT NULL,
    consent_notice_digest BYTEA NOT NULL
        CHECK (pg_catalog.octet_length(consent_notice_digest) = 32),
    event_type TEXT NOT NULL CHECK (event_type IN ('accepted', 'withdrawn')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (invite_id, event_type)
);
CREATE INDEX IF NOT EXISTS idx_delphi_participant_consent_event_study
    ON kokonut_security.delphi_participant_consent_event(study_id, created_at, id);

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_participant_acceptance_request (
    invite_id UUID PRIMARY KEY
        REFERENCES kokonut_security.delphi_participant_invite(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL UNIQUE,
    session_id UUID NOT NULL UNIQUE
        REFERENCES kokonut_security.delphi_participant_session(id) ON DELETE RESTRICT,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_participant_withdrawal (
    session_id UUID PRIMARY KEY
        REFERENCES kokonut_security.delphi_participant_session(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL UNIQUE,
    invite_id UUID NOT NULL UNIQUE
        REFERENCES kokonut_security.delphi_participant_invite(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_participant_history_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi participant consent and receipt history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_participant_consent_event_immutable
    ON kokonut_security.delphi_participant_consent_event;
CREATE TRIGGER trg_delphi_participant_consent_event_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_participant_consent_event
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_participant_history_mutation();
DROP TRIGGER IF EXISTS trg_delphi_participant_acceptance_request_immutable
    ON kokonut_security.delphi_participant_acceptance_request;
CREATE TRIGGER trg_delphi_participant_acceptance_request_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_participant_acceptance_request
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_participant_history_mutation();
DROP TRIGGER IF EXISTS trg_delphi_participant_withdrawal_immutable
    ON kokonut_security.delphi_participant_withdrawal;
CREATE TRIGGER trg_delphi_participant_withdrawal_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_participant_withdrawal
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_participant_history_mutation();

CREATE OR REPLACE FUNCTION kokonut_security.guard_delphi_participant_session_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF ROW(NEW.id, NEW.invite_id, NEW.location_id, NEW.study_id,
           NEW.panel_member_id, NEW.session_token_digest, NEW.csrf_token_digest,
           NEW.created_at, NEW.expires_at)
       IS DISTINCT FROM
       ROW(OLD.id, OLD.invite_id, OLD.location_id, OLD.study_id,
           OLD.panel_member_id, OLD.session_token_digest, OLD.csrf_token_digest,
           OLD.created_at, OLD.expires_at) THEN
        RAISE EXCEPTION 'Delphi participant session credentials are immutable';
    END IF;
    IF OLD.status = 'active' AND NEW.status = 'revoked'
       AND NEW.revoked_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Delphi participant session allows only revocation';
END;
$$;
DROP TRIGGER IF EXISTS trg_delphi_participant_session_guard
    ON kokonut_security.delphi_participant_session;
CREATE TRIGGER trg_delphi_participant_session_guard
    BEFORE UPDATE ON kokonut_security.delphi_participant_session
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.guard_delphi_participant_session_update();

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_participant_session_delete()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi participant session history cannot be deleted';
    RETURN NULL;
END;
$$;
DROP TRIGGER IF EXISTS trg_delphi_participant_session_no_delete
    ON kokonut_security.delphi_participant_session;
CREATE TRIGGER trg_delphi_participant_session_no_delete
    BEFORE DELETE ON kokonut_security.delphi_participant_session
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_participant_session_delete();

ALTER TABLE kokonut_security.delphi_participant_session OWNER TO kokonut_delphi_participant;
ALTER TABLE kokonut_security.delphi_participant_consent_event OWNER TO kokonut_delphi_participant;
ALTER TABLE kokonut_security.delphi_participant_acceptance_request OWNER TO kokonut_delphi_participant;
ALTER TABLE kokonut_security.delphi_participant_withdrawal OWNER TO kokonut_delphi_participant;
REVOKE ALL ON TABLE kokonut_security.delphi_participant_session,
    kokonut_security.delphi_participant_consent_event,
    kokonut_security.delphi_participant_acceptance_request,
    kokonut_security.delphi_participant_withdrawal FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_delphi_participant;

REVOKE ALL ON TABLE kokonut_security.delphi_participant_invite FROM kokonut_delphi_participant;
GRANT SELECT ON TABLE kokonut_security.delphi_participant_invite TO kokonut_delphi_participant;
GRANT UPDATE (id) ON TABLE kokonut_security.delphi_participant_invite
    TO kokonut_delphi_participant;
GRANT UPDATE (status, accepted_at) ON TABLE kokonut_security.delphi_participant_invite
    TO kokonut_delphi_participant;
GRANT SELECT (id, location_id, status, title) ON TABLE public.delphi_study
    TO kokonut_delphi_participant;
GRANT UPDATE (id) ON TABLE public.delphi_study TO kokonut_delphi_participant;
GRANT SELECT (id, location_id, study_id, version, notice_text, notice_digest, status)
    ON TABLE kokonut_security.delphi_consent_notice TO kokonut_delphi_participant;
GRANT UPDATE (id) ON TABLE kokonut_security.delphi_consent_notice
    TO kokonut_delphi_participant;
REVOKE ALL ON TABLE public.delphi_panel_member FROM kokonut_delphi_participant;
GRANT SELECT (id, study_id, consent_status) ON TABLE public.delphi_panel_member
    TO kokonut_delphi_participant;
GRANT INSERT (id, study_id, participant_ref_type, participant_ref_id,
              display_token, is_anonymous, expert_weight, role, consent_status)
    ON TABLE public.delphi_panel_member TO kokonut_delphi_participant;
GRANT UPDATE (id) ON TABLE public.delphi_panel_member TO kokonut_delphi_participant;
GRANT UPDATE (consent_status) ON TABLE public.delphi_panel_member
    TO kokonut_delphi_participant;
GRANT SELECT, INSERT ON TABLE kokonut_security.delphi_participant_session,
    kokonut_security.delphi_participant_consent_event,
    kokonut_security.delphi_participant_acceptance_request,
    kokonut_security.delphi_participant_withdrawal TO kokonut_delphi_participant;
GRANT UPDATE (status, revoked_at) ON TABLE kokonut_security.delphi_participant_session
    TO kokonut_delphi_participant;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_delphi_participant;
GRANT EXECUTE ON FUNCTION public.gen_random_bytes(INTEGER)
    TO kokonut_delphi_participant;

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
    IF OLD.status = 'pending' AND NEW.status = 'revoked'
       AND NEW.revoked_by IS NOT NULL AND NEW.revoked_at IS NOT NULL
       AND NEW.revoke_reason_code IS NOT NULL AND NEW.accepted_at IS NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'pending' AND NEW.status = 'accepted'
       AND NEW.revoked_by IS NULL AND NEW.revoked_at IS NULL
       AND NEW.revoke_reason_code IS NULL AND NEW.accepted_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Delphi invite permits only acceptance or revoke transitions';
END;
$$;
ALTER FUNCTION kokonut_security.guard_delphi_participant_invite_update()
    OWNER TO kokonut_delphi_invite;

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_participant_history_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi participant consent and receipt history is append-only';
    RETURN NULL;
END;
$$;
ALTER FUNCTION kokonut_security.prevent_delphi_participant_history_mutation()
    OWNER TO kokonut_delphi_participant;
CREATE OR REPLACE FUNCTION kokonut_security.guard_delphi_participant_session_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF ROW(NEW.id, NEW.invite_id, NEW.location_id, NEW.study_id,
           NEW.panel_member_id, NEW.session_token_digest, NEW.csrf_token_digest,
           NEW.created_at, NEW.expires_at)
       IS DISTINCT FROM
       ROW(OLD.id, OLD.invite_id, OLD.location_id, OLD.study_id,
           OLD.panel_member_id, OLD.session_token_digest, OLD.csrf_token_digest,
           OLD.created_at, OLD.expires_at) THEN
        RAISE EXCEPTION 'Delphi participant session credentials are immutable';
    END IF;
    IF OLD.status = 'active' AND NEW.status = 'revoked' AND NEW.revoked_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Delphi participant session allows only revocation';
END;
$$;
ALTER FUNCTION kokonut_security.guard_delphi_participant_session_update()
    OWNER TO kokonut_delphi_participant;
CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_participant_session_delete()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi participant session history cannot be deleted';
    RETURN NULL;
END;
$$;
ALTER FUNCTION kokonut_security.prevent_delphi_participant_session_delete()
    OWNER TO kokonut_delphi_participant;

CREATE OR REPLACE FUNCTION kokonut_security.preview_location_delphi_participant_invite(
    requested_invite_token TEXT
)
RETURNS TABLE (
    study_title TEXT,
    notice_version TEXT,
    notice_text TEXT,
    notice_digest TEXT,
    expires_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE invite_digest BYTEA;
BEGIN
    IF requested_invite_token IS NULL OR requested_invite_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Delphi invite is invalid or unavailable' USING ERRCODE = '42501';
    END IF;
    invite_digest := public.digest(pg_catalog.convert_to(requested_invite_token, 'UTF8'), 'sha256');
    RETURN QUERY
    SELECT study.title::TEXT, notice.version, notice.notice_text,
           pg_catalog.encode(notice.notice_digest, 'hex'), invite.expires_at
      FROM kokonut_security.delphi_participant_invite AS invite
      JOIN public.delphi_study AS study ON study.id = invite.study_id
      JOIN kokonut_security.delphi_consent_notice AS notice
        ON notice.id = invite.consent_notice_id
       AND notice.study_id = invite.study_id
       AND notice.location_id = invite.location_id
       AND notice.version = invite.consent_notice_version
       AND notice.notice_digest = invite.consent_notice_digest
       AND notice.status = 'approved'
     WHERE invite.token_digest = invite_digest
       AND invite.status = 'pending'
       AND invite.expires_at > pg_catalog.clock_timestamp()
       AND study.location_id = invite.location_id
       AND study.status = 'draft';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi invite is invalid or unavailable' USING ERRCODE = '42501';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.accept_location_delphi_participant_invite(
    requested_invite_token TEXT,
    requested_notice_digest TEXT,
    requested_session_token TEXT,
    requested_csrf_token TEXT,
    requested_request_id UUID,
    requested_accepted BOOLEAN
)
RETURNS TABLE (
    status TEXT,
    notice_version TEXT,
    notice_digest TEXT,
    accepted_at TIMESTAMPTZ,
    session_expires_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE invite_digest BYTEA;
    session_digest BYTEA;
    csrf_digest BYTEA;
    requested_digest BYTEA;
    payload_digest BYTEA;
    invite_record RECORD;
    study_record RECORD;
    notice_record RECORD;
    prior_record RECORD;
    session_record RECORD;
    member_id UUID;
    session_id UUID;
    acceptance_time TIMESTAMPTZ;
    session_expiry TIMESTAMPTZ;
    display_value TEXT;
BEGIN
    IF requested_invite_token IS NULL OR requested_invite_token !~ '^[0-9a-f]{64}$'
       OR requested_notice_digest IS NULL OR requested_notice_digest !~ '^[0-9a-f]{64}$'
       OR requested_session_token IS NULL OR requested_session_token !~ '^[0-9a-f]{64}$'
       OR requested_csrf_token IS NULL OR requested_csrf_token !~ '^[0-9a-f]{64}$'
       OR requested_request_id IS NULL OR requested_accepted IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Delphi consent acceptance fields are invalid'
            USING ERRCODE = '22023';
    END IF;
    invite_digest := public.digest(pg_catalog.convert_to(requested_invite_token, 'UTF8'), 'sha256');
    session_digest := public.digest(pg_catalog.convert_to(requested_session_token, 'UTF8'), 'sha256');
    csrf_digest := public.digest(pg_catalog.convert_to(requested_csrf_token, 'UTF8'), 'sha256');
    IF session_digest = csrf_digest THEN
        RAISE EXCEPTION 'Participant session and CSRF tokens must differ'
            USING ERRCODE = '22023';
    END IF;
    requested_digest := pg_catalog.decode(requested_notice_digest, 'hex');
    payload_digest := public.digest(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'notice_digest', requested_notice_digest,
            'session_digest', pg_catalog.encode(session_digest, 'hex'),
            'csrf_digest', pg_catalog.encode(csrf_digest, 'hex'),
            'accepted', requested_accepted
        )::TEXT, 'UTF8'), 'sha256');

    SELECT invite.id, invite.location_id, invite.study_id, invite.consent_notice_id,
           invite.consent_notice_version, invite.consent_notice_digest,
           invite.status, invite.expires_at
      INTO invite_record
      FROM kokonut_security.delphi_participant_invite AS invite
     WHERE invite.token_digest = invite_digest
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi invite is invalid or unavailable' USING ERRCODE = '42501';
    END IF;

    SELECT request.invite_id, request.request_id, request.session_id, request.payload_digest,
           request.created_at, session.status, session.expires_at
      INTO prior_record
      FROM kokonut_security.delphi_participant_acceptance_request AS request
      JOIN kokonut_security.delphi_participant_session AS session
        ON session.id = request.session_id
     WHERE request.invite_id = invite_record.id;
    IF FOUND THEN
        IF prior_record.request_id IS DISTINCT FROM requested_request_id
           OR prior_record.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Delphi invite was already redeemed with different credentials'
                USING ERRCODE = '55000';
        END IF;
        IF prior_record.status IS DISTINCT FROM 'active'
           OR prior_record.expires_at <= pg_catalog.clock_timestamp() THEN
            RAISE EXCEPTION 'Delphi participant session is no longer active'
                USING ERRCODE = '55000';
        END IF;
        status := 'accepted';
        notice_version := invite_record.consent_notice_version;
        notice_digest := pg_catalog.encode(invite_record.consent_notice_digest, 'hex');
        accepted_at := prior_record.created_at;
        session_expires_at := prior_record.expires_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    IF invite_record.status IS DISTINCT FROM 'pending'
       OR invite_record.expires_at <= pg_catalog.clock_timestamp() THEN
        RAISE EXCEPTION 'Delphi invite is invalid or no longer pending'
            USING ERRCODE = '55000';
    END IF;
    IF invite_record.consent_notice_digest IS DISTINCT FROM requested_digest THEN
        RAISE EXCEPTION 'Consent notice changed; preview the current invite again'
            USING ERRCODE = '22023';
    END IF;

    SELECT study.id, study.location_id, study.status, study.title
      INTO study_record
      FROM public.delphi_study AS study
     WHERE study.id = invite_record.study_id
       AND study.location_id = invite_record.location_id
     FOR UPDATE;
    IF NOT FOUND OR study_record.status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Delphi invite is invalid or no longer available'
            USING ERRCODE = '55000';
    END IF;
    SELECT notice.id, notice.version, notice.notice_digest, notice.status
      INTO notice_record
      FROM kokonut_security.delphi_consent_notice AS notice
     WHERE notice.id = invite_record.consent_notice_id
       AND notice.study_id = invite_record.study_id
       AND notice.location_id = invite_record.location_id
     FOR UPDATE;
    IF NOT FOUND OR notice_record.status IS DISTINCT FROM 'approved'
       OR notice_record.version IS DISTINCT FROM invite_record.consent_notice_version
       OR notice_record.notice_digest IS DISTINCT FROM invite_record.consent_notice_digest THEN
        RAISE EXCEPTION 'The invite notice is no longer the approved study version'
            USING ERRCODE = '55000';
    END IF;

    member_id := public.gen_random_uuid();
    session_id := public.gen_random_uuid();
    acceptance_time := pg_catalog.clock_timestamp();
    session_expiry := acceptance_time + INTERVAL '30 days';
    display_value := 'P-' || pg_catalog.upper(
        pg_catalog.substr(pg_catalog.encode(public.gen_random_bytes(8), 'hex'), 1, 12)
    );
    INSERT INTO public.delphi_panel_member (
        id, study_id, participant_ref_type, participant_ref_id, display_token,
        is_anonymous, expert_weight, role, consent_status
    ) VALUES (
        member_id, invite_record.study_id, 'pseudonymous_participant', NULL,
        display_value, TRUE, 1.0, 'expert', 'granted'
    );
    INSERT INTO kokonut_security.delphi_participant_session (
        id, invite_id, location_id, study_id, panel_member_id,
        session_token_digest, csrf_token_digest, status, created_at, expires_at
    ) VALUES (
        session_id, invite_record.id, invite_record.location_id, invite_record.study_id,
        member_id, session_digest, csrf_digest, 'active', acceptance_time, session_expiry
    );
    UPDATE kokonut_security.delphi_participant_invite AS invite
       SET status = 'accepted', accepted_at = acceptance_time
     WHERE invite.id = invite_record.id;
    INSERT INTO kokonut_security.delphi_participant_consent_event (
        invite_id, session_id, location_id, study_id, panel_member_id,
        consent_notice_id, consent_notice_version, consent_notice_digest,
        event_type, created_at
    ) VALUES (
        invite_record.id, session_id, invite_record.location_id, invite_record.study_id,
        member_id, invite_record.consent_notice_id, invite_record.consent_notice_version,
        invite_record.consent_notice_digest, 'accepted', acceptance_time
    );
    INSERT INTO kokonut_security.delphi_participant_acceptance_request (
        invite_id, request_id, session_id, payload_digest, created_at
    ) VALUES (
        invite_record.id, requested_request_id, session_id, payload_digest, acceptance_time
    );
    status := 'accepted';
    notice_version := invite_record.consent_notice_version;
    notice_digest := pg_catalog.encode(invite_record.consent_notice_digest, 'hex');
    accepted_at := acceptance_time;
    session_expires_at := session_expiry;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.withdraw_location_delphi_participant(
    requested_session_token TEXT,
    requested_csrf_token TEXT,
    requested_request_id UUID
)
RETURNS TABLE (
    status TEXT,
    withdrawn_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE session_digest BYTEA;
    csrf_digest BYTEA;
    payload_digest BYTEA;
    session_record RECORD;
    prior_record RECORD;
    withdrawal_time TIMESTAMPTZ;
BEGIN
    IF requested_session_token IS NULL OR requested_session_token !~ '^[0-9a-f]{64}$'
       OR requested_csrf_token IS NULL OR requested_csrf_token !~ '^[0-9a-f]{64}$'
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Delphi withdrawal request is invalid' USING ERRCODE = '22023';
    END IF;
    session_digest := public.digest(pg_catalog.convert_to(requested_session_token, 'UTF8'), 'sha256');
    csrf_digest := public.digest(pg_catalog.convert_to(requested_csrf_token, 'UTF8'), 'sha256');
    payload_digest := public.digest(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'session_digest', pg_catalog.encode(session_digest, 'hex'),
            'csrf_digest', pg_catalog.encode(csrf_digest, 'hex')
        )::TEXT, 'UTF8'), 'sha256');
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        pg_catalog.encode(session_digest, 'hex') || ':' || requested_request_id::TEXT, 0));
    SELECT session.id, session.invite_id, session.location_id, session.study_id,
           session.panel_member_id, session.status, session.expires_at
      INTO session_record
      FROM kokonut_security.delphi_participant_session AS session
     WHERE session.session_token_digest = session_digest
       AND session.csrf_token_digest = csrf_digest
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi participant session is invalid or unavailable'
            USING ERRCODE = '42501';
    END IF;
    SELECT withdrawal.session_id, withdrawal.request_id, withdrawal.payload_digest,
           withdrawal.created_at
      INTO prior_record
      FROM kokonut_security.delphi_participant_withdrawal AS withdrawal
     WHERE withdrawal.session_id = session_record.id;
    IF FOUND THEN
        IF prior_record.request_id IS DISTINCT FROM requested_request_id
           OR prior_record.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Delphi participant already withdrew with different request content'
                USING ERRCODE = '55000';
        END IF;
        status := 'withdrawn';
        withdrawn_at := prior_record.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;
    IF session_record.status IS DISTINCT FROM 'active'
       OR session_record.expires_at <= pg_catalog.clock_timestamp() THEN
        RAISE EXCEPTION 'Delphi participant session is no longer active'
            USING ERRCODE = '55000';
    END IF;
    withdrawal_time := pg_catalog.clock_timestamp();
    UPDATE public.delphi_panel_member AS member
       SET consent_status = 'withdrawn'
     WHERE member.id = session_record.panel_member_id
       AND member.study_id = session_record.study_id
       AND member.consent_status = 'granted';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi participant consent state is unavailable'
            USING ERRCODE = '55000';
    END IF;
    UPDATE kokonut_security.delphi_participant_session AS session
       SET status = 'revoked', revoked_at = withdrawal_time
     WHERE session.id = session_record.id;
    INSERT INTO kokonut_security.delphi_participant_consent_event (
        invite_id, session_id, location_id, study_id, panel_member_id,
        consent_notice_id, consent_notice_version, consent_notice_digest,
        event_type, created_at
    )
    SELECT invite.id, session_record.id, invite.location_id, invite.study_id,
           session_record.panel_member_id, invite.consent_notice_id,
           invite.consent_notice_version, invite.consent_notice_digest,
           'withdrawn', withdrawal_time
      FROM kokonut_security.delphi_participant_invite AS invite
     WHERE invite.id = session_record.invite_id;
    INSERT INTO kokonut_security.delphi_participant_withdrawal (
        session_id, request_id, invite_id, location_id, study_id,
        payload_digest, created_at
    ) VALUES (
        session_record.id, requested_request_id, session_record.invite_id,
        session_record.location_id, session_record.study_id,
        payload_digest, withdrawal_time
    );
    status := 'withdrawn';
    withdrawn_at := withdrawal_time;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.prevent_delphi_participant_history_mutation()
    OWNER TO kokonut_delphi_participant;
ALTER FUNCTION kokonut_security.guard_delphi_participant_session_update()
    OWNER TO kokonut_delphi_participant;
ALTER FUNCTION kokonut_security.prevent_delphi_participant_session_delete()
    OWNER TO kokonut_delphi_participant;
ALTER FUNCTION kokonut_security.preview_location_delphi_participant_invite(TEXT)
    OWNER TO kokonut_delphi_participant;
ALTER FUNCTION kokonut_security.accept_location_delphi_participant_invite(TEXT, TEXT, TEXT, TEXT, UUID, BOOLEAN)
    OWNER TO kokonut_delphi_participant;
ALTER FUNCTION kokonut_security.withdraw_location_delphi_participant(TEXT, TEXT, UUID)
    OWNER TO kokonut_delphi_participant;

REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_participant_history_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.guard_delphi_participant_session_update() FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_participant_session_delete() FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.preview_location_delphi_participant_invite(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.accept_location_delphi_participant_invite(TEXT, TEXT, TEXT, TEXT, UUID, BOOLEAN)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.withdraw_location_delphi_participant(TEXT, TEXT, UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.preview_location_delphi_participant_invite(TEXT)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.accept_location_delphi_participant_invite(
            TEXT, TEXT, TEXT, TEXT, UUID, BOOLEAN
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.withdraw_location_delphi_participant(
            TEXT, TEXT, UUID
        ) TO kokonut_runtime;
        REVOKE ALL ON TABLE kokonut_security.delphi_participant_session,
            kokonut_security.delphi_participant_consent_event,
            kokonut_security.delphi_participant_acceptance_request,
            kokonut_security.delphi_participant_withdrawal FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_participant_session,
            kokonut_security.delphi_participant_consent_event,
            kokonut_security.delphi_participant_acceptance_request,
            kokonut_security.delphi_participant_withdrawal FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.preview_location_delphi_participant_invite(TEXT)
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.accept_location_delphi_participant_invite(
            TEXT, TEXT, TEXT, TEXT, UUID, BOOLEAN
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.withdraw_location_delphi_participant(
            TEXT, TEXT, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE kokonut_security.delphi_participant_session IS
'One revocable pseudonymous participant session; only session and CSRF token digests are stored.';
COMMENT ON TABLE kokonut_security.delphi_participant_consent_event IS
'Append-only acceptance and withdrawal events bound to the exact approved notice version and digest.';
COMMENT ON FUNCTION kokonut_security.accept_location_delphi_participant_invite(TEXT, TEXT, TEXT, TEXT, UUID, BOOLEAN) IS
'Atomically consume a pending one-time invite, create a pseudonymous panel member, record notice acceptance, and establish digest-only session credentials.';
COMMENT ON FUNCTION kokonut_security.withdraw_location_delphi_participant(TEXT, TEXT, UUID) IS
'Revoke the participant session, mark consent withdrawn, and preserve prior submissions for configured retention/erasure disposition.';

COMMIT;
