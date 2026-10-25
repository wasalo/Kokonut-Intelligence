-- Versioned, independently reviewed Delphi participant consent notices.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_consent_notice'
    ) THEN
        CREATE ROLE kokonut_delphi_consent_notice
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_consent_notice'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) OR EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_delphi_consent_notice'
            OR member_role.rolname = 'kokonut_delphi_consent_notice'
    ) THEN
        RAISE EXCEPTION 'Delphi consent notice role must remain isolated and non-login';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_consent_notice (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    version TEXT NOT NULL CHECK (version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,39}$'),
    notice_text TEXT NOT NULL CHECK (
        pg_catalog.char_length(pg_catalog.btrim(notice_text)) BETWEEN 1 AND 12000
    ),
    notice_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(notice_digest) = 32),
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'approved', 'rejected', 'superseded')),
    created_by UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    reviewed_by UUID REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ,
    review_reason_code TEXT CHECK (review_reason_code IN (
        'approved_after_independent_review', 'privacy_scope_incomplete',
        'purpose_unclear', 'withdrawal_terms_incomplete', 'other'
    )),
    UNIQUE (study_id, version),
    CHECK ((status IN ('submitted') AND reviewed_by IS NULL AND reviewed_at IS NULL
            AND review_reason_code IS NULL)
        OR (status = 'approved' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
            AND review_reason_code IS NOT NULL
            AND review_reason_code = 'approved_after_independent_review')
        OR (status = 'rejected' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
            AND review_reason_code IS NOT NULL
            AND review_reason_code <> 'approved_after_independent_review')
        OR (status = 'superseded' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
            AND review_reason_code IS NOT NULL
            AND review_reason_code = 'approved_after_independent_review'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_delphi_consent_notice_one_approved
    ON kokonut_security.delphi_consent_notice(study_id)
    WHERE status = 'approved';
CREATE INDEX IF NOT EXISTS idx_delphi_consent_notice_review_queue
    ON kokonut_security.delphi_consent_notice(location_id, created_at, id)
    WHERE status = 'submitted';

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_consent_notice_request (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    notice_id UUID NOT NULL UNIQUE
        REFERENCES kokonut_security.delphi_consent_notice(id) ON DELETE RESTRICT,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS kokonut_security.delphi_consent_notice_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reviewer_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    notice_id UUID NOT NULL UNIQUE
        REFERENCES kokonut_security.delphi_consent_notice(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
    reason_code TEXT NOT NULL CHECK (reason_code IN (
        'approved_after_independent_review', 'privacy_scope_incomplete',
        'purpose_unclear', 'withdrawal_terms_incomplete', 'other'
    )),
    resulting_status TEXT NOT NULL CHECK (resulting_status IN ('approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (reviewer_id, request_id),
    CHECK ((decision = 'approve' AND reason_code = 'approved_after_independent_review'
            AND resulting_status = 'approved')
        OR (decision = 'reject' AND reason_code <> 'approved_after_independent_review'
            AND resulting_status = 'rejected'))
);

CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_consent_notice_receipt_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi consent notice receipts are append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_consent_notice_request_immutable
    ON kokonut_security.delphi_consent_notice_request;
CREATE TRIGGER trg_delphi_consent_notice_request_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_consent_notice_request
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_consent_notice_receipt_mutation();
DROP TRIGGER IF EXISTS trg_delphi_consent_notice_decision_immutable
    ON kokonut_security.delphi_consent_notice_decision;
CREATE TRIGGER trg_delphi_consent_notice_decision_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.delphi_consent_notice_decision
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_consent_notice_receipt_mutation();

CREATE OR REPLACE FUNCTION kokonut_security.guard_delphi_consent_notice_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF ROW(NEW.id, NEW.location_id, NEW.study_id, NEW.version, NEW.notice_text,
           NEW.notice_digest, NEW.created_by, NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.id, OLD.location_id, OLD.study_id, OLD.version, OLD.notice_text,
           OLD.notice_digest, OLD.created_by, OLD.created_at) THEN
        RAISE EXCEPTION 'Delphi consent notice content is immutable';
    END IF;
    IF OLD.status = 'submitted'
       AND NEW.status IN ('approved', 'rejected')
       AND NEW.reviewed_by IS NOT NULL
       AND NEW.reviewed_at IS NOT NULL
       AND NEW.review_reason_code IS NOT NULL
       AND NOT (NEW.reviewed_by = NEW.created_by) THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'approved' AND NEW.status = 'superseded'
       AND NEW.reviewed_by IS NOT DISTINCT FROM OLD.reviewed_by
       AND NEW.reviewed_at IS NOT DISTINCT FROM OLD.reviewed_at
       AND NEW.review_reason_code IS NOT DISTINCT FROM OLD.review_reason_code THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Delphi consent notice permits only independent decisions or superseding';
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_consent_notice_content_immutable
    ON kokonut_security.delphi_consent_notice;
CREATE TRIGGER trg_delphi_consent_notice_content_immutable
    BEFORE UPDATE ON kokonut_security.delphi_consent_notice
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.guard_delphi_consent_notice_update();
CREATE OR REPLACE FUNCTION kokonut_security.prevent_delphi_consent_notice_delete()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi consent notice history cannot be deleted';
    RETURN NULL;
END;
$$;
DROP TRIGGER IF EXISTS trg_delphi_consent_notice_no_delete
    ON kokonut_security.delphi_consent_notice;
CREATE TRIGGER trg_delphi_consent_notice_no_delete
    BEFORE DELETE ON kokonut_security.delphi_consent_notice
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_delphi_consent_notice_delete();

ALTER TABLE kokonut_security.delphi_consent_notice OWNER TO kokonut_delphi_consent_notice;
ALTER TABLE kokonut_security.delphi_consent_notice_request OWNER TO kokonut_delphi_consent_notice;
ALTER TABLE kokonut_security.delphi_consent_notice_decision OWNER TO kokonut_delphi_consent_notice;
REVOKE ALL ON TABLE kokonut_security.delphi_consent_notice,
    kokonut_security.delphi_consent_notice_request,
    kokonut_security.delphi_consent_notice_decision FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_delphi_consent_notice;
GRANT SELECT ON TABLE public.operator_scope_grant
    TO kokonut_delphi_consent_notice;
GRANT SELECT (id, location_id, title, status) ON TABLE public.delphi_study
    TO kokonut_delphi_consent_notice;
GRANT SELECT ON TABLE kokonut_security.delphi_consent_notice
    TO kokonut_delphi_consent_notice;
GRANT SELECT, INSERT ON TABLE kokonut_security.delphi_consent_notice_request,
    kokonut_security.delphi_consent_notice_decision TO kokonut_delphi_consent_notice;
GRANT UPDATE (status, reviewed_by, reviewed_at, review_reason_code)
    ON TABLE kokonut_security.delphi_consent_notice TO kokonut_delphi_consent_notice;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_delphi_consent_notice;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_delphi_consent_notice;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_delphi_consent_notice;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_delphi_consent_notice(
    requested_location_id UUID,
    requested_study_id UUID,
    requested_version TEXT,
    requested_notice_text TEXT,
    requested_request_id UUID
)
RETURNS TABLE (
    notice_id UUID,
    location_id UUID,
    study_id UUID,
    version TEXT,
    status TEXT,
    notice_digest TEXT,
    created_at TIMESTAMPTZ,
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
    prior_record RECORD;
    payload_digest BYTEA;
    notice_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_study_id IS NULL THEN
        RAISE EXCEPTION 'Delphi consent notice requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'consent_draft', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi consent notice requires a current location draft grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_request_id IS NULL
       OR requested_version IS NULL
       OR requested_version !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,39}$'
       OR requested_notice_text IS NULL
       OR pg_catalog.char_length(pg_catalog.btrim(requested_notice_text)) NOT BETWEEN 1 AND 12000 THEN
        RAISE EXCEPTION 'Delphi consent notice version or text is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT study.id, study.location_id, study.status
      INTO study_record
      FROM public.delphi_study AS study
     WHERE study.id = requested_study_id
       AND study.location_id = requested_location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi study is unavailable for this location'
            USING ERRCODE = '42501';
    END IF;
    IF study_record.status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Consent notices may be submitted only for draft studies'
            USING ERRCODE = '22023';
    END IF;

    payload_digest := public.digest(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'study_id', requested_study_id,
            'version', requested_version,
            'notice_text', requested_notice_text
        )::TEXT, 'UTF8'), 'sha256');
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0));

    SELECT request.location_id, request.study_id, request.notice_id, request.payload_digest
      INTO prior_record
      FROM kokonut_security.delphi_consent_notice_request AS request
     WHERE request.operator_id = context_record.actor_id
       AND request.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_record.location_id IS DISTINCT FROM requested_location_id
           OR prior_record.study_id IS DISTINCT FROM requested_study_id
           OR prior_record.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Delphi consent notice request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        SELECT notice.id, notice.version, notice.status, notice.notice_digest,
               notice.created_at
          INTO notice_record
          FROM kokonut_security.delphi_consent_notice AS notice
         WHERE notice.id = prior_record.notice_id;
        notice_id := notice_record.id;
        location_id := requested_location_id;
        study_id := requested_study_id;
        version := notice_record.version;
        status := notice_record.status;
        notice_digest := pg_catalog.encode(notice_record.notice_digest, 'hex');
        created_at := notice_record.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    INSERT INTO kokonut_security.delphi_consent_notice (
        location_id, study_id, version, notice_text, notice_digest,
        status, created_by
    ) VALUES (
        requested_location_id, requested_study_id, requested_version,
        requested_notice_text,
        public.digest(pg_catalog.convert_to(requested_notice_text, 'UTF8'), 'sha256'),
        'submitted', context_record.actor_id
    ) RETURNING id, version, status, notice_digest, created_at INTO notice_record;

    INSERT INTO kokonut_security.delphi_consent_notice_request (
        operator_id, request_id, location_id, study_id, notice_id, payload_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_study_id, notice_record.id, payload_digest
    );
    notice_id := notice_record.id;
    location_id := requested_location_id;
    study_id := requested_study_id;
    version := notice_record.version;
    status := notice_record.status;
    notice_digest := pg_catalog.encode(notice_record.notice_digest, 'hex');
    created_at := notice_record.created_at;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_delphi_consent_notices(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 51,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    notice_id UUID,
    study_id UUID,
    study_title TEXT,
    version TEXT,
    notice_text TEXT,
    notice_digest TEXT,
    created_at TIMESTAMPTZ,
    review_ready BOOLEAN,
    blocked_reasons TEXT[]
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Delphi consent review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'consent_review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi consent review requires a current location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Delphi consent review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT notice.id, study.id, study.title::TEXT, notice.version,
           notice.notice_text, pg_catalog.encode(notice.notice_digest, 'hex'),
           notice.created_at,
           notice.created_by IS DISTINCT FROM context_record.actor_id,
           CASE WHEN notice.created_by = context_record.actor_id
                THEN ARRAY['self_review']::TEXT[] ELSE ARRAY[]::TEXT[] END
      FROM kokonut_security.delphi_consent_notice AS notice
      JOIN public.delphi_study AS study ON study.id = notice.study_id
     WHERE notice.location_id = requested_location_id
       AND study.location_id = requested_location_id
       AND notice.status = 'submitted'
     ORDER BY notice.created_at, notice.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.decide_location_delphi_consent_notice(
    requested_location_id UUID,
    requested_notice_id UUID,
    requested_decision TEXT,
    requested_request_id UUID,
    requested_reason_code TEXT
)
RETURNS TABLE (
    decision_id UUID,
    notice_id UUID,
    study_id UUID,
    decision TEXT,
    resulting_status TEXT,
    decided_at TIMESTAMPTZ,
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
    notice_record RECORD;
    resulting TEXT;
    payload_digest BYTEA;
    new_decision_id UUID;
    decision_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_notice_id IS NULL THEN
        RAISE EXCEPTION 'Delphi consent decision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'consent_review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi consent decision requires a current location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_request_id IS NULL
       OR requested_decision IS NULL
       OR requested_reason_code IS NULL
       OR requested_decision NOT IN ('approve', 'reject')
       OR requested_reason_code NOT IN (
           'approved_after_independent_review', 'privacy_scope_incomplete',
           'purpose_unclear', 'withdrawal_terms_incomplete', 'other'
       )
       OR (requested_decision = 'approve') IS DISTINCT FROM
          (requested_reason_code = 'approved_after_independent_review') THEN
        RAISE EXCEPTION 'Delphi consent decision fields are invalid'
            USING ERRCODE = '22023';
    END IF;
    resulting := CASE requested_decision WHEN 'approve' THEN 'approved' ELSE 'rejected' END;
    payload_digest := public.digest(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'notice_id', requested_notice_id,
            'decision', requested_decision,
            'reason_code', requested_reason_code
        )::TEXT, 'UTF8'), 'sha256');
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0));

    SELECT item.location_id, item.study_id, item.notice_id, item.decision,
           item.reason_code, item.resulting_status, item.id, item.created_at
      INTO prior_record
      FROM kokonut_security.delphi_consent_notice_decision AS item
     WHERE item.reviewer_id = context_record.actor_id
       AND item.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_record.location_id IS DISTINCT FROM requested_location_id
           OR prior_record.notice_id IS DISTINCT FROM requested_notice_id
           OR prior_record.decision IS DISTINCT FROM requested_decision
           OR prior_record.reason_code IS DISTINCT FROM requested_reason_code THEN
            RAISE EXCEPTION 'Delphi consent decision request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        decision_id := prior_record.id;
        notice_id := requested_notice_id;
        study_id := prior_record.study_id;
        decision := prior_record.decision;
        resulting_status := prior_record.resulting_status;
        decided_at := prior_record.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT notice.id, notice.study_id, notice.location_id,
           notice.created_by, notice.status
      INTO notice_record
      FROM kokonut_security.delphi_consent_notice AS notice
     WHERE notice.id = requested_notice_id
       AND notice.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi consent notice is unavailable for this location'
            USING ERRCODE = '42501';
    END IF;
    IF notice_record.created_by = context_record.actor_id THEN
        RAISE EXCEPTION 'Consent notice authors cannot review their own notice'
            USING ERRCODE = '55000';
    END IF;
    IF notice_record.status IS DISTINCT FROM 'submitted' THEN
        RAISE EXCEPTION 'Only submitted Delphi consent notices can be reviewed'
            USING ERRCODE = '55000';
    END IF;

    IF requested_decision = 'approve' THEN
        UPDATE kokonut_security.delphi_consent_notice AS old
           SET status = 'superseded'
         WHERE old.study_id = notice_record.study_id
           AND old.status = 'approved';
    END IF;
    decision_time := pg_catalog.clock_timestamp();
    UPDATE kokonut_security.delphi_consent_notice AS notice
       SET status = resulting,
           reviewed_by = context_record.actor_id,
           reviewed_at = decision_time,
           review_reason_code = requested_reason_code
     WHERE notice.id = requested_notice_id;

    INSERT INTO kokonut_security.delphi_consent_notice_decision (
        reviewer_id, request_id, location_id, study_id, notice_id,
        decision, reason_code, resulting_status, created_at
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        notice_record.study_id, requested_notice_id, requested_decision,
        requested_reason_code, resulting, decision_time
    ) RETURNING id INTO new_decision_id;
    decision_id := new_decision_id;
    notice_id := requested_notice_id;
    study_id := notice_record.study_id;
    decision := requested_decision;
    resulting_status := resulting;
    decided_at := decision_time;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.prevent_delphi_consent_notice_receipt_mutation()
    OWNER TO kokonut_delphi_consent_notice;
ALTER FUNCTION kokonut_security.guard_delphi_consent_notice_update()
    OWNER TO kokonut_delphi_consent_notice;
ALTER FUNCTION kokonut_security.prevent_delphi_consent_notice_delete()
    OWNER TO kokonut_delphi_consent_notice;
ALTER FUNCTION kokonut_security.submit_location_delphi_consent_notice(UUID, UUID, TEXT, TEXT, UUID)
    OWNER TO kokonut_delphi_consent_notice;
ALTER FUNCTION kokonut_security.list_location_delphi_consent_notices(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_delphi_consent_notice;
ALTER FUNCTION kokonut_security.decide_location_delphi_consent_notice(UUID, UUID, TEXT, UUID, TEXT)
    OWNER TO kokonut_delphi_consent_notice;
REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_consent_notice_receipt_mutation()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.guard_delphi_consent_notice_update()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.prevent_delphi_consent_notice_delete()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_consent_notice(UUID, UUID, TEXT, TEXT, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_consent_notices(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.decide_location_delphi_consent_notice(UUID, UUID, TEXT, UUID, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_delphi_consent_notice(
            UUID, UUID, TEXT, TEXT, UUID
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_delphi_consent_notices(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.decide_location_delphi_consent_notice(
            UUID, UUID, TEXT, UUID, TEXT
        ) TO kokonut_runtime;
        REVOKE ALL ON TABLE kokonut_security.delphi_consent_notice,
            kokonut_security.delphi_consent_notice_request,
            kokonut_security.delphi_consent_notice_decision FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE kokonut_security.delphi_consent_notice,
            kokonut_security.delphi_consent_notice_request,
            kokonut_security.delphi_consent_notice_decision FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_consent_notice(
            UUID, UUID, TEXT, TEXT, UUID
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_consent_notices(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.decide_location_delphi_consent_notice(
            UUID, UUID, TEXT, UUID, TEXT
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE kokonut_security.delphi_consent_notice IS
'Immutable versioned participant notice text; a different location reviewer must approve it before invitations can reference it.';
COMMENT ON FUNCTION kokonut_security.submit_location_delphi_consent_notice(UUID, UUID, TEXT, TEXT, UUID) IS
'Submit one immutable versioned Delphi participant notice for a draft study under delphi:consent_draft.';
COMMENT ON FUNCTION kokonut_security.list_location_delphi_consent_notices(UUID, INTEGER, INTEGER) IS
'Return bounded submitted Delphi notice text and self-review blocker to exact-location delphi:consent_review operators.';
COMMENT ON FUNCTION kokonut_security.decide_location_delphi_consent_notice(UUID, UUID, TEXT, UUID, TEXT) IS
'Approve or reject a submitted Delphi participant notice with independent review and immutable retry history.';

COMMIT;
