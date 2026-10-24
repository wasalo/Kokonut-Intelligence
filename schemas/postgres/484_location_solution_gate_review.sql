-- Private gate evidence review and independent location-scoped approval.

BEGIN;

DO $$
DECLARE
    target_role TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_solution_gate_reviewer',
        'kokonut_solution_gate_approver'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                target_role
            );
        ELSIF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE rolname = target_role
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'Solution gate review role has unsafe attributes: %', target_role;
        END IF;
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_auth_members AS membership
              JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
              JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
             WHERE granted_role.rolname = target_role OR member_role.rolname = target_role
        ) THEN
            RAISE EXCEPTION 'Solution gate review role must not have memberships: %', target_role;
        END IF;
    END LOOP;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_gate_approval_submission_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    gate_id UUID NOT NULL UNIQUE REFERENCES public.solution_stage_gate(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_gate_approval_submission_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_gate_approval_submission_receipt
    FROM kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;

GRANT SELECT (id, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (id, solution_id, from_stage, to_stage, requires_human_approval,
              status, approved_by_party_id, approved_at)
    ON TABLE public.solution_stage_gate
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (id, gate_id, passed, observed, evidence, evaluated_by_party_id, evaluated_at)
    ON TABLE public.solution_gate_evaluation
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
-- PostgreSQL requires UPDATE privilege on a table to lock its rows. These
-- primary-key-only grants do not allow changing the business fields.
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding,
    public.operator_identity, public.party
    TO kokonut_solution_gate_approver;
GRANT UPDATE (id, status, approved_by_party_id, approved_at)
    ON TABLE public.solution_stage_gate TO kokonut_solution_gate_approver;
GRANT SELECT (id, operator_id, reviewer_party_id, location_id, gate_id,
              request_id, approved_at)
    ON TABLE public.solution_gate_approval_submission_receipt
    TO kokonut_solution_gate_approver;
GRANT INSERT (operator_id, reviewer_party_id, location_id, gate_id,
              request_id, approved_at)
    ON TABLE public.solution_gate_approval_submission_receipt
    TO kokonut_solution_gate_approver;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_gate_review(
    requested_location_id UUID,
    requested_gate_id UUID
)
RETURNS TABLE (
    gate_id UUID,
    from_stage TEXT,
    to_stage TEXT,
    requires_human_approval BOOLEAN,
    gate_status TEXT,
    evaluation_passed BOOLEAN,
    observed JSONB,
    evidence JSONB,
    evaluated_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
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
       OR requested_location_id IS NULL OR requested_gate_id IS NULL THEN
        RAISE EXCEPTION 'Solution gate review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution gate review requires an active exact location grant'
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
        RAISE EXCEPTION 'Solution gate review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT gate.id, gate.from_stage::TEXT, gate.to_stage::TEXT,
           gate.requires_human_approval, gate.status::TEXT,
           latest.passed, latest.observed, latest.evidence, latest.evaluated_at
      FROM public.solution_stage_gate AS gate
      JOIN public.solution AS solution ON solution.id = gate.solution_id
      LEFT JOIN LATERAL (
          SELECT evaluation.passed, evaluation.observed, evaluation.evidence,
                 evaluation.evaluated_at
            FROM public.solution_gate_evaluation AS evaluation
           WHERE evaluation.gate_id = gate.id
           ORDER BY evaluation.evaluated_at DESC, evaluation.id DESC
           LIMIT 1
      ) AS latest ON TRUE
     WHERE gate.id = requested_gate_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.approve_location_solution_gate(
    requested_location_id UUID,
    requested_gate_id UUID,
    requested_request_id UUID
)
RETURNS TABLE (
    gate_id UUID,
    gate_status TEXT,
    approved_at TIMESTAMPTZ,
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
    gate_status TEXT;
    gate_requires_human_approval BOOLEAN;
    latest_evaluation RECORD;
    existing RECORD;
    saved_approval RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_gate_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Solution gate approval requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution gate approval requires an active exact location grant'
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
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, reviewer;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Solution gate approval requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.gate_id, receipt.reviewer_party_id,
           receipt.approved_at
      INTO existing
      FROM public.solution_gate_approval_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.gate_id IS DISTINCT FROM requested_gate_id
           OR existing.reviewer_party_id IS DISTINCT FROM reviewer_party_id THEN
            RAISE EXCEPTION 'Solution gate approval request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT existing.gate_id, 'approved'::TEXT,
                            existing.approved_at, TRUE;
        RETURN;
    END IF;

    SELECT gate.status, gate.requires_human_approval
      INTO gate_status, gate_requires_human_approval
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
        RAISE EXCEPTION 'Only draft or ready solution gates can be approved'
            USING ERRCODE = '55000';
    END IF;
    IF gate_requires_human_approval IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'This solution gate does not require human approval'
            USING ERRCODE = '55000';
    END IF;

    SELECT evaluation.passed, evaluation.evaluated_by_party_id
      INTO latest_evaluation
      FROM public.solution_gate_evaluation AS evaluation
     WHERE evaluation.gate_id = requested_gate_id
     ORDER BY evaluation.evaluated_at DESC, evaluation.id DESC
     LIMIT 1;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'A latest passing gate evaluation is required before approval'
            USING ERRCODE = '55000';
    END IF;
    IF latest_evaluation.passed IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'A latest passing gate evaluation is required before approval'
            USING ERRCODE = '55000';
    END IF;
    IF latest_evaluation.evaluated_by_party_id IS NULL
       OR latest_evaluation.evaluated_by_party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Gate approval requires a human reviewer distinct from the evaluator'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.solution_stage_gate AS gate
       SET status = 'approved', approved_by_party_id = reviewer_party_id,
           approved_at = pg_catalog.clock_timestamp()
     WHERE gate.id = requested_gate_id
       AND gate.status IN ('draft', 'ready')
    RETURNING gate.id, gate.status::TEXT, gate.approved_at
         INTO saved_approval;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Solution gate changed before approval could be recorded'
            USING ERRCODE = '40001';
    END IF;
    INSERT INTO public.solution_gate_approval_submission_receipt (
        operator_id, reviewer_party_id, location_id, gate_id, request_id, approved_at
    ) VALUES (
        context_record.actor_id, reviewer_party_id, requested_location_id,
        requested_gate_id, requested_request_id, saved_approval.approved_at
    );
    RETURN QUERY SELECT saved_approval.id, saved_approval.status,
                        saved_approval.approved_at, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
ALTER FUNCTION kokonut_security.location_solution_gate_review(UUID, UUID)
    OWNER TO kokonut_solution_gate_reviewer;
ALTER FUNCTION kokonut_security.approve_location_solution_gate(UUID, UUID, UUID)
    OWNER TO kokonut_solution_gate_approver;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_gate_reviewer, kokonut_solution_gate_approver;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_gate_review(UUID, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.approve_location_solution_gate(UUID, UUID, UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_solution_gate_review(UUID, UUID)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.approve_location_solution_gate(UUID, UUID, UUID)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_solution_gate_review(UUID, UUID)
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.approve_location_solution_gate(UUID, UUID, UUID)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_gate_approval_submission_receipt IS
'Private append-only idempotency receipts for independently reviewed, exact-location solution-gate approvals.';
COMMENT ON FUNCTION kokonut_security.location_solution_gate_review(UUID, UUID) IS
'Returns the latest bounded gate evaluation evidence only under a signed exact-location solution_lifecycle:review grant and active human binding; evaluator identity is withheld.';
COMMENT ON FUNCTION kokonut_security.approve_location_solution_gate(UUID, UUID, UUID) IS
'Approves an exact location-origin gate only after a latest passing evaluation by a different active human party; approval and its append-only request receipt are atomic and retry-safe.';

COMMIT;
