-- Add explicit, independent human review for proposed governance assignments.

BEGIN;

CREATE TABLE IF NOT EXISTS public.governance_role_assignment_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    decision_request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    assignment_id UUID NOT NULL UNIQUE
        REFERENCES public.governance_role_assignment(id) ON DELETE RESTRICT,
    role_id UUID NOT NULL REFERENCES public.governance_role(id) ON DELETE RESTRICT,
    submitted_by_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
    reason TEXT NOT NULL CHECK (
        NULLIF(BTRIM(reason), '') IS NOT NULL AND CHAR_LENGTH(reason) <= 4000
    ),
    result_status TEXT NOT NULL CHECK (result_status IN ('active', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, decision_request_id),
    CHECK (submitted_by_party_id <> reviewer_party_id),
    CHECK ((decision = 'approve' AND result_status = 'active')
        OR (decision = 'reject' AND result_status = 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_governance_role_assignment_decision_location
    ON public.governance_role_assignment_decision(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_governance_role_assignment_decision_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'governance role assignment decision history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_role_assignment_decision_immutable
    ON public.governance_role_assignment_decision;
CREATE TRIGGER trg_governance_role_assignment_decision_immutable
    BEFORE UPDATE OR DELETE ON public.governance_role_assignment_decision
    FOR EACH ROW EXECUTE FUNCTION public.prevent_governance_role_assignment_decision_mutation();

REVOKE ALL ON TABLE public.governance_role_assignment_decision FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE public.governance_role_assignment_decision
    TO kokonut_governance_action_owner;
GRANT UPDATE (status, approved_by_party_id, effective_from, approval_evidence, updated_at)
    ON TABLE public.governance_role_assignment TO kokonut_governance_action_owner;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding, public.party,
    public.governance_role, public.governance_circle TO kokonut_governance_action_owner;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE public.governance_role_assignment_decision FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.governance_role_assignment_decision FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_governance_role_assignment_review_queue(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 51,
    before_created_at TIMESTAMPTZ DEFAULT NULL,
    before_assignment_id UUID DEFAULT NULL
)
RETURNS TABLE (
    assignment_id UUID,
    request_id UUID,
    role_id UUID,
    role_key TEXT,
    role_name TEXT,
    nominee_party_id UUID,
    nominee_name TEXT,
    nominee_status TEXT,
    submitted_by_party_id UUID,
    submitted_by_name TEXT,
    assignment_type TEXT,
    mandate TEXT,
    role_status TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    bound_reviewer_party_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'assignment review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_roles', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'assignment review queue requires an active review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 101
       OR ((before_created_at IS NULL) <> (before_assignment_id IS NULL)) THEN
        RAISE EXCEPTION 'assignment review queue pagination is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id INTO bound_reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id
       AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF bound_reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'reviewer has no active governance person binding'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT assignment.id, request.request_id, role.id,
           role.role_key::TEXT, role.name::TEXT,
           nominee.id, nominee.display_name::TEXT, nominee.status::TEXT,
           submitter.id, submitter.display_name::TEXT,
           assignment.assignment_type::TEXT, assignment.mandate,
           role.status::TEXT, assignment.created_at
      FROM public.governance_role_assignment AS assignment
      JOIN public.governance_role_assignment_request AS request
        ON request.assignment_id = assignment.id
       AND request.requested_by_party_id = assignment.assigned_by_party_id
      JOIN public.governance_role AS role ON role.id = assignment.role_id
      JOIN public.governance_circle AS circle ON circle.id = role.circle_id
      JOIN public.party AS nominee ON nominee.id = assignment.party_id
      JOIN public.party AS submitter ON submitter.id = assignment.assigned_by_party_id
     WHERE assignment.status = 'proposed'
       AND circle.status = 'active'
       AND circle.scope_type = 'location'
       AND circle.scope_id = requested_location_id
       AND role.status IN ('approved', 'active')
       AND (before_created_at IS NULL OR
            (assignment.created_at, assignment.id) <
            (before_created_at, before_assignment_id))
     ORDER BY assignment.created_at DESC, assignment.id DESC
     LIMIT requested_limit;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.decide_governance_role_assignment(
    requested_location_id UUID,
    requested_role_id UUID,
    requested_assignment_id UUID,
    requested_decision_request_id UUID,
    requested_decision TEXT,
    requested_reason TEXT
)
RETURNS TABLE (
    decision_id UUID,
    assignment_id UUID,
    decision TEXT,
    assignment_status TEXT,
    reviewer_party_id UUID,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    bound_reviewer_party_id UUID;
    required_action TEXT;
    normalized_reason TEXT;
    prior_decision public.governance_role_assignment_decision%ROWTYPE;
    assignment_record RECORD;
    new_decision_id UUID;
    resulting_status TEXT;
    decision_created_at TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_role_id IS NULL
       OR requested_assignment_id IS NULL
       OR requested_decision_request_id IS NULL THEN
        RAISE EXCEPTION 'assignment decision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision IS NULL OR requested_decision NOT IN ('approve', 'reject') THEN
        RAISE EXCEPTION 'assignment decision is invalid' USING ERRCODE = '22023';
    END IF;
    required_action := requested_decision;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_roles', required_action, requested_location_id
    ) THEN
        RAISE EXCEPTION 'assignment decision requires a matching active tenant grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_reason IS NULL OR NULLIF(BTRIM(requested_reason), '') IS NULL
       OR CHAR_LENGTH(requested_reason) > 4000 THEN
        RAISE EXCEPTION 'assignment decision requires a reason of at most 4000 characters'
            USING ERRCODE = '22023';
    END IF;
    normalized_reason := BTRIM(requested_reason);

    SELECT binding.party_id INTO bound_reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id
       AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, reviewer;
    IF bound_reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'reviewer has no active governance person binding'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_decision_request_id::TEXT, 0
        )
    );
    SELECT decision_row.* INTO prior_decision
      FROM public.governance_role_assignment_decision AS decision_row
     WHERE decision_row.operator_id = context_record.actor_id
       AND decision_row.decision_request_id = requested_decision_request_id;
    IF FOUND THEN
        IF prior_decision.location_id IS DISTINCT FROM requested_location_id
           OR prior_decision.role_id IS DISTINCT FROM requested_role_id
           OR prior_decision.assignment_id IS DISTINCT FROM requested_assignment_id
           OR prior_decision.reviewer_party_id IS DISTINCT FROM bound_reviewer_party_id
           OR prior_decision.decision IS DISTINCT FROM requested_decision
           OR prior_decision.reason IS DISTINCT FROM normalized_reason THEN
            RAISE EXCEPTION 'assignment decision request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        decision_id := prior_decision.id;
        assignment_id := prior_decision.assignment_id;
        decision := prior_decision.decision;
        assignment_status := prior_decision.result_status;
        reviewer_party_id := prior_decision.reviewer_party_id;
        created_at := prior_decision.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT assignment.id, assignment.role_id, assignment.party_id,
           assignment.assigned_by_party_id, assignment.status,
           role.status AS role_status, circle.status AS circle_status,
           circle.scope_type, circle.scope_id,
           nominee.party_type AS nominee_party_type,
           nominee.status AS nominee_status,
           request.operator_id AS submitter_operator_id,
           request.requested_by_party_id AS submitter_party_id
      INTO assignment_record
      FROM public.governance_role_assignment AS assignment
      JOIN public.governance_role AS role ON role.id = assignment.role_id
      JOIN public.governance_circle AS circle ON circle.id = role.circle_id
      JOIN public.party AS nominee ON nominee.id = assignment.party_id
      JOIN public.governance_role_assignment_request AS request
        ON request.assignment_id = assignment.id
       AND request.requested_by_party_id = assignment.assigned_by_party_id
     WHERE assignment.id = requested_assignment_id
       AND assignment.role_id = requested_role_id
     FOR UPDATE OF assignment
     FOR SHARE OF role, circle, nominee;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'assignment proposal is not available in this location'
            USING ERRCODE = '22023';
    END IF;
    IF assignment_record.scope_type IS DISTINCT FROM 'location'
       OR assignment_record.scope_id IS DISTINCT FROM requested_location_id
       OR assignment_record.circle_status IS DISTINCT FROM 'active'
       OR assignment_record.role_status NOT IN ('approved', 'active') THEN
        RAISE EXCEPTION 'assignment proposal is not available in this location'
            USING ERRCODE = '22023';
    END IF;
    IF assignment_record.status IS DISTINCT FROM 'proposed' THEN
        RAISE EXCEPTION 'assignment proposal has already been decided'
            USING ERRCODE = '55000';
    END IF;
    IF assignment_record.submitter_party_id IS NOT DISTINCT FROM bound_reviewer_party_id THEN
        RAISE EXCEPTION 'the nominating person cannot decide their own assignment'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision = 'approve'
       AND (assignment_record.role_status IS DISTINCT FROM 'active'
            OR assignment_record.nominee_party_type IS DISTINCT FROM 'person'
            OR assignment_record.nominee_status IS DISTINCT FROM 'active') THEN
        RAISE EXCEPTION 'approval requires an active role and active person nominee'
            USING ERRCODE = '22023';
    END IF;

    new_decision_id := gen_random_uuid();
    resulting_status := CASE WHEN requested_decision = 'approve' THEN 'active' ELSE 'rejected' END;
    INSERT INTO public.governance_role_assignment_decision (
        id, operator_id, decision_request_id, location_id, assignment_id,
        role_id, submitted_by_party_id, reviewer_party_id, decision,
        reason, result_status
    ) VALUES (
        new_decision_id, context_record.actor_id, requested_decision_request_id,
        requested_location_id, requested_assignment_id, requested_role_id,
        assignment_record.submitter_party_id, bound_reviewer_party_id, requested_decision,
        normalized_reason, resulting_status
    ) RETURNING public.governance_role_assignment_decision.created_at
      INTO decision_created_at;

    IF requested_decision = 'approve' THEN
        UPDATE public.governance_role_assignment AS assignment
           SET status = 'active',
               approved_by_party_id = bound_reviewer_party_id,
               effective_from = clock_timestamp(),
               approval_evidence = pg_catalog.jsonb_build_array(
                   pg_catalog.jsonb_build_object(
                       'kind', 'operator_assignment_review',
                       'decision_id', new_decision_id,
                       'decision', requested_decision
                   )
               ),
               updated_at = clock_timestamp()
         WHERE assignment.id = requested_assignment_id;
    ELSE
        UPDATE public.governance_role_assignment AS assignment
           SET status = 'rejected',
               updated_at = clock_timestamp()
         WHERE assignment.id = requested_assignment_id;
    END IF;

    decision_id := new_decision_id;
    assignment_id := requested_assignment_id;
    decision := requested_decision;
    assignment_status := resulting_status;
    reviewer_party_id := bound_reviewer_party_id;
    created_at := decision_created_at;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.list_governance_role_assignment_review_queue(UUID, INTEGER, TIMESTAMPTZ, UUID)
    OWNER TO kokonut_governance_action_owner;
ALTER FUNCTION kokonut_security.decide_governance_role_assignment(UUID, UUID, UUID, UUID, TEXT, TEXT)
    OWNER TO kokonut_governance_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.list_governance_role_assignment_review_queue(UUID, INTEGER, TIMESTAMPTZ, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.decide_governance_role_assignment(UUID, UUID, UUID, UUID, TEXT, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.list_governance_role_assignment_review_queue(UUID, INTEGER, TIMESTAMPTZ, UUID)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.decide_governance_role_assignment(UUID, UUID, UUID, UUID, TEXT, TEXT)
            TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.governance_role_assignment_decision IS
    'Append-only independent human decision records for a single proposed governance role assignment.';
COMMENT ON FUNCTION kokonut_security.list_governance_role_assignment_review_queue(UUID, INTEGER, TIMESTAMPTZ, UUID) IS
    'Returns bounded pending assignment details only under the signed operator location review grant.';
COMMENT ON FUNCTION kokonut_security.decide_governance_role_assignment(UUID, UUID, UUID, UUID, TEXT, TEXT) IS
    'Applies an idempotent approve/reject decision only under the matching signed location grant and an independent active person binding.';

COMMIT;
