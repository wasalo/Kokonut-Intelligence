-- Attribute Gateway-created AI-summary drafts to the authenticated operator,
-- make draft creation idempotent, and prevent an operator from reviewing their
-- own attributed draft. Legacy unattributed drafts remain rejectable, but can
-- never be verified until they have trustworthy creator attribution.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_ai_summary_drafter'
    ) THEN
        CREATE ROLE kokonut_ai_summary_drafter
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_ai_summary_drafter'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'AI summary drafter role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_ai_summary_drafter'
            OR member_role.rolname = 'kokonut_ai_summary_drafter'
    ) THEN
        RAISE EXCEPTION 'AI summary drafter role must not have memberships';
    END IF;
END;
$$;

-- Agent-authored summaries stay draft-only until an independent human review
-- is recorded. A verified summary may later be published through its separate
-- governed path while retaining that review attribution.
ALTER TABLE public.ai_summary
    DROP CONSTRAINT IF EXISTS chk_ai_summary_agent_draft_only;
ALTER TABLE public.ai_summary
    ADD CONSTRAINT chk_ai_summary_agent_draft_only CHECK (
        created_by IS NULL
        OR status IN ('draft', 'submitted', 'rejected')
        OR (
            status IN ('verified', 'published')
            AND reviewed_by IS NOT NULL
            AND reviewed_by <> created_by
            AND reviewed_at IS NOT NULL
        )
    ) NOT VALID;
ALTER TABLE public.ai_summary
    VALIDATE CONSTRAINT chk_ai_summary_agent_draft_only;

CREATE TABLE IF NOT EXISTS public.ai_summary_draft_request (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    summary_type TEXT NOT NULL CHECK (summary_type IN (
        'operations', 'financial', 'environmental', 'combined'
    )),
    request_hash TEXT NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
    summary_id UUID NOT NULL UNIQUE REFERENCES public.ai_summary(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

CREATE OR REPLACE FUNCTION public.prevent_ai_summary_draft_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'AI summary draft request history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_summary_draft_request_immutable
    ON public.ai_summary_draft_request;
CREATE TRIGGER trg_ai_summary_draft_request_immutable
    BEFORE UPDATE OR DELETE ON public.ai_summary_draft_request
    FOR EACH ROW EXECUTE FUNCTION public.prevent_ai_summary_draft_request_mutation();

CREATE OR REPLACE FUNCTION kokonut_security.get_location_ai_summary_draft_request(
    requested_location_id UUID,
    requested_summary_type TEXT,
    requested_request_id UUID
)
RETURNS TABLE (
    summary_id UUID,
    content TEXT,
    source_tables TEXT[],
    model_version TEXT,
    created_at TIMESTAMPTZ,
    resulting_status TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    existing_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'AI summary draft requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'ai_summary', 'draft', requested_location_id
    ) THEN
        RAISE EXCEPTION 'AI summary draft requires an active draft grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_request_id IS NULL
       OR requested_summary_type IS NULL
       OR requested_summary_type NOT IN ('operations', 'financial', 'environmental', 'combined') THEN
        RAISE EXCEPTION 'AI summary draft request is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT draft_request.location_id, draft_request.summary_type,
           summary.id, summary.content::TEXT, summary.source_tables,
           summary.model_version::TEXT, summary.created_at,
           summary.status::TEXT
      INTO existing_record
      FROM public.ai_summary_draft_request AS draft_request
      JOIN public.ai_summary AS summary ON summary.id = draft_request.summary_id
     WHERE draft_request.operator_id = context_record.actor_id
       AND draft_request.request_id = requested_request_id;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    IF existing_record.location_id IS DISTINCT FROM requested_location_id
       OR existing_record.summary_type IS DISTINCT FROM requested_summary_type THEN
        RAISE EXCEPTION 'AI summary draft request identifier was reused for another intent'
            USING ERRCODE = '22023';
    END IF;
    RETURN QUERY SELECT existing_record.id, existing_record.content,
                        existing_record.source_tables, existing_record.model_version,
                        existing_record.created_at, existing_record.status;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_ai_summary_draft(
    requested_location_id UUID,
    requested_summary_type TEXT,
    requested_content TEXT,
    requested_source_tables TEXT[],
    requested_request_id UUID
)
RETURNS TABLE (
    summary_id UUID,
    content TEXT,
    source_tables TEXT[],
    model_version TEXT,
    created_at TIMESTAMPTZ,
    resulting_status TEXT,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    existing_record RECORD;
    new_summary_id UUID;
    request_intent_hash TEXT;
    created_at_value TIMESTAMPTZ := pg_catalog.clock_timestamp();
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'AI summary draft requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'ai_summary', 'draft', requested_location_id
    ) THEN
        RAISE EXCEPTION 'AI summary draft requires an active draft grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_request_id IS NULL
       OR requested_summary_type IS NULL
       OR requested_summary_type NOT IN ('operations', 'financial', 'environmental', 'combined')
       OR requested_content IS NULL
       OR NULLIF(pg_catalog.btrim(requested_content), '') IS NULL
       OR pg_catalog.length(requested_content) > 20000
       OR requested_source_tables IS NULL
       OR pg_catalog.cardinality(requested_source_tables) NOT BETWEEN 1 AND 20
       OR EXISTS (
            SELECT 1 FROM pg_catalog.unnest(requested_source_tables) AS source_rows(source_table)
             WHERE source_table IS NULL OR source_table !~ '^[a-z][a-z0-9_]{0,62}$'
       ) THEN
        RAISE EXCEPTION 'AI summary draft payload is invalid'
            USING ERRCODE = '22023';
    END IF;

    request_intent_hash := pg_catalog.encode(public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(requested_location_id, requested_summary_type)::TEXT,
            'UTF8'
        ),
        'sha256'
    ), 'hex');
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT draft_request.id, draft_request.location_id, draft_request.summary_type,
           draft_request.request_hash, draft_request.summary_id
      INTO existing_record
      FROM public.ai_summary_draft_request AS draft_request
     WHERE draft_request.operator_id = context_record.actor_id
       AND draft_request.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_record.location_id IS DISTINCT FROM requested_location_id
           OR existing_record.summary_type IS DISTINCT FROM requested_summary_type
           OR existing_record.request_hash IS DISTINCT FROM request_intent_hash THEN
            RAISE EXCEPTION 'AI summary draft request identifier was reused for another intent'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY
        SELECT summary.id, summary.content::TEXT, summary.source_tables,
               summary.model_version::TEXT, summary.created_at,
               summary.status::TEXT, TRUE
          FROM public.ai_summary AS summary
         WHERE summary.id = existing_record.summary_id;
        RETURN;
    END IF;

    INSERT INTO public.ai_summary (
        subject_type, subject_id, summary_type, content, source_tables,
        model_version, status, created_by, created_at
    ) VALUES (
        'location', requested_location_id, requested_summary_type,
        requested_content, requested_source_tables, 'rules-v1', 'draft',
        context_record.actor_id, created_at_value
    ) RETURNING id INTO new_summary_id;

    INSERT INTO public.ai_summary_draft_request (
        operator_id, request_id, location_id, summary_type, request_hash,
        summary_id, created_at
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_summary_type, request_intent_hash, new_summary_id, created_at_value
    );

    RETURN QUERY SELECT new_summary_id, requested_content, requested_source_tables,
                        'rules-v1'::TEXT, created_at_value, 'draft'::TEXT, FALSE;
END;
$$;

-- The review queue now distinguishes self-review and legacy rows that lack a
-- reliable requester identity. No legacy row is auto-attributed.
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
                   THEN 'content_exceeds_review_limit'::TEXT END,
              CASE WHEN summary.created_by IS NULL
                   THEN 'creator_unattributed'::TEXT END,
              CASE WHEN summary.created_by = context_record.actor_id
                   THEN 'self_review'::TEXT END
          ], NULL) AS reasons
      ) AS blockers
     WHERE summary.subject_type = 'location'
       AND summary.subject_id = requested_location_id
       AND summary.status IN ('draft', 'submitted')
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
       OR summary_record.status NOT IN ('draft', 'submitted') THEN
        RAISE EXCEPTION 'AI summary is not currently reviewable in this location'
            USING ERRCODE = '55000';
    END IF;
    IF summary_record.created_by = context_record.actor_id THEN
        RAISE EXCEPTION 'The requester cannot review their own AI summary'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision = 'approve'
       AND (summary_record.created_by IS NULL
            OR NULLIF(pg_catalog.btrim(summary_record.content), '') IS NULL
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

REVOKE ALL ON TABLE public.ai_summary_draft_request FROM PUBLIC;
REVOKE ALL ON FUNCTION public.prevent_ai_summary_draft_request_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_ai_summary_draft_request(UUID, TEXT, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.create_location_ai_summary_draft(UUID, TEXT, TEXT, TEXT[], UUID)
    FROM PUBLIC;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_ai_summary_drafter;
GRANT SELECT ON TABLE public.operator_scope_grant TO kokonut_ai_summary_drafter;
GRANT SELECT (id, subject_type, subject_id, summary_type, content, source_tables,
              model_version, status, created_at, created_by)
    ON TABLE public.ai_summary TO kokonut_ai_summary_drafter;
GRANT INSERT (subject_type, subject_id, summary_type, content, source_tables,
              model_version, status, created_by, created_at)
    ON TABLE public.ai_summary TO kokonut_ai_summary_drafter;
GRANT SELECT, INSERT ON TABLE public.ai_summary_draft_request
    TO kokonut_ai_summary_drafter;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_ai_summary_drafter;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_ai_summary_drafter;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_ai_summary_drafter;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_ai_summary_drafter;
ALTER FUNCTION kokonut_security.create_location_ai_summary_draft(UUID, TEXT, TEXT, TEXT[], UUID)
    OWNER TO kokonut_ai_summary_drafter;
ALTER FUNCTION kokonut_security.get_location_ai_summary_draft_request(UUID, TEXT, UUID)
    OWNER TO kokonut_ai_summary_drafter;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_ai_summary_drafter;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_ai_summary_draft(
            UUID, TEXT, TEXT, TEXT[], UUID
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.get_location_ai_summary_draft_request(
            UUID, TEXT, UUID
        ) TO kokonut_runtime;
        REVOKE ALL ON TABLE public.ai_summary_draft_request FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'directus') THEN
        REVOKE ALL ON TABLE public.ai_summary_draft_request FROM directus;
        REVOKE ALL ON FUNCTION kokonut_security.create_location_ai_summary_draft(
            UUID, TEXT, TEXT, TEXT[], UUID
        ) FROM directus;
        REVOKE ALL ON FUNCTION kokonut_security.get_location_ai_summary_draft_request(
            UUID, TEXT, UUID
        ) FROM directus;
    END IF;
END;
$$;

COMMENT ON TABLE public.ai_summary_draft_request IS
'Private immutable idempotency receipts for OIDC operator-requested AI summary drafts.';
COMMENT ON FUNCTION kokonut_security.create_location_ai_summary_draft(UUID, TEXT, TEXT, TEXT[], UUID) IS
'Creates an AI summary draft with authenticated operator attribution under signed exact-location ai_summary:draft context; exact retries return the original draft.';
COMMENT ON FUNCTION kokonut_security.get_location_ai_summary_draft_request(UUID, TEXT, UUID) IS
'Returns a previously created operator AI-summary draft for an exact request intent before regeneration, under signed exact-location ai_summary:draft context.';

COMMIT;
