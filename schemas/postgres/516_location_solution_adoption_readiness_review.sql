-- Require an independent, exact-location human review for adoption readiness.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_adoption_readiness_manager'
    ) THEN
        CREATE ROLE kokonut_solution_adoption_readiness_manager
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_adoption_readiness_manager'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Adoption readiness manager role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_adoption_readiness_manager'
            OR member_role.rolname = 'kokonut_solution_adoption_readiness_manager'
    ) THEN
        RAISE EXCEPTION 'Adoption readiness manager role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_adopter_readiness_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    assessor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    readiness_id UUID NOT NULL REFERENCES public.solution_adopter_readiness(id) ON DELETE RESTRICT,
    current_level NUMERIC(6,3) NOT NULL CHECK (current_level >= 0),
    required_level NUMERIC(6,3) NOT NULL CHECK (required_level >= 0),
    remediation_plan TEXT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    assessed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS public.solution_adopter_readiness_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    assessor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    readiness_id UUID NOT NULL REFERENCES public.solution_adopter_readiness(id) ON DELETE RESTRICT,
    assessment_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_adopter_readiness_assessment(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('ready', 'remediating', 'rejected')),
    review_note TEXT NOT NULL CHECK (pg_catalog.length(review_note) BETWEEN 1 AND 2000),
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    reviewed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id),
    CHECK (reviewer_party_id <> assessor_party_id)
);

ALTER TABLE public.solution_adopter_readiness
    ADD COLUMN IF NOT EXISTS current_assessment_id UUID;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.solution_adopter_readiness'::regclass
           AND conname = 'solution_adopter_readiness_current_assessment_fk'
    ) THEN
        ALTER TABLE public.solution_adopter_readiness
            ADD CONSTRAINT solution_adopter_readiness_current_assessment_fk
            FOREIGN KEY (current_assessment_id)
            REFERENCES public.solution_adopter_readiness_assessment(id)
            ON DELETE RESTRICT;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_solution_adopter_readiness_pending_review
    ON public.solution_adopter_readiness(adopter_scope_id, assessed_at DESC, id DESC)
    WHERE readiness_status = 'not_ready' AND current_assessment_id IS NOT NULL;

ALTER TABLE public.solution_adopter_readiness_assessment ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_adopter_readiness_assessment FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_adopter_readiness_manager_assessment
    ON public.solution_adopter_readiness_assessment;
CREATE POLICY solution_adopter_readiness_manager_assessment
    ON public.solution_adopter_readiness_assessment
    TO kokonut_solution_adoption_readiness_manager
    USING (CURRENT_USER = 'kokonut_solution_adoption_readiness_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_readiness_manager');

ALTER TABLE public.solution_adopter_readiness_review ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_adopter_readiness_review FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_adopter_readiness_manager_review
    ON public.solution_adopter_readiness_review;
CREATE POLICY solution_adopter_readiness_manager_review
    ON public.solution_adopter_readiness_review
    TO kokonut_solution_adoption_readiness_manager
    USING (CURRENT_USER = 'kokonut_solution_adoption_readiness_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_readiness_manager');

REVOKE ALL ON TABLE public.solution_adopter_readiness_assessment,
    public.solution_adopter_readiness_review FROM PUBLIC,
    kokonut_runtime, kokonut_directus_runtime,
    kokonut_solution_adoption_readiness_manager;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE
    ON TABLE public.solution_adopter_readiness
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;

-- A previous `ready` value did not prove independent review. Preserve the
-- historical row and its assessor, but require a fresh scoped assessment.
UPDATE public.solution_adopter_readiness
   SET readiness_status = 'expired', current_assessment_id = NULL
 WHERE readiness_status = 'ready';

CREATE OR REPLACE FUNCTION public.enforce_location_solution_readiness_review()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF NEW.readiness_status = 'ready' THEN
        IF NEW.current_assessment_id IS NULL OR NOT EXISTS (
            SELECT 1
              FROM public.solution_adopter_readiness_assessment AS assessment
              JOIN public.solution_adopter_readiness_review AS review
                ON review.assessment_id = assessment.id
               AND review.decision = 'ready'
               AND review.reviewer_party_id <> assessment.assessor_party_id
             WHERE assessment.id = NEW.current_assessment_id
               AND assessment.readiness_id = NEW.id
               AND assessment.solution_id = NEW.solution_id
               AND NEW.adopter_scope_type = 'location'
               AND assessment.location_id = NEW.adopter_scope_id
               AND assessment.assessor_party_id = NEW.assessed_by_party_id
               AND assessment.current_level = NEW.current_level
               AND assessment.required_level = NEW.required_level
               AND assessment.remediation_plan IS NOT DISTINCT FROM NEW.remediation_plan
        ) THEN
            RAISE EXCEPTION 'Readiness cannot be marked ready without independent review of the current assessment'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_solution_adopter_readiness_independent_review
    ON public.solution_adopter_readiness;
CREATE TRIGGER trg_solution_adopter_readiness_independent_review
    BEFORE INSERT OR UPDATE OF readiness_status, current_assessment_id,
        current_level, required_level, remediation_plan, assessed_by_party_id
    ON public.solution_adopter_readiness
    FOR EACH ROW EXECUTE FUNCTION public.enforce_location_solution_readiness_review();

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_adoption_readiness_manager;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_adoption_readiness_manager;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_adoption_readiness_manager;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_adoption_readiness_manager;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_adoption_readiness_manager;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_adoption_readiness_manager;

GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage, status)
    ON TABLE public.solution TO kokonut_solution_adoption_readiness_manager;
GRANT UPDATE (id) ON TABLE public.solution TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_adoption_readiness_manager;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_adoption_readiness_manager;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_adoption_readiness_manager;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (id, solution_id, adopter_scope_type, adopter_scope_id,
              current_level, required_level, readiness_status, assessed_by_party_id,
              assessed_at, remediation_plan, current_assessment_id)
    ON TABLE public.solution_adopter_readiness
    TO kokonut_solution_adoption_readiness_manager;
GRANT UPDATE (id) ON TABLE public.solution_adopter_readiness
    TO kokonut_solution_adoption_readiness_manager;
GRANT INSERT (solution_id, adopter_scope_type, adopter_scope_id, current_level,
              required_level, remediation_plan, readiness_status,
              assessed_by_party_id, assessed_at, current_assessment_id)
    ON TABLE public.solution_adopter_readiness
    TO kokonut_solution_adoption_readiness_manager;
GRANT UPDATE (current_level, required_level, remediation_plan, readiness_status,
              assessed_by_party_id, assessed_at, current_assessment_id)
    ON TABLE public.solution_adopter_readiness
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (id, operator_id, assessor_party_id, location_id, solution_id,
              readiness_id, current_level, required_level, remediation_plan,
              request_id, payload_digest, assessed_at)
    ON TABLE public.solution_adopter_readiness_assessment
    TO kokonut_solution_adoption_readiness_manager;
GRANT INSERT (operator_id, assessor_party_id, location_id, solution_id,
              readiness_id, current_level, required_level, remediation_plan,
              request_id, payload_digest, assessed_at)
    ON TABLE public.solution_adopter_readiness_assessment
    TO kokonut_solution_adoption_readiness_manager;
GRANT SELECT (id, operator_id, reviewer_party_id, assessor_party_id,
              location_id, solution_id, readiness_id, assessment_id, decision, review_note,
              request_id, payload_digest, reviewed_at)
    ON TABLE public.solution_adopter_readiness_review
    TO kokonut_solution_adoption_readiness_manager;
GRANT INSERT (operator_id, reviewer_party_id, assessor_party_id, location_id,
              solution_id, readiness_id, assessment_id, decision, review_note, request_id,
              payload_digest, reviewed_at)
    ON TABLE public.solution_adopter_readiness_review
    TO kokonut_solution_adoption_readiness_manager;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_adoption_readiness_manager;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_adoption_readiness_manager;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_adoption_readiness_manager;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_solution_adopter_readiness(
    requested_location_id UUID,
    requested_solution_id UUID,
    requested_request_id UUID,
    requested_current_level NUMERIC,
    requested_required_level NUMERIC,
    requested_remediation_plan TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    assessment_id UUID,
    readiness_id UUID,
    solution_id UUID,
    current_level NUMERIC,
    required_level NUMERIC,
    readiness_status TEXT,
    assessed_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    assessor_party_id UUID;
    solution_record RECORD;
    prior_assessment RECORD;
    assessment_key UUID;
    readiness_key UUID;
    assessment_time TIMESTAMPTZ;
    payload_digest BYTEA;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Readiness assessment requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Readiness assessment requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_solution_id IS NULL OR requested_request_id IS NULL
       OR requested_current_level IS NULL OR requested_required_level IS NULL
       OR requested_current_level < 0 OR requested_required_level < 0
       OR requested_current_level > 999.999 OR requested_required_level > 999.999
       OR requested_current_level <> pg_catalog.round(requested_current_level, 3)
       OR requested_required_level <> pg_catalog.round(requested_required_level, 3)
       OR requested_remediation_plan IS NOT NULL
          AND (pg_catalog.length(requested_remediation_plan) > 4000
               OR pg_catalog.octet_length(pg_catalog.convert_to(requested_remediation_plan, 'UTF8')) > 8000)
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Readiness assessment input is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id
      INTO assessor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS assessor
        ON assessor.id = binding.party_id
       AND assessor.party_type = 'person'
       AND assessor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, assessor;
    IF assessor_party_id IS NULL THEN
        RAISE EXCEPTION 'Readiness assessment requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'solution_id', requested_solution_id,
            'current_level', requested_current_level,
            'required_level', requested_required_level,
            'remediation_plan', NULLIF(pg_catalog.btrim(requested_remediation_plan), ''),
            'acknowledged', requested_acknowledged
        )::TEXT, 'UTF8'), 'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT assessment.* INTO prior_assessment
      FROM public.solution_adopter_readiness_assessment AS assessment
     WHERE assessment.operator_id = context_record.actor_id
       AND assessment.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_assessment.assessor_party_id IS DISTINCT FROM assessor_party_id
           OR prior_assessment.location_id IS DISTINCT FROM requested_location_id
           OR prior_assessment.solution_id IS DISTINCT FROM requested_solution_id
           OR prior_assessment.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Readiness request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_assessment.id, prior_assessment.readiness_id,
                            prior_assessment.solution_id, prior_assessment.current_level,
                            prior_assessment.required_level, 'submitted'::TEXT,
                            prior_assessment.assessed_at, TRUE;
        RETURN;
    END IF;

    SELECT solution.id INTO solution_record
      FROM public.solution AS solution
     WHERE solution.id = requested_solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.current_stage IN ('pilot_active', 'adoption_ready', 'adopting')
       AND solution.status = 'active'
     FOR UPDATE;
    IF solution_record.id IS NULL THEN
        RAISE EXCEPTION 'Active location-origin solution was not found'
            USING ERRCODE = 'P0002';
    END IF;

    assessment_time := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_adopter_readiness AS readiness (
        solution_id, adopter_scope_type, adopter_scope_id, current_level,
        required_level, remediation_plan, readiness_status, assessed_by_party_id,
        assessed_at, current_assessment_id
    ) VALUES (
        requested_solution_id, 'location', requested_location_id,
        requested_current_level, requested_required_level,
        NULLIF(pg_catalog.btrim(requested_remediation_plan), ''), 'not_ready',
        assessor_party_id, assessment_time, NULL
    ) ON CONFLICT (solution_id, adopter_scope_type, adopter_scope_id)
    DO UPDATE SET current_level = EXCLUDED.current_level,
                  required_level = EXCLUDED.required_level,
                  remediation_plan = EXCLUDED.remediation_plan,
                  readiness_status = 'not_ready',
                  assessed_by_party_id = EXCLUDED.assessed_by_party_id,
                  assessed_at = EXCLUDED.assessed_at,
                  current_assessment_id = EXCLUDED.current_assessment_id
    RETURNING id INTO readiness_key;

    INSERT INTO public.solution_adopter_readiness_assessment (
        operator_id, assessor_party_id, location_id, solution_id, readiness_id,
        current_level, required_level, remediation_plan, request_id,
        payload_digest, assessed_at
    ) VALUES (
        context_record.actor_id, assessor_party_id, requested_location_id,
        requested_solution_id, readiness_key, requested_current_level,
        requested_required_level, NULLIF(pg_catalog.btrim(requested_remediation_plan), ''),
        requested_request_id, payload_digest, assessment_time
    ) RETURNING id INTO assessment_key;
    UPDATE public.solution_adopter_readiness AS readiness
       SET current_assessment_id = assessment_key
     WHERE readiness.id = readiness_key;
    RETURN QUERY SELECT assessment_key, readiness_key, requested_solution_id,
                        requested_current_level, requested_required_level,
                        'submitted'::TEXT, assessment_time, FALSE;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_adopter_readiness_review_queue(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    assessment_id UUID,
    readiness_id UUID,
    solution_id UUID,
    current_level NUMERIC,
    required_level NUMERIC,
    remediation_plan TEXT,
    assessed_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    reviewer_party_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Readiness review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Readiness review queue requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 101
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Readiness review queue page is invalid'
            USING ERRCODE = '22023';
    END IF;
    SELECT binding.party_id INTO reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id
       AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Readiness review queue requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT assessment.id, readiness.id, assessment.solution_id,
           assessment.current_level, assessment.required_level,
           assessment.remediation_plan, assessment.assessed_at
      FROM public.solution_adopter_readiness AS readiness
      JOIN public.solution_adopter_readiness_assessment AS assessment
        ON assessment.id = readiness.current_assessment_id
     WHERE readiness.adopter_scope_type = 'location'
       AND readiness.adopter_scope_id = requested_location_id
       AND readiness.readiness_status = 'not_ready'
       AND assessment.assessor_party_id <> reviewer_party_id
       AND NOT EXISTS (
           SELECT 1 FROM public.solution_adopter_readiness_review AS review
            WHERE review.assessment_id = assessment.id
       )
     ORDER BY assessment.assessed_at DESC, assessment.id DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_solution_adopter_readiness(
    requested_location_id UUID,
    requested_assessment_id UUID,
    requested_request_id UUID,
    requested_decision TEXT,
    requested_review_note TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    assessment_id UUID,
    readiness_id UUID,
    decision TEXT,
    readiness_status TEXT,
    reviewed_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    reviewer_party_id UUID;
    assessment RECORD;
    readiness RECORD;
    prior_review RECORD;
    review_time TIMESTAMPTZ;
    resulting_status TEXT;
    payload_digest BYTEA;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Readiness review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Readiness review requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_assessment_id IS NULL OR requested_request_id IS NULL
       OR requested_decision IS NULL
       OR requested_decision NOT IN ('ready', 'remediating', 'rejected')
       OR requested_review_note IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_review_note)) NOT BETWEEN 1 AND 2000
       OR pg_catalog.octet_length(pg_catalog.convert_to(requested_review_note, 'UTF8')) > 4000
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Readiness review input is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id INTO reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id
       AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, reviewer;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Readiness review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'assessment_id', requested_assessment_id,
            'decision', requested_decision,
            'review_note', pg_catalog.btrim(requested_review_note),
            'acknowledged', requested_acknowledged
        )::TEXT, 'UTF8'), 'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT review.* INTO prior_review
      FROM public.solution_adopter_readiness_review AS review
     WHERE review.operator_id = context_record.actor_id
       AND review.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_review.reviewer_party_id IS DISTINCT FROM reviewer_party_id
           OR prior_review.location_id IS DISTINCT FROM requested_location_id
           OR prior_review.assessment_id IS DISTINCT FROM requested_assessment_id
           OR prior_review.decision IS DISTINCT FROM requested_decision
           OR prior_review.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Readiness review request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_review.assessment_id,
                            prior_review.readiness_id,
                            prior_review.decision,
                            CASE prior_review.decision
                                WHEN 'ready' THEN 'ready'
                                WHEN 'remediating' THEN 'remediating'
                                ELSE 'not_ready'
                            END::TEXT,
                            prior_review.reviewed_at, TRUE;
        RETURN;
    END IF;

    SELECT assessment.* INTO assessment
      FROM public.solution_adopter_readiness_assessment AS assessment
     WHERE assessment.id = requested_assessment_id
       AND assessment.location_id = requested_location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location readiness assessment was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF assessment.assessor_party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Readiness assessment must be reviewed by another active human'
            USING ERRCODE = '42501';
    END IF;
    PERFORM 1
      FROM public.solution AS solution
     WHERE solution.id = assessment.solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.current_stage IN ('pilot_active', 'adoption_ready', 'adopting')
       AND solution.status = 'active'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Readiness solution is no longer active at this location'
            USING ERRCODE = '55000';
    END IF;
    SELECT readiness.* INTO readiness
      FROM public.solution_adopter_readiness AS readiness
     WHERE readiness.id = assessment.readiness_id
     FOR UPDATE;
    IF NOT FOUND OR readiness.current_assessment_id IS DISTINCT FROM assessment.id
       OR readiness.adopter_scope_type <> 'location'
       OR readiness.adopter_scope_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'Readiness assessment is no longer current; refresh the queue'
            USING ERRCODE = '55000';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.solution_adopter_readiness_review AS review
         WHERE review.assessment_id = assessment.id
    ) THEN
        RAISE EXCEPTION 'Readiness assessment already has a final review'
            USING ERRCODE = '55000';
    END IF;
    IF requested_decision = 'ready'
       AND assessment.current_level < assessment.required_level THEN
        RAISE EXCEPTION 'Readiness cannot be approved below its required level'
            USING ERRCODE = '55000';
    END IF;
    IF requested_decision = 'remediating'
       AND NULLIF(pg_catalog.btrim(assessment.remediation_plan), '') IS NULL THEN
        RAISE EXCEPTION 'A remediation plan is required for a remediating decision'
            USING ERRCODE = '55000';
    END IF;

    resulting_status := CASE requested_decision
        WHEN 'ready' THEN 'ready'
        WHEN 'remediating' THEN 'remediating'
        ELSE 'not_ready'
    END;
    review_time := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_adopter_readiness_review (
        operator_id, reviewer_party_id, assessor_party_id, location_id,
        solution_id, readiness_id, assessment_id, decision, review_note, request_id,
        payload_digest, reviewed_at
    ) VALUES (
        context_record.actor_id, reviewer_party_id, assessment.assessor_party_id,
        requested_location_id, assessment.solution_id, assessment.readiness_id, assessment.id,
        requested_decision, pg_catalog.btrim(requested_review_note),
        requested_request_id, payload_digest, review_time
    );
    UPDATE public.solution_adopter_readiness AS current_readiness
       SET readiness_status = resulting_status
     WHERE current_readiness.id = assessment.readiness_id;
    RETURN QUERY SELECT assessment.id, assessment.readiness_id,
                        requested_decision, resulting_status, review_time, FALSE;
END;
$$;

ALTER FUNCTION kokonut_security.submit_location_solution_adopter_readiness(
    UUID, UUID, UUID, NUMERIC, NUMERIC, TEXT, BOOLEAN
) OWNER TO kokonut_solution_adoption_readiness_manager;
ALTER FUNCTION kokonut_security.location_solution_adopter_readiness_review_queue(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_solution_adoption_readiness_manager;
ALTER FUNCTION kokonut_security.review_location_solution_adopter_readiness(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) OWNER TO kokonut_solution_adoption_readiness_manager;

REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_adopter_readiness(
    UUID, UUID, UUID, NUMERIC, NUMERIC, TEXT, BOOLEAN
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_adopter_readiness_review_queue(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.review_location_solution_adopter_readiness(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_solution_adopter_readiness(
            UUID, UUID, UUID, NUMERIC, NUMERIC, TEXT, BOOLEAN
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_solution_adopter_readiness_review_queue(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.review_location_solution_adopter_readiness(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_adopter_readiness(
            UUID, UUID, UUID, NUMERIC, NUMERIC, TEXT, BOOLEAN
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.location_solution_adopter_readiness_review_queue(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.review_location_solution_adopter_readiness(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_adopter_readiness_assessment IS
    'Immutable location-scoped human readiness submissions; a separate active operator must review the exact current assessment before readiness may become ready.';
COMMENT ON TABLE public.solution_adopter_readiness_review IS
    'Private immutable independent readiness decisions. Shared runtime and Directus roles cannot read or mutate review records directly.';
COMMENT ON COLUMN public.solution_adopter_readiness.current_assessment_id IS
    'The latest immutable location-scoped assessment. Every new assessment invalidates prior readiness until independently reviewed.';
COMMENT ON FUNCTION public.enforce_location_solution_readiness_review() IS
    'Prevents readiness from becoming ready without an independent approval of the exact current immutable assessment.';

COMMIT;
