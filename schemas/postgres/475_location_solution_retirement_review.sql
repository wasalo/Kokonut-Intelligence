-- Location-granted, independently attributed retirement approval with an append-only receipt.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_action_owner'
    ) THEN
        CREATE ROLE kokonut_solution_action_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_action_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution action owner role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_action_owner'
            OR member_role.rolname = 'kokonut_solution_action_owner'
    ) THEN
        RAISE EXCEPTION 'Solution action owner role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_retirement_review_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    retirement_id UUID NOT NULL REFERENCES public.solution_retirement(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    action TEXT NOT NULL CHECK (action = 'approved'),
    previous_status TEXT NOT NULL,
    resulting_status TEXT NOT NULL CHECK (resulting_status = 'approved'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id),
    UNIQUE (retirement_id, action)
);

REVOKE ALL ON TABLE public.solution_retirement_review_event FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_retirement_review_event
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_solution_action_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_solution_action_owner;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_solution_action_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_solution_action_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_solution_action_owner;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_solution_action_owner;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding TO kokonut_solution_action_owner;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity TO kokonut_solution_action_owner;
GRANT SELECT (id, party_type, status) ON TABLE public.party TO kokonut_solution_action_owner;
-- PostgreSQL requires a narrow UPDATE privilege to take row locks during review.
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding,
    public.operator_identity, public.party TO kokonut_solution_action_owner;
GRANT SELECT (id, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_action_owner;
GRANT SELECT (
    id, solution_id, retirement_type, evidence_refs, replacement_solution_id,
    migration_plan, status, created_by_party_id, approved_by_party_id, approved_at
) ON TABLE public.solution_retirement TO kokonut_solution_action_owner;
GRANT UPDATE (status, approved_by_party_id, approved_at)
    ON TABLE public.solution_retirement TO kokonut_solution_action_owner;
GRANT SELECT, INSERT ON TABLE public.solution_retirement_review_event
    TO kokonut_solution_action_owner;

GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_solution_action_owner;
GRANT SELECT (id, organization_id) ON TABLE public.location TO kokonut_solution_action_owner;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership TO kokonut_solution_action_owner;
GRANT SELECT (id, status) ON TABLE public.organization TO kokonut_solution_action_owner;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification TO kokonut_solution_action_owner;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share TO kokonut_solution_action_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_action_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_action_owner;

CREATE OR REPLACE FUNCTION kokonut_security.approve_location_solution_retirement(
    requested_location_id UUID,
    requested_retirement_id UUID,
    requested_request_id UUID
)
RETURNS TABLE (
    event_id UUID,
    retirement_id UUID,
    retirement_status TEXT,
    approved_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    reviewer_party_id UUID;
    selected_retirement RECORD;
    existing_event RECORD;
    approval_timestamp TIMESTAMPTZ;
    generated_event_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_retirement_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Solution retirement review requires signed operator location context and request identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution retirement review requires an active exact location grant'
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
     FOR SHARE OF binding, operator, reviewer;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Operator has no active human governance-party binding'
            USING ERRCODE = '42501';
    END IF;

    SELECT review_event.id, review_event.location_id, review_event.retirement_id,
           review_event.reviewer_party_id, review_event.resulting_status,
           retirement.approved_at
      INTO existing_event
      FROM public.solution_retirement_review_event AS review_event
      JOIN public.solution_retirement AS retirement
        ON retirement.id = review_event.retirement_id
     WHERE review_event.operator_id = context_record.actor_id
       AND review_event.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_event.location_id IS DISTINCT FROM requested_location_id
           OR existing_event.retirement_id IS DISTINCT FROM requested_retirement_id
           OR existing_event.reviewer_party_id IS DISTINCT FROM reviewer_party_id THEN
            RAISE EXCEPTION 'Solution retirement review request id was reused with different scope'
                USING ERRCODE = '22023';
        END IF;
        event_id := existing_event.id;
        retirement_id := existing_event.retirement_id;
        retirement_status := existing_event.resulting_status;
        approved_at := existing_event.approved_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT retirement.id, retirement.solution_id, retirement.retirement_type,
           retirement.evidence_refs, retirement.replacement_solution_id,
           retirement.migration_plan, retirement.status,
           retirement.created_by_party_id, retirement.approved_by_party_id,
           retirement.approved_at
      INTO selected_retirement
      FROM public.solution_retirement AS retirement
      JOIN public.solution AS solution
        ON solution.id = retirement.solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     WHERE retirement.id = requested_retirement_id
     FOR UPDATE OF retirement;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Solution retirement was not found for this location'
            USING ERRCODE = 'P0002';
    END IF;

    -- A concurrent identical request may have committed while this transaction waited for the row lock.
    SELECT review_event.id, review_event.location_id, review_event.retirement_id,
           review_event.reviewer_party_id, review_event.resulting_status,
           retirement.approved_at
      INTO existing_event
      FROM public.solution_retirement_review_event AS review_event
      JOIN public.solution_retirement AS retirement
        ON retirement.id = review_event.retirement_id
     WHERE review_event.operator_id = context_record.actor_id
       AND review_event.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_event.location_id IS DISTINCT FROM requested_location_id
           OR existing_event.retirement_id IS DISTINCT FROM requested_retirement_id
           OR existing_event.reviewer_party_id IS DISTINCT FROM reviewer_party_id THEN
            RAISE EXCEPTION 'Solution retirement review request id was reused with different scope'
                USING ERRCODE = '22023';
        END IF;
        event_id := existing_event.id;
        retirement_id := existing_event.retirement_id;
        retirement_status := existing_event.resulting_status;
        approved_at := existing_event.approved_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    IF selected_retirement.status NOT IN ('proposed', 'impact_review')
       OR selected_retirement.approved_by_party_id IS NOT NULL
       OR selected_retirement.approved_at IS NOT NULL THEN
        RAISE EXCEPTION 'Only unapproved proposed or impact-review retirements can be approved'
            USING ERRCODE = '55000';
    END IF;
    IF selected_retirement.created_by_party_id IS NULL
       OR selected_retirement.created_by_party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Retirement approval requires a proposer distinct from the reviewer'
            USING ERRCODE = '55000';
    END IF;
    IF pg_catalog.jsonb_typeof(selected_retirement.evidence_refs) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Retirement approval requires evidence and a migration plan'
            USING ERRCODE = '55000';
    END IF;
    IF pg_catalog.jsonb_array_length(selected_retirement.evidence_refs) = 0
       OR selected_retirement.migration_plan IS NULL
       OR pg_catalog.btrim(selected_retirement.migration_plan) = '' THEN
        RAISE EXCEPTION 'Retirement approval requires evidence and a migration plan'
            USING ERRCODE = '55000';
    END IF;
    IF selected_retirement.retirement_type = 'superseded'
       AND (selected_retirement.replacement_solution_id IS NULL
            OR selected_retirement.replacement_solution_id = selected_retirement.solution_id) THEN
        RAISE EXCEPTION 'Superseded retirement requires a distinct replacement solution'
            USING ERRCODE = '55000';
    END IF;

    approval_timestamp := clock_timestamp();
    UPDATE public.solution_retirement AS retirement
       SET status = 'approved',
           approved_by_party_id = reviewer_party_id,
           approved_at = approval_timestamp
     WHERE retirement.id = requested_retirement_id
       AND retirement.status IN ('proposed', 'impact_review')
       AND retirement.approved_by_party_id IS NULL
       AND retirement.approved_at IS NULL
     RETURNING retirement.approved_at INTO approval_timestamp;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Retirement changed before approval'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.solution_retirement_review_event (
        operator_id, reviewer_party_id, location_id, retirement_id,
        request_id, action, previous_status, resulting_status, created_at
    ) VALUES (
        context_record.actor_id, reviewer_party_id, requested_location_id,
        requested_retirement_id, requested_request_id, 'approved',
        selected_retirement.status, 'approved', approval_timestamp
    ) RETURNING id INTO generated_event_id;

    event_id := generated_event_id;
    retirement_id := requested_retirement_id;
    retirement_status := 'approved';
    approved_at := approval_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_action_owner;
ALTER FUNCTION kokonut_security.approve_location_solution_retirement(UUID, UUID, UUID)
    OWNER TO kokonut_solution_action_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.approve_location_solution_retirement(UUID, UUID, UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.approve_location_solution_retirement(UUID, UUID, UUID)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.approve_location_solution_retirement(UUID, UUID, UUID)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_retirement_review_event IS
'Append-only receipt for independently attributed location-scoped retirement review decisions; runtime and Directus access is through the bounded security-definer function only.';
COMMENT ON FUNCTION kokonut_security.approve_location_solution_retirement(UUID, UUID, UUID) IS
'Approves only a proposed retirement for a solution originated at the exact location under signed solution_lifecycle:review context and an active independent OIDC-to-party binding; the approval update and idempotent review receipt are atomic.';

COMMIT;
