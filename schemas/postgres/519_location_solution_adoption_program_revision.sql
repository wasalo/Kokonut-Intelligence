-- Preserve reviewed adoption-program redesigns and link each revised draft.

BEGIN;

CREATE TABLE IF NOT EXISTS public.solution_adoption_program_revision (
    revision_program_id UUID PRIMARY KEY
        REFERENCES public.solution_adoption_program(id) ON DELETE RESTRICT,
    prior_program_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_adoption_program(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    revision_number INTEGER NOT NULL CHECK (revision_number >= 2),
    created_by_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL,
    CHECK (revision_program_id <> prior_program_id)
);

ALTER TABLE public.solution_adoption_program_revision
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_adoption_program_revision
    FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_adoption_program_revision_manager
    ON public.solution_adoption_program_revision;
CREATE POLICY solution_adoption_program_revision_manager
    ON public.solution_adoption_program_revision
    TO kokonut_solution_adoption_program_manager
    USING (CURRENT_USER = 'kokonut_solution_adoption_program_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_program_manager');
REVOKE ALL ON TABLE public.solution_adoption_program_revision
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_adoption_program_manager;

CREATE TABLE IF NOT EXISTS public.solution_adoption_program_revision_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    prior_program_id UUID NOT NULL
        REFERENCES public.solution_adoption_program(id) ON DELETE RESTRICT,
    revision_program_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_adoption_program(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    revision_number INTEGER NOT NULL CHECK (revision_number >= 2),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

ALTER TABLE public.solution_adoption_program_revision_receipt
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_adoption_program_revision_receipt
    FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_adoption_program_revision_receipt_manager
    ON public.solution_adoption_program_revision_receipt;
CREATE POLICY solution_adoption_program_revision_receipt_manager
    ON public.solution_adoption_program_revision_receipt
    TO kokonut_solution_adoption_program_manager
    USING (CURRENT_USER = 'kokonut_solution_adoption_program_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_program_manager');
REVOKE ALL ON TABLE public.solution_adoption_program_revision_receipt
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_adoption_program_manager;

GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage,
              status, name)
    ON TABLE public.solution TO kokonut_solution_adoption_program_manager;
GRANT SELECT (id, solution_id, target_scope_type, target_scope_id, status,
              created_by_party_id, created_at, adoption_pathway,
              local_adaptation_policy, submitted_by_party_id, submitted_at,
              current_submission_id)
    ON TABLE public.solution_adoption_program
    TO kokonut_solution_adoption_program_manager;
GRANT INSERT (solution_id, target_scope_type, target_scope_id, target_population,
              adoption_pathway, local_adaptation_policy, status, created_by_party_id)
    ON TABLE public.solution_adoption_program
    TO kokonut_solution_adoption_program_manager;
GRANT INSERT (revision_program_id, prior_program_id, solution_id, location_id,
              revision_number, created_by_party_id, created_at),
      SELECT (revision_program_id, prior_program_id, solution_id, location_id,
              revision_number, created_by_party_id, created_at)
    ON TABLE public.solution_adoption_program_revision
    TO kokonut_solution_adoption_program_manager;
GRANT SELECT (operator_id, actor_party_id, location_id, solution_id,
              prior_program_id, revision_program_id, request_id, payload_digest,
              revision_number, created_at),
      INSERT (operator_id, actor_party_id, location_id, solution_id,
              prior_program_id, revision_program_id, request_id, payload_digest,
              revision_number, created_at)
    ON TABLE public.solution_adoption_program_revision_receipt
    TO kokonut_solution_adoption_program_manager;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_adoption_program_redesigns(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    program_id UUID,
    solution_id UUID,
    solution_name TEXT,
    adoption_pathway TEXT,
    local_adaptation_policy TEXT,
    next_revision_number INTEGER,
    reviewed_at TIMESTAMPTZ
)
LANGUAGE plpgsql
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
        RAISE EXCEPTION 'Adoption program revision listing requires signed location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Adoption program revision listing requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Adoption program revision page is invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT program.id, program.solution_id, solution.name::TEXT,
           program.adoption_pathway, program.local_adaptation_policy,
           COALESCE(revision.revision_number, 1) + 1,
           review.reviewed_at
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
      JOIN public.solution_adoption_program_review_receipt AS review
        ON review.program_id = program.id
       AND review.submission_id = program.current_submission_id
       AND review.decision = 'redesign'
      LEFT JOIN public.solution_adoption_program_revision AS revision
        ON revision.revision_program_id = program.id
     WHERE program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
       AND program.status = 'redesign'
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.status = 'active'
       AND solution.current_stage IN ('pilot_active', 'adoption_ready', 'adopting')
       AND NOT EXISTS (
            SELECT 1
              FROM public.solution_adoption_program_revision AS child
             WHERE child.prior_program_id = program.id
       )
     ORDER BY review.reviewed_at DESC, program.id
     LIMIT requested_limit + 1 OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.revise_location_solution_adoption_program(
    requested_location_id UUID,
    requested_prior_program_id UUID,
    requested_request_id UUID,
    requested_adoption_pathway TEXT,
    requested_local_adaptation_policy TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    program_id UUID,
    prior_program_id UUID,
    solution_id UUID,
    revision_number INTEGER,
    program_status TEXT,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    prior_program RECORD;
    prior_revision_number INTEGER;
    next_revision_number INTEGER;
    prior_receipt RECORD;
    payload_digest BYTEA;
    created_program_id UUID;
    created_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Adoption program revision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Adoption program revision requires an active exact location create grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_prior_program_id IS NULL OR requested_request_id IS NULL
       OR requested_adoption_pathway IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_adoption_pathway)) NOT BETWEEN 1 AND 2000
       OR pg_catalog.octet_length(pg_catalog.convert_to(requested_adoption_pathway, 'UTF8')) > 4000
       OR requested_local_adaptation_policy IS NOT NULL
          AND (pg_catalog.length(requested_local_adaptation_policy) > 4000
               OR pg_catalog.octet_length(pg_catalog.convert_to(requested_local_adaptation_policy, 'UTF8')) > 8000)
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Adoption program revision input is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id
      INTO actor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id
       AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, actor;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Adoption program revision requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'prior_program_id', requested_prior_program_id,
                'adoption_pathway', pg_catalog.btrim(requested_adoption_pathway),
                'local_adaptation_policy', NULLIF(pg_catalog.btrim(requested_local_adaptation_policy), ''),
                'acknowledged', requested_acknowledged
            )::TEXT,
            'UTF8'
        ), 'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.actor_party_id, receipt.location_id, receipt.solution_id,
           receipt.prior_program_id, receipt.revision_program_id,
           receipt.payload_digest, receipt.revision_number, receipt.created_at
      INTO prior_receipt
      FROM public.solution_adoption_program_revision_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.prior_program_id IS DISTINCT FROM requested_prior_program_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Adoption program revision request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_receipt.revision_program_id,
            prior_receipt.prior_program_id, prior_receipt.solution_id,
            prior_receipt.revision_number, 'draft'::TEXT,
            prior_receipt.created_at, TRUE;
        RETURN;
    END IF;

    SELECT program.id, program.solution_id, program.target_scope_type,
           program.target_scope_id, program.status, program.current_submission_id,
           solution.originating_scope_type, solution.originating_scope_id,
           solution.current_stage, solution.status AS solution_status,
           COALESCE(revision.revision_number, 1) AS prior_revision_number
      INTO prior_program
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
      LEFT JOIN public.solution_adoption_program_revision AS revision
        ON revision.revision_program_id = program.id
     WHERE program.id = requested_prior_program_id
       AND program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR UPDATE OF program;
    IF prior_program.id IS NULL THEN
        RAISE EXCEPTION 'Exact-location redesigned adoption program not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF prior_program.status <> 'redesign'
       OR NOT EXISTS (
            SELECT 1
              FROM public.solution_adoption_program_review_receipt AS review
             WHERE review.program_id = prior_program.id
               AND review.submission_id = prior_program.current_submission_id
               AND review.solution_id = prior_program.solution_id
               AND review.location_id = requested_location_id
               AND review.decision = 'redesign'
       ) THEN
        RAISE EXCEPTION 'Only a reviewed redesign decision can start a program revision'
            USING ERRCODE = '55000';
    END IF;
    IF prior_program.solution_status <> 'active'
       OR prior_program.current_stage NOT IN ('pilot_active', 'adoption_ready', 'adopting') THEN
        RAISE EXCEPTION 'The source solution is no longer eligible for a program revision'
            USING ERRCODE = '55000';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.solution_adoption_program_revision AS child
         WHERE child.prior_program_id = prior_program.id
    ) THEN
        RAISE EXCEPTION 'A newer adoption-program revision already exists'
            USING ERRCODE = '55000';
    END IF;
    next_revision_number := prior_program.prior_revision_number + 1;

    INSERT INTO public.solution_adoption_program AS created_program (
        solution_id, target_scope_type, target_scope_id, target_population,
        adoption_pathway, local_adaptation_policy, status, created_by_party_id
    ) VALUES (
        prior_program.solution_id, 'location', requested_location_id, '{}'::JSONB,
        pg_catalog.btrim(requested_adoption_pathway),
        NULLIF(pg_catalog.btrim(requested_local_adaptation_policy), ''),
        'draft', actor_party_id
    ) RETURNING created_program.id, created_program.created_at
      INTO created_program_id, created_time;

    INSERT INTO public.solution_adoption_program_revision (
        revision_program_id, prior_program_id, solution_id, location_id,
        revision_number, created_by_party_id, created_at
    ) VALUES (
        created_program_id, prior_program.id, prior_program.solution_id,
        requested_location_id, next_revision_number, actor_party_id, created_time
    );
    INSERT INTO public.solution_adoption_program_revision_receipt (
        operator_id, actor_party_id, location_id, solution_id, prior_program_id,
        revision_program_id, request_id, payload_digest, revision_number, created_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        prior_program.solution_id, prior_program.id, created_program_id,
        requested_request_id, payload_digest, next_revision_number, created_time
    );

    RETURN QUERY SELECT created_program_id, prior_program.id,
        prior_program.solution_id, next_revision_number, 'draft'::TEXT,
        created_time, FALSE;
END;
$$;

ALTER FUNCTION kokonut_security.location_solution_adoption_program_redesigns(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_adoption_program_manager;
ALTER FUNCTION kokonut_security.revise_location_solution_adoption_program(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
    OWNER TO kokonut_solution_adoption_program_manager;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_adoption_program_redesigns(UUID, INTEGER, INTEGER),
    kokonut_security.revise_location_solution_adoption_program(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
    FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.location_solution_adoption_program_redesigns(UUID, INTEGER, INTEGER),
            kokonut_security.revise_location_solution_adoption_program(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_solution_adoption_program_redesigns(UUID, INTEGER, INTEGER),
            kokonut_security.revise_location_solution_adoption_program(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_adoption_program_revision IS
    'Private immutable lineage between a reviewed redesign decision and its replacement adoption-program draft.';
COMMENT ON TABLE public.solution_adoption_program_revision_receipt IS
    'Private immutable idempotency receipts for exact-location adoption-program revisions.';
COMMENT ON FUNCTION kokonut_security.revise_location_solution_adoption_program(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN) IS
    'Creates a new exact-location draft only from an independently reviewed redesign decision; preserves the prior program and creates a non-branching revision link.';

COMMIT;
