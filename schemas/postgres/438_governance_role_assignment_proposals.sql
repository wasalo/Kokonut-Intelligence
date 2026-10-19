-- Add an idempotent, tenant-scoped nomination path for governance roles.
-- This path can only create proposed assignments; approval remains separate.

BEGIN;

CREATE TABLE IF NOT EXISTS public.governance_role_assignment_request (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    assignment_id UUID NOT NULL UNIQUE
        REFERENCES public.governance_role_assignment(id) ON DELETE RESTRICT,
    role_id UUID NOT NULL REFERENCES public.governance_role(id) ON DELETE RESTRICT,
    party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    requested_by_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    assignment_type TEXT NOT NULL
        CHECK (assignment_type IN ('primary', 'delegate', 'representative', 'interim')),
    mandate TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id),
    CHECK (assignment_type <> 'delegate' OR NULLIF(BTRIM(mandate), '') IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_governance_role_assignment_request_assignment
    ON public.governance_role_assignment_request(assignment_id);

CREATE OR REPLACE FUNCTION public.prevent_governance_role_assignment_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'governance role assignment request history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_governance_role_assignment_request_immutable
    ON public.governance_role_assignment_request;
CREATE TRIGGER trg_governance_role_assignment_request_immutable
    BEFORE UPDATE OR DELETE ON public.governance_role_assignment_request
    FOR EACH ROW EXECUTE FUNCTION public.prevent_governance_role_assignment_request_mutation();

REVOKE ALL ON TABLE public.governance_role_assignment_request FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_role_assignment FROM PUBLIC;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_governance_action_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_governance_action_owner;
GRANT SELECT ON TABLE public.governance_role, public.governance_circle,
    public.governance_role_assignment TO kokonut_governance_action_owner;
GRANT UPDATE (id) ON TABLE public.governance_role, public.governance_circle
    TO kokonut_governance_action_owner;
GRANT INSERT (
    role_id, party_id, assignment_type, status, assigned_by_party_id,
    mandate, effective_from, review_due_at
) ON TABLE public.governance_role_assignment TO kokonut_governance_action_owner;
GRANT SELECT, INSERT ON TABLE public.governance_role_assignment_request
    TO kokonut_governance_action_owner;
GRANT SELECT ON TABLE public.operator_governance_party_binding,
    public.operator_identity, public.party TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_governance_action_owner;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_role_assignment
            FROM kokonut_runtime;
        REVOKE ALL ON TABLE public.governance_role_assignment_request
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE INSERT, UPDATE, DELETE ON TABLE public.governance_role_assignment
            FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.governance_role_assignment_request
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.propose_governance_role_assignment(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_role_id UUID,
    requested_party_id UUID,
    requested_assignment_type TEXT,
    requested_mandate TEXT DEFAULT NULL
)
RETURNS TABLE (
    assignment_id UUID,
    role_id UUID,
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
    normalized_mandate TEXT;
    prior_request public.governance_role_assignment_request%ROWTYPE;
    assignment_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_request_id IS NULL
       OR requested_role_id IS NULL
       OR requested_party_id IS NULL THEN
        RAISE EXCEPTION 'role assignment proposal requires a signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_roles', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'role assignment proposal requires an active tenant grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_assignment_type IS NULL OR requested_assignment_type NOT IN
       ('primary', 'delegate', 'representative', 'interim') THEN
        RAISE EXCEPTION 'role assignment type is invalid' USING ERRCODE = '22023';
    END IF;
    IF requested_mandate IS NOT NULL AND CHAR_LENGTH(requested_mandate) > 2000 THEN
        RAISE EXCEPTION 'role assignment mandate exceeds the allowed length'
            USING ERRCODE = '22023';
    END IF;
    normalized_mandate := NULLIF(BTRIM(requested_mandate), '');
    IF requested_assignment_type = 'delegate' AND normalized_mandate IS NULL THEN
        RAISE EXCEPTION 'delegated role assignments require a mandate'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id INTO requester_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.party AS requester
        ON requester.id = binding.party_id
       AND requester.party_type = 'person'
       AND requester.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, requester;
    IF requester_party_id IS NULL THEN
        RAISE EXCEPTION 'operator has no active governance person binding'
            USING ERRCODE = '42501';
    END IF;

    -- Serialize retries with the same OIDC operator and request key.
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT request.* INTO prior_request
      FROM public.governance_role_assignment_request AS request
     WHERE request.operator_id = context_record.actor_id
       AND request.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_request.role_id IS DISTINCT FROM requested_role_id
           OR prior_request.party_id IS DISTINCT FROM requested_party_id
           OR prior_request.requested_by_party_id IS DISTINCT FROM requester_party_id
           OR prior_request.assignment_type IS DISTINCT FROM requested_assignment_type
           OR prior_request.mandate IS DISTINCT FROM normalized_mandate THEN
            RAISE EXCEPTION 'role assignment request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        SELECT assignment.id, assignment.role_id, assignment.assignment_type,
               assignment.status, assignment.created_at
          INTO assignment_record
          FROM public.governance_role_assignment AS assignment
         WHERE assignment.id = prior_request.assignment_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'role assignment proposal history is inconsistent'
                USING ERRCODE = '55000';
        END IF;
        assignment_id := assignment_record.id;
        role_id := assignment_record.role_id;
        assignment_type := assignment_record.assignment_type;
        status := assignment_record.status;
        created_at := assignment_record.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    PERFORM role.id
      FROM public.governance_role AS role
      JOIN public.governance_circle AS circle ON circle.id = role.circle_id
     WHERE role.id = requested_role_id
       AND role.status IN ('approved', 'active')
       AND circle.status = 'active'
       AND circle.scope_type = 'location'
       AND circle.scope_id = requested_location_id
     FOR SHARE OF role, circle;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'role is not available for proposals at this location'
            USING ERRCODE = '22023';
    END IF;

    PERFORM candidate.id
      FROM public.party AS candidate
     WHERE candidate.id = requested_party_id
       AND candidate.status = 'active'
     FOR SHARE OF candidate;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'active nomination party was not found'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.governance_role_assignment AS assignment (
        role_id, party_id, assignment_type, status, assigned_by_party_id,
        mandate, effective_from
    ) VALUES (
        requested_role_id, requested_party_id, requested_assignment_type,
        'proposed', requester_party_id, normalized_mandate, NULL
    )
    RETURNING assignment.id, assignment.role_id, assignment.assignment_type,
              assignment.status, assignment.created_at
         INTO assignment_record;

    INSERT INTO public.governance_role_assignment_request (
        operator_id, request_id, assignment_id, role_id, party_id,
        requested_by_party_id, assignment_type, mandate
    ) VALUES (
        context_record.actor_id, requested_request_id, assignment_record.id,
        requested_role_id, requested_party_id, requester_party_id,
        requested_assignment_type, normalized_mandate
    );

    assignment_id := assignment_record.id;
    role_id := assignment_record.role_id;
    assignment_type := assignment_record.assignment_type;
    status := assignment_record.status;
    created_at := assignment_record.created_at;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.propose_governance_role_assignment(UUID, UUID, UUID, UUID, TEXT, TEXT)
    OWNER TO kokonut_governance_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.propose_governance_role_assignment(UUID, UUID, UUID, UUID, TEXT, TEXT)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.propose_governance_role_assignment(UUID, UUID, UUID, UUID, TEXT, TEXT)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.governance_role_assignment_request
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_governance_action_owner;
REVOKE ALL ON TABLE public.governance_role_assignment_request FROM PUBLIC;

COMMENT ON TABLE public.governance_role_assignment_request IS
    'Append-only idempotency and actor attribution ledger for Gateway governance role nominations; it is not an approval record.';
COMMENT ON FUNCTION kokonut_security.propose_governance_role_assignment(UUID, UUID, UUID, UUID, TEXT, TEXT) IS
    'Creates only a proposed, location-scoped governance role assignment under a signed operator grant. It cannot approve or activate the nomination.';

COMMIT;
