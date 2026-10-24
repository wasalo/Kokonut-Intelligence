-- Location-scoped Kernel creation for facilitator recommendation drafts.
-- Drafting never approves or publishes recommendation text.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_recommendation_drafter'
    ) THEN
        CREATE ROLE kokonut_delphi_recommendation_drafter
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_delphi_recommendation_drafter'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Delphi recommendation drafter role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_delphi_recommendation_drafter'
            OR member_role.rolname = 'kokonut_delphi_recommendation_drafter'
    ) THEN
        RAISE EXCEPTION 'Delphi recommendation drafter role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.delphi_recommendation_draft_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    study_id UUID NOT NULL REFERENCES public.delphi_study(id) ON DELETE RESTRICT,
    recommendation_id UUID NOT NULL UNIQUE
        REFERENCES public.delphi_recommendation(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (created_by, request_id)
);

CREATE INDEX IF NOT EXISTS idx_delphi_draft_request_location
    ON public.delphi_recommendation_draft_request(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_delphi_recommendation_draft_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Delphi recommendation draft request history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_delphi_recommendation_draft_request_immutable
    ON public.delphi_recommendation_draft_request;
CREATE TRIGGER trg_delphi_recommendation_draft_request_immutable
    BEFORE UPDATE OR DELETE ON public.delphi_recommendation_draft_request
    FOR EACH ROW EXECUTE FUNCTION public.prevent_delphi_recommendation_draft_request_mutation();

REVOKE ALL ON TABLE public.delphi_recommendation_draft_request FROM PUBLIC;
REVOKE ALL ON FUNCTION public.prevent_delphi_recommendation_draft_request_mutation()
    FROM PUBLIC;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_delphi_recommendation_drafter;
GRANT SELECT ON TABLE public.delphi_study, public.operator_scope_grant,
    public.delphi_recommendation
    TO kokonut_delphi_recommendation_drafter;
GRANT INSERT (id, study_id, summary, recommendation_text, status, created_by)
    ON TABLE public.delphi_recommendation
    TO kokonut_delphi_recommendation_drafter;
-- PostgreSQL requires a narrow UPDATE privilege to lock study eligibility
-- while the security-definer function creates its draft.
GRANT UPDATE (id) ON TABLE public.delphi_study
    TO kokonut_delphi_recommendation_drafter;
GRANT SELECT, INSERT ON TABLE public.delphi_recommendation_draft_request
    TO kokonut_delphi_recommendation_drafter;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_delphi_recommendation_drafter;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_delphi_recommendation_drafter;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_delphi_draftable_studies(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 50,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    study_id UUID,
    title TEXT,
    status TEXT,
    updated_at TIMESTAMPTZ
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
        RAISE EXCEPTION 'Delphi draft study list requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'draft', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi draft study list requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Delphi draft study page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT study.id, study.title::TEXT, study.status::TEXT, study.updated_at
      FROM public.delphi_study AS study
     WHERE study.location_id = requested_location_id
       AND study.status IN ('open', 'closed')
     ORDER BY study.updated_at DESC NULLS LAST, study.id DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_delphi_recommendation_draft(
    requested_location_id UUID,
    requested_study_id UUID,
    requested_request_id UUID,
    requested_summary TEXT,
    requested_recommendation_text TEXT
)
RETURNS TABLE (
    recommendation_id UUID,
    study_id UUID,
    status TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    prior_record RECORD;
    study_status_value TEXT;
    created_recommendation_id UUID;
    created_at_value TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Delphi draft creation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'delphi', 'draft', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Delphi draft creation requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_study_id IS NULL OR requested_request_id IS NULL
       OR requested_recommendation_text IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_recommendation_text)) = 0
       OR pg_catalog.length(requested_recommendation_text) > 20000
       OR (requested_summary IS NOT NULL AND pg_catalog.length(requested_summary) > 4000) THEN
        RAISE EXCEPTION 'Delphi recommendation draft payload is invalid'
            USING ERRCODE = '22023';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT recommendation.id, recommendation.study_id,
           recommendation.summary, recommendation.recommendation_text,
           recommendation.status, recommendation.created_at,
           draft_request.location_id
      INTO prior_record
      FROM public.delphi_recommendation_draft_request AS draft_request
      JOIN public.delphi_recommendation AS recommendation
        ON recommendation.id = draft_request.recommendation_id
     WHERE draft_request.created_by = context_record.actor_id
       AND draft_request.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_record.location_id IS DISTINCT FROM requested_location_id
           OR prior_record.study_id IS DISTINCT FROM requested_study_id
           OR prior_record.summary IS DISTINCT FROM requested_summary
           OR prior_record.recommendation_text IS DISTINCT FROM requested_recommendation_text THEN
            RAISE EXCEPTION 'Delphi draft request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        recommendation_id := prior_record.id;
        study_id := prior_record.study_id;
        status := prior_record.status;
        created_at := prior_record.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT study.status::TEXT INTO study_status_value
      FROM public.delphi_study AS study
     WHERE study.id = requested_study_id
       AND study.location_id = requested_location_id
     FOR UPDATE OF study;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Delphi study is unavailable in this location'
            USING ERRCODE = '22023';
    END IF;
    IF study_status_value NOT IN ('open', 'closed') THEN
        RAISE EXCEPTION 'Delphi recommendation drafts require an open or closed study'
            USING ERRCODE = '55000';
    END IF;

    INSERT INTO public.delphi_recommendation (
        id, study_id, summary, recommendation_text, status, created_by
    ) VALUES (
        pg_catalog.gen_random_uuid(), requested_study_id, requested_summary,
        requested_recommendation_text, 'draft', context_record.actor_id
    )
    RETURNING public.delphi_recommendation.id,
              public.delphi_recommendation.created_at
         INTO created_recommendation_id, created_at_value;

    INSERT INTO public.delphi_recommendation_draft_request (
        created_by, request_id, location_id, study_id, recommendation_id
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_study_id, created_recommendation_id
    );

    recommendation_id := created_recommendation_id;
    study_id := requested_study_id;
    status := 'draft';
    created_at := created_at_value;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_delphi_recommendation_drafter;
ALTER FUNCTION kokonut_security.list_location_delphi_draftable_studies(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_delphi_recommendation_drafter;
ALTER FUNCTION kokonut_security.create_location_delphi_recommendation_draft(UUID, UUID, UUID, TEXT, TEXT)
    OWNER TO kokonut_delphi_recommendation_drafter;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_delphi_recommendation_drafter;
REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_draftable_studies(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.create_location_delphi_recommendation_draft(UUID, UUID, UUID, TEXT, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_delphi_draftable_studies(UUID, INTEGER, INTEGER),
            kokonut_security.create_location_delphi_recommendation_draft(UUID, UUID, UUID, TEXT, TEXT)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.delphi_recommendation_draft_request
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_delphi_draftable_studies(UUID, INTEGER, INTEGER),
            kokonut_security.create_location_delphi_recommendation_draft(UUID, UUID, UUID, TEXT, TEXT)
            FROM kokonut_directus_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE public.delphi_recommendation_draft_request
            FROM kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_delphi_draftable_studies(UUID, INTEGER, INTEGER) IS
    'Lists bounded open or closed Delphi studies only to an operator with a signed location-scoped delphi:draft grant.';
COMMENT ON FUNCTION kokonut_security.create_location_delphi_recommendation_draft(UUID, UUID, UUID, TEXT, TEXT) IS
    'Creates an idempotent, location-scoped draft recommendation for an open or closed study. It never approves or publishes draft text.';
COMMENT ON TABLE public.delphi_recommendation_draft_request IS
    'Private append-only idempotency ledger for Gateway-created location-scoped Delphi drafts; contains request identity and row references, not draft text.';

COMMIT;
