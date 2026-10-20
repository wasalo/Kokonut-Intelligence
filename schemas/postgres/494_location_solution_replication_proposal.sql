-- Location-scoped, attributed, draft-only proposals to replicate validated solutions.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_replication_proposer'
    ) THEN
        CREATE ROLE kokonut_solution_replication_proposer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_replication_proposer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution replication proposer role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_replication_proposer'
            OR member_role.rolname = 'kokonut_solution_replication_proposer'
    ) THEN
        RAISE EXCEPTION 'Solution replication proposer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_replication_proposal_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    proposer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    source_experiment_id UUID NOT NULL
        REFERENCES public.solution_experiment(id) ON DELETE RESTRICT,
    replication_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_replication(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_replication_proposal_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_replication_proposal_receipt
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_replication_proposer;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_replication_proposer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_replication_proposer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_replication_proposer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_replication_proposer;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_replication_proposer;
GRANT SELECT, INSERT ON TABLE public.solution_replication_proposal_receipt
    TO kokonut_solution_replication_proposer;

GRANT SELECT (
    id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
    target_context, adaptation_required, replication_protocol, result,
    evidence_maturity, status, reviewed_by_party_id, evidence, created_at, completed_at
) ON TABLE public.solution_replication
    TO kokonut_solution_replication_proposer;
GRANT INSERT (
    id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
    target_context, adaptation_required, replication_protocol, result,
    evidence_maturity, status, reviewed_by_party_id, evidence, created_at, completed_at
) ON TABLE public.solution_replication
    TO kokonut_solution_replication_proposer;

GRANT SELECT (id, solution_id, status, owner_party_id, approved_by_party_id)
    ON TABLE public.solution_experiment
    TO kokonut_solution_replication_proposer;
GRANT UPDATE (id) ON TABLE public.solution_experiment
    TO kokonut_solution_replication_proposer;
GRANT SELECT (experiment_id, outcome, reviewed_by_party_id, reviewed_at)
    ON TABLE public.solution_experiment_result
    TO kokonut_solution_replication_proposer;
GRANT UPDATE (id) ON TABLE public.solution_experiment_result
    TO kokonut_solution_replication_proposer;
GRANT SELECT (id, originating_scope_type, originating_scope_id, status)
    ON TABLE public.solution
    TO kokonut_solution_replication_proposer;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_replication_proposer;
GRANT SELECT (id, solution_id, entity_type, entity_id)
    ON TABLE public.solution_link
    TO kokonut_solution_replication_proposer;
GRANT UPDATE (id) ON TABLE public.solution_link
    TO kokonut_solution_replication_proposer;
GRANT SELECT (id, party_type, status)
    ON TABLE public.party
    TO kokonut_solution_replication_proposer;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_replication_proposer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_replication_proposer;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_replication_proposer;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_replication_proposer;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_replication_proposer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_replication_proposer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_replication_proposer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_replication_proposer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_replication_proposer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_replication_proposer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_replication_proposer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_replication_proposer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_replication_proposer;

CREATE OR REPLACE FUNCTION kokonut_security.propose_location_solution_replication(
    requested_location_id UUID,
    requested_source_experiment_id UUID,
    requested_request_id UUID,
    requested_target_context TEXT,
    requested_adaptation_required TEXT,
    requested_replication_protocol JSONB
)
RETURNS TABLE (
    event_id UUID,
    replication_id UUID,
    replication_status TEXT,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    proposer_party_id UUID;
    existing_proposal RECORD;
    selected_solution_id UUID;
    selected_solution_origin_type TEXT;
    selected_solution_origin_id UUID;
    generated_replication_id UUID;
    generated_event_id UUID;
    proposal_timestamp TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_source_experiment_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Solution replication proposal requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution replication proposal requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;

    SELECT binding.party_id
      INTO proposer_party_id
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
    IF proposer_party_id IS NULL THEN
        RAISE EXCEPTION 'Operator has no active human governance-party binding'
            USING ERRCODE = '42501';
    END IF;

    IF pg_catalog.btrim(COALESCE(requested_target_context, '')) = ''
       OR pg_catalog.char_length(requested_target_context) > 2000
       OR (requested_adaptation_required IS NOT NULL
           AND (pg_catalog.btrim(requested_adaptation_required) = ''
                OR pg_catalog.char_length(requested_adaptation_required) > 4000))
       OR pg_catalog.jsonb_typeof(requested_replication_protocol) IS DISTINCT FROM 'object'
       OR pg_catalog.pg_column_size(requested_replication_protocol) > 65536 THEN
        RAISE EXCEPTION 'Solution replication context, adaptation, or protocol is invalid or exceeds bounds'
            USING ERRCODE = '22023';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || requested_request_id::TEXT, 0)
    );

    SELECT receipt.id, receipt.location_id, receipt.source_experiment_id,
           receipt.replication_id, receipt.proposer_party_id, receipt.created_at,
           replication.target_context, replication.adaptation_required,
           replication.replication_protocol, replication.status
      INTO existing_proposal
      FROM public.solution_replication_proposal_receipt AS receipt
      JOIN public.solution_replication AS replication
        ON replication.id = receipt.replication_id
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_proposal.location_id IS DISTINCT FROM requested_location_id
           OR existing_proposal.source_experiment_id IS DISTINCT FROM requested_source_experiment_id
           OR existing_proposal.proposer_party_id IS DISTINCT FROM proposer_party_id
           OR existing_proposal.target_context IS DISTINCT FROM requested_target_context
           OR existing_proposal.adaptation_required IS DISTINCT FROM requested_adaptation_required
           OR existing_proposal.replication_protocol IS DISTINCT FROM requested_replication_protocol THEN
            RAISE EXCEPTION 'Solution replication request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        event_id := existing_proposal.id;
        replication_id := existing_proposal.replication_id;
        replication_status := existing_proposal.status;
        created_at := existing_proposal.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT solution.id,
           solution.originating_scope_type,
           solution.originating_scope_id
      INTO selected_solution_id,
           selected_solution_origin_type,
           selected_solution_origin_id
      FROM public.solution_experiment AS experiment
      JOIN public.solution_experiment_result AS result
        ON result.experiment_id = experiment.id
       AND result.outcome = 'validated'
       AND result.reviewed_at IS NOT NULL
      JOIN public.party AS result_reviewer
        ON result_reviewer.id = result.reviewed_by_party_id
       AND result_reviewer.party_type = 'person'
       AND result_reviewer.status = 'active'
      JOIN public.solution AS solution
        ON solution.id = experiment.solution_id
       AND solution.status = 'active'
     WHERE experiment.id = requested_source_experiment_id
       AND experiment.status = 'validated'
       AND result.reviewed_by_party_id IS DISTINCT FROM experiment.owner_party_id
       AND result.reviewed_by_party_id IS DISTINCT FROM experiment.approved_by_party_id
     FOR SHARE OF experiment, result, result_reviewer, solution;
    IF selected_solution_id IS NULL THEN
        RAISE EXCEPTION 'Validated, independently reviewed source experiment was not found for this target location'
            USING ERRCODE = 'P0002';
    END IF;
    IF selected_solution_origin_type IS DISTINCT FROM 'location'
       OR selected_solution_origin_id IS DISTINCT FROM requested_location_id THEN
        PERFORM 1
          FROM public.solution_link AS location_link
         WHERE location_link.solution_id = selected_solution_id
           AND location_link.entity_type = 'location'
           AND location_link.entity_id = requested_location_id
         FOR SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Source solution is not visible at the exact target location'
                USING ERRCODE = 'P0002';
        END IF;
    END IF;

    generated_replication_id := pg_catalog.gen_random_uuid();
    proposal_timestamp := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_replication (
        id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
        target_context, adaptation_required, replication_protocol, result,
        evidence_maturity, status, reviewed_by_party_id, evidence, created_at, completed_at
    ) VALUES (
        generated_replication_id, selected_solution_id, requested_source_experiment_id, 'location',
        requested_location_id, requested_target_context, requested_adaptation_required,
        requested_replication_protocol, NULL, NULL, 'proposed', NULL, '[]'::JSONB,
        proposal_timestamp, NULL
    );

    INSERT INTO public.solution_replication_proposal_receipt (
        operator_id, proposer_party_id, location_id, source_experiment_id,
        replication_id, request_id, created_at
    ) VALUES (
        context_record.actor_id, proposer_party_id, requested_location_id,
        requested_source_experiment_id, generated_replication_id,
        requested_request_id, proposal_timestamp
    ) RETURNING id INTO generated_event_id;

    event_id := generated_event_id;
    replication_id := generated_replication_id;
    replication_status := 'proposed';
    created_at := proposal_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_replication_proposer;
ALTER FUNCTION kokonut_security.propose_location_solution_replication(
    UUID, UUID, UUID, TEXT, TEXT, JSONB
) OWNER TO kokonut_solution_replication_proposer;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_replication_proposer;
REVOKE ALL ON FUNCTION kokonut_security.propose_location_solution_replication(
    UUID, UUID, UUID, TEXT, TEXT, JSONB
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.propose_location_solution_replication(
            UUID, UUID, UUID, TEXT, TEXT, JSONB
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.propose_location_solution_replication(
            UUID, UUID, UUID, TEXT, TEXT, JSONB
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_replication_proposal_receipt IS
'Append-only attribution and retry receipt for proposals to replicate a validated solution at an exact location.';
COMMENT ON FUNCTION kokonut_security.propose_location_solution_replication(
    UUID, UUID, UUID, TEXT, TEXT, JSONB
) IS
'Creates only a proposed replication at the exact signed location for an explicitly location-linked active solution with a validated, actively reviewed source experiment; records OIDC human attribution and an immutable retry receipt without changing solution lifecycle stage or review state.';

COMMIT;
