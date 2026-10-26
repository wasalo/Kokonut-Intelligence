-- Independently approve a proposed tranche after its funding case is approved.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_funding_tranche_approver'
    ) THEN
        CREATE ROLE kokonut_solution_funding_tranche_approver
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_funding_tranche_approver'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution funding tranche approver role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_funding_tranche_approver'
            OR member_role.rolname = 'kokonut_solution_funding_tranche_approver'
    ) THEN
        RAISE EXCEPTION 'Solution funding tranche approver role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_funding_tranche_approval_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    funding_case_id UUID NOT NULL
        REFERENCES public.solution_funding_case(id) ON DELETE RESTRICT,
    tranche_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_funding_tranche(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    acknowledged BOOLEAN NOT NULL CHECK (acknowledged IS TRUE),
    approved_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_funding_tranche_approval_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_funding_tranche_approval_receipt
    FROM kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_funding_tranche_approver;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_funding_tranche_approver;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_funding_tranche_approver;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_funding_tranche_approver;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_funding_tranche_approver;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_funding_tranche_approver;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_funding_tranche_approver;

GRANT SELECT (id, name, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_funding_tranche_approver;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_funding_tranche_approver;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_funding_tranche_approver;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_funding_tranche_approver;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_funding_tranche_approver;

GRANT SELECT (id, solution_id, currency, decision_status,
              submitted_by_party_id, approved_by_party_id)
    ON TABLE public.solution_funding_case
    TO kokonut_solution_funding_tranche_approver;
GRANT UPDATE (id) ON TABLE public.solution_funding_case
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (id, funding_case_id, tranche_number, amount,
              milestone_conditions, status, approved_by_party_id,
              approved_at, released_at)
    ON TABLE public.solution_funding_tranche
    TO kokonut_solution_funding_tranche_approver;
GRANT UPDATE (status, approved_by_party_id, approved_at)
    ON TABLE public.solution_funding_tranche
    TO kokonut_solution_funding_tranche_approver;
GRANT SELECT (operator_id, reviewer_party_id, location_id,
              funding_case_id, tranche_id, request_id, acknowledged, approved_at)
    ON TABLE public.solution_funding_tranche_approval_receipt
    TO kokonut_solution_funding_tranche_approver;
GRANT INSERT (operator_id, reviewer_party_id, location_id, funding_case_id,
              tranche_id, request_id, acknowledged, approved_at)
    ON TABLE public.solution_funding_tranche_approval_receipt
    TO kokonut_solution_funding_tranche_approver;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_funding_tranche_approver;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_funding_tranche_approver;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_solution_funding_tranche_review_detail(
    requested_location_id UUID,
    requested_funding_case_id UUID,
    requested_tranche_id UUID
)
RETURNS TABLE (
    funding_case_id UUID,
    tranche_id UUID,
    solution_name TEXT,
    case_decision_status TEXT,
    case_currency TEXT,
    case_submitter_attributed BOOLEAN,
    is_self_authored BOOLEAN,
    is_case_approver BOOLEAN,
    tranche_number INTEGER,
    tranche_amount NUMERIC,
    milestone_conditions JSONB,
    tranche_status TEXT,
    tranche_approved_at TIMESTAMPTZ,
    eligible_for_independent_approval BOOLEAN
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    reviewer_party_id UUID;
    funding_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_funding_case_id IS NULL
       OR requested_tranche_id IS NULL THEN
        RAISE EXCEPTION 'Funding tranche review requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Funding tranche review requires an active exact location grant'
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
        RAISE EXCEPTION 'Funding tranche review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    SELECT funding.id, solution.name, funding.decision_status, funding.currency,
           funding.submitted_by_party_id, funding.approved_by_party_id,
           tranche.id AS tranche_id, tranche.tranche_number, tranche.amount,
           tranche.milestone_conditions, tranche.status AS tranche_status,
           tranche.approved_at
      INTO funding_record
      FROM public.solution_funding_case AS funding
      JOIN public.solution AS solution ON solution.id = funding.solution_id
      JOIN public.solution_funding_tranche AS tranche
        ON tranche.funding_case_id = funding.id
     WHERE funding.id = requested_funding_case_id
       AND tranche.id = requested_tranche_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location funding tranche was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF pg_catalog.octet_length(
        COALESCE(funding_record.milestone_conditions, '{}'::JSONB)::TEXT
    ) > 8192 THEN
        RAISE EXCEPTION 'Funding tranche review terms exceed the private payload bound'
            USING ERRCODE = '54000';
    END IF;
    RETURN QUERY SELECT
        funding_record.id,
        funding_record.tranche_id,
        pg_catalog.left(funding_record.name, 255)::TEXT,
        funding_record.decision_status::TEXT,
        pg_catalog.left(funding_record.currency, 10)::TEXT,
        funding_record.submitted_by_party_id IS NOT NULL,
        COALESCE(funding_record.submitted_by_party_id = reviewer_party_id, FALSE),
        COALESCE(funding_record.approved_by_party_id = reviewer_party_id, FALSE),
        funding_record.tranche_number,
        funding_record.amount,
        funding_record.milestone_conditions,
        funding_record.tranche_status::TEXT,
        funding_record.approved_at,
        funding_record.decision_status = 'approved'
            AND funding_record.tranche_status = 'proposed'
            AND funding_record.submitted_by_party_id IS NOT NULL
            AND funding_record.submitted_by_party_id <> reviewer_party_id
            AND funding_record.approved_by_party_id IS NOT NULL
            AND funding_record.approved_by_party_id <> reviewer_party_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.approve_location_solution_funding_tranche(
    requested_location_id UUID,
    requested_funding_case_id UUID,
    requested_tranche_id UUID,
    requested_request_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    funding_case_id UUID,
    tranche_id UUID,
    tranche_status TEXT,
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
    tranche_record RECORD;
    saved_approval RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_funding_case_id IS NULL
       OR requested_tranche_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Funding tranche approval requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Funding tranche approval requires explicit acknowledgement'
            USING ERRCODE = '22023';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Funding tranche approval requires an active exact location review grant'
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
        RAISE EXCEPTION 'Funding tranche approval requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.reviewer_party_id,
           receipt.funding_case_id, receipt.tranche_id,
           receipt.acknowledged, receipt.approved_at
      INTO existing
      FROM public.solution_funding_tranche_approval_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.reviewer_party_id IS DISTINCT FROM reviewer_party_id
           OR existing.funding_case_id IS DISTINCT FROM requested_funding_case_id
           OR existing.tranche_id IS DISTINCT FROM requested_tranche_id
           OR existing.acknowledged IS DISTINCT FROM requested_acknowledged THEN
            RAISE EXCEPTION 'Funding tranche approval request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT existing.funding_case_id, existing.tranche_id,
                            'approved'::TEXT, existing.approved_at, TRUE;
        RETURN;
    END IF;

    SELECT funding.id, funding.decision_status, funding.submitted_by_party_id,
           funding.approved_by_party_id AS case_approved_by_party_id,
           tranche.id AS tranche_id,
           tranche.status AS tranche_status,
           tranche.approved_by_party_id AS tranche_approved_by_party_id,
           tranche.approved_at, tranche.released_at,
           solution.originating_scope_type, solution.originating_scope_id
      INTO tranche_record
      FROM public.solution_funding_case AS funding
      JOIN public.solution AS solution ON solution.id = funding.solution_id
      JOIN public.solution_funding_tranche AS tranche
        ON tranche.funding_case_id = funding.id
     WHERE funding.id = requested_funding_case_id
       AND tranche.id = requested_tranche_id
     FOR KEY SHARE OF solution, funding
     FOR UPDATE OF tranche;
    IF NOT FOUND
       OR tranche_record.originating_scope_type IS DISTINCT FROM 'location'
       OR tranche_record.originating_scope_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'Exact-location funding tranche was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF tranche_record.decision_status IS DISTINCT FROM 'approved'
       OR tranche_record.tranche_status IS DISTINCT FROM 'proposed'
       OR tranche_record.tranche_approved_by_party_id IS NOT NULL
       OR tranche_record.approved_at IS NOT NULL
       OR tranche_record.released_at IS NOT NULL THEN
        RAISE EXCEPTION 'Funding case or tranche is no longer eligible for approval'
            USING ERRCODE = '55000';
    END IF;
    IF tranche_record.submitted_by_party_id IS NULL
       OR tranche_record.case_approved_by_party_id IS NULL THEN
        RAISE EXCEPTION 'Funding tranche approval requires attributed case submission and approval'
            USING ERRCODE = '42501';
    END IF;
    IF tranche_record.submitted_by_party_id = reviewer_party_id
       OR tranche_record.case_approved_by_party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Funding tranche approval requires a human distinct from submitter and case approver'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.solution_funding_tranche AS tranche
       SET status = 'approved',
           approved_by_party_id = reviewer_party_id,
           approved_at = pg_catalog.clock_timestamp()
     WHERE tranche.id = requested_tranche_id
       AND tranche.funding_case_id = requested_funding_case_id
       AND tranche.status = 'proposed'
       AND tranche.approved_by_party_id IS NULL
       AND tranche.approved_at IS NULL
       AND tranche.released_at IS NULL
    RETURNING tranche.id, tranche.status::TEXT, tranche.approved_at
         INTO saved_approval;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Funding tranche changed before approval could be recorded'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.solution_funding_tranche_approval_receipt (
        operator_id, reviewer_party_id, location_id, funding_case_id,
        tranche_id, request_id, acknowledged, approved_at
    ) VALUES (
        context_record.actor_id, reviewer_party_id, requested_location_id,
        requested_funding_case_id, requested_tranche_id, requested_request_id,
        requested_acknowledged, saved_approval.approved_at
    );
    RETURN QUERY SELECT requested_funding_case_id, saved_approval.id,
                        saved_approval.status, saved_approval.approved_at, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_funding_tranche_approver;
ALTER FUNCTION kokonut_security.get_location_solution_funding_tranche_review_detail(UUID, UUID, UUID)
    OWNER TO kokonut_solution_funding_tranche_approver;
ALTER FUNCTION kokonut_security.approve_location_solution_funding_tranche(UUID, UUID, UUID, UUID, BOOLEAN)
    OWNER TO kokonut_solution_funding_tranche_approver;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_funding_tranche_approver;
REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_funding_tranche_review_detail(UUID, UUID, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.approve_location_solution_funding_tranche(UUID, UUID, UUID, UUID, BOOLEAN)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.get_location_solution_funding_tranche_review_detail(
            UUID, UUID, UUID
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.approve_location_solution_funding_tranche(
            UUID, UUID, UUID, UUID, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_funding_tranche_review_detail(
            UUID, UUID, UUID
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.approve_location_solution_funding_tranche(
            UUID, UUID, UUID, UUID, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.get_location_solution_funding_tranche_review_detail(UUID, UUID, UUID) IS
'Returns bounded private tranche terms for an exact-location funding case under signed solution_lifecycle:review. It exposes eligibility booleans, not submitter or approver identities.';
COMMENT ON FUNCTION kokonut_security.approve_location_solution_funding_tranche(UUID, UUID, UUID, UUID, BOOLEAN) IS
'Approves one proposed tranche only after its exact-location case is approved. Requires an active reviewer distinct from both submitter and case approver; writes an immutable retry receipt and does not release funds or change solution stage.';

COMMIT;
