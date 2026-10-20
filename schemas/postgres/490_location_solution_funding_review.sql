-- Private, exact-location review reads for submitted solution funding cases.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_funding_reviewer'
    ) THEN
        CREATE ROLE kokonut_solution_funding_reviewer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_funding_reviewer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution funding reviewer role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_funding_reviewer'
            OR member_role.rolname = 'kokonut_solution_funding_reviewer'
    ) THEN
        RAISE EXCEPTION 'Solution funding reviewer role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_funding_reviewer;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_funding_reviewer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_funding_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_funding_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_funding_reviewer;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_funding_reviewer;

GRANT SELECT (id, name, solution_type, current_stage, status,
              originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_funding_reviewer;
GRANT SELECT (
    id, solution_id, capital_stage, funding_instrument, requested_amount,
    minimum_viable_amount, maximum_authorized_amount, currency,
    risk_adjusted_expected_value, public_goods_value, community_share,
    downside_exposure, decision_status, rationale, evidence,
    submitted_by_party_id, approved_by_party_id, approved_at, created_at
) ON TABLE public.solution_funding_case
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (
    id, funding_case_id, tranche_number, amount, milestone_conditions, status
) ON TABLE public.solution_funding_tranche
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (location_id, funding_case_id, submitted_at)
    ON TABLE public.solution_funding_submission_receipt
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_funding_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_funding_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_funding_reviewer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_funding_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_funding_review_queue(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    funding_case_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    solution_stage TEXT,
    capital_stage TEXT,
    funding_instrument TEXT,
    requested_amount NUMERIC,
    currency TEXT,
    created_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    tranche_count INTEGER,
    submitter_attributed BOOLEAN,
    is_self_authored BOOLEAN
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
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
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Funding review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Funding review queue requires an active exact location grant'
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
        RAISE EXCEPTION 'Funding review queue requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Funding review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT funding.id,
           pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT,
           solution.current_stage::TEXT,
           funding.capital_stage::TEXT,
           funding.funding_instrument::TEXT,
           funding.requested_amount,
           pg_catalog.left(funding.currency, 10)::TEXT,
           funding.created_at,
           submission.submitted_at,
           (SELECT pg_catalog.count(*)::INTEGER
              FROM public.solution_funding_tranche AS tranche
             WHERE tranche.funding_case_id = funding.id),
           funding.submitted_by_party_id IS NOT NULL,
           COALESCE(funding.submitted_by_party_id = reviewer_party_id, FALSE)
      FROM public.solution_funding_case AS funding
      JOIN public.solution AS solution
        ON solution.id = funding.solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
      LEFT JOIN public.solution_funding_submission_receipt AS submission
        ON submission.funding_case_id = funding.id
       AND submission.location_id = requested_location_id
     WHERE funding.decision_status = 'submitted'
       AND funding.approved_by_party_id IS NULL
       AND funding.approved_at IS NULL
     ORDER BY submission.submitted_at DESC NULLS LAST,
              funding.created_at DESC, funding.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_solution_funding_review_detail(
    requested_location_id UUID,
    requested_funding_case_id UUID
)
RETURNS TABLE (
    funding_case_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    solution_stage TEXT,
    capital_stage TEXT,
    funding_instrument TEXT,
    requested_amount NUMERIC,
    minimum_viable_amount NUMERIC,
    maximum_authorized_amount NUMERIC,
    currency TEXT,
    risk_adjusted_expected_value NUMERIC,
    public_goods_value NUMERIC,
    community_share NUMERIC,
    downside_exposure NUMERIC,
    decision_status TEXT,
    rationale TEXT,
    evidence JSONB,
    created_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    tranches JSONB,
    submitter_attributed BOOLEAN,
    is_self_authored BOOLEAN
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
    tranche_payload JSONB;
    tranche_count INTEGER;
    oversized_tranche_count INTEGER;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_funding_case_id IS NULL THEN
        RAISE EXCEPTION 'Funding review detail requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Funding review detail requires an active exact location grant'
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
        RAISE EXCEPTION 'Funding review detail requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    SELECT funding.id, solution.name, solution.solution_type,
           solution.current_stage, funding.capital_stage,
           funding.funding_instrument, funding.requested_amount,
           funding.minimum_viable_amount, funding.maximum_authorized_amount,
           funding.currency, funding.risk_adjusted_expected_value,
           funding.public_goods_value, funding.community_share,
           funding.downside_exposure, funding.decision_status,
           funding.rationale, funding.evidence, funding.created_at,
           submission.submitted_at, funding.submitted_by_party_id
      INTO funding_record
      FROM public.solution_funding_case AS funding
      JOIN public.solution AS solution
        ON solution.id = funding.solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
      LEFT JOIN public.solution_funding_submission_receipt AS submission
        ON submission.funding_case_id = funding.id
       AND submission.location_id = requested_location_id
     WHERE funding.id = requested_funding_case_id
       AND funding.decision_status = 'submitted'
       AND funding.approved_by_party_id IS NULL
       AND funding.approved_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submitted exact-location funding case was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF pg_catalog.octet_length(COALESCE(funding_record.rationale, '')) > 4000
       OR pg_catalog.octet_length(
           COALESCE(funding_record.evidence, 'null'::JSONB)::TEXT
       ) > 65536 THEN
        RAISE EXCEPTION 'Funding review detail exceeds private payload bounds'
            USING ERRCODE = '54000';
    END IF;

    SELECT pg_catalog.count(*)::INTEGER,
           pg_catalog.count(*) FILTER (
               WHERE pg_catalog.octet_length(tranche.milestone_conditions::TEXT) > 8192
           )::INTEGER
      INTO tranche_count, oversized_tranche_count
      FROM public.solution_funding_tranche AS tranche
     WHERE tranche.funding_case_id = requested_funding_case_id;
    IF tranche_count > 50 OR oversized_tranche_count > 0 THEN
        RAISE EXCEPTION 'Funding tranche review detail exceeds private payload bounds'
            USING ERRCODE = '54000';
    END IF;
    SELECT COALESCE(
               pg_catalog.jsonb_agg(
                   pg_catalog.jsonb_build_object(
                       'tranche_number', tranche.tranche_number,
                       'amount', tranche.amount,
                       'milestone_conditions', tranche.milestone_conditions,
                       'status', tranche.status
                   ) ORDER BY tranche.tranche_number, tranche.id
               ), '[]'::JSONB
           )
      INTO tranche_payload
      FROM public.solution_funding_tranche AS tranche
     WHERE tranche.funding_case_id = requested_funding_case_id;
    IF pg_catalog.octet_length(tranche_payload::TEXT) > 131072 THEN
        RAISE EXCEPTION 'Funding tranche review detail exceeds private payload bounds'
            USING ERRCODE = '54000';
    END IF;

    RETURN QUERY SELECT
        funding_record.id,
        pg_catalog.left(funding_record.name, 255)::TEXT,
        funding_record.solution_type::TEXT,
        funding_record.current_stage::TEXT,
        funding_record.capital_stage::TEXT,
        funding_record.funding_instrument::TEXT,
        funding_record.requested_amount,
        funding_record.minimum_viable_amount,
        funding_record.maximum_authorized_amount,
        pg_catalog.left(funding_record.currency, 10)::TEXT,
        funding_record.risk_adjusted_expected_value,
        funding_record.public_goods_value,
        funding_record.community_share,
        funding_record.downside_exposure,
        funding_record.decision_status::TEXT,
        pg_catalog.left(funding_record.rationale, 4000)::TEXT,
        funding_record.evidence,
        funding_record.created_at,
        funding_record.submitted_at,
        tranche_payload,
        funding_record.submitted_by_party_id IS NOT NULL,
        COALESCE(funding_record.submitted_by_party_id = reviewer_party_id, FALSE);
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_funding_reviewer;
ALTER FUNCTION kokonut_security.list_location_solution_funding_review_queue(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_funding_reviewer;
ALTER FUNCTION kokonut_security.get_location_solution_funding_review_detail(UUID, UUID)
    OWNER TO kokonut_solution_funding_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_funding_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_funding_review_queue(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_funding_review_detail(UUID, UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_funding_review_queue(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.get_location_solution_funding_review_detail(
            UUID, UUID
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_funding_review_queue(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_funding_review_detail(
            UUID, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_solution_funding_review_queue(UUID, INTEGER, INTEGER) IS
'Returns bounded submitted funding cases for exact location-origin solutions under signed solution_lifecycle:review and active human attribution. Financial request amount and self-authorship are visible only to the reviewer; identities and narratives are omitted.';
COMMENT ON FUNCTION kokonut_security.get_location_solution_funding_review_detail(UUID, UUID) IS
'Returns bounded private case terms, evidence, and proposed tranche details only for a submitted exact location-origin funding case under signed solution_lifecycle:review and active human attribution. It does not approve or release funds.';

COMMIT;
