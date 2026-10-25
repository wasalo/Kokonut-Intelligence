-- Bind explicit participant activity scopes to immutable Delphi consent notices.
-- Empty scope arrays are retained only for legacy notices; newly submitted
-- versions must explicitly name questionnaire response collection.

BEGIN;

ALTER TABLE kokonut_security.delphi_consent_notice
    ADD COLUMN IF NOT EXISTS collection_scopes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conrelid = 'kokonut_security.delphi_consent_notice'::pg_catalog.regclass
           AND conname = 'ck_delphi_consent_notice_collection_scopes'
    ) THEN
        ALTER TABLE kokonut_security.delphi_consent_notice
            ADD CONSTRAINT ck_delphi_consent_notice_collection_scopes
            CHECK (
                pg_catalog.cardinality(collection_scopes) <= 2
                AND pg_catalog.array_position(collection_scopes, NULL) IS NULL
                AND collection_scopes <@ ARRAY['questionnaire_responses', 'minority_reports']::TEXT[]
                AND (pg_catalog.cardinality(collection_scopes) <> 2
                     OR collection_scopes[1] <> collection_scopes[2])
            );
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.guard_delphi_consent_notice_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF ROW(NEW.id, NEW.location_id, NEW.study_id, NEW.version, NEW.notice_text,
           NEW.collection_scopes, NEW.notice_digest, NEW.created_by, NEW.created_at)
       IS DISTINCT FROM
       ROW(OLD.id, OLD.location_id, OLD.study_id, OLD.version, OLD.notice_text,
           OLD.collection_scopes, OLD.notice_digest, OLD.created_by, OLD.created_at) THEN
        RAISE EXCEPTION 'Delphi consent notice content and activity scopes are immutable';
    END IF;
    IF OLD.status = 'submitted' AND NEW.status = 'approved'
       AND pg_catalog.cardinality(OLD.collection_scopes) = 0 THEN
        RAISE EXCEPTION 'An unscoped legacy notice cannot be approved; submit a scoped replacement'
            USING ERRCODE = '55000';
    END IF;
    IF OLD.status = 'submitted'
       AND NEW.status IN ('approved', 'rejected')
       AND NEW.reviewed_by IS NOT NULL
       AND NEW.reviewed_at IS NOT NULL
       AND NEW.review_reason_code IS NOT NULL
       AND NEW.reviewed_by IS DISTINCT FROM NEW.created_by
       AND (NEW.status <> 'approved'
            OR pg_catalog.cardinality(OLD.collection_scopes) > 0) THEN
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

CREATE OR REPLACE FUNCTION kokonut_security.guard_delphi_participant_invite_notice_scope()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE notice_scopes TEXT[];
BEGIN
    SELECT notice.collection_scopes
      INTO notice_scopes
      FROM kokonut_security.delphi_consent_notice AS notice
     WHERE notice.id = NEW.consent_notice_id
       AND notice.location_id = NEW.location_id
       AND notice.study_id = NEW.study_id
       AND notice.version = NEW.consent_notice_version
       AND notice.notice_digest = NEW.consent_notice_digest
       AND notice.status = 'approved';
    IF NOT FOUND OR pg_catalog.cardinality(notice_scopes) = 0 THEN
        RAISE EXCEPTION 'A reviewed notice with explicit participant activity scope is required for new invites'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

ALTER FUNCTION kokonut_security.guard_delphi_participant_invite_notice_scope()
    OWNER TO kokonut_delphi_consent_notice;
REVOKE ALL ON FUNCTION kokonut_security.guard_delphi_participant_invite_notice_scope()
    FROM PUBLIC;
DROP TRIGGER IF EXISTS trg_delphi_participant_invite_notice_scope
    ON kokonut_security.delphi_participant_invite;
CREATE TRIGGER trg_delphi_participant_invite_notice_scope
    BEFORE INSERT ON kokonut_security.delphi_participant_invite
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.guard_delphi_participant_invite_notice_scope();

-- The old text-only entry points would allow new notices to omit structured
-- scope, or allow reviewers/participants to see a notice without its scope.
REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_consent_notice(
    UUID, UUID, TEXT, TEXT, UUID
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_consent_notices(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.preview_location_delphi_participant_invite(TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_consent_notice(
            UUID, UUID, TEXT, TEXT, UUID
        ) FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_consent_notices(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.preview_location_delphi_participant_invite(TEXT)
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_consent_notice(
            UUID, UUID, TEXT, TEXT, UUID
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_consent_notices(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.preview_location_delphi_participant_invite(TEXT)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_delphi_consent_notice_scoped(
    requested_location_id UUID,
    requested_study_id UUID,
    requested_version TEXT,
    requested_notice_text TEXT,
    requested_collection_scopes TEXT[],
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
    notice_record RECORD;
    normalized_scopes TEXT[];
    payload_digest BYTEA;
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
       OR pg_catalog.char_length(pg_catalog.btrim(requested_notice_text)) NOT BETWEEN 1 AND 12000
       OR requested_collection_scopes IS NULL
       OR pg_catalog.cardinality(requested_collection_scopes) NOT BETWEEN 1 AND 2
       OR pg_catalog.array_position(requested_collection_scopes, NULL) IS NOT NULL THEN
        RAISE EXCEPTION 'Delphi consent notice version, text, or activity scope is invalid'
            USING ERRCODE = '22023';
    END IF;
    SELECT COALESCE(
               pg_catalog.array_agg(scope_value ORDER BY
                   CASE scope_value
                       WHEN 'questionnaire_responses' THEN 1
                       WHEN 'minority_reports' THEN 2
                   END),
               ARRAY[]::TEXT[]
           )
      INTO normalized_scopes
      FROM (SELECT DISTINCT pg_catalog.unnest(requested_collection_scopes) AS scope_value) AS scopes;
    IF pg_catalog.cardinality(normalized_scopes) <> pg_catalog.cardinality(requested_collection_scopes)
       OR NOT normalized_scopes <@ ARRAY['questionnaire_responses', 'minority_reports']::TEXT[]
       OR NOT ('questionnaire_responses' = ANY(normalized_scopes)) THEN
        RAISE EXCEPTION 'Delphi consent notice activity scope is invalid'
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
            'notice_text', requested_notice_text,
            'collection_scopes', normalized_scopes
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
        location_id, study_id, version, notice_text, collection_scopes,
        notice_digest, status, created_by
    ) VALUES (
        requested_location_id, requested_study_id, requested_version,
        requested_notice_text, normalized_scopes,
        public.digest(pg_catalog.convert_to(pg_catalog.jsonb_build_object(
            'notice_text', requested_notice_text,
            'collection_scopes', normalized_scopes
        )::TEXT, 'UTF8'), 'sha256'),
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

DROP FUNCTION IF EXISTS kokonut_security.list_location_delphi_consent_notices_scoped(
    UUID, INTEGER, INTEGER
);
CREATE FUNCTION kokonut_security.list_location_delphi_consent_notices_scoped(
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
    blocked_reasons TEXT[],
    collection_scopes TEXT[]
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE context_record RECORD;
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
                THEN ARRAY['self_review']::TEXT[] ELSE ARRAY[]::TEXT[] END,
           notice.collection_scopes
      FROM kokonut_security.delphi_consent_notice AS notice
      JOIN public.delphi_study AS study ON study.id = notice.study_id
     WHERE notice.location_id = requested_location_id
       AND study.location_id = requested_location_id
       AND notice.status = 'submitted'
     ORDER BY notice.created_at, notice.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

DROP FUNCTION IF EXISTS kokonut_security.preview_location_delphi_participant_invite_scoped(TEXT);
CREATE FUNCTION kokonut_security.preview_location_delphi_participant_invite_scoped(
    requested_invite_token TEXT
)
RETURNS TABLE (
    study_title TEXT,
    notice_version TEXT,
    notice_text TEXT,
    notice_digest TEXT,
    expires_at TIMESTAMPTZ,
    collection_scopes TEXT[]
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
           pg_catalog.encode(notice.notice_digest, 'hex'), invite.expires_at,
           notice.collection_scopes
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

ALTER FUNCTION kokonut_security.submit_location_delphi_consent_notice_scoped(
    UUID, UUID, TEXT, TEXT, TEXT[], UUID
) OWNER TO kokonut_delphi_consent_notice;
ALTER FUNCTION kokonut_security.list_location_delphi_consent_notices_scoped(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_delphi_consent_notice;
ALTER FUNCTION kokonut_security.preview_location_delphi_participant_invite_scoped(TEXT)
    OWNER TO kokonut_delphi_participant;

REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_consent_notice_scoped(
    UUID, UUID, TEXT, TEXT, TEXT[], UUID
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_consent_notices_scoped(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.preview_location_delphi_participant_invite_scoped(TEXT)
    FROM PUBLIC;
GRANT SELECT (collection_scopes) ON TABLE kokonut_security.delphi_consent_notice
    TO kokonut_delphi_participant;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_delphi_consent_notice_scoped(
            UUID, UUID, TEXT, TEXT, TEXT[], UUID
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_delphi_consent_notices_scoped(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.preview_location_delphi_participant_invite_scoped(TEXT)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_delphi_consent_notice_scoped(
            UUID, UUID, TEXT, TEXT, TEXT[], UUID
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_consent_notices_scoped(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.preview_location_delphi_participant_invite_scoped(TEXT)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON COLUMN kokonut_security.delphi_consent_notice.collection_scopes IS
'Explicit versioned participant activity scopes shown with the notice and bound into its digest; empty denotes a legacy notice without structured scope.';
COMMENT ON FUNCTION kokonut_security.submit_location_delphi_consent_notice_scoped(
    UUID, UUID, TEXT, TEXT, TEXT[], UUID
) IS 'Submit an immutable versioned Delphi participant notice whose explicitly selected activity scopes are included in both request and notice digests.';
COMMENT ON FUNCTION kokonut_security.preview_location_delphi_participant_invite_scoped(TEXT) IS
'Preview the exact approved notice and its digest-bound activity scopes for a pending invite.';

COMMIT;
