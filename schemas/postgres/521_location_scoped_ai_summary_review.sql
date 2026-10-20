-- Human review of agent-created location summaries. Approval verifies the
-- draft only; publication remains a separate governed action.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_ai_summary_reviewer'
    ) THEN
        CREATE ROLE kokonut_ai_summary_reviewer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_ai_summary_reviewer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'AI summary reviewer role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_ai_summary_reviewer'
            OR member_role.rolname = 'kokonut_ai_summary_reviewer'
    ) THEN
        RAISE EXCEPTION 'AI summary reviewer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.ai_summary_review_decision (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    reviewer_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    summary_id UUID NOT NULL UNIQUE REFERENCES public.ai_summary(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
    reason_code TEXT NOT NULL CHECK (reason_code IN (
        'approved_after_review', 'insufficient_evidence', 'privacy_concern',
        'unsupported_claim', 'other'
    )),
    resulting_status TEXT NOT NULL CHECK (resulting_status IN ('verified', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (reviewer_id, request_id),
    CHECK ((decision = 'approve' AND reason_code = 'approved_after_review'
            AND resulting_status = 'verified')
        OR (decision = 'reject' AND reason_code <> 'approved_after_review'
            AND resulting_status = 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_ai_summary_review_location
    ON public.ai_summary_review_decision(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_ai_summary_review_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'AI summary review history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_summary_review_immutable
    ON public.ai_summary_review_decision;
CREATE TRIGGER trg_ai_summary_review_immutable
    BEFORE UPDATE OR DELETE ON public.ai_summary_review_decision
    FOR EACH ROW EXECUTE FUNCTION public.prevent_ai_summary_review_mutation();

CREATE OR REPLACE FUNCTION kokonut_security.list_location_ai_summary_reviews(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 51,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    summary_id UUID,
    summary_type TEXT,
    content TEXT,
    content_truncated BOOLEAN,
    source_tables TEXT[],
    model_version TEXT,
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
        RAISE EXCEPTION 'AI summary review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'ai_summary', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'AI summary review requires an active review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'AI summary review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT summary.id,
           summary.summary_type::TEXT,
           pg_catalog.left(summary.content, 20000),
           pg_catalog.length(summary.content) > 20000,
           summary.source_tables,
           summary.model_version,
           summary.created_at,
           pg_catalog.cardinality(blockers.reasons) = 0,
           blockers.reasons
      FROM public.ai_summary AS summary
      CROSS JOIN LATERAL (
          SELECT pg_catalog.array_remove(ARRAY[
              CASE WHEN NULLIF(pg_catalog.btrim(summary.content), '') IS NULL
                   THEN 'empty_content'::TEXT END,
              CASE WHEN COALESCE(pg_catalog.cardinality(summary.source_tables), 0) = 0
                   THEN 'missing_source_lineage'::TEXT END,
              CASE WHEN pg_catalog.length(summary.content) > 20000
                   THEN 'content_exceeds_review_limit'::TEXT END
          ], NULL) AS reasons
      ) AS blockers
     WHERE summary.subject_type = 'location'
       AND summary.subject_id = requested_location_id
       AND summary.status IN ('draft', 'submitted')
       AND summary.created_by IS NULL
     ORDER BY summary.created_at ASC, summary.id ASC
     LIMIT requested_limit
    OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.decide_location_ai_summary_review(
    requested_location_id UUID,
    requested_summary_id UUID,
    requested_decision TEXT,
    requested_request_id UUID,
    requested_reason_code TEXT
)
RETURNS TABLE (
    review_id UUID,
    summary_id UUID,
    decision TEXT,
    resulting_status TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    summary_record RECORD;
    existing_record RECORD;
    next_status TEXT;
    new_review_id UUID;
    reviewed_at_value TIMESTAMPTZ := pg_catalog.clock_timestamp();
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'AI summary review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'ai_summary', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'AI summary review requires an active review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_summary_id IS NULL OR requested_request_id IS NULL
       OR requested_decision IS NULL OR requested_reason_code IS NULL
       OR requested_decision NOT IN ('approve', 'reject')
       OR (requested_decision = 'approve'
           AND requested_reason_code IS DISTINCT FROM 'approved_after_review')
       OR (requested_decision = 'reject'
           AND requested_reason_code NOT IN (
               'insufficient_evidence', 'privacy_concern', 'unsupported_claim', 'other'
           )) THEN
        RAISE EXCEPTION 'AI summary review decision is invalid'
            USING ERRCODE = '22023';
    END IF;
    next_status := CASE WHEN requested_decision = 'approve' THEN 'verified' ELSE 'rejected' END;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT decision_row.id, decision_row.location_id, decision_row.summary_id,
           decision_row.decision, decision_row.reason_code, decision_row.resulting_status,
           decision_row.created_at
      INTO existing_record
      FROM public.ai_summary_review_decision AS decision_row
     WHERE decision_row.reviewer_id = context_record.actor_id
       AND decision_row.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_record.location_id IS DISTINCT FROM requested_location_id
           OR existing_record.summary_id IS DISTINCT FROM requested_summary_id
           OR existing_record.decision IS DISTINCT FROM requested_decision
           OR existing_record.reason_code IS DISTINCT FROM requested_reason_code THEN
            RAISE EXCEPTION 'AI summary review request identifier was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT existing_record.id, existing_record.summary_id,
                            existing_record.decision, existing_record.resulting_status,
                            existing_record.created_at;
        RETURN;
    END IF;

    SELECT summary.id, summary.subject_type, summary.subject_id, summary.status,
           summary.content, summary.source_tables, summary.created_by
      INTO summary_record
      FROM public.ai_summary AS summary
     WHERE summary.id = requested_summary_id
     FOR UPDATE;
    IF NOT FOUND
       OR summary_record.subject_type IS DISTINCT FROM 'location'
       OR summary_record.subject_id IS DISTINCT FROM requested_location_id
       OR summary_record.created_by IS NOT NULL
       OR summary_record.status NOT IN ('draft', 'submitted') THEN
        RAISE EXCEPTION 'AI summary is not currently reviewable in this location'
            USING ERRCODE = '55000';
    END IF;
    IF requested_decision = 'approve'
       AND (NULLIF(pg_catalog.btrim(summary_record.content), '') IS NULL
            OR COALESCE(pg_catalog.cardinality(summary_record.source_tables), 0) = 0
            OR pg_catalog.length(summary_record.content) > 20000) THEN
        RAISE EXCEPTION 'AI summary has unresolved review blockers'
            USING ERRCODE = '55000';
    END IF;

    PERFORM pg_catalog.set_config('kokonut.actor_id', context_record.actor_id::TEXT, true);
    PERFORM pg_catalog.set_config('kokonut.actor_type', 'operator', true);
    UPDATE public.ai_summary
       SET status = next_status,
           reviewed_by = context_record.actor_id,
           reviewed_at = reviewed_at_value
     WHERE id = requested_summary_id;

    INSERT INTO public.ai_summary_review_decision (
        reviewer_id, request_id, location_id, summary_id,
        decision, reason_code, resulting_status, created_at
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_summary_id, requested_decision, requested_reason_code,
        next_status, reviewed_at_value
    ) RETURNING id INTO new_review_id;

    RETURN QUERY SELECT new_review_id, requested_summary_id, requested_decision,
                        next_status, reviewed_at_value;
END;
$$;

REVOKE ALL ON TABLE public.ai_summary_review_decision FROM PUBLIC;
REVOKE ALL ON FUNCTION public.prevent_ai_summary_review_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_ai_summary_reviews(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.decide_location_ai_summary_review(UUID, UUID, TEXT, UUID, TEXT)
    FROM PUBLIC;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_ai_summary_reviewer;
GRANT SELECT ON TABLE public.operator_scope_grant TO kokonut_ai_summary_reviewer;
GRANT SELECT (id, subject_type, subject_id, summary_type, content, source_tables,
              model_version, status, created_at, created_by)
    ON TABLE public.ai_summary TO kokonut_ai_summary_reviewer;
GRANT UPDATE (status, reviewed_by, reviewed_at)
    ON TABLE public.ai_summary TO kokonut_ai_summary_reviewer;
GRANT SELECT, INSERT ON TABLE public.ai_summary_review_decision
    TO kokonut_ai_summary_reviewer;
GRANT INSERT ON TABLE public.lifecycle_transition
    TO kokonut_ai_summary_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_ai_summary_reviewer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_ai_summary_reviewer;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_ai_summary_reviewer;
ALTER FUNCTION kokonut_security.list_location_ai_summary_reviews(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_ai_summary_reviewer;
ALTER FUNCTION kokonut_security.decide_location_ai_summary_review(UUID, UUID, TEXT, UUID, TEXT)
    OWNER TO kokonut_ai_summary_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_ai_summary_reviewer;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_ai_summary_reviews(UUID, INTEGER, INTEGER),
            kokonut_security.decide_location_ai_summary_review(UUID, UUID, TEXT, UUID, TEXT)
            TO kokonut_runtime;
        REVOKE ALL ON TABLE public.ai_summary_review_decision FROM kokonut_runtime;
        REVOKE UPDATE ON TABLE public.ai_summary FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'directus') THEN
        REVOKE ALL ON TABLE public.ai_summary_review_decision FROM directus;
        REVOKE UPDATE ON TABLE public.ai_summary FROM directus;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_ai_summary_reviews(UUID, INTEGER, INTEGER)
            FROM directus;
        REVOKE ALL ON FUNCTION kokonut_security.decide_location_ai_summary_review(UUID, UUID, TEXT, UUID, TEXT)
            FROM directus;
    END IF;
END;
$$;

COMMENT ON TABLE public.ai_summary_review_decision IS
'Append-only human decisions for location-scoped AI summary drafts. Approval verifies a draft only and never publishes it.';
COMMENT ON FUNCTION kokonut_security.list_location_ai_summary_reviews(UUID, INTEGER, INTEGER) IS
'Returns bounded, exact-location, unattributed AI summary drafts for an operator with a signed ai_summary:review grant. Content is capped and marked when truncated.';
COMMENT ON FUNCTION kokonut_security.decide_location_ai_summary_review(UUID, UUID, TEXT, UUID, TEXT) IS
'Records an idempotent human approval/rejection under signed exact-location ai_summary:review context. Approval sets verified, never published, and is lifecycle-audited.';

COMMIT;
