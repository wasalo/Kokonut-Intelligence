-- Private, location-scoped human review for submitted Delphi minority reports.
-- Consent withdrawal hides a report from the review surface pending disposition.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_recommendation_reviewer'
           AND NOT rolcanlogin AND NOT rolsuper AND NOT rolcreatedb
           AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
           AND NOT rolinherit
    ) THEN
        RAISE EXCEPTION 'Delphi review function owner is missing or has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_delphi_recommendation_reviewer'
            OR member_role.rolname = 'kokonut_delphi_recommendation_reviewer'
    ) THEN
        RAISE EXCEPTION 'Delphi review function owner must not have role memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.delphi_minority_report_review_decision (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    reviewer_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    report_id UUID NOT NULL UNIQUE REFERENCES public.delphi_minority_report(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('verified', 'rejected')),
    reason_code TEXT NOT NULL CHECK (reason_code IN (
        'evidence_considered', 'out_of_scope', 'privacy_concern',
        'insufficient_evidence', 'other'
    )),
    resulting_status TEXT NOT NULL CHECK (resulting_status IN ('verified', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (reviewer_id, request_id),
    CHECK ((decision = 'verified' AND reason_code = 'evidence_considered'
            AND resulting_status = 'verified')
        OR (decision = 'rejected' AND reason_code <> 'evidence_considered'
            AND resulting_status = 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_delphi_minority_review_location
    ON public.delphi_minority_report_review_decision(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_delphi_minority_report_review_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi minority-report review history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_minority_report_review_immutable
    ON public.delphi_minority_report_review_decision;
CREATE TRIGGER trg_delphi_minority_report_review_immutable
    BEFORE UPDATE OR DELETE ON public.delphi_minority_report_review_decision
    FOR EACH ROW EXECUTE FUNCTION public.prevent_delphi_minority_report_review_mutation();

REVOKE ALL ON TABLE public.delphi_minority_report_review_decision FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_delphi_recommendation_reviewer;
GRANT SELECT ON TABLE public.delphi_study, public.delphi_item,
    public.delphi_panel_member, public.delphi_minority_report,
    public.operator_scope_grant
    TO kokonut_delphi_recommendation_reviewer;
GRANT UPDATE (id) ON TABLE public.delphi_study, public.delphi_panel_member
    TO kokonut_delphi_recommendation_reviewer;
GRANT UPDATE (status, verified_by, verified_at, verification_notes, updated_at)
    ON TABLE public.delphi_minority_report
    TO kokonut_delphi_recommendation_reviewer;
GRANT SELECT, INSERT ON TABLE public.delphi_minority_report_review_decision
    TO kokonut_delphi_recommendation_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_delphi_recommendation_reviewer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_delphi_recommendation_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_delphi_minority_reports(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 51,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    report_id UUID,
    study_id UUID,
    study_title TEXT,
    item_id UUID,
    item_label TEXT,
    report_title TEXT,
    position_summary TEXT,
    rationale TEXT,
    implications TEXT,
    submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ
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
        RAISE EXCEPTION 'Delphi minority-report review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi minority-report review requires an active review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Delphi minority-report review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT report.id,
           study.id,
           study.title::TEXT,
           item.id,
           item.label::TEXT,
           report.title::TEXT,
           report.position_summary::TEXT,
           report.rationale::TEXT,
           report.implications::TEXT,
           report.submitted_at,
           report.created_at
      FROM public.delphi_minority_report AS report
      JOIN public.delphi_study AS study ON study.id = report.study_id
      JOIN public.delphi_panel_member AS member
        ON member.id = report.created_by_panel_member_id
       AND member.study_id = report.study_id
      LEFT JOIN public.delphi_item AS item
        ON item.id = report.item_id
       AND item.study_id = report.study_id
     WHERE study.location_id = requested_location_id
       AND report.status = 'submitted'
       AND member.consent_status = 'granted'
     ORDER BY report.submitted_at, report.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.decide_location_delphi_minority_report(
    requested_location_id UUID,
    requested_report_id UUID,
    requested_decision TEXT,
    requested_request_id UUID,
    requested_reason_code TEXT
)
RETURNS TABLE (
    review_id UUID,
    report_id UUID,
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
    prior_decision public.delphi_minority_report_review_decision%ROWTYPE;
    report_record RECORD;
    inserted_decision_id UUID;
    decided_at_value TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Delphi minority-report decision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi minority-report decision requires an active review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_report_id IS NULL OR requested_request_id IS NULL
       OR requested_decision IS NULL OR requested_reason_code IS NULL
       OR requested_decision NOT IN ('verified', 'rejected')
       OR requested_reason_code NOT IN (
           'evidence_considered', 'out_of_scope', 'privacy_concern',
           'insufficient_evidence', 'other'
       )
       OR (requested_decision = 'verified'
           AND requested_reason_code <> 'evidence_considered')
       OR (requested_decision = 'rejected'
           AND requested_reason_code = 'evidence_considered') THEN
        RAISE EXCEPTION 'Delphi minority-report decision payload is invalid'
            USING ERRCODE = '22023';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT decision_row.* INTO prior_decision
      FROM public.delphi_minority_report_review_decision AS decision_row
     WHERE decision_row.reviewer_id = context_record.actor_id
       AND decision_row.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_decision.location_id IS DISTINCT FROM requested_location_id
           OR prior_decision.report_id IS DISTINCT FROM requested_report_id
           OR prior_decision.decision IS DISTINCT FROM requested_decision
           OR prior_decision.reason_code IS DISTINCT FROM requested_reason_code THEN
            RAISE EXCEPTION 'Delphi minority-report request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        review_id := prior_decision.id;
        report_id := prior_decision.report_id;
        study_id := prior_decision.study_id;
        decision := prior_decision.decision;
        resulting_status := prior_decision.resulting_status;
        decided_at := prior_decision.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT report.id, report.study_id, report.status,
           study.location_id, member.consent_status
      INTO report_record
      FROM public.delphi_minority_report AS report
      JOIN public.delphi_study AS study ON study.id = report.study_id
      JOIN public.delphi_panel_member AS member
        ON member.id = report.created_by_panel_member_id
       AND member.study_id = report.study_id
     WHERE report.id = requested_report_id
       AND study.location_id = requested_location_id
     FOR UPDATE OF report, study, member;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi minority report is unavailable in this location'
            USING ERRCODE = '22023';
    END IF;
    IF report_record.consent_status IS DISTINCT FROM 'granted' THEN
        RAISE EXCEPTION 'Delphi minority report requires participant disposition after withdrawal'
            USING ERRCODE = '55000';
    END IF;
    IF report_record.status IS DISTINCT FROM 'submitted' THEN
        RAISE EXCEPTION 'Delphi minority report is not currently reviewable'
            USING ERRCODE = '55000';
    END IF;

    UPDATE public.delphi_minority_report AS report
       SET status = requested_decision,
           verified_by = CASE
               WHEN requested_decision = 'verified' THEN context_record.actor_id
               ELSE NULL
           END,
           verified_at = CASE
               WHEN requested_decision = 'verified' THEN pg_catalog.clock_timestamp()
               ELSE NULL
           END,
           verification_notes = requested_reason_code,
           updated_at = pg_catalog.clock_timestamp()
     WHERE report.id = requested_report_id;

    inserted_decision_id := pg_catalog.gen_random_uuid();
    INSERT INTO public.delphi_minority_report_review_decision (
        id, reviewer_id, request_id, location_id, report_id, study_id,
        decision, reason_code, resulting_status
    ) VALUES (
        inserted_decision_id, context_record.actor_id, requested_request_id,
        requested_location_id, requested_report_id, report_record.study_id,
        requested_decision, requested_reason_code, requested_decision
    ) RETURNING public.delphi_minority_report_review_decision.created_at
      INTO decided_at_value;

    review_id := inserted_decision_id;
    report_id := requested_report_id;
    study_id := report_record.study_id;
    decision := requested_decision;
    resulting_status := requested_decision;
    decided_at := decided_at_value;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_delphi_recommendation_reviewer;
ALTER FUNCTION kokonut_security.list_location_delphi_minority_reports(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_delphi_recommendation_reviewer;
ALTER FUNCTION kokonut_security.decide_location_delphi_minority_report(UUID, UUID, TEXT, UUID, TEXT)
    OWNER TO kokonut_delphi_recommendation_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_delphi_recommendation_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_minority_reports(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.decide_location_delphi_minority_report(UUID, UUID, TEXT, UUID, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_delphi_minority_reports(UUID, INTEGER, INTEGER),
            kokonut_security.decide_location_delphi_minority_report(UUID, UUID, TEXT, UUID, TEXT)
            TO kokonut_runtime;
        REVOKE ALL ON TABLE public.delphi_minority_report_review_decision
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.delphi_minority_report_review_decision
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_minority_reports(UUID, INTEGER, INTEGER),
            kokonut_security.decide_location_delphi_minority_report(UUID, UUID, TEXT, UUID, TEXT)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.delphi_minority_report_review_decision IS
'Private append-only operator disposition history for location-scoped Delphi minority reports; it does not publish report content.';
COMMENT ON FUNCTION kokonut_security.list_location_delphi_minority_reports(UUID, INTEGER, INTEGER) IS
'Returns bounded submitted minority report content only for the exact granted location and only while the pseudonymous participant has active consent; withdrawn and unlinked records are hidden pending disposition.';
COMMENT ON FUNCTION kokonut_security.decide_location_delphi_minority_report(UUID, UUID, TEXT, UUID, TEXT) IS
'Records one idempotent verified/rejected operator disposition for a submitted report with active participant consent; this does not publish the report.';

COMMIT;
