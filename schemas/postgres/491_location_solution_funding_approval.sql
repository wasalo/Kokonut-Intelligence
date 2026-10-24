-- Record an independent human decision for a submitted location funding case.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_funding_approver'
    ) THEN
        CREATE ROLE kokonut_solution_funding_approver
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_funding_approver'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution funding approver role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_funding_approver'
            OR member_role.rolname = 'kokonut_solution_funding_approver'
    ) THEN
        RAISE EXCEPTION 'Solution funding approver role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_funding_approval_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    funding_case_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_funding_case(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    acknowledged BOOLEAN NOT NULL CHECK (acknowledged IS TRUE),
    approved_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_funding_approval_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_funding_approval_receipt
    FROM kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_funding_approver;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_funding_approver;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_funding_approver;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_funding_approver;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_funding_approver;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_funding_approver;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_funding_approver;

GRANT SELECT (id, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_funding_approver;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_funding_approver;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_funding_approver;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_funding_approver;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_funding_approver;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_funding_approver;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_funding_approver;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_funding_approver;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_funding_approver;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_funding_approver;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_funding_approver;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_funding_approver;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_funding_approver;

GRANT SELECT (id, solution_id, decision_status, submitted_by_party_id,
              approved_by_party_id, approved_at)
    ON TABLE public.solution_funding_case
    TO kokonut_solution_funding_approver;
GRANT UPDATE (decision_status, approved_by_party_id, approved_at)
    ON TABLE public.solution_funding_case
    TO kokonut_solution_funding_approver;
GRANT SELECT (operator_id, reviewer_party_id, location_id, funding_case_id,
              request_id, acknowledged, approved_at)
    ON TABLE public.solution_funding_approval_receipt
    TO kokonut_solution_funding_approver;
GRANT INSERT (operator_id, reviewer_party_id, location_id, funding_case_id,
              request_id, acknowledged, approved_at)
    ON TABLE public.solution_funding_approval_receipt
    TO kokonut_solution_funding_approver;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_funding_approver;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_funding_approver;

CREATE OR REPLACE FUNCTION kokonut_security.approve_location_solution_funding(
    requested_location_id UUID,
    requested_funding_case_id UUID,
    requested_request_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    funding_case_id UUID,
    decision_status TEXT,
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
    existing RECORD;
    funding_record RECORD;
    saved_approval RECORD;
    approval_timestamp TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_funding_case_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Funding approval requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Funding approval requires explicit acknowledgement'
            USING ERRCODE = '22023';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Funding approval requires an active exact location review grant'
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
        RAISE EXCEPTION 'Funding approval requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.reviewer_party_id,
           receipt.funding_case_id, receipt.acknowledged, receipt.approved_at
      INTO existing
      FROM public.solution_funding_approval_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.reviewer_party_id IS DISTINCT FROM reviewer_party_id
           OR existing.funding_case_id IS DISTINCT FROM requested_funding_case_id
           OR existing.acknowledged IS DISTINCT FROM requested_acknowledged THEN
            RAISE EXCEPTION 'Funding approval request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT existing.funding_case_id, 'approved'::TEXT,
                            existing.approved_at, TRUE;
        RETURN;
    END IF;

    SELECT funding.id, funding.solution_id, funding.decision_status,
           funding.submitted_by_party_id, funding.approved_by_party_id,
           funding.approved_at, solution.originating_scope_type,
           solution.originating_scope_id
      INTO funding_record
      FROM public.solution_funding_case AS funding
      JOIN public.solution AS solution ON solution.id = funding.solution_id
     WHERE funding.id = requested_funding_case_id
     FOR UPDATE OF funding;
    IF NOT FOUND
       OR funding_record.originating_scope_type IS DISTINCT FROM 'location'
       OR funding_record.originating_scope_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'Submitted exact-location funding case was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF funding_record.decision_status IS DISTINCT FROM 'submitted'
       OR funding_record.approved_by_party_id IS NOT NULL
       OR funding_record.approved_at IS NOT NULL THEN
        RAISE EXCEPTION 'Funding case is no longer eligible for approval'
            USING ERRCODE = '55000';
    END IF;
    IF funding_record.submitted_by_party_id IS NULL THEN
        RAISE EXCEPTION 'Unattributed legacy funding submissions cannot be approved'
            USING ERRCODE = '42501';
    END IF;
    IF funding_record.submitted_by_party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Funding approval requires a human distinct from the submitter'
            USING ERRCODE = '42501';
    END IF;

    approval_timestamp := pg_catalog.clock_timestamp();
    UPDATE public.solution_funding_case AS funding
       SET decision_status = 'approved',
           approved_by_party_id = reviewer_party_id,
           approved_at = approval_timestamp
     WHERE funding.id = requested_funding_case_id
       AND funding.decision_status = 'submitted'
       AND funding.approved_by_party_id IS NULL
       AND funding.approved_at IS NULL
    RETURNING funding.id, funding.decision_status::TEXT,
              funding.approved_by_party_id, funding.approved_at
         INTO saved_approval;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Funding case changed before approval could be recorded'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.solution_funding_approval_receipt (
        operator_id, reviewer_party_id, location_id, funding_case_id,
        request_id, acknowledged, approved_at
    ) VALUES (
        context_record.actor_id, reviewer_party_id, requested_location_id,
        requested_funding_case_id, requested_request_id, requested_acknowledged,
        saved_approval.approved_at
    );
    RETURN QUERY SELECT saved_approval.id, saved_approval.decision_status,
                        saved_approval.approved_at, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_funding_approver;
ALTER FUNCTION kokonut_security.approve_location_solution_funding(UUID, UUID, UUID, BOOLEAN)
    OWNER TO kokonut_solution_funding_approver;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_funding_approver;
REVOKE ALL ON FUNCTION kokonut_security.approve_location_solution_funding(UUID, UUID, UUID, BOOLEAN)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.approve_location_solution_funding(
            UUID, UUID, UUID, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.approve_location_solution_funding(
            UUID, UUID, UUID, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.approve_location_solution_funding(UUID, UUID, UUID, BOOLEAN) IS
'Records one independent human approval for an attributed, submitted exact-location funding case. It changes only case decision and approver attribution, with an immutable retry receipt; it does not approve tranches, release funds, or advance solution stage.';

COMMIT;
