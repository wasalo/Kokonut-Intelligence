-- Advance an exact-location solution through an already approved promotion gate.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_gate_transitioner'
    ) THEN
        CREATE ROLE kokonut_solution_gate_transitioner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_gate_transitioner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution gate transition role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_gate_transitioner'
            OR member_role.rolname = 'kokonut_solution_gate_transitioner'
    ) THEN
        RAISE EXCEPTION 'Solution gate transition role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_gate_transition_submission_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    gate_id UUID NOT NULL UNIQUE REFERENCES public.solution_stage_gate(id) ON DELETE RESTRICT,
    lifecycle_event_id UUID NOT NULL UNIQUE REFERENCES public.solution_lifecycle_event(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    from_stage VARCHAR(30) NOT NULL,
    to_stage VARCHAR(30) NOT NULL,
    solution_status VARCHAR(20) NOT NULL,
    transitioned_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_gate_transition_submission_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_gate_transition_submission_receipt
    FROM kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_gate_transitioner;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_solution_gate_transitioner;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_solution_gate_transitioner;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_solution_gate_transitioner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_solution_gate_transitioner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_solution_gate_transitioner;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_solution_gate_transitioner;

GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage,
              status, evidence_maturity)
    ON TABLE public.solution TO kokonut_solution_gate_transitioner;
GRANT UPDATE (id) ON TABLE public.solution TO kokonut_solution_gate_transitioner;
GRANT UPDATE (current_stage, updated_at)
    ON TABLE public.solution TO kokonut_solution_gate_transitioner;
GRANT SELECT (id, solution_id, from_stage, to_stage, required_evidence_maturity,
              required_experiment_count, minimum_evaluation_count,
              requires_human_approval, status, approved_by_party_id)
    ON TABLE public.solution_stage_gate TO kokonut_solution_gate_transitioner;
GRANT UPDATE (id) ON TABLE public.solution_stage_gate TO kokonut_solution_gate_transitioner;
GRANT SELECT (id, gate_id, passed, evaluated_by_party_id, evaluated_at)
    ON TABLE public.solution_gate_evaluation TO kokonut_solution_gate_transitioner;
GRANT SELECT (id, solution_id) ON TABLE public.solution_experiment
    TO kokonut_solution_gate_transitioner;
GRANT SELECT (experiment_id, outcome) ON TABLE public.solution_experiment_result
    TO kokonut_solution_gate_transitioner;
GRANT SELECT (solution_id, target_scope_type, target_scope_id, status)
    ON TABLE public.solution_adoption_program TO kokonut_solution_gate_transitioner;
GRANT SELECT (solution_id, adopter_scope_type, adopter_scope_id, readiness_status,
              assessed_by_party_id)
    ON TABLE public.solution_adopter_readiness TO kokonut_solution_gate_transitioner;
GRANT SELECT (solution_id, scope_type, scope_id, approval_status,
              approved_by_party_id)
    ON TABLE public.solution_configuration TO kokonut_solution_gate_transitioner;
GRANT SELECT (solution_id, scope_type, scope_id, status, approved_by_party_id)
    ON TABLE public.solution_scale_gate TO kokonut_solution_gate_transitioner;
GRANT SELECT (solution_id, decision_status, approved_by_party_id)
    ON TABLE public.solution_funding_case TO kokonut_solution_gate_transitioner;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding TO kokonut_solution_gate_transitioner;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding,
    public.operator_identity, public.party TO kokonut_solution_gate_transitioner;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_gate_transitioner;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_gate_transitioner;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_solution_gate_transitioner;
-- operator_scope_grant_allows is SECURITY INVOKER; keep its tenant proof
-- dependencies explicit and column-scoped for this function owner.
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_gate_transitioner;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_gate_transitioner;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_gate_transitioner;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_gate_transitioner;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_gate_transitioner;
GRANT SELECT (solution_id, from_stage, to_stage, rationale, evidence, rollback_plan,
              actor_party_id, approved_by_party_id, id, created_at)
    ON TABLE public.solution_lifecycle_event TO kokonut_solution_gate_transitioner;
GRANT INSERT (solution_id, from_stage, to_stage, rationale, evidence,
              rollback_plan, actor_party_id, approved_by_party_id)
    ON TABLE public.solution_lifecycle_event TO kokonut_solution_gate_transitioner;
GRANT SELECT (id, operator_id, actor_party_id, location_id, solution_id, gate_id,
              lifecycle_event_id, request_id, payload_digest, from_stage, to_stage,
              solution_status, transitioned_at)
    ON TABLE public.solution_gate_transition_submission_receipt
    TO kokonut_solution_gate_transitioner;
GRANT INSERT (operator_id, actor_party_id, location_id, solution_id, gate_id,
              lifecycle_event_id, request_id, payload_digest, from_stage, to_stage,
              solution_status, transitioned_at)
    ON TABLE public.solution_gate_transition_submission_receipt
    TO kokonut_solution_gate_transitioner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_gate_transitioner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_gate_transitioner;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_gate_transitioner;

CREATE OR REPLACE FUNCTION kokonut_security.transition_location_solution_gate(
    requested_location_id UUID,
    requested_gate_id UUID,
    requested_request_id UUID,
    requested_rationale TEXT,
    requested_evidence JSONB,
    requested_rollback_plan TEXT
)
RETURNS TABLE (
    lifecycle_event_id UUID,
    solution_id UUID,
    gate_id UUID,
    from_stage TEXT,
    to_stage TEXT,
    solution_status TEXT,
    transitioned_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    solution_record RECORD;
    gate_record RECORD;
    latest_evaluation RECORD;
    existing RECORD;
    event_record RECORD;
    passed_evaluation_count BIGINT;
    validated_experiment_count BIGINT;
    scale_gate_record RECORD;
    payload_digest BYTEA;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_gate_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Solution gate transition requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'transition', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution gate transition requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_rationale IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_rationale)) NOT BETWEEN 10 AND 4000
       OR requested_evidence IS NULL
       OR pg_catalog.jsonb_typeof(requested_evidence) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_evidence) NOT BETWEEN 1 AND 100
       OR pg_catalog.octet_length(requested_evidence::TEXT) > 65536
       OR requested_rollback_plan IS NOT NULL
          AND pg_catalog.length(requested_rollback_plan) > 4000 THEN
        RAISE EXCEPTION 'Solution transition rationale, evidence, or rollback plan is invalid'
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
        RAISE EXCEPTION 'Solution transition requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'gate_id', requested_gate_id,
                'rationale', requested_rationale,
                'evidence', requested_evidence,
                'rollback_plan', requested_rollback_plan
            )::TEXT,
            'UTF8'
        ),
        'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.solution_id, receipt.gate_id,
           receipt.lifecycle_event_id, receipt.payload_digest, receipt.from_stage,
           receipt.to_stage, receipt.solution_status, receipt.transitioned_at
      INTO existing
      FROM public.solution_gate_transition_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.gate_id IS DISTINCT FROM requested_gate_id
           OR existing.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Solution gate transition request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT existing.lifecycle_event_id, existing.solution_id,
                            existing.gate_id, existing.from_stage::TEXT,
                            existing.to_stage::TEXT, existing.solution_status::TEXT,
                            existing.transitioned_at, TRUE;
        RETURN;
    END IF;

    SELECT solution.id, solution.current_stage, solution.status,
           solution.evidence_maturity
      INTO solution_record
      FROM public.solution AS solution
     WHERE solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.id = (
           SELECT gate.solution_id
             FROM public.solution_stage_gate AS gate
            WHERE gate.id = requested_gate_id
       )
     FOR UPDATE OF solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location-origin solution gate was not found'
            USING ERRCODE = 'P0002';
    END IF;

    SELECT gate.id, gate.solution_id, gate.from_stage, gate.to_stage,
           gate.required_evidence_maturity, gate.required_experiment_count,
           gate.minimum_evaluation_count, gate.requires_human_approval,
           gate.status, gate.approved_by_party_id
      INTO gate_record
      FROM public.solution_stage_gate AS gate
     WHERE gate.id = requested_gate_id
       AND gate.solution_id = solution_record.id
     FOR UPDATE OF gate;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location-origin solution gate was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF gate_record.to_stage NOT IN ('validated', 'funded', 'adoption_ready', 'scaled')
       OR gate_record.from_stage IS DISTINCT FROM solution_record.current_stage THEN
        RAISE EXCEPTION 'Gate does not represent a current supported promotion'
            USING ERRCODE = '55000';
    END IF;
    IF gate_record.status IS DISTINCT FROM 'approved'
       OR gate_record.requires_human_approval
          AND gate_record.approved_by_party_id IS NULL THEN
        RAISE EXCEPTION 'An approved gate is required before stage transition'
            USING ERRCODE = '55000';
    END IF;

    SELECT evaluation.passed, evaluation.evaluated_by_party_id
      INTO latest_evaluation
      FROM public.solution_gate_evaluation AS evaluation
     WHERE evaluation.gate_id = requested_gate_id
     ORDER BY evaluation.evaluated_at DESC, evaluation.id DESC
     LIMIT 1;
    IF NOT FOUND OR latest_evaluation.passed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'A latest passing evaluation is required before stage transition'
            USING ERRCODE = '55000';
    END IF;
    SELECT pg_catalog.count(*) INTO passed_evaluation_count
      FROM public.solution_gate_evaluation AS evaluation
     WHERE evaluation.gate_id = requested_gate_id AND evaluation.passed;
    IF passed_evaluation_count < gate_record.minimum_evaluation_count THEN
        RAISE EXCEPTION 'The required number of passing gate evaluations has not been reached'
            USING ERRCODE = '55000';
    END IF;
    IF gate_record.requires_human_approval IS TRUE
       AND (gate_record.approved_by_party_id IS NULL
            OR gate_record.approved_by_party_id IS NOT DISTINCT FROM
               latest_evaluation.evaluated_by_party_id) THEN
        RAISE EXCEPTION 'An independently approved human gate is required'
            USING ERRCODE = '55000';
    END IF;
    IF gate_record.required_evidence_maturity IS NOT NULL
       AND (solution_record.evidence_maturity IS NULL
            OR solution_record.evidence_maturity < gate_record.required_evidence_maturity) THEN
        RAISE EXCEPTION 'Required evidence maturity has not been reached'
            USING ERRCODE = '55000';
    END IF;
    IF gate_record.required_experiment_count > 0 THEN
        SELECT pg_catalog.count(*) INTO validated_experiment_count
          FROM public.solution_experiment_result AS result
          JOIN public.solution_experiment AS experiment
            ON experiment.id = result.experiment_id
         WHERE experiment.solution_id = solution_record.id
           AND result.outcome = 'validated';
        IF validated_experiment_count < gate_record.required_experiment_count THEN
            RAISE EXCEPTION 'Required validated experiment count has not been reached'
                USING ERRCODE = '55000';
        END IF;
    END IF;

    IF gate_record.to_stage = 'adoption_ready' THEN
        IF NOT EXISTS (
            SELECT 1
              FROM public.solution_adoption_program AS program
              JOIN public.solution_adopter_readiness AS readiness
                ON readiness.solution_id = program.solution_id
               AND readiness.adopter_scope_type = program.target_scope_type
               AND readiness.adopter_scope_id = program.target_scope_id
              JOIN public.solution_configuration AS configuration
                ON configuration.solution_id = program.solution_id
               AND configuration.scope_type = program.target_scope_type
               AND configuration.scope_id = program.target_scope_id
             WHERE program.solution_id = solution_record.id
               AND program.target_scope_type = 'location'
               AND program.target_scope_id = requested_location_id
               AND program.status IN ('enablement_ready', 'launch', 'onboarding', 'active', 'assessed', 'expand')
               AND readiness.readiness_status = 'ready'
               AND readiness.assessed_by_party_id IS NOT NULL
               AND configuration.approval_status = 'approved'
               AND configuration.approved_by_party_id IS NOT NULL
        ) THEN
            RAISE EXCEPTION 'Approved location adoption configuration and readiness are required'
                USING ERRCODE = '55000';
        END IF;
    END IF;

    IF gate_record.to_stage = 'scaled' THEN
        SELECT pg_catalog.count(*) AS total,
               pg_catalog.count(*) FILTER (WHERE gate.status IN ('passed', 'waived')) AS satisfied,
               pg_catalog.count(*) FILTER (
                   WHERE gate.status IN ('passed', 'waived')
                     AND gate.approved_by_party_id IS NULL
               ) AS unapproved_satisfied
          INTO scale_gate_record
          FROM public.solution_scale_gate AS gate
         WHERE gate.solution_id = solution_record.id
           AND gate.scope_type = 'location'
           AND gate.scope_id = requested_location_id;
        IF scale_gate_record.total = 0
           OR scale_gate_record.satisfied <> scale_gate_record.total
           OR scale_gate_record.unapproved_satisfied <> 0 THEN
            RAISE EXCEPTION 'All approved location scale gates must be satisfied before scaling'
                USING ERRCODE = '55000';
        END IF;
    END IF;

    IF gate_record.to_stage = 'funded'
       AND NOT EXISTS (
           SELECT 1
             FROM public.solution_funding_case AS funding_case
            WHERE funding_case.solution_id = solution_record.id
              AND funding_case.decision_status = 'approved'
              AND funding_case.approved_by_party_id IS NOT NULL
       ) THEN
        RAISE EXCEPTION 'An approved funding case is required before funding'
            USING ERRCODE = '55000';
    END IF;

    UPDATE public.solution AS solution
       SET current_stage = gate_record.to_stage,
           updated_at = pg_catalog.clock_timestamp()
     WHERE solution.id = solution_record.id
    RETURNING solution.status INTO solution_record.status;

    INSERT INTO public.solution_lifecycle_event (
        solution_id, from_stage, to_stage, rationale, evidence, rollback_plan,
        actor_party_id, approved_by_party_id
    ) VALUES (
        solution_record.id, gate_record.from_stage, gate_record.to_stage,
        requested_rationale, requested_evidence, requested_rollback_plan,
        actor_party_id, gate_record.approved_by_party_id
    )
    RETURNING id, created_at INTO event_record;

    INSERT INTO public.solution_gate_transition_submission_receipt (
        operator_id, actor_party_id, location_id, solution_id, gate_id,
        lifecycle_event_id, request_id, payload_digest, from_stage, to_stage,
        solution_status, transitioned_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        solution_record.id, gate_record.id, event_record.id,
        requested_request_id, payload_digest, gate_record.from_stage,
        gate_record.to_stage, solution_record.status, event_record.created_at
    );
    RETURN QUERY SELECT event_record.id, solution_record.id, gate_record.id,
                        gate_record.from_stage::TEXT, gate_record.to_stage::TEXT,
                        solution_record.status::TEXT, event_record.created_at, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_gate_transitioner;
ALTER FUNCTION kokonut_security.transition_location_solution_gate(
    UUID, UUID, UUID, TEXT, JSONB, TEXT
) OWNER TO kokonut_solution_gate_transitioner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_gate_transitioner;
REVOKE ALL ON FUNCTION kokonut_security.transition_location_solution_gate(
    UUID, UUID, UUID, TEXT, JSONB, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.transition_location_solution_gate(
            UUID, UUID, UUID, TEXT, JSONB, TEXT
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.transition_location_solution_gate(
            UUID, UUID, UUID, TEXT, JSONB, TEXT
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_gate_transition_submission_receipt IS
'Private append-only receipts for exact-location promotion gate transitions.';
COMMENT ON FUNCTION kokonut_security.transition_location_solution_gate(
    UUID, UUID, UUID, TEXT, JSONB, TEXT
) IS
'Advances only an exact location-origin solution through an already approved, latest-passing promotion gate after legacy lifecycle prerequisites pass; the stage update, lifecycle event, and retry receipt commit atomically.';

COMMIT;
