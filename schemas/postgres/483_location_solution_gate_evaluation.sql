-- Attributed, idempotent location-origin solution-gate evaluations.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_gate_evaluator'
    ) THEN
        CREATE ROLE kokonut_solution_gate_evaluator
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_gate_evaluator'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution gate evaluator role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_gate_evaluator'
            OR member_role.rolname = 'kokonut_solution_gate_evaluator'
    ) THEN
        RAISE EXCEPTION 'Solution gate evaluator role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_gate_evaluation_submission_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    evaluator_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    gate_id UUID NOT NULL REFERENCES public.solution_stage_gate(id) ON DELETE RESTRICT,
    evaluation_id UUID NOT NULL UNIQUE REFERENCES public.solution_gate_evaluation(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_gate_evaluation_submission_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_gate_evaluation_submission_receipt
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_solution_gate_evaluator;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_solution_gate_evaluator;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_solution_gate_evaluator;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_solution_gate_evaluator;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_solution_gate_evaluator;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_solution_gate_evaluator;

GRANT SELECT (id, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_gate_evaluator;
GRANT SELECT (id, solution_id, status)
    ON TABLE public.solution_stage_gate TO kokonut_solution_gate_evaluator;
GRANT UPDATE (id) ON TABLE public.solution_stage_gate TO kokonut_solution_gate_evaluator;
GRANT SELECT (id, gate_id, passed, observed, evidence, evaluated_by_party_id, evaluated_at),
      INSERT (gate_id, passed, observed, evidence, evaluated_by_party_id)
    ON TABLE public.solution_gate_evaluation TO kokonut_solution_gate_evaluator;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding TO kokonut_solution_gate_evaluator;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding,
    public.operator_identity, public.party TO kokonut_solution_gate_evaluator;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity TO kokonut_solution_gate_evaluator;
GRANT SELECT (id, party_type, status) ON TABLE public.party TO kokonut_solution_gate_evaluator;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_solution_gate_evaluator;
GRANT SELECT (id, organization_id) ON TABLE public.location TO kokonut_solution_gate_evaluator;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership TO kokonut_solution_gate_evaluator;
GRANT SELECT (id, status) ON TABLE public.organization TO kokonut_solution_gate_evaluator;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification TO kokonut_solution_gate_evaluator;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share TO kokonut_solution_gate_evaluator;
GRANT SELECT (id, operator_id, evaluator_party_id, location_id, gate_id,
              evaluation_id, request_id, created_at)
    ON TABLE public.solution_gate_evaluation_submission_receipt
    TO kokonut_solution_gate_evaluator;
GRANT INSERT (operator_id, evaluator_party_id, location_id, gate_id,
              evaluation_id, request_id)
    ON TABLE public.solution_gate_evaluation_submission_receipt
    TO kokonut_solution_gate_evaluator;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_gate_evaluator;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_gate_evaluator;

CREATE OR REPLACE FUNCTION kokonut_security.record_location_solution_gate_evaluation(
    requested_location_id UUID,
    requested_gate_id UUID,
    requested_request_id UUID,
    requested_passed BOOLEAN,
    requested_observed JSONB,
    requested_evidence JSONB
)
RETURNS TABLE (
    evaluation_id UUID,
    gate_id UUID,
    passed BOOLEAN,
    evaluated_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    evaluator_party_id UUID;
    gate_status TEXT;
    existing RECORD;
    created_evaluation RECORD;
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
        RAISE EXCEPTION 'Solution gate evaluation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution gate evaluation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_passed IS NULL
       OR requested_observed IS NULL
       OR pg_catalog.jsonb_typeof(requested_observed) IS DISTINCT FROM 'object'
       OR requested_evidence IS NULL
       OR pg_catalog.jsonb_typeof(requested_evidence) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_evidence) NOT BETWEEN 1 AND 100
       OR pg_catalog.octet_length(requested_observed::TEXT) > 65536
       OR pg_catalog.octet_length(requested_evidence::TEXT) > 65536 THEN
        RAISE EXCEPTION 'Solution gate evaluation payload is invalid or exceeds its bounds'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id
      INTO evaluator_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS evaluator
        ON evaluator.id = binding.party_id
       AND evaluator.party_type = 'person'
       AND evaluator.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, evaluator;
    IF evaluator_party_id IS NULL THEN
        RAISE EXCEPTION 'Operator has no active human governance-party binding'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT receipt.location_id, receipt.evaluation_id, evaluation.gate_id, evaluation.passed,
           evaluation.observed, evaluation.evidence, evaluation.evaluated_by_party_id,
           evaluation.evaluated_at
      INTO existing
      FROM public.solution_gate_evaluation_submission_receipt AS receipt
      JOIN public.solution_gate_evaluation AS evaluation
        ON evaluation.id = receipt.evaluation_id
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.gate_id IS DISTINCT FROM requested_gate_id
           OR existing.passed IS DISTINCT FROM requested_passed
           OR existing.observed IS DISTINCT FROM requested_observed
           OR existing.evidence IS DISTINCT FROM requested_evidence
           OR existing.evaluated_by_party_id IS DISTINCT FROM evaluator_party_id THEN
            RAISE EXCEPTION 'Solution gate evaluation request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT existing.evaluation_id, existing.gate_id,
                            existing.passed, existing.evaluated_at, TRUE;
        RETURN;
    END IF;

    SELECT gate.status
      INTO gate_status
      FROM public.solution_stage_gate AS gate
      JOIN public.solution AS solution ON solution.id = gate.solution_id
     WHERE gate.id = requested_gate_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR UPDATE OF gate;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location-origin solution gate was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF gate_status NOT IN ('draft', 'ready') THEN
        RAISE EXCEPTION 'Only draft or ready location-origin gates can be evaluated'
            USING ERRCODE = '55000';
    END IF;

    INSERT INTO public.solution_gate_evaluation (
        gate_id, passed, observed, evidence, evaluated_by_party_id
    ) VALUES (
        requested_gate_id, requested_passed, requested_observed,
        requested_evidence, evaluator_party_id
    ) RETURNING id, gate_id, passed, evaluated_at
      INTO created_evaluation;

    INSERT INTO public.solution_gate_evaluation_submission_receipt (
        operator_id, evaluator_party_id, location_id, gate_id, evaluation_id, request_id
    ) VALUES (
        context_record.actor_id, evaluator_party_id, requested_location_id,
        requested_gate_id, created_evaluation.id, requested_request_id
    );

    RETURN QUERY SELECT created_evaluation.id, created_evaluation.gate_id,
                        created_evaluation.passed, created_evaluation.evaluated_at, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_gate_evaluator;
ALTER FUNCTION kokonut_security.record_location_solution_gate_evaluation(
    UUID, UUID, UUID, BOOLEAN, JSONB, JSONB
) OWNER TO kokonut_solution_gate_evaluator;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_gate_evaluator;
REVOKE ALL ON FUNCTION kokonut_security.record_location_solution_gate_evaluation(
    UUID, UUID, UUID, BOOLEAN, JSONB, JSONB
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.record_location_solution_gate_evaluation(
            UUID, UUID, UUID, BOOLEAN, JSONB, JSONB
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.record_location_solution_gate_evaluation(
            UUID, UUID, UUID, BOOLEAN, JSONB, JSONB
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_gate_evaluation_submission_receipt IS
'Append-only idempotency receipts for exact-location solution-gate evaluations submitted through the scoped Kernel action.';
COMMENT ON FUNCTION kokonut_security.record_location_solution_gate_evaluation(
    UUID, UUID, UUID, BOOLEAN, JSONB, JSONB
) IS
'Records an attributed location-origin solution-gate evaluation under a signed exact solution_lifecycle:create grant; evidence and observed values are bounded, retries are idempotent, and this action does not approve the gate.';

COMMIT;
