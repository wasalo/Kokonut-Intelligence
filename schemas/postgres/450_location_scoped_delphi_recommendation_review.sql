-- Location-scoped human review for Delphi facilitator drafts.
-- Approval remains a review decision; this path does not publish recommendation text.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_recommendation_reviewer'
    ) THEN
        CREATE ROLE kokonut_delphi_recommendation_reviewer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_recommendation_reviewer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Delphi recommendation reviewer role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_delphi_recommendation_reviewer'
            OR member_role.rolname = 'kokonut_delphi_recommendation_reviewer'
    ) THEN
        RAISE EXCEPTION 'Delphi recommendation reviewer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.delphi_recommendation_review_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reviewer_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    recommendation_id UUID NOT NULL UNIQUE
        REFERENCES public.delphi_recommendation(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
    reason_code TEXT NOT NULL CHECK (reason_code IN (
        'approved_after_review', 'insufficient_evidence', 'privacy_concern',
        'minority_report_open', 'other'
    )),
    resulting_status TEXT NOT NULL CHECK (resulting_status IN ('approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (reviewer_id, request_id),
    CHECK ((decision = 'approve' AND reason_code = 'approved_after_review'
            AND resulting_status = 'approved')
        OR (decision = 'reject' AND reason_code <> 'approved_after_review'
            AND resulting_status = 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_delphi_recommendation_review_location
    ON public.delphi_recommendation_review_decision(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_delphi_recommendation_review_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi recommendation review history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_recommendation_review_immutable
    ON public.delphi_recommendation_review_decision;
CREATE TRIGGER trg_delphi_recommendation_review_immutable
    BEFORE UPDATE OR DELETE ON public.delphi_recommendation_review_decision
    FOR EACH ROW EXECUTE FUNCTION public.prevent_delphi_recommendation_review_mutation();

REVOKE ALL ON TABLE public.delphi_recommendation_review_decision FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_delphi_recommendation_reviewer;
GRANT SELECT ON TABLE public.delphi_study, public.delphi_recommendation,
    public.delphi_diversity_assessment, public.delphi_minority_report,
    public.operator_scope_grant
    TO kokonut_delphi_recommendation_reviewer;
GRANT SELECT, INSERT ON TABLE public.delphi_recommendation_review_decision
    TO kokonut_delphi_recommendation_reviewer;
GRANT UPDATE (status, approved_by, approved_at)
    ON TABLE public.delphi_recommendation
    TO kokonut_delphi_recommendation_reviewer;
-- PostgreSQL requires an UPDATE privilege to lock rows with FOR UPDATE; the
-- function only uses this narrow column grant to lock study ownership state.
GRANT UPDATE (id) ON TABLE public.delphi_study
    TO kokonut_delphi_recommendation_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_delphi_recommendation_reviewer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_delphi_recommendation_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_delphi_recommendation_reviews(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 51,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    recommendation_id UUID,
    study_id UUID,
    study_title TEXT,
    study_status TEXT,
    summary TEXT,
    recommendation_text TEXT,
    created_at TIMESTAMPTZ,
    review_ready BOOLEAN,
    blocked_reasons TEXT[]
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
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
        RAISE EXCEPTION 'Delphi recommendation review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi recommendation review requires an active review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Delphi recommendation review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT recommendation.id,
           study.id,
           study.title::TEXT,
           study.status::TEXT,
           recommendation.summary::TEXT,
           recommendation.recommendation_text::TEXT,
           recommendation.created_at,
           cardinality(blockers.reasons) = 0,
           blockers.reasons
      FROM public.delphi_recommendation AS recommendation
      JOIN public.delphi_study AS study ON study.id = recommendation.study_id
      CROSS JOIN LATERAL (
          SELECT array_remove(ARRAY[
              CASE WHEN recommendation.created_by = context_record.actor_id
                   THEN 'self_review'::TEXT END,
              CASE WHEN NOT EXISTS (
                   SELECT 1 FROM public.delphi_diversity_assessment AS assessment
                    WHERE assessment.study_id = study.id
              ) THEN 'diversity_assessment_required'::TEXT END,
              CASE WHEN EXISTS (
                   SELECT 1 FROM public.delphi_minority_report AS report
                    WHERE report.study_id = study.id
                      AND report.status IN ('draft', 'submitted')
              ) THEN 'minority_report_review_required'::TEXT END
          ], NULL) AS reasons
      ) AS blockers
     WHERE study.location_id = requested_location_id
       AND recommendation.status = 'draft'
     ORDER BY recommendation.created_at, recommendation.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.decide_location_delphi_recommendation(
    requested_location_id UUID,
    requested_recommendation_id UUID,
    requested_decision TEXT,
    requested_request_id UUID,
    requested_reason_code TEXT
)
RETURNS TABLE (
    review_id UUID,
    recommendation_id UUID,
    study_id UUID,
    decision TEXT,
    resulting_status TEXT,
    decided_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    prior_decision public.delphi_recommendation_review_decision%ROWTYPE;
    recommendation_record RECORD;
    inserted_decision_id UUID;
    resulting_status_value TEXT;
    decided_at_value TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Delphi recommendation decision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi recommendation decision requires an active review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_recommendation_id IS NULL OR requested_request_id IS NULL
       OR requested_decision IS NULL OR requested_reason_code IS NULL
       OR requested_decision NOT IN ('approve', 'reject')
       OR requested_reason_code NOT IN (
           'approved_after_review', 'insufficient_evidence', 'privacy_concern',
           'minority_report_open', 'other'
       )
       OR (requested_decision = 'approve'
           AND requested_reason_code <> 'approved_after_review')
       OR (requested_decision = 'reject'
           AND requested_reason_code = 'approved_after_review') THEN
        RAISE EXCEPTION 'Delphi recommendation decision payload is invalid'
            USING ERRCODE = '22023';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT decision_row.* INTO prior_decision
      FROM public.delphi_recommendation_review_decision AS decision_row
     WHERE decision_row.reviewer_id = context_record.actor_id
       AND decision_row.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_decision.location_id IS DISTINCT FROM requested_location_id
           OR prior_decision.recommendation_id IS DISTINCT FROM requested_recommendation_id
           OR prior_decision.decision IS DISTINCT FROM requested_decision
           OR prior_decision.reason_code IS DISTINCT FROM requested_reason_code THEN
            RAISE EXCEPTION 'Delphi review request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        review_id := prior_decision.id;
        recommendation_id := prior_decision.recommendation_id;
        SELECT recommendation.study_id INTO study_id
          FROM public.delphi_recommendation AS recommendation
         WHERE recommendation.id = prior_decision.recommendation_id;
        decision := prior_decision.decision;
        resulting_status := prior_decision.resulting_status;
        decided_at := prior_decision.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT recommendation.id, recommendation.study_id,
           recommendation.created_by, recommendation.status,
           study.location_id
      INTO recommendation_record
      FROM public.delphi_recommendation AS recommendation
      JOIN public.delphi_study AS study ON study.id = recommendation.study_id
     WHERE recommendation.id = requested_recommendation_id
       AND study.location_id = requested_location_id
     FOR UPDATE OF recommendation, study;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi recommendation is unavailable in this location'
            USING ERRCODE = '22023';
    END IF;
    IF recommendation_record.status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Delphi recommendation has already been decided'
            USING ERRCODE = '55000';
    END IF;
    IF recommendation_record.created_by IS NOT NULL
       AND recommendation_record.created_by = context_record.actor_id THEN
        RAISE EXCEPTION 'Recommendation creator cannot review their own draft'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision = 'approve'
       AND NOT EXISTS (
           SELECT 1 FROM public.delphi_diversity_assessment AS assessment
            WHERE assessment.study_id = recommendation_record.study_id
       ) THEN
        RAISE EXCEPTION 'Recommendation approval requires a diversity assessment'
            USING ERRCODE = '55000';
    END IF;
    IF requested_decision = 'approve'
       AND EXISTS (
           SELECT 1 FROM public.delphi_minority_report AS report
            WHERE report.study_id = recommendation_record.study_id
              AND report.status IN ('draft', 'submitted')
       ) THEN
        RAISE EXCEPTION 'Recommendation approval requires minority-report review'
            USING ERRCODE = '55000';
    END IF;

    resulting_status_value := CASE
        WHEN requested_decision = 'approve' THEN 'approved' ELSE 'rejected' END;
    UPDATE public.delphi_recommendation AS recommendation
       SET status = resulting_status_value,
           approved_by = context_record.actor_id,
           approved_at = clock_timestamp()
     WHERE recommendation.id = requested_recommendation_id;

    inserted_decision_id := gen_random_uuid();
    INSERT INTO public.delphi_recommendation_review_decision (
        id, reviewer_id, request_id, location_id, recommendation_id,
        decision, reason_code, resulting_status
    ) VALUES (
        inserted_decision_id, context_record.actor_id, requested_request_id,
        requested_location_id, requested_recommendation_id,
        requested_decision, requested_reason_code, resulting_status_value
    ) RETURNING public.delphi_recommendation_review_decision.created_at
      INTO decided_at_value;

    review_id := inserted_decision_id;
    recommendation_id := requested_recommendation_id;
    study_id := recommendation_record.study_id;
    decision := requested_decision;
    resulting_status := resulting_status_value;
    decided_at := decided_at_value;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_delphi_recommendation_reviewer;
ALTER FUNCTION kokonut_security.list_location_delphi_recommendation_reviews(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_delphi_recommendation_reviewer;
ALTER FUNCTION kokonut_security.decide_location_delphi_recommendation(UUID, UUID, TEXT, UUID, TEXT)
    OWNER TO kokonut_delphi_recommendation_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_delphi_recommendation_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_recommendation_reviews(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.decide_location_delphi_recommendation(UUID, UUID, TEXT, UUID, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_delphi_recommendation_reviews(UUID, INTEGER, INTEGER),
            kokonut_security.decide_location_delphi_recommendation(UUID, UUID, TEXT, UUID, TEXT)
            TO kokonut_runtime;
        REVOKE ALL ON TABLE public.delphi_recommendation_review_decision FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.delphi_recommendation_review_decision FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_recommendation_reviews(UUID, INTEGER, INTEGER),
            kokonut_security.decide_location_delphi_recommendation(UUID, UUID, TEXT, UUID, TEXT)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.delphi_recommendation_review_decision IS
    'Private immutable operator audit for location-scoped human review of facilitator drafts; contains reason codes, never free-text participant feedback.';
COMMENT ON FUNCTION kokonut_security.list_location_delphi_recommendation_reviews(UUID, INTEGER, INTEGER) IS
    'Lists bounded location-owned draft recommendations to a signed Delphi reviewer and annotates self-review, missing diversity, and pending minority-report gates.';
COMMENT ON FUNCTION kokonut_security.decide_location_delphi_recommendation(UUID, UUID, TEXT, UUID, TEXT) IS
    'Records an idempotent location-scoped human approval or rejection; rejects self-review and enforces existing diversity/minority-report approval gates. Approval does not expose recommendation text publicly.';

COMMIT;
