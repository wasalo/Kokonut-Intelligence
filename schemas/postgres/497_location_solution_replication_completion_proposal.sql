-- Submit a private, reviewable completion report without changing replication state.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_replication_completion_proposer'
    ) THEN
        CREATE ROLE kokonut_solution_replication_completion_proposer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_replication_completion_proposer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution replication completion proposer role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_replication_completion_proposer'
            OR member_role.rolname = 'kokonut_solution_replication_completion_proposer'
    ) THEN
        RAISE EXCEPTION 'Solution replication completion proposer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_replication_completion_proposal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    proposer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    replication_id UUID NOT NULL REFERENCES public.solution_replication(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('successful', 'failed', 'mixed', 'inconclusive')),
    evidence_maturity INTEGER NOT NULL REFERENCES public.evidence_maturity_level(level)
        CHECK (evidence_maturity BETWEEN 1 AND 6),
    outcome_summary TEXT NOT NULL
        CHECK (pg_catalog.char_length(pg_catalog.btrim(outcome_summary)) BETWEEN 10 AND 4000),
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB
        CHECK (CASE WHEN pg_catalog.jsonb_typeof(evidence) = 'array'
                    THEN pg_catalog.jsonb_array_length(evidence) <= 100
                         AND pg_catalog.octet_length(evidence::TEXT) <= 65536
                    ELSE FALSE END),
    decision_status TEXT NOT NULL DEFAULT 'proposed'
        CHECK (decision_status IN ('proposed', 'accepted', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    reviewed_by_party_id UUID REFERENCES public.party(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ,
    review_reason TEXT
        CHECK (review_reason IS NULL OR pg_catalog.char_length(review_reason) <= 4000),
    UNIQUE (operator_id, request_id),
    CHECK ((decision_status = 'proposed') = (reviewed_by_party_id IS NULL)),
    CHECK ((decision_status = 'proposed') = (reviewed_at IS NULL)),
    CHECK (decision_status <> 'rejected'
           OR pg_catalog.char_length(pg_catalog.btrim(COALESCE(review_reason, ''))) >= 10)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_solution_replication_completion_pending
    ON public.solution_replication_completion_proposal (replication_id)
    WHERE decision_status = 'proposed';

REVOKE ALL ON TABLE public.solution_replication_completion_proposal FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_replication_completion_proposal
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader,
         kokonut_solution_replication_proposer, kokonut_solution_replication_reviewer,
         kokonut_solution_replication_starter;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_replication_completion_proposer;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_replication_completion_proposer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_replication_completion_proposer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_replication_completion_proposer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_replication_completion_proposer;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_replication_completion_proposer;

GRANT SELECT, INSERT ON TABLE public.solution_replication_completion_proposal
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (
    id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
    status, reviewed_by_party_id, reviewed_at, started_at, started_by_party_id,
    result, evidence_maturity, evidence, completed_at
) ON TABLE public.solution_replication TO kokonut_solution_replication_completion_proposer;
GRANT UPDATE (id) ON TABLE public.solution_replication
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (id, status, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_replication_completion_proposer;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (source_experiment_id, proposer_party_id, location_id, replication_id)
    ON TABLE public.solution_replication_proposal_receipt
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (reviewer_party_id, location_id, replication_id, decision, reviewed_at)
    ON TABLE public.solution_replication_review_receipt
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (id, solution_id, status, owner_party_id, approved_by_party_id)
    ON TABLE public.solution_experiment TO kokonut_solution_replication_completion_proposer;
GRANT UPDATE (id) ON TABLE public.solution_experiment
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (experiment_id, outcome, reviewed_by_party_id, reviewed_at)
    ON TABLE public.solution_experiment_result
    TO kokonut_solution_replication_completion_proposer;
GRANT UPDATE (id) ON TABLE public.solution_experiment_result
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_replication_completion_proposer;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_replication_completion_proposer;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_replication_completion_proposer;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_replication_completion_proposer;
GRANT SELECT (id, entity_type, entity_id, solution_id) ON TABLE public.solution_link
    TO kokonut_solution_replication_completion_proposer;
GRANT UPDATE (id) ON TABLE public.solution_link
    TO kokonut_solution_replication_completion_proposer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_replication_completion_proposer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_replication_completion_proposer;

CREATE OR REPLACE FUNCTION kokonut_security.guard_solution_replication_completion_proposal()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
DECLARE
    caller_role TEXT := CURRENT_USER;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF caller_role <> 'kokonut_solution_replication_completion_proposer'
           OR NEW.decision_status <> 'proposed'
           OR NEW.reviewed_by_party_id IS NOT NULL
           OR NEW.reviewed_at IS NOT NULL
           OR NEW.review_reason IS NOT NULL THEN
            RAISE EXCEPTION 'Completion reports require the bounded proposal function'
                USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'UPDATE'
       AND caller_role = 'kokonut_solution_replication_completion_reviewer'
       AND OLD.decision_status = 'proposed'
       AND NEW.decision_status IN ('accepted', 'rejected')
       AND NEW.reviewed_by_party_id IS NOT NULL
       AND NEW.reviewed_at IS NOT NULL
       AND NEW.id IS NOT DISTINCT FROM OLD.id
       AND NEW.operator_id IS NOT DISTINCT FROM OLD.operator_id
       AND NEW.proposer_party_id IS NOT DISTINCT FROM OLD.proposer_party_id
       AND NEW.location_id IS NOT DISTINCT FROM OLD.location_id
       AND NEW.replication_id IS NOT DISTINCT FROM OLD.replication_id
       AND NEW.request_id IS NOT DISTINCT FROM OLD.request_id
       AND NEW.outcome IS NOT DISTINCT FROM OLD.outcome
       AND NEW.evidence_maturity IS NOT DISTINCT FROM OLD.evidence_maturity
       AND NEW.outcome_summary IS NOT DISTINCT FROM OLD.outcome_summary
       AND NEW.evidence IS NOT DISTINCT FROM OLD.evidence
       AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at THEN
        RETURN NEW;
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.operator_id IS DISTINCT FROM OLD.operator_id
       OR NEW.proposer_party_id IS DISTINCT FROM OLD.proposer_party_id
       OR NEW.location_id IS DISTINCT FROM OLD.location_id
       OR NEW.replication_id IS DISTINCT FROM OLD.replication_id
       OR NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.outcome IS DISTINCT FROM OLD.outcome
       OR NEW.evidence_maturity IS DISTINCT FROM OLD.evidence_maturity
       OR NEW.outcome_summary IS DISTINCT FROM OLD.outcome_summary
       OR NEW.evidence IS DISTINCT FROM OLD.evidence
       OR NEW.decision_status IS DISTINCT FROM OLD.decision_status
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.reviewed_by_party_id IS DISTINCT FROM OLD.reviewed_by_party_id
       OR NEW.reviewed_at IS DISTINCT FROM OLD.reviewed_at
       OR NEW.review_reason IS DISTINCT FROM OLD.review_reason THEN
        RAISE EXCEPTION 'Completion proposal fields require a bounded transition function'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_solution_replication_completion_proposal_guard
    ON public.solution_replication_completion_proposal;
CREATE TRIGGER trg_solution_replication_completion_proposal_guard
    BEFORE INSERT OR UPDATE ON public.solution_replication_completion_proposal
    FOR EACH ROW
    EXECUTE FUNCTION kokonut_security.guard_solution_replication_completion_proposal();

CREATE OR REPLACE FUNCTION kokonut_security.propose_location_solution_replication_completion(
    requested_location_id UUID,
    requested_replication_id UUID,
    requested_request_id UUID,
    requested_outcome TEXT,
    requested_evidence_maturity INTEGER,
    requested_outcome_summary TEXT,
    requested_evidence JSONB
)
RETURNS TABLE (
    proposal_id UUID,
    replication_id UUID,
    decision_status TEXT,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    proposer_party UUID;
    existing_proposal RECORD;
    source_experiment UUID;
    solution_record UUID;
    source_origin_type TEXT;
    source_origin_id UUID;
    source_proposer UUID;
    source_approver UUID;
    source_reviewer UUID;
    activation_party UUID;
    generated_proposal_id UUID;
    proposal_timestamp TIMESTAMPTZ;
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
        RAISE EXCEPTION 'Replication completion proposal requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF requested_outcome IS NULL
       OR requested_outcome NOT IN ('successful', 'failed', 'mixed', 'inconclusive')
       OR requested_evidence_maturity IS NULL
       OR requested_evidence_maturity NOT BETWEEN 1 AND 6
       OR requested_outcome_summary IS NULL
       OR pg_catalog.char_length(pg_catalog.btrim(requested_outcome_summary)) NOT BETWEEN 10 AND 4000
       OR requested_evidence IS NULL
       OR pg_catalog.jsonb_typeof(requested_evidence) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Replication completion proposal fields are invalid'
            USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.jsonb_array_length(requested_evidence) > 100
       OR pg_catalog.octet_length(requested_evidence::TEXT) > 65536 THEN
        RAISE EXCEPTION 'Replication completion proposal evidence exceeds its bounds'
            USING ERRCODE = '22023';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'submit', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Replication completion proposal requires an active exact location submit grant'
            USING ERRCODE = '42501';
    END IF;

    SELECT binding.party_id
      INTO proposer_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS proposer
        ON proposer.id = binding.party_id
       AND proposer.party_type = 'person'
       AND proposer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, operator, proposer;
    IF proposer_party IS NULL THEN
        RAISE EXCEPTION 'Replication completion proposal requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || requested_request_id::TEXT, 0)
    );
    SELECT proposal.id, proposal.location_id, proposal.replication_id,
           proposal.proposer_party_id, proposal.outcome,
           proposal.evidence_maturity, proposal.outcome_summary,
           proposal.evidence, proposal.decision_status, proposal.created_at
      INTO existing_proposal
      FROM public.solution_replication_completion_proposal AS proposal
     WHERE proposal.operator_id = context_record.actor_id
       AND proposal.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_proposal.location_id IS DISTINCT FROM requested_location_id
           OR existing_proposal.replication_id IS DISTINCT FROM requested_replication_id
           OR existing_proposal.proposer_party_id IS DISTINCT FROM proposer_party
           OR existing_proposal.outcome IS DISTINCT FROM requested_outcome
           OR existing_proposal.evidence_maturity IS DISTINCT FROM requested_evidence_maturity
           OR existing_proposal.outcome_summary IS DISTINCT FROM requested_outcome_summary
           OR existing_proposal.evidence IS DISTINCT FROM requested_evidence THEN
            RAISE EXCEPTION 'Replication completion request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        proposal_id := existing_proposal.id;
        replication_id := existing_proposal.replication_id;
        decision_status := existing_proposal.decision_status;
        created_at := existing_proposal.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT replication.source_experiment_id,
           replication.solution_id,
           solution.originating_scope_type,
           solution.originating_scope_id,
           proposal.proposer_party_id,
           approval.reviewer_party_id,
           source_result.reviewed_by_party_id,
           replication.started_by_party_id
      INTO source_experiment,
           solution_record,
           source_origin_type,
           source_origin_id,
           source_proposer,
           source_approver,
           source_reviewer,
           activation_party
      FROM public.solution_replication AS replication
      JOIN public.solution AS solution
        ON solution.id = replication.solution_id
       AND solution.status = 'active'
      JOIN public.solution_replication_proposal_receipt AS proposal
        ON proposal.replication_id = replication.id
       AND proposal.location_id = requested_location_id
       AND proposal.source_experiment_id = replication.source_experiment_id
      JOIN public.solution_replication_review_receipt AS approval
        ON approval.replication_id = replication.id
       AND approval.location_id = requested_location_id
       AND approval.decision = 'approved'
       AND approval.reviewer_party_id = replication.reviewed_by_party_id
       AND approval.reviewed_at = replication.reviewed_at
      JOIN public.solution_experiment AS experiment
        ON experiment.id = replication.source_experiment_id
       AND experiment.status = 'validated'
      JOIN public.solution_experiment_result AS source_result
        ON source_result.experiment_id = experiment.id
       AND source_result.outcome = 'validated'
       AND source_result.reviewed_at IS NOT NULL
      JOIN public.party AS source_human
        ON source_human.id = source_result.reviewed_by_party_id
       AND source_human.party_type = 'person'
       AND source_human.status = 'active'
      JOIN public.party AS approver_human
        ON approver_human.id = approval.reviewer_party_id
       AND approver_human.party_type = 'person'
       AND approver_human.status = 'active'
     WHERE replication.id = requested_replication_id
       AND replication.status = 'active'
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND replication.started_at IS NOT NULL
       AND replication.started_by_party_id IS NOT NULL
       AND replication.result IS NULL
       AND replication.evidence_maturity IS NULL
       AND replication.evidence = '[]'::JSONB
       AND replication.completed_at IS NULL
       AND experiment.owner_party_id IS DISTINCT FROM source_result.reviewed_by_party_id
       AND experiment.approved_by_party_id IS DISTINCT FROM source_result.reviewed_by_party_id
     FOR UPDATE OF replication, solution, experiment, source_result
     FOR SHARE OF source_human, approver_human;
    IF source_experiment IS NULL OR source_proposer IS NULL
       OR source_approver IS NULL OR source_reviewer IS NULL OR activation_party IS NULL THEN
        RAISE EXCEPTION 'Started, independently approved replication not found for this location'
            USING ERRCODE = 'P0002';
    END IF;

    IF source_origin_type IS DISTINCT FROM 'location'
       OR source_origin_id IS DISTINCT FROM requested_location_id THEN
        PERFORM 1
          FROM public.solution_link AS location_link
         WHERE location_link.solution_id = solution_record
           AND location_link.entity_type = 'location'
           AND location_link.entity_id = requested_location_id
         FOR SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Replication solution is no longer visible at the exact target location'
                USING ERRCODE = 'P0002';
        END IF;
    END IF;

    proposal_timestamp := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_replication_completion_proposal (
        operator_id, proposer_party_id, location_id, replication_id, request_id,
        outcome, evidence_maturity, outcome_summary, evidence, created_at
    ) VALUES (
        context_record.actor_id, proposer_party, requested_location_id,
        requested_replication_id, requested_request_id, requested_outcome,
        requested_evidence_maturity, pg_catalog.btrim(requested_outcome_summary),
        requested_evidence, proposal_timestamp
    ) RETURNING id INTO generated_proposal_id;

    proposal_id := generated_proposal_id;
    replication_id := requested_replication_id;
    decision_status := 'proposed';
    created_at := proposal_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_replication_completion_proposer;
ALTER FUNCTION kokonut_security.propose_location_solution_replication_completion(
    UUID, UUID, UUID, TEXT, INTEGER, TEXT, JSONB
) OWNER TO kokonut_solution_replication_completion_proposer;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_replication_completion_proposer;
REVOKE ALL ON FUNCTION kokonut_security.propose_location_solution_replication_completion(
    UUID, UUID, UUID, TEXT, INTEGER, TEXT, JSONB
) FROM PUBLIC;

COMMENT ON TABLE public.solution_replication_completion_proposal IS
'Private immutable completion report awaiting independent location-scoped review; proposal alone does not complete a replication.';
COMMENT ON FUNCTION kokonut_security.propose_location_solution_replication_completion(
    UUID, UUID, UUID, TEXT, INTEGER, TEXT, JSONB
) IS
'Creates a bounded exact-location completion report only for an active, started, independently approved replication with current validated source lineage; records a retry-stable proposal without changing replication or solution state.';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.propose_location_solution_replication_completion(
            UUID, UUID, UUID, TEXT, INTEGER, TEXT, JSONB
        ) TO kokonut_runtime;
        REVOKE ALL ON TABLE public.solution_replication_completion_proposal
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.propose_location_solution_replication_completion(
            UUID, UUID, UUID, TEXT, INTEGER, TEXT, JSONB
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.solution_replication_completion_proposal
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMIT;
