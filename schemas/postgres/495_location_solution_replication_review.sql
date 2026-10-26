-- Private location-scoped review and independent decision for replication proposals.

BEGIN;

ALTER TABLE public.solution_replication
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS review_reason TEXT;

ALTER TABLE public.solution_replication
    DROP CONSTRAINT IF EXISTS solution_replication_status_check;
ALTER TABLE public.solution_replication
    ADD CONSTRAINT solution_replication_status_check
    CHECK (status IN ('proposed', 'approved', 'active', 'completed', 'failed', 'rejected'));
ALTER TABLE public.solution_replication
    DROP CONSTRAINT IF EXISTS solution_replication_review_reason_check;
ALTER TABLE public.solution_replication
    ADD CONSTRAINT solution_replication_review_reason_check
    CHECK (review_reason IS NULL OR pg_catalog.char_length(review_reason) <= 4000);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_replication_reviewer'
    ) THEN
        CREATE ROLE kokonut_solution_replication_reviewer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_replication_reviewer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution replication reviewer role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_replication_reviewer'
            OR member_role.rolname = 'kokonut_solution_replication_reviewer'
    ) THEN
        RAISE EXCEPTION 'Solution replication reviewer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_replication_review_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    replication_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_replication(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    review_reason TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id),
    CHECK (review_reason IS NULL OR pg_catalog.char_length(review_reason) <= 4000)
);

REVOKE ALL ON TABLE public.solution_replication_review_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_replication_review_receipt
    FROM kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_reader, kokonut_solution_replication_proposer;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_replication_reviewer;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_replication_reviewer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_replication_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_replication_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_replication_reviewer;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_replication_reviewer;

GRANT SELECT (id, name, solution_type, current_stage, status,
              originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_replication_reviewer;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (
    id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
    target_context, adaptation_required, replication_protocol, result,
    evidence_maturity, status, reviewed_by_party_id, reviewed_at,
    review_reason, created_at, completed_at
) ON TABLE public.solution_replication TO kokonut_solution_replication_reviewer;
GRANT UPDATE (id, status, reviewed_by_party_id, reviewed_at, review_reason)
    ON TABLE public.solution_replication TO kokonut_solution_replication_reviewer;
GRANT SELECT (
    operator_id, proposer_party_id, location_id, source_experiment_id, replication_id
) ON TABLE public.solution_replication_proposal_receipt
    TO kokonut_solution_replication_reviewer;
GRANT SELECT, INSERT ON TABLE public.solution_replication_review_receipt
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (
    id, solution_id, status, owner_party_id, approved_by_party_id
) ON TABLE public.solution_experiment TO kokonut_solution_replication_reviewer;
GRANT UPDATE (id) ON TABLE public.solution_experiment
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (experiment_id, outcome, reviewed_by_party_id, reviewed_at)
    ON TABLE public.solution_experiment_result
    TO kokonut_solution_replication_reviewer;
GRANT UPDATE (id) ON TABLE public.solution_experiment_result
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_replication_reviewer;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (id, solution_id, entity_type, entity_id)
    ON TABLE public.solution_link TO kokonut_solution_replication_reviewer;
GRANT UPDATE (id) ON TABLE public.solution_link
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_replication_reviewer;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_replication_reviewer;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_solution_replication_reviewer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_replication_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_replication_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_replication_reviewer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_replication_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_replication_review_queue(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    replication_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    solution_stage TEXT,
    source_experiment_validated BOOLEAN,
    source_result_reviewed BOOLEAN,
    created_at TIMESTAMPTZ,
    proposer_attributed BOOLEAN,
    is_self_authored BOOLEAN
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
        RAISE EXCEPTION 'Replication review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Replication review queue requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id
      INTO reviewer_party_id
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
        RAISE EXCEPTION 'Replication review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Replication review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT replication.id,
           pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT,
           solution.current_stage::TEXT,
           experiment.status = 'validated',
           source_result.outcome = 'validated' AND source_result.reviewed_at IS NOT NULL,
           replication.created_at,
           proposal.proposer_party_id IS NOT NULL,
           COALESCE(proposal.proposer_party_id = reviewer_party_id, FALSE)
      FROM public.solution_replication AS replication
      JOIN public.solution AS solution
        ON solution.id = replication.solution_id
       AND solution.status = 'active'
      JOIN public.solution_replication_proposal_receipt AS proposal
        ON proposal.replication_id = replication.id
       AND proposal.location_id = requested_location_id
      JOIN public.solution_experiment AS experiment
        ON experiment.id = proposal.source_experiment_id
      LEFT JOIN public.solution_experiment_result AS source_result
        ON source_result.experiment_id = experiment.id
     WHERE replication.status = 'proposed'
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND (
           (solution.originating_scope_type = 'location'
            AND solution.originating_scope_id = requested_location_id)
           OR EXISTS (
               SELECT 1 FROM public.solution_link AS location_link
                WHERE location_link.solution_id = solution.id
                  AND location_link.entity_type = 'location'
                  AND location_link.entity_id = requested_location_id
           )
       )
     ORDER BY replication.created_at DESC, replication.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_solution_replication_review_detail(
    requested_location_id UUID,
    requested_replication_id UUID
)
RETURNS TABLE (
    replication_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    solution_stage TEXT,
    replication_status TEXT,
    target_context TEXT,
    adaptation_required TEXT,
    replication_protocol JSONB,
    source_experiment_id UUID,
    source_experiment_status TEXT,
    source_result_outcome TEXT,
    source_result_reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    proposer_attributed BOOLEAN,
    is_self_authored BOOLEAN
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
       OR requested_location_id IS NULL
       OR requested_replication_id IS NULL THEN
        RAISE EXCEPTION 'Replication review detail requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Replication review detail requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id
      INTO reviewer_party_id
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
        RAISE EXCEPTION 'Replication review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT replication.id,
           pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT,
           solution.current_stage::TEXT,
           replication.status::TEXT,
           pg_catalog.left(replication.target_context, 2000)::TEXT,
           pg_catalog.left(replication.adaptation_required, 4000)::TEXT,
           CASE WHEN pg_catalog.pg_column_size(replication.replication_protocol) <= 65536
                THEN replication.replication_protocol ELSE '{}'::JSONB END,
           experiment.id,
           experiment.status::TEXT,
           source_result.outcome::TEXT,
           source_result.reviewed_at,
           replication.created_at,
           proposal.proposer_party_id IS NOT NULL,
           COALESCE(proposal.proposer_party_id = reviewer_party_id, FALSE)
      FROM public.solution_replication AS replication
      JOIN public.solution AS solution
        ON solution.id = replication.solution_id
       AND solution.status = 'active'
      JOIN public.solution_replication_proposal_receipt AS proposal
        ON proposal.replication_id = replication.id
       AND proposal.location_id = requested_location_id
      JOIN public.solution_experiment AS experiment
        ON experiment.id = proposal.source_experiment_id
      LEFT JOIN public.solution_experiment_result AS source_result
        ON source_result.experiment_id = experiment.id
     WHERE replication.id = requested_replication_id
       AND replication.status = 'proposed'
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND (
           (solution.originating_scope_type = 'location'
            AND solution.originating_scope_id = requested_location_id)
           OR EXISTS (
               SELECT 1 FROM public.solution_link AS location_link
                WHERE location_link.solution_id = solution.id
                  AND location_link.entity_type = 'location'
                  AND location_link.entity_id = requested_location_id
           )
       );
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_solution_replication(
    requested_location_id UUID,
    requested_replication_id UUID,
    requested_request_id UUID,
    requested_decision TEXT,
    requested_review_reason TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    event_id UUID,
    replication_id UUID,
    decision TEXT,
    reviewed_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    reviewer_party_id UUID;
    proposer_party_id UUID;
    source_solution_id UUID;
    source_origin_type TEXT;
    source_origin_id UUID;
    existing_review RECORD;
    generated_event_id UUID;
    review_timestamp TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_replication_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Replication review requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Replication review requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision IS NULL
       OR requested_decision NOT IN ('approved', 'rejected')
       OR requested_acknowledged IS DISTINCT FROM TRUE
       OR (requested_review_reason IS NOT NULL
           AND (pg_catalog.btrim(requested_review_reason) = ''
                OR pg_catalog.char_length(requested_review_reason) > 4000))
       OR (requested_decision = 'rejected'
           AND (requested_review_reason IS NULL
                OR pg_catalog.char_length(pg_catalog.btrim(requested_review_reason)) < 10)) THEN
        RAISE EXCEPTION 'Replication review decision, reason, or acknowledgement is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id
      INTO reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id
       AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, operator, reviewer;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Replication review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || requested_request_id::TEXT, 0)
    );
    SELECT receipt.id, receipt.location_id, receipt.replication_id,
           receipt.reviewer_party_id, receipt.decision, receipt.review_reason,
           receipt.reviewed_at
      INTO existing_review
      FROM public.solution_replication_review_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_review.location_id IS DISTINCT FROM requested_location_id
           OR existing_review.replication_id IS DISTINCT FROM requested_replication_id
           OR existing_review.reviewer_party_id IS DISTINCT FROM reviewer_party_id
           OR existing_review.decision IS DISTINCT FROM requested_decision
           OR existing_review.review_reason IS DISTINCT FROM requested_review_reason THEN
            RAISE EXCEPTION 'Replication review request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        event_id := existing_review.id;
        replication_id := existing_review.replication_id;
        decision := existing_review.decision;
        reviewed_at := existing_review.reviewed_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT replication.solution_id,
           solution.originating_scope_type,
           solution.originating_scope_id,
           proposal.proposer_party_id
      INTO source_solution_id,
           source_origin_type,
           source_origin_id,
           proposer_party_id
      FROM public.solution_replication AS replication
      JOIN public.solution AS solution
        ON solution.id = replication.solution_id
       AND solution.status = 'active'
      JOIN public.solution_replication_proposal_receipt AS proposal
        ON proposal.replication_id = replication.id
       AND proposal.location_id = requested_location_id
      JOIN public.solution_experiment AS experiment
        ON experiment.id = proposal.source_experiment_id
       AND experiment.status = 'validated'
      JOIN public.solution_experiment_result AS source_result
        ON source_result.experiment_id = experiment.id
       AND source_result.outcome = 'validated'
       AND source_result.reviewed_at IS NOT NULL
      JOIN public.party AS result_reviewer
        ON result_reviewer.id = source_result.reviewed_by_party_id
       AND result_reviewer.party_type = 'person'
       AND result_reviewer.status = 'active'
     WHERE replication.id = requested_replication_id
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND replication.status = 'proposed'
       AND replication.reviewed_by_party_id IS NULL
     FOR UPDATE OF replication, solution, experiment, source_result
     FOR SHARE OF result_reviewer;
    IF source_solution_id IS NULL THEN
        RAISE EXCEPTION 'Pending attributed replication proposal was not found for this location'
            USING ERRCODE = 'P0002';
    END IF;
    IF source_origin_type IS DISTINCT FROM 'location'
       OR source_origin_id IS DISTINCT FROM requested_location_id THEN
        PERFORM 1
          FROM public.solution_link AS location_link
         WHERE location_link.solution_id = source_solution_id
           AND location_link.entity_type = 'location'
           AND location_link.entity_id = requested_location_id
         FOR SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Replication solution is not visible at the exact target location'
                USING ERRCODE = 'P0002';
        END IF;
    END IF;
    IF reviewer_party_id IS NOT DISTINCT FROM proposer_party_id THEN
        RAISE EXCEPTION 'Replication proposer cannot review their own proposal'
            USING ERRCODE = '42501';
    END IF;

    review_timestamp := pg_catalog.clock_timestamp();
    UPDATE public.solution_replication
       SET status = requested_decision,
           reviewed_by_party_id = reviewer_party_id,
           reviewed_at = review_timestamp,
           review_reason = requested_review_reason
     WHERE id = requested_replication_id;

    INSERT INTO public.solution_replication_review_receipt (
        operator_id, reviewer_party_id, location_id, replication_id,
        request_id, decision, review_reason, reviewed_at
    ) VALUES (
        context_record.actor_id, reviewer_party_id, requested_location_id,
        requested_replication_id, requested_request_id, requested_decision,
        requested_review_reason, review_timestamp
    ) RETURNING id INTO generated_event_id;

    event_id := generated_event_id;
    replication_id := requested_replication_id;
    decision := requested_decision;
    reviewed_at := review_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_replication_reviewer;
ALTER FUNCTION kokonut_security.list_location_solution_replication_review_queue(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_replication_reviewer;
ALTER FUNCTION kokonut_security.get_location_solution_replication_review_detail(UUID, UUID)
    OWNER TO kokonut_solution_replication_reviewer;
ALTER FUNCTION kokonut_security.review_location_solution_replication(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
    OWNER TO kokonut_solution_replication_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_replication_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_replication_review_queue(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_replication_review_detail(UUID, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.review_location_solution_replication(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
    FROM PUBLIC;

COMMENT ON TABLE public.solution_replication_review_receipt IS
'Append-only, location-scoped receipt for an independently reviewed replication proposal decision.';
COMMENT ON FUNCTION kokonut_security.list_location_solution_replication_review_queue(UUID, INTEGER, INTEGER) IS
'Returns bounded metadata for proposed replications targeting the exact signed location under solution_lifecycle:review; proposal context and protocol remain hidden until detail review.';
COMMENT ON FUNCTION kokonut_security.get_location_solution_replication_review_detail(UUID, UUID) IS
'Returns private bounded proposal context and protocol only for an attributed proposed replication targeting the exact signed location under solution_lifecycle:review; no outcome or evidence mutation occurs.';
COMMENT ON FUNCTION kokonut_security.review_location_solution_replication(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN) IS
'Records one independently reviewed approve/reject decision for an attributed location replication proposal with an immutable idempotency receipt; it never activates or completes the replication or changes solution stage.';
COMMENT ON FUNCTION kokonut_security.propose_location_solution_replication(UUID, UUID, UUID, TEXT, TEXT, JSONB) IS
'Creates a proposed replication at the exact signed location for an active solution visible by location origin or explicit location link, with a validated independently reviewed source experiment; records OIDC human attribution and an immutable retry receipt without changing lifecycle stage or review state.';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_replication_review_queue(UUID, INTEGER, INTEGER),
            kokonut_security.get_location_solution_replication_review_detail(UUID, UUID),
            kokonut_security.review_location_solution_replication(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
            TO kokonut_runtime;
        REVOKE ALL ON TABLE public.solution_replication_review_receipt FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_replication_review_queue(UUID, INTEGER, INTEGER),
            kokonut_security.get_location_solution_replication_review_detail(UUID, UUID),
            kokonut_security.review_location_solution_replication(UUID, UUID, UUID, TEXT, TEXT, BOOLEAN)
            FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.solution_replication_review_receipt FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMIT;
