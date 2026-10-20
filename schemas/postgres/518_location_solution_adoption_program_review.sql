-- Add exact-location submission and independent review for adoption programs.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_adoption_program_manager'
    ) THEN
        CREATE ROLE kokonut_solution_adoption_program_manager
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_adoption_program_manager'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Adoption program manager role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_adoption_program_manager'
            OR member_role.rolname = 'kokonut_solution_adoption_program_manager'
    ) THEN
        RAISE EXCEPTION 'Adoption program manager role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_adoption_program_submission_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    program_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_adoption_program(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    submitted_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS public.solution_adoption_program_review_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    proposer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    submitter_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    program_id UUID NOT NULL REFERENCES public.solution_adoption_program(id) ON DELETE RESTRICT,
    submission_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_adoption_program_submission_receipt(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('enablement_ready', 'redesign')),
    review_note TEXT NOT NULL CHECK (pg_catalog.length(review_note) BETWEEN 1 AND 2000),
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    reviewed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id),
    CHECK (reviewer_party_id <> proposer_party_id),
    CHECK (reviewer_party_id <> submitter_party_id)
);

ALTER TABLE public.solution_adoption_program
    ADD COLUMN IF NOT EXISTS submitted_by_party_id UUID REFERENCES public.party(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS current_submission_id UUID;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.solution_adoption_program'::regclass
           AND conname = 'solution_adoption_program_current_submission_fk'
    ) THEN
        ALTER TABLE public.solution_adoption_program
            ADD CONSTRAINT solution_adoption_program_current_submission_fk
            FOREIGN KEY (current_submission_id)
            REFERENCES public.solution_adoption_program_submission_receipt(id)
            ON DELETE RESTRICT;
    END IF;
END;
$$;

ALTER TABLE public.solution_adoption_program_submission_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_adoption_program_submission_receipt FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_adoption_program_manager_submission
    ON public.solution_adoption_program_submission_receipt;
CREATE POLICY solution_adoption_program_manager_submission
    ON public.solution_adoption_program_submission_receipt
    TO kokonut_solution_adoption_program_manager
    USING (CURRENT_USER = 'kokonut_solution_adoption_program_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_program_manager');

ALTER TABLE public.solution_adoption_program_review_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_adoption_program_review_receipt FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_adoption_program_manager_review
    ON public.solution_adoption_program_review_receipt;
CREATE POLICY solution_adoption_program_manager_review
    ON public.solution_adoption_program_review_receipt
    TO kokonut_solution_adoption_program_manager
    USING (CURRENT_USER = 'kokonut_solution_adoption_program_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_program_manager');

REVOKE ALL ON TABLE public.solution_adoption_program_submission_receipt,
    public.solution_adoption_program_review_receipt FROM PUBLIC,
    kokonut_runtime, kokonut_directus_runtime,
    kokonut_solution_adoption_program_manager;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE
    ON TABLE public.solution_adoption_program FROM PUBLIC,
    kokonut_runtime, kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION public.enforce_location_adoption_program_review()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'draft' OR NEW.submitted_by_party_id IS NOT NULL
           OR NEW.submitted_at IS NOT NULL OR NEW.current_submission_id IS NOT NULL THEN
            RAISE EXCEPTION 'Adoption programs must begin as unsubmitted drafts'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.status IS NOT DISTINCT FROM OLD.status
       AND (NEW.submitted_by_party_id IS DISTINCT FROM OLD.submitted_by_party_id
            OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at
            OR NEW.current_submission_id IS DISTINCT FROM OLD.current_submission_id) THEN
        RAISE EXCEPTION 'Adoption program submission metadata is immutable outside its lifecycle transition'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'draft' AND NEW.status = 'community_review' THEN
            IF NEW.target_scope_type IS DISTINCT FROM 'location'
               OR NEW.current_submission_id IS NULL
               OR NEW.submitted_by_party_id IS NULL OR NEW.submitted_at IS NULL
               OR NOT EXISTS (
                    SELECT 1
                      FROM public.solution_adoption_program_submission_receipt AS receipt
                     WHERE receipt.id = NEW.current_submission_id
                       AND receipt.program_id = NEW.id
                       AND receipt.solution_id = NEW.solution_id
                       AND receipt.location_id = NEW.target_scope_id
                       AND receipt.actor_party_id = NEW.submitted_by_party_id
                       AND receipt.submitted_at = NEW.submitted_at
               ) THEN
                RAISE EXCEPTION 'Community review requires a matching submission receipt'
                    USING ERRCODE = '23514';
            END IF;
        ELSIF OLD.status = 'community_review'
          AND NEW.status IN ('enablement_ready', 'redesign') THEN
            IF NEW.current_submission_id IS NULL
               OR NOT EXISTS (
                    SELECT 1
                      FROM public.solution_adoption_program_review_receipt AS review
                     WHERE review.program_id = NEW.id
                       AND review.submission_id = NEW.current_submission_id
                       AND review.solution_id = NEW.solution_id
                       AND review.location_id = NEW.target_scope_id
                       AND review.decision = NEW.status
               ) THEN
                RAISE EXCEPTION 'Adoption program decision requires a matching independent review receipt'
                    USING ERRCODE = '23514';
            END IF;
        ELSE
            RAISE EXCEPTION 'Adoption program review transition is not allowed'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_location_adoption_program_review
    ON public.solution_adoption_program;
CREATE TRIGGER trg_location_adoption_program_review
    BEFORE INSERT OR UPDATE OF status, submitted_by_party_id, submitted_at,
        current_submission_id
    ON public.solution_adoption_program
    FOR EACH ROW EXECUTE FUNCTION public.enforce_location_adoption_program_review();

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_adoption_program_manager;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_adoption_program_manager;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_adoption_program_manager;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_adoption_program_manager;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_adoption_program_manager;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_adoption_program_manager;

GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage, status, name)
    ON TABLE public.solution TO kokonut_solution_adoption_program_manager;
GRANT UPDATE (id) ON TABLE public.solution TO kokonut_solution_adoption_program_manager;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_adoption_program_manager;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_adoption_program_manager;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_adoption_program_manager;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (id, solution_id, target_scope_type, target_scope_id, status,
              created_by_party_id, created_at, adoption_pathway,
              local_adaptation_policy, submitted_by_party_id, submitted_at,
              current_submission_id)
    ON TABLE public.solution_adoption_program
    TO kokonut_solution_adoption_program_manager;
GRANT UPDATE (id) ON TABLE public.solution_adoption_program
    TO kokonut_solution_adoption_program_manager;
GRANT UPDATE (status, submitted_by_party_id, submitted_at, current_submission_id)
    ON TABLE public.solution_adoption_program
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (id, operator_id, actor_party_id, location_id, solution_id,
              program_id, request_id, payload_digest, submitted_at)
    ON TABLE public.solution_adoption_program_submission_receipt
    TO kokonut_solution_adoption_program_manager;
GRANT INSERT (operator_id, actor_party_id, location_id, solution_id, program_id,
              request_id, payload_digest, submitted_at)
    ON TABLE public.solution_adoption_program_submission_receipt
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (id, operator_id, reviewer_party_id, proposer_party_id,
              submitter_party_id, location_id, solution_id, program_id,
              submission_id, decision, review_note, request_id,
              payload_digest, reviewed_at)
    ON TABLE public.solution_adoption_program_review_receipt
    TO kokonut_solution_adoption_program_manager;
GRANT INSERT (operator_id, reviewer_party_id, proposer_party_id,
              submitter_party_id, location_id, solution_id, program_id,
              submission_id, decision, review_note, request_id,
              payload_digest, reviewed_at)
    ON TABLE public.solution_adoption_program_review_receipt
    TO kokonut_solution_adoption_program_manager;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_adoption_program_manager;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_adoption_program_manager;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_adoption_program_manager;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_solution_adoption_program(
    requested_location_id UUID,
    requested_program_id UUID,
    requested_request_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (program_id UUID, solution_id UUID, program_status TEXT,
               submitted_at TIMESTAMPTZ, replayed BOOLEAN)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    program_record RECORD;
    prior_receipt RECORD;
    digest_value BYTEA;
    submit_time TIMESTAMPTZ;
    submission_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Adoption program submission requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'submit', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Adoption program submission requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_program_id IS NULL OR requested_request_id IS NULL
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Adoption program submission input is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id INTO actor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, actor;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Adoption program submission requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    digest_value := public.digest(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object('location_id', requested_location_id,
            'program_id', requested_program_id, 'acknowledged', requested_acknowledged)::TEXT,
        'UTF8'), 'sha256');
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0));
    SELECT receipt.id, receipt.actor_party_id, receipt.location_id,
           receipt.solution_id, receipt.program_id, receipt.payload_digest,
           receipt.submitted_at
      INTO prior_receipt
      FROM public.solution_adoption_program_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.program_id IS DISTINCT FROM requested_program_id
           OR prior_receipt.payload_digest IS DISTINCT FROM digest_value THEN
            RAISE EXCEPTION 'Adoption submission request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_receipt.program_id, prior_receipt.solution_id,
                            'community_review'::TEXT, prior_receipt.submitted_at, TRUE;
        RETURN;
    END IF;

    SELECT program.id, program.solution_id, program.status,
           program.target_scope_type, program.target_scope_id,
           program.created_by_party_id, solution.originating_scope_type,
           solution.originating_scope_id, solution.current_stage, solution.status AS solution_status
      INTO program_record
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
     WHERE program.id = requested_program_id
       AND program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
     FOR UPDATE OF program, solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location adoption program was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF program_record.status IS DISTINCT FROM 'draft'
       OR program_record.created_by_party_id IS DISTINCT FROM actor_party_id
       OR program_record.originating_scope_type IS DISTINCT FROM 'location'
       OR program_record.originating_scope_id IS DISTINCT FROM requested_location_id
       OR program_record.solution_status IS DISTINCT FROM 'active'
       OR program_record.current_stage NOT IN ('pilot_active', 'adoption_ready', 'adopting') THEN
        RAISE EXCEPTION 'Only the active location solution draft creator may submit this program'
            USING ERRCODE = '55000';
    END IF;

    submit_time := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_adoption_program_submission_receipt (
        operator_id, actor_party_id, location_id, solution_id, program_id,
        request_id, payload_digest, submitted_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        program_record.solution_id, requested_program_id,
        requested_request_id, digest_value, submit_time
    ) RETURNING id INTO submission_id;
    UPDATE public.solution_adoption_program AS program
       SET status = 'community_review', submitted_by_party_id = actor_party_id,
           submitted_at = submit_time, current_submission_id = submission_id
     WHERE program.id = requested_program_id;
    RETURN QUERY SELECT requested_program_id, program_record.solution_id,
                        'community_review'::TEXT, submit_time, FALSE;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_adoption_program_drafts(
    requested_location_id UUID, requested_limit INTEGER, requested_offset INTEGER
)
RETURNS TABLE (program_id UUID, solution_id UUID, solution_name TEXT,
               program_status TEXT, adoption_pathway TEXT,
               local_adaptation_policy TEXT, created_at TIMESTAMPTZ)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR NOT public.operator_scope_grant_allows(
          context_record.actor_id, 'solution_lifecycle', 'submit', requested_location_id
       ) THEN
        RAISE EXCEPTION 'Adoption program draft listing requires signed location submit scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Adoption program draft page bounds are invalid' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.operator_governance_party_binding AS binding
        JOIN public.operator_identity AS operator
          ON operator.id = binding.operator_id AND operator.enabled
        JOIN public.party AS actor ON actor.id = binding.party_id
         AND actor.party_type = 'person' AND actor.status = 'active'
        WHERE binding.operator_id = context_record.actor_id AND binding.revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Adoption program draft listing requires active human identity'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT program.id, program.solution_id, pg_catalog.left(solution.name, 255)::TEXT,
           program.status::TEXT, pg_catalog.left(program.adoption_pathway, 2000)::TEXT,
           pg_catalog.left(program.local_adaptation_policy, 4000)::TEXT, program.created_at
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
      JOIN public.operator_governance_party_binding AS binding
        ON binding.operator_id = context_record.actor_id AND binding.revoked_at IS NULL
       AND binding.party_id = program.created_by_party_id
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor ON actor.id = binding.party_id
       AND actor.party_type = 'person' AND actor.status = 'active'
     WHERE program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
       AND program.status = 'draft'
     ORDER BY program.created_at DESC, program.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_adoption_program_review_queue(
    requested_location_id UUID, requested_limit INTEGER, requested_offset INTEGER
)
RETURNS TABLE (program_id UUID, solution_id UUID, solution_name TEXT,
               program_status TEXT, adoption_pathway TEXT,
               local_adaptation_policy TEXT, submitted_at TIMESTAMPTZ)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD; reviewer_party_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR NOT public.operator_scope_grant_allows(
          context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
       ) THEN
        RAISE EXCEPTION 'Adoption program review queue requires signed location review scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Adoption program review page bounds are invalid' USING ERRCODE = '22023';
    END IF;
    SELECT binding.party_id INTO reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor ON actor.id = binding.party_id
       AND actor.party_type = 'person' AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id AND binding.revoked_at IS NULL;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Adoption program review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT program.id, program.solution_id, pg_catalog.left(solution.name, 255)::TEXT,
           program.status::TEXT, pg_catalog.left(program.adoption_pathway, 2000)::TEXT,
           pg_catalog.left(program.local_adaptation_policy, 4000)::TEXT, program.submitted_at
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
      JOIN public.solution_adoption_program_submission_receipt AS submission
        ON submission.id = program.current_submission_id
       AND submission.program_id = program.id
     WHERE program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
       AND program.status = 'community_review'
       AND program.created_by_party_id <> reviewer_party_id
       AND program.submitted_by_party_id <> reviewer_party_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.status = 'active'
       AND solution.current_stage IN ('pilot_active', 'adoption_ready', 'adopting')
     ORDER BY program.submitted_at, program.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_solution_adoption_program(
    requested_location_id UUID, requested_program_id UUID, requested_request_id UUID,
    requested_decision TEXT, requested_review_note TEXT, requested_acknowledged BOOLEAN
)
RETURNS TABLE (program_id UUID, solution_id UUID, program_status TEXT,
               decision TEXT, reviewed_at TIMESTAMPTZ, replayed BOOLEAN)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD; reviewer_party_id UUID; program_record RECORD;
        prior_receipt RECORD; digest_value BYTEA; review_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR NOT public.operator_scope_grant_allows(
          context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
       ) THEN
        RAISE EXCEPTION 'Adoption program review requires signed location review scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_program_id IS NULL OR requested_request_id IS NULL
       OR requested_decision NOT IN ('enablement_ready', 'redesign')
       OR requested_review_note IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_review_note)) NOT BETWEEN 1 AND 2000
       OR pg_catalog.octet_length(pg_catalog.convert_to(requested_review_note, 'UTF8')) > 4000
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Adoption program review input is invalid' USING ERRCODE = '22023';
    END IF;
    SELECT binding.party_id INTO reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor ON actor.id = binding.party_id
       AND actor.party_type = 'person' AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, actor;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Adoption program review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    digest_value := public.digest(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object('location_id', requested_location_id,
            'program_id', requested_program_id, 'decision', requested_decision,
            'review_note', pg_catalog.btrim(requested_review_note),
            'acknowledged', requested_acknowledged)::TEXT, 'UTF8'), 'sha256');
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0));
    SELECT review.program_id, review.solution_id, review.location_id,
           review.reviewer_party_id, review.decision, review.review_note,
           review.payload_digest, review.reviewed_at
      INTO prior_receipt
      FROM public.solution_adoption_program_review_receipt AS review
     WHERE review.operator_id = context_record.actor_id
       AND review.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.program_id IS DISTINCT FROM requested_program_id
           OR prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.reviewer_party_id IS DISTINCT FROM reviewer_party_id
           OR prior_receipt.decision IS DISTINCT FROM requested_decision
           OR prior_receipt.review_note IS DISTINCT FROM pg_catalog.btrim(requested_review_note)
           OR prior_receipt.payload_digest IS DISTINCT FROM digest_value THEN
            RAISE EXCEPTION 'Adoption program review request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_receipt.program_id, prior_receipt.solution_id,
                            prior_receipt.decision, prior_receipt.decision,
                            prior_receipt.reviewed_at, TRUE;
        RETURN;
    END IF;

    SELECT program.id, program.solution_id, program.status,
           program.target_scope_type, program.target_scope_id,
           program.created_by_party_id, program.submitted_by_party_id,
           program.current_submission_id, solution.originating_scope_type,
           solution.originating_scope_id, solution.status AS solution_status,
           solution.current_stage
      INTO program_record
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
     WHERE program.id = requested_program_id
       AND program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
     FOR UPDATE OF program, solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location adoption program was not found' USING ERRCODE = 'P0002';
    END IF;
    IF program_record.created_by_party_id = reviewer_party_id
       OR program_record.submitted_by_party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Adoption program proposer or submitter cannot review their own program'
            USING ERRCODE = '42501';
    END IF;
    IF program_record.status IS DISTINCT FROM 'community_review'
       OR program_record.created_by_party_id IS NULL
       OR program_record.submitted_by_party_id IS NULL
       OR program_record.current_submission_id IS NULL
       OR program_record.originating_scope_type IS DISTINCT FROM 'location'
       OR program_record.originating_scope_id IS DISTINCT FROM requested_location_id
       OR program_record.solution_status IS DISTINCT FROM 'active'
       OR program_record.current_stage NOT IN ('pilot_active', 'adoption_ready', 'adopting') THEN
        RAISE EXCEPTION 'Program is not eligible for independent review'
            USING ERRCODE = '55000';
    END IF;
    review_time := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_adoption_program_review_receipt (
        operator_id, reviewer_party_id, proposer_party_id, submitter_party_id,
        location_id, solution_id, program_id, submission_id, decision,
        review_note, request_id, payload_digest, reviewed_at
    ) VALUES (
        context_record.actor_id, reviewer_party_id, program_record.created_by_party_id,
        program_record.submitted_by_party_id, requested_location_id,
        program_record.solution_id, requested_program_id,
        program_record.current_submission_id, requested_decision,
        pg_catalog.btrim(requested_review_note), requested_request_id,
        digest_value, review_time
    );
    UPDATE public.solution_adoption_program AS program
       SET status = requested_decision
     WHERE program.id = requested_program_id;
    RETURN QUERY SELECT requested_program_id, program_record.solution_id,
                        requested_decision, requested_decision, review_time, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA public, kokonut_security
    TO kokonut_solution_adoption_program_manager;
ALTER FUNCTION public.enforce_location_adoption_program_review()
    OWNER TO kokonut_solution_adoption_program_manager;
ALTER FUNCTION kokonut_security.submit_location_solution_adoption_program(UUID, UUID, UUID, BOOLEAN)
    OWNER TO kokonut_solution_adoption_program_manager;
ALTER FUNCTION kokonut_security.location_solution_adoption_program_drafts(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_adoption_program_manager;
ALTER FUNCTION kokonut_security.location_solution_adoption_program_review_queue(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_adoption_program_manager;
ALTER FUNCTION kokonut_security.review_location_solution_adoption_program(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
    OWNER TO kokonut_solution_adoption_program_manager;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_adoption_program_manager;
REVOKE CREATE ON SCHEMA public FROM kokonut_solution_adoption_program_manager;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_adoption_program(UUID, UUID, UUID, BOOLEAN),
    kokonut_security.location_solution_adoption_program_drafts(UUID, INTEGER, INTEGER),
    kokonut_security.location_solution_adoption_program_review_queue(UUID, INTEGER, INTEGER),
    kokonut_security.review_location_solution_adoption_program(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_solution_adoption_program(UUID, UUID, UUID, BOOLEAN),
            kokonut_security.location_solution_adoption_program_drafts(UUID, INTEGER, INTEGER),
            kokonut_security.location_solution_adoption_program_review_queue(UUID, INTEGER, INTEGER),
            kokonut_security.review_location_solution_adoption_program(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_adoption_program(UUID, UUID, UUID, BOOLEAN),
            kokonut_security.location_solution_adoption_program_drafts(UUID, INTEGER, INTEGER),
            kokonut_security.location_solution_adoption_program_review_queue(UUID, INTEGER, INTEGER),
            kokonut_security.review_location_solution_adoption_program(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_adoption_program_submission_receipt IS
    'Private immutable receipts for exact-location human submission of adoption-program drafts; submission enters community_review only.';
COMMENT ON TABLE public.solution_adoption_program_review_receipt IS
    'Private immutable independent decisions on submitted adoption programs; enablement_ready and redesign do not launch adoption.';
COMMENT ON FUNCTION kokonut_security.review_location_solution_adoption_program(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN) IS
    'Records an independent active-human decision on an exact-location submitted adoption program. Approval changes only program status to enablement_ready; readiness, configuration approval, consent, event capture, and lifecycle transition remain separate.';

COMMIT;
