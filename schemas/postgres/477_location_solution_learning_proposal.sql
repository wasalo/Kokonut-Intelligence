-- Create attributed, location-scoped learning proposals from reviewed replications.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_learning_proposal_owner'
    ) THEN
        CREATE ROLE kokonut_solution_learning_proposal_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_learning_proposal_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution learning proposal owner role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_learning_proposal_owner'
            OR member_role.rolname = 'kokonut_solution_learning_proposal_owner'
    ) THEN
        RAISE EXCEPTION 'Solution learning proposal owner role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_learning_proposal_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    proposer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    replication_id UUID NOT NULL REFERENCES public.solution_replication(id) ON DELETE RESTRICT,
    learning_record_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_learning_record(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_learning_proposal_event FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_learning_proposal_event
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader;
REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_learning_proposal_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_learning_proposal_owner;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_learning_proposal_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_learning_proposal_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_learning_proposal_owner;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT, INSERT ON TABLE public.solution_learning_proposal_event
    TO kokonut_solution_learning_proposal_owner;

GRANT SELECT (id, solution_id, target_scope_type, target_scope_id, status,
              reviewed_by_party_id)
    ON TABLE public.solution_replication
    TO kokonut_solution_learning_proposal_owner;
GRANT UPDATE (id) ON TABLE public.solution_replication
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (id, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_learning_proposal_owner;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (solution_id, entity_type, entity_id)
    ON TABLE public.solution_link TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (id, party_type, status)
    ON TABLE public.party TO kokonut_solution_learning_proposal_owner;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_learning_proposal_owner;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_learning_proposal_owner;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_learning_proposal_owner;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_learning_proposal_owner;

GRANT SELECT (
    id, solution_id, source_replication_id, lesson_type, finding, confidence,
    transferability, affected_assumptions, affected_metrics, recommended_action,
    decision_status, evidence, owner_party_id
) ON TABLE public.solution_learning_record
    TO kokonut_solution_learning_proposal_owner;
GRANT INSERT (
    id, solution_id, source_replication_id, lesson_type, finding, confidence,
    transferability, affected_assumptions, affected_metrics, recommended_action,
    decision_status, evidence, created_at
) ON TABLE public.solution_learning_record
    TO kokonut_solution_learning_proposal_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_learning_proposal_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_learning_proposal_owner;

CREATE OR REPLACE FUNCTION kokonut_security.propose_location_solution_learning(
    requested_location_id UUID,
    requested_replication_id UUID,
    requested_request_id UUID,
    requested_lesson_type TEXT,
    requested_finding TEXT,
    requested_confidence TEXT,
    requested_transferability TEXT,
    requested_affected_assumptions JSONB,
    requested_affected_metrics JSONB,
    requested_recommended_action TEXT,
    requested_evidence JSONB
)
RETURNS TABLE (
    event_id UUID,
    learning_record_id UUID,
    learning_status TEXT,
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
    generated_record_id UUID;
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
       OR requested_replication_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Solution learning proposal requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution learning proposal requires an active exact location grant'
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

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || requested_request_id::TEXT, 0)
    );

    SELECT proposal.id, proposal.location_id, proposal.replication_id,
           proposal.learning_record_id, proposal.proposer_party_id,
           proposal.created_at, learning.solution_id,
           learning.source_replication_id, learning.lesson_type, learning.finding,
           learning.confidence, learning.transferability,
           learning.affected_assumptions, learning.affected_metrics,
           learning.recommended_action, learning.evidence, learning.decision_status
      INTO existing_proposal
      FROM public.solution_learning_proposal_event AS proposal
      JOIN public.solution_learning_record AS learning
        ON learning.id = proposal.learning_record_id
     WHERE proposal.operator_id = context_record.actor_id
       AND proposal.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_proposal.location_id IS DISTINCT FROM requested_location_id
           OR existing_proposal.replication_id IS DISTINCT FROM requested_replication_id
           OR existing_proposal.source_replication_id IS DISTINCT FROM requested_replication_id
           OR existing_proposal.proposer_party_id IS DISTINCT FROM proposer_party_id
           OR existing_proposal.lesson_type IS DISTINCT FROM requested_lesson_type
           OR existing_proposal.finding IS DISTINCT FROM requested_finding
           OR existing_proposal.confidence IS DISTINCT FROM requested_confidence
           OR existing_proposal.transferability IS DISTINCT FROM requested_transferability
           OR existing_proposal.affected_assumptions IS DISTINCT FROM requested_affected_assumptions
           OR existing_proposal.affected_metrics IS DISTINCT FROM requested_affected_metrics
           OR existing_proposal.recommended_action IS DISTINCT FROM requested_recommended_action
           OR existing_proposal.evidence IS DISTINCT FROM requested_evidence THEN
            RAISE EXCEPTION 'Solution learning proposal request id was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        event_id := existing_proposal.id;
        learning_record_id := existing_proposal.learning_record_id;
        learning_status := existing_proposal.decision_status;
        created_at := existing_proposal.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT replication.solution_id
      INTO selected_solution_id
      FROM public.solution_replication AS replication
      JOIN public.solution AS solution
        ON solution.id = replication.solution_id
      JOIN public.party AS reviewer
        ON reviewer.id = replication.reviewed_by_party_id
       AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE replication.id = requested_replication_id
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND replication.status = 'completed'
       AND replication.reviewed_by_party_id IS NOT NULL
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
     FOR SHARE OF replication, solution, reviewer;
    IF selected_solution_id IS NULL THEN
        RAISE EXCEPTION 'Completed, reviewed replication was not found in this location scope'
            USING ERRCODE = 'P0002';
    END IF;

    IF requested_lesson_type IS NULL OR requested_lesson_type NOT IN (
        'validated_assumption', 'invalidated_assumption', 'implementation',
        'adoption', 'safety', 'economic', 'equity', 'context_transfer'
    ) THEN
        RAISE EXCEPTION 'Solution learning lesson type is invalid' USING ERRCODE = '22023';
    END IF;
    IF requested_confidence IS NULL OR requested_confidence NOT IN (
        'high', 'moderate', 'low', 'insufficient_evidence'
    ) OR requested_transferability IS NULL OR requested_transferability NOT IN (
        'high', 'medium', 'low', 'unknown'
    ) THEN
        RAISE EXCEPTION 'Solution learning confidence or transferability is invalid'
            USING ERRCODE = '22023';
    END IF;
    IF requested_finding IS NULL OR pg_catalog.btrim(requested_finding) = ''
       OR pg_catalog.char_length(requested_finding) > 4000
       OR requested_recommended_action IS NULL
       OR pg_catalog.btrim(requested_recommended_action) = ''
       OR pg_catalog.char_length(requested_recommended_action) > 4000 THEN
        RAISE EXCEPTION 'Solution learning finding and recommendation must be bounded'
            USING ERRCODE = '22023';
    END IF;

    IF pg_catalog.jsonb_typeof(requested_affected_assumptions) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(requested_affected_metrics) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(requested_evidence) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Solution learning references and evidence must be arrays'
            USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.jsonb_array_length(requested_affected_assumptions) > 100
       OR pg_catalog.jsonb_array_length(requested_affected_metrics) > 100
       OR pg_catalog.jsonb_array_length(requested_evidence) NOT BETWEEN 1 AND 100
       OR pg_catalog.pg_column_size(requested_affected_assumptions) > 65536
       OR pg_catalog.pg_column_size(requested_affected_metrics) > 65536
       OR pg_catalog.pg_column_size(requested_evidence) > 65536 THEN
        RAISE EXCEPTION 'Solution learning references or evidence exceed bounds'
            USING ERRCODE = '22023';
    END IF;

    generated_record_id := pg_catalog.gen_random_uuid();
    proposal_timestamp := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_learning_record (
        id, solution_id, source_replication_id, lesson_type, finding, confidence,
        transferability, affected_assumptions, affected_metrics, recommended_action,
        decision_status, evidence, created_at
    ) VALUES (
        generated_record_id, selected_solution_id, requested_replication_id,
        requested_lesson_type, requested_finding, requested_confidence,
        requested_transferability, requested_affected_assumptions,
        requested_affected_metrics, requested_recommended_action, 'proposed',
        requested_evidence, proposal_timestamp
    );

    INSERT INTO public.solution_learning_proposal_event (
        operator_id, proposer_party_id, location_id, replication_id,
        learning_record_id, request_id, created_at
    ) VALUES (
        context_record.actor_id, proposer_party_id, requested_location_id,
        requested_replication_id, generated_record_id, requested_request_id,
        proposal_timestamp
    ) RETURNING id INTO generated_event_id;

    event_id := generated_event_id;
    learning_record_id := generated_record_id;
    learning_status := 'proposed';
    created_at := proposal_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_learning_proposal_owner;
ALTER FUNCTION kokonut_security.propose_location_solution_learning(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, TEXT, JSONB, JSONB, TEXT, JSONB
) OWNER TO kokonut_solution_learning_proposal_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_learning_proposal_owner;
REVOKE ALL ON FUNCTION kokonut_security.propose_location_solution_learning(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, TEXT, JSONB, JSONB, TEXT, JSONB
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.propose_location_solution_learning(
            UUID, UUID, UUID, TEXT, TEXT, TEXT, TEXT, JSONB, JSONB, TEXT, JSONB
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.propose_location_solution_learning(
            UUID, UUID, UUID, TEXT, TEXT, TEXT, TEXT, JSONB, JSONB, TEXT, JSONB
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_learning_proposal_event IS
'Append-only receipt for location-scoped learning proposals grounded in completed, independently reviewed replications.';
COMMENT ON FUNCTION kokonut_security.propose_location_solution_learning(
    UUID, UUID, UUID, TEXT, TEXT, TEXT, TEXT, JSONB, JSONB, TEXT, JSONB
) IS
'Creates only a proposed learning record for a completed, actively reviewed replication targeting the exact signed location; records active OIDC proposer attribution in an append-only idempotent receipt and exposes no narrative or evidence in the result.';

COMMIT;
