-- Pseudonymous participant minority-report submission under explicit notice scope.
-- Reports are private, immutable submissions; withdrawal hides them from review.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_minority_submitter'
    ) THEN
        CREATE ROLE kokonut_delphi_minority_submitter
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_minority_submitter'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) OR EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_delphi_minority_submitter'
            OR member_role.rolname = 'kokonut_delphi_minority_submitter'
    ) THEN
        RAISE EXCEPTION 'Delphi minority-report submitter role must remain isolated and non-login';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_participant_minority_report_request (
    id UUID PRIMARY KEY DEFAULT public.gen_random_uuid(),
    session_id UUID NOT NULL
        REFERENCES kokonut_security.delphi_participant_session(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    report_id UUID NOT NULL UNIQUE REFERENCES public.delphi_minority_report(id) ON DELETE RESTRICT,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    submitted_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (session_id, request_id)
);

CREATE INDEX IF NOT EXISTS idx_delphi_participant_minority_report_request_study
    ON kokonut_security.delphi_participant_minority_report_request(location_id, study_id, created_at DESC);

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_minority_report_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi participant minority-report request history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_participant_minority_report_request_immutable
    ON kokonut_security.delphi_participant_minority_report_request;
CREATE TRIGGER trg_delphi_participant_minority_report_request_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_participant_minority_report_request
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_minority_report_request_mutation();

REVOKE ALL ON TABLE kokonut_security.delphi_participant_minority_report_request FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.delphi_minority_report FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_delphi_minority_submitter;

GRANT SELECT (
    id, invite_id, location_id, study_id, panel_member_id,
    session_token_digest, csrf_token_digest, status, expires_at
) ON TABLE kokonut_security.delphi_participant_session
    TO kokonut_delphi_minority_submitter;
GRANT UPDATE (id) ON TABLE kokonut_security.delphi_participant_session
    TO kokonut_delphi_minority_submitter;
GRANT SELECT (id, study_id, consent_status) ON TABLE public.delphi_panel_member
    TO kokonut_delphi_minority_submitter;
GRANT SELECT (
    id, location_id, study_id, consent_notice_id, consent_notice_version,
    consent_notice_digest, status
) ON TABLE kokonut_security.delphi_participant_invite
    TO kokonut_delphi_minority_submitter;
GRANT SELECT (
    session_id, invite_id, location_id, study_id, panel_member_id,
    consent_notice_id, consent_notice_version, consent_notice_digest, event_type
) ON TABLE kokonut_security.delphi_participant_consent_event
    TO kokonut_delphi_minority_submitter;
GRANT SELECT (id, location_id, study_id, version, notice_digest, collection_scopes)
    ON TABLE kokonut_security.delphi_consent_notice
    TO kokonut_delphi_minority_submitter;
GRANT SELECT (id, location_id, status) ON TABLE public.delphi_study
    TO kokonut_delphi_minority_submitter;
GRANT UPDATE (id) ON TABLE public.delphi_study
    TO kokonut_delphi_minority_submitter;
GRANT SELECT (id, study_id) ON TABLE public.delphi_item
    TO kokonut_delphi_minority_submitter;
GRANT SELECT (id) ON TABLE public.delphi_minority_report
    TO kokonut_delphi_minority_submitter;
GRANT INSERT (
    id, study_id, item_id, title, position_summary, rationale, implications,
    status, created_by_panel_member_id, submitted_at, created_at, updated_at
) ON TABLE public.delphi_minority_report
    TO kokonut_delphi_minority_submitter;
GRANT SELECT, INSERT ON TABLE kokonut_security.delphi_participant_minority_report_request
    TO kokonut_delphi_minority_submitter;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT), public.gen_random_uuid()
    TO kokonut_delphi_minority_submitter;

-- All new report writes use the bounded participant function or the existing
-- independent-review function; shared application roles cannot write the row.
REVOKE INSERT, UPDATE, DELETE ON TABLE public.delphi_minority_report FROM kokonut_runtime;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.delphi_minority_report FROM kokonut_directus_runtime;
REVOKE ALL ON TABLE kokonut_security.delphi_participant_minority_report_request
    FROM kokonut_runtime, kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_delphi_participant_scoped_workspace(
    requested_session_token TEXT,
    requested_limit INTEGER DEFAULT 50,
    requested_offset INTEGER DEFAULT 0
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    session_digest BYTEA;
    session_record RECORD;
    workspace_value JSONB;
    scopes TEXT[];
BEGIN
    workspace_value := kokonut_security.get_location_delphi_participant_workspace(
        requested_session_token, requested_limit, requested_offset
    );
    session_digest := public.digest(
        pg_catalog.convert_to(requested_session_token, 'UTF8'), 'sha256'
    );
    SELECT session.id, session.invite_id, session.location_id,
           session.study_id, session.panel_member_id
      INTO session_record
      FROM kokonut_security.delphi_participant_session AS session
      JOIN public.delphi_panel_member AS member
        ON member.id = session.panel_member_id
       AND member.study_id = session.study_id
     WHERE session.session_token_digest = session_digest
       AND session.status = 'active'
       AND session.expires_at > pg_catalog.clock_timestamp()
       AND member.consent_status = 'granted'
     FOR SHARE OF session, member;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi participant session is invalid or unavailable'
            USING ERRCODE = '42501';
    END IF;

    SELECT notice.collection_scopes
      INTO scopes
      FROM kokonut_security.delphi_participant_invite AS invite
      JOIN kokonut_security.delphi_participant_consent_event AS accepted
        ON accepted.invite_id = invite.id
       AND accepted.session_id = session_record.id
       AND accepted.panel_member_id = session_record.panel_member_id
       AND accepted.event_type = 'accepted'
      JOIN kokonut_security.delphi_consent_notice AS notice
        ON notice.id = invite.consent_notice_id
       AND notice.location_id = invite.location_id
       AND notice.study_id = invite.study_id
       AND notice.version = invite.consent_notice_version
       AND notice.notice_digest = invite.consent_notice_digest
       AND notice.id = accepted.consent_notice_id
       AND notice.version = accepted.consent_notice_version
       AND notice.notice_digest = accepted.consent_notice_digest
     WHERE invite.id = session_record.invite_id
       AND invite.location_id = session_record.location_id
       AND invite.study_id = session_record.study_id
       AND invite.status = 'accepted';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi participant consent scope is unavailable'
            USING ERRCODE = '42501';
    END IF;
    RETURN workspace_value || pg_catalog.jsonb_build_object(
        'collection_scopes', COALESCE(scopes, ARRAY[]::TEXT[])
    );
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_delphi_participant_minority_report(
    requested_session_token TEXT,
    requested_csrf_token TEXT,
    requested_item_id UUID,
    requested_title TEXT,
    requested_position_summary TEXT,
    requested_rationale TEXT,
    requested_implications TEXT,
    requested_request_id UUID
)
RETURNS TABLE (
    status TEXT,
    report_id UUID,
    submitted_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    session_digest BYTEA;
    csrf_digest BYTEA;
    payload_digest BYTEA;
    session_record RECORD;
    scope_record RECORD;
    study_record RECORD;
    prior_record RECORD;
    result_report_id UUID;
    result_submitted_at TIMESTAMPTZ;
    normalized_title TEXT;
    normalized_position TEXT;
    normalized_rationale TEXT;
    normalized_implications TEXT;
    submission_time TIMESTAMPTZ;
BEGIN
    IF requested_session_token IS NULL OR requested_session_token !~ '^[0-9a-f]{64}$'
       OR requested_csrf_token IS NULL OR requested_csrf_token !~ '^[0-9a-f]{64}$'
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Delphi participant minority-report request is invalid'
            USING ERRCODE = '22023';
    END IF;
    normalized_title := pg_catalog.btrim(requested_title);
    normalized_position := pg_catalog.btrim(requested_position_summary);
    normalized_rationale := pg_catalog.btrim(requested_rationale);
    normalized_implications := NULLIF(pg_catalog.btrim(requested_implications), '');
    IF normalized_title IS NULL OR pg_catalog.char_length(normalized_title) NOT BETWEEN 1 AND 255
       OR normalized_position IS NULL OR pg_catalog.char_length(normalized_position) NOT BETWEEN 1 AND 4000
       OR normalized_rationale IS NULL OR pg_catalog.char_length(normalized_rationale) NOT BETWEEN 1 AND 8000
       OR normalized_implications IS NOT NULL
          AND pg_catalog.char_length(normalized_implications) > 3000 THEN
        RAISE EXCEPTION 'Delphi participant minority-report content is invalid'
            USING ERRCODE = '22023';
    END IF;

    session_digest := public.digest(
        pg_catalog.convert_to(requested_session_token, 'UTF8'), 'sha256'
    );
    csrf_digest := public.digest(
        pg_catalog.convert_to(requested_csrf_token, 'UTF8'), 'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        pg_catalog.encode(session_digest, 'hex') || ':' || requested_request_id::TEXT, 0
    ));

    -- The session lock uses the same first lock as withdrawal and contribution
    -- writes, so report insertion cannot race past a consent withdrawal.
    SELECT session.id, session.invite_id, session.location_id, session.study_id,
           session.panel_member_id, session.status, session.expires_at,
           session.csrf_token_digest, member.consent_status
      INTO session_record
      FROM kokonut_security.delphi_participant_session AS session
      JOIN public.delphi_panel_member AS member
        ON member.id = session.panel_member_id
       AND member.study_id = session.study_id
     WHERE session.session_token_digest = session_digest
     FOR UPDATE OF session;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi participant session is invalid or unavailable'
            USING ERRCODE = '42501';
    END IF;
    IF session_record.csrf_token_digest IS DISTINCT FROM csrf_digest
       OR session_record.status IS DISTINCT FROM 'active'
       OR session_record.expires_at <= pg_catalog.clock_timestamp()
       OR session_record.consent_status IS DISTINCT FROM 'granted' THEN
        RAISE EXCEPTION 'Delphi participant session is invalid or unavailable'
            USING ERRCODE = '42501';
    END IF;

    SELECT notice.collection_scopes
      INTO scope_record
      FROM kokonut_security.delphi_participant_invite AS invite
      JOIN kokonut_security.delphi_participant_consent_event AS accepted
        ON accepted.invite_id = invite.id
       AND accepted.session_id = session_record.id
       AND accepted.panel_member_id = session_record.panel_member_id
       AND accepted.location_id = session_record.location_id
       AND accepted.study_id = session_record.study_id
       AND accepted.event_type = 'accepted'
      JOIN kokonut_security.delphi_consent_notice AS notice
        ON notice.id = invite.consent_notice_id
       AND notice.location_id = invite.location_id
       AND notice.study_id = invite.study_id
       AND notice.version = invite.consent_notice_version
       AND notice.notice_digest = invite.consent_notice_digest
       AND notice.id = accepted.consent_notice_id
       AND notice.version = accepted.consent_notice_version
       AND notice.notice_digest = accepted.consent_notice_digest
     WHERE invite.id = session_record.invite_id
       AND invite.location_id = session_record.location_id
       AND invite.study_id = session_record.study_id
       AND invite.status = 'accepted';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Accepted Delphi notice does not authorize minority reports'
            USING ERRCODE = '55000';
    END IF;
    IF NOT ('minority_reports' = ANY(scope_record.collection_scopes)) THEN
        RAISE EXCEPTION 'Accepted Delphi notice does not authorize minority reports'
            USING ERRCODE = '55000';
    END IF;

    payload_digest := public.digest(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'item_id', requested_item_id,
            'title', normalized_title,
            'position_summary', normalized_position,
            'rationale', normalized_rationale,
            'implications', normalized_implications
        )::TEXT, 'UTF8'), 'sha256');
    SELECT receipt.payload_digest, receipt.report_id, receipt.submitted_at
      INTO prior_record
      FROM kokonut_security.delphi_participant_minority_report_request AS receipt
     WHERE receipt.session_id = session_record.id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_record.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Delphi minority-report request id was reused with changed content'
                USING ERRCODE = '55000';
        END IF;
        status := 'submitted';
        report_id := prior_record.report_id;
        submitted_at := prior_record.submitted_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT study.id, study.status
      INTO study_record
      FROM public.delphi_study AS study
     WHERE study.id = session_record.study_id
       AND study.location_id = session_record.location_id
     FOR UPDATE;
    IF NOT FOUND OR study_record.status IS DISTINCT FROM 'open' THEN
        RAISE EXCEPTION 'Delphi study is not open for minority-report submission'
            USING ERRCODE = '55000';
    END IF;
    IF requested_item_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.delphi_item AS item
         WHERE item.id = requested_item_id AND item.study_id = session_record.study_id
    ) THEN
        RAISE EXCEPTION 'Delphi minority-report item is unavailable'
            USING ERRCODE = '22023';
    END IF;

    submission_time := pg_catalog.clock_timestamp();
    INSERT INTO public.delphi_minority_report (
        id, study_id, item_id, title, position_summary, rationale, implications,
        status, created_by_panel_member_id, submitted_at, created_at, updated_at
    ) VALUES (
        public.gen_random_uuid(), session_record.study_id, requested_item_id,
        normalized_title, normalized_position, normalized_rationale,
        normalized_implications, 'submitted', session_record.panel_member_id,
        submission_time, submission_time, submission_time
    ) RETURNING public.delphi_minority_report.id
         INTO result_report_id;
    INSERT INTO kokonut_security.delphi_participant_minority_report_request (
        session_id, request_id, location_id, study_id, report_id,
        payload_digest, submitted_at
    ) VALUES (
        session_record.id, requested_request_id, session_record.location_id,
        session_record.study_id, result_report_id, payload_digest, submission_time
    );
    status := 'submitted';
    report_id := result_report_id;
    submitted_at := submission_time;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.prevent_delphi_minority_report_request_mutation()
    OWNER TO kokonut_delphi_minority_submitter;
ALTER FUNCTION kokonut_security.get_location_delphi_participant_scoped_workspace(
    TEXT, INTEGER, INTEGER
) OWNER TO kokonut_delphi_participant;
ALTER FUNCTION kokonut_security.submit_location_delphi_participant_minority_report(
    TEXT, TEXT, UUID, TEXT, TEXT, TEXT, TEXT, UUID
) OWNER TO kokonut_delphi_minority_submitter;

REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_minority_report_request_mutation()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_delphi_participant_scoped_workspace(
    TEXT, INTEGER, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_participant_minority_report(
    TEXT, TEXT, UUID, TEXT, TEXT, TEXT, TEXT, UUID
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.get_location_delphi_participant_workspace(
            TEXT, INTEGER, INTEGER
        ) FROM kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.get_location_delphi_participant_scoped_workspace(
            TEXT, INTEGER, INTEGER
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_delphi_participant_minority_report(
            TEXT, TEXT, UUID, TEXT, TEXT, TEXT, TEXT, UUID
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_participant_minority_report_request
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.get_location_delphi_participant_workspace(
            TEXT, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.get_location_delphi_participant_scoped_workspace(
            TEXT, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_participant_minority_report(
            TEXT, TEXT, UUID, TEXT, TEXT, TEXT, TEXT, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE kokonut_security.delphi_participant_minority_report_request IS
'Private digest-only idempotency receipts for pseudonymous Delphi minority-report submissions.';
COMMENT ON FUNCTION kokonut_security.submit_location_delphi_participant_minority_report(
    TEXT, TEXT, UUID, TEXT, TEXT, TEXT, TEXT, UUID
) IS 'Creates one immutable submitted minority report only for an active participant session whose accepted notice explicitly includes minority_reports.';
COMMENT ON FUNCTION kokonut_security.get_location_delphi_participant_scoped_workspace(
    TEXT, INTEGER, INTEGER
) IS 'Returns the participant workspace plus the exact activity scopes bound to their accepted notice.';

COMMIT;
