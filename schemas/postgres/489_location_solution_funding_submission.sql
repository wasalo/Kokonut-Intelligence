-- Submit a Kernel-created funding draft for independent human review.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_funding_submitter'
    ) THEN
        CREATE ROLE kokonut_solution_funding_submitter
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_funding_submitter'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution funding submitter role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_funding_submitter'
            OR member_role.rolname = 'kokonut_solution_funding_submitter'
    ) THEN
        RAISE EXCEPTION 'Solution funding submitter role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_funding_submission_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    submitter_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    funding_case_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_funding_case(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload JSONB NOT NULL CHECK (pg_catalog.jsonb_typeof(payload) = 'object'),
    submitted_at TIMESTAMPTZ NOT NULL,
    tranche_count INTEGER NOT NULL CHECK (tranche_count BETWEEN 0 AND 50),
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_funding_submission_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_funding_submission_receipt
    FROM kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_funding_submitter;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_funding_submitter;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_funding_submitter;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_funding_submitter;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_funding_submitter;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_funding_submitter;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_funding_submitter;

GRANT SELECT (id, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_funding_submitter;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_funding_submitter;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_funding_submitter;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_funding_submitter;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_funding_submitter;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_funding_submitter;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_funding_submitter;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_funding_submitter;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_funding_submitter;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_funding_submitter;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_funding_submitter;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_funding_submitter;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_funding_submitter;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_funding_submitter;

GRANT SELECT (id, solution_id, decision_status, submitted_by_party_id,
              approved_by_party_id, approved_at)
    ON TABLE public.solution_funding_case
    TO kokonut_solution_funding_submitter;
GRANT UPDATE (decision_status, submitted_by_party_id)
    ON TABLE public.solution_funding_case
    TO kokonut_solution_funding_submitter;
GRANT SELECT (funding_case_id, status)
    ON TABLE public.solution_funding_tranche
    TO kokonut_solution_funding_submitter;
GRANT SELECT (operator_id, proposer_party_id, location_id, solution_id,
              funding_case_id)
    ON TABLE public.solution_funding_proposal_receipt
    TO kokonut_solution_funding_submitter;
GRANT SELECT (operator_id, submitter_party_id, location_id, funding_case_id,
              request_id, payload, submitted_at, tranche_count)
    ON TABLE public.solution_funding_submission_receipt
    TO kokonut_solution_funding_submitter;
GRANT INSERT (operator_id, submitter_party_id, location_id, funding_case_id,
              request_id, payload, submitted_at, tranche_count)
    ON TABLE public.solution_funding_submission_receipt
    TO kokonut_solution_funding_submitter;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_funding_submitter;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_funding_submitter;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_solution_funding(
    requested_location_id UUID,
    requested_funding_case_id UUID,
    requested_request_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    funding_case_id UUID,
    decision_status TEXT,
    tranche_count INTEGER,
    submitted_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    submitter_party_id UUID;
    request_payload JSONB;
    existing RECORD;
    existing_found BOOLEAN := FALSE;
    source_receipt RECORD;
    funding_record RECORD;
    actual_tranche_count INTEGER;
    invalid_tranche_count INTEGER;
    submission_timestamp TIMESTAMPTZ;
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
        RAISE EXCEPTION 'Funding submission requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Funding submission requires explicit acknowledgement'
            USING ERRCODE = '22023';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'submit', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Funding submission requires an active exact location submit grant'
            USING ERRCODE = '42501';
    END IF;

    SELECT binding.party_id
      INTO submitter_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS submitter
        ON submitter.id = binding.party_id
       AND submitter.party_type = 'person'
       AND submitter.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, submitter;
    IF submitter_party_id IS NULL THEN
        RAISE EXCEPTION 'Funding submission requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    request_payload := pg_catalog.jsonb_build_object(
        'funding_case_id', requested_funding_case_id,
        'acknowledged', requested_acknowledged
    );
    SELECT receipt.location_id, receipt.submitter_party_id,
           receipt.funding_case_id, receipt.payload, receipt.submitted_at,
           receipt.tranche_count
      INTO existing
      FROM public.solution_funding_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    existing_found := FOUND;
    IF existing_found THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.submitter_party_id IS DISTINCT FROM submitter_party_id
           OR existing.funding_case_id IS DISTINCT FROM requested_funding_case_id
           OR existing.payload IS DISTINCT FROM request_payload THEN
            RAISE EXCEPTION 'Funding submission request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT existing.funding_case_id, 'submitted'::TEXT,
                            existing.tranche_count, existing.submitted_at, TRUE;
        RETURN;
    END IF;

    SELECT receipt.operator_id, receipt.proposer_party_id,
           receipt.location_id, receipt.solution_id
      INTO source_receipt
      FROM public.solution_funding_proposal_receipt AS receipt
     WHERE receipt.funding_case_id = requested_funding_case_id;
    IF NOT FOUND
       OR source_receipt.operator_id IS DISTINCT FROM context_record.actor_id
       OR source_receipt.proposer_party_id IS DISTINCT FROM submitter_party_id
       OR source_receipt.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'Funding draft is unavailable for this operator and location'
            USING ERRCODE = 'P0002';
    END IF;

    SELECT funding.id, funding.decision_status, funding.submitted_by_party_id,
           funding.approved_by_party_id, funding.approved_at
      INTO funding_record
      FROM public.solution_funding_case AS funding
      JOIN public.solution AS solution ON solution.id = funding.solution_id
     WHERE funding.id = requested_funding_case_id
       AND funding.solution_id = source_receipt.solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR UPDATE OF funding, solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location funding draft was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF funding_record.decision_status IS DISTINCT FROM 'draft'
       OR funding_record.submitted_by_party_id IS NOT NULL
       OR funding_record.approved_by_party_id IS NOT NULL
       OR funding_record.approved_at IS NOT NULL THEN
        RAISE EXCEPTION 'Funding draft is no longer eligible for submission'
            USING ERRCODE = '55000';
    END IF;

    SELECT pg_catalog.count(*)::INTEGER,
           pg_catalog.count(*) FILTER (WHERE tranche.status IS DISTINCT FROM 'proposed')::INTEGER
      INTO actual_tranche_count, invalid_tranche_count
      FROM public.solution_funding_tranche AS tranche
     WHERE tranche.funding_case_id = requested_funding_case_id;
    IF actual_tranche_count > 50 OR invalid_tranche_count <> 0 THEN
        RAISE EXCEPTION 'Funding draft contains a tranche outside the proposed state'
            USING ERRCODE = '55000';
    END IF;

    submission_timestamp := pg_catalog.clock_timestamp();
    UPDATE public.solution_funding_case AS funding
       SET decision_status = 'submitted',
           submitted_by_party_id = submitter_party_id
     WHERE funding.id = requested_funding_case_id
       AND funding.decision_status = 'draft';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Funding draft changed before submission'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.solution_funding_submission_receipt (
        operator_id, submitter_party_id, location_id, funding_case_id,
        request_id, payload, submitted_at, tranche_count
    ) VALUES (
        context_record.actor_id, submitter_party_id, requested_location_id,
        requested_funding_case_id, requested_request_id, request_payload,
        submission_timestamp, actual_tranche_count
    );
    RETURN QUERY SELECT requested_funding_case_id, 'submitted'::TEXT,
                        actual_tranche_count, submission_timestamp, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_funding_submitter;
ALTER FUNCTION kokonut_security.submit_location_solution_funding(UUID, UUID, UUID, BOOLEAN)
    OWNER TO kokonut_solution_funding_submitter;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_funding_submitter;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_funding(UUID, UUID, UUID, BOOLEAN)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_solution_funding(
            UUID, UUID, UUID, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_funding(
            UUID, UUID, UUID, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_funding_submission_receipt IS
'Private immutable idempotency receipts for exact-location Kernel funding draft submission.';
COMMENT ON FUNCTION kokonut_security.submit_location_solution_funding(UUID, UUID, UUID, BOOLEAN) IS
'Submits only a funding draft created by the same authenticated operator and active human party at the exact location. Requires signed solution_lifecycle:submit, explicit acknowledgement, and all-proposed tranches. It changes no approval/release state and does not advance solution stage.';

COMMIT;
