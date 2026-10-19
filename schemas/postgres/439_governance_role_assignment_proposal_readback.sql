-- Allow an operator to review only their own role assignment nominations.
-- Approval and nominee identity remain outside this projection.

BEGIN;

CREATE OR REPLACE FUNCTION kokonut_security.list_my_governance_role_assignment_proposals(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 51,
    before_created_at TIMESTAMPTZ DEFAULT NULL,
    before_assignment_id UUID DEFAULT NULL
)
RETURNS TABLE (
    request_id UUID,
    assignment_id UUID,
    role_id UUID,
    role_key TEXT,
    role_name TEXT,
    assignment_type TEXT,
    status TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    requester_party_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'role proposal readback requires a signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_roles', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'role proposal readback requires an active tenant grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 101
       OR ((before_created_at IS NULL) <> (before_assignment_id IS NULL)) THEN
        RAISE EXCEPTION 'role proposal readback pagination is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id INTO requester_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.party AS requester
        ON requester.id = binding.party_id
       AND requester.party_type = 'person'
       AND requester.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF requester_party_id IS NULL THEN
        RAISE EXCEPTION 'operator has no active governance person binding'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT request.request_id, assignment.id, role.id,
           role.role_key::TEXT, role.name::TEXT,
           assignment.assignment_type::TEXT, assignment.status::TEXT,
           assignment.created_at
      FROM public.governance_role_assignment_request AS request
      JOIN public.governance_role_assignment AS assignment
        ON assignment.id = request.assignment_id
       AND assignment.assigned_by_party_id = requester_party_id
      JOIN public.governance_role AS role ON role.id = assignment.role_id
      JOIN public.governance_circle AS circle ON circle.id = role.circle_id
     WHERE request.operator_id = context_record.actor_id
       AND request.requested_by_party_id = requester_party_id
       AND circle.scope_type = 'location'
       AND circle.scope_id = requested_location_id
       AND (before_created_at IS NULL OR
            (assignment.created_at, assignment.id) <
            (before_created_at, before_assignment_id))
     ORDER BY assignment.created_at DESC, assignment.id DESC
     LIMIT requested_limit;
END;
$$;

ALTER FUNCTION kokonut_security.list_my_governance_role_assignment_proposals(UUID, INTEGER, TIMESTAMPTZ, UUID)
    OWNER TO kokonut_governance_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.list_my_governance_role_assignment_proposals(UUID, INTEGER, TIMESTAMPTZ, UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.list_my_governance_role_assignment_proposals(UUID, INTEGER, TIMESTAMPTZ, UUID)
            TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_my_governance_role_assignment_proposals(UUID, INTEGER, TIMESTAMPTZ, UUID) IS
    'Returns a bounded, location-scoped status projection for nominations created by the signed operator; excludes nominee identity and approval controls.';

COMMIT;
