-- Preserve approval behavior for gates that do not require independent human review.

BEGIN;

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
    IF gate_requires_human_approval IS TRUE
       AND (latest_evaluation.evaluated_by_party_id IS NULL
            OR latest_evaluation.evaluated_by_party_id = reviewer_party_id) THEN
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

COMMENT ON FUNCTION kokonut_security.approve_location_solution_gate(UUID, UUID, UUID) IS
'Approves an exact location-origin gate with a latest passing evaluation; distinct active human attribution is required when the gate requires human approval. Approval and its append-only request receipt are atomic and retry-safe.';

COMMIT;
