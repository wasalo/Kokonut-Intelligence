-- Create private, location-origin funding drafts without approving or releasing funds.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_funding_proposer'
    ) THEN
        CREATE ROLE kokonut_solution_funding_proposer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_funding_proposer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution funding proposer role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_funding_proposer'
            OR member_role.rolname = 'kokonut_solution_funding_proposer'
    ) THEN
        RAISE EXCEPTION 'Solution funding proposer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_funding_proposal_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    proposer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    funding_case_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_funding_case(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    tranche_count INTEGER NOT NULL CHECK (tranche_count BETWEEN 0 AND 50),
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_funding_proposal_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_funding_proposal_receipt
    FROM kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_funding_proposer;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_funding_proposer;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_funding_proposer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_funding_proposer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_funding_proposer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_funding_proposer;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_funding_proposer;

GRANT SELECT (id, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_funding_proposer;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_funding_proposer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_funding_proposer;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_funding_proposer;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_funding_proposer;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_funding_proposer;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_funding_proposer;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_funding_proposer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_funding_proposer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_funding_proposer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_funding_proposer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_funding_proposer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_funding_proposer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_funding_proposer;

GRANT SELECT (
    id, solution_id, capital_stage, funding_instrument, requested_amount,
    minimum_viable_amount, maximum_authorized_amount, currency,
    risk_adjusted_expected_value, public_goods_value, community_share,
    downside_exposure, decision_status, rationale, evidence,
    submitted_by_party_id, created_at
) ON TABLE public.solution_funding_case
    TO kokonut_solution_funding_proposer;
GRANT INSERT (
    solution_id, capital_stage, funding_instrument, requested_amount,
    minimum_viable_amount, maximum_authorized_amount, currency,
    risk_adjusted_expected_value, public_goods_value, community_share,
    downside_exposure, decision_status, rationale, evidence, created_at
) ON TABLE public.solution_funding_case
    TO kokonut_solution_funding_proposer;
GRANT SELECT (id, funding_case_id, tranche_number, amount, milestone_conditions, status)
    ON TABLE public.solution_funding_tranche
    TO kokonut_solution_funding_proposer;
GRANT INSERT (funding_case_id, tranche_number, amount, milestone_conditions, status)
    ON TABLE public.solution_funding_tranche
    TO kokonut_solution_funding_proposer;

GRANT SELECT (operator_id, proposer_party_id, location_id, solution_id,
              funding_case_id, request_id, payload, created_at, tranche_count)
    ON TABLE public.solution_funding_proposal_receipt
    TO kokonut_solution_funding_proposer;
GRANT INSERT (operator_id, proposer_party_id, location_id, solution_id,
              funding_case_id, request_id, payload, created_at, tranche_count)
    ON TABLE public.solution_funding_proposal_receipt
    TO kokonut_solution_funding_proposer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_funding_proposer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_funding_proposer;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_funding_targets(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    solution_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    current_stage TEXT,
    solution_status TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Funding target read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Funding target read requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Funding target page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT solution.id,
           pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT,
           solution.current_stage::TEXT,
           solution.status::TEXT
      FROM public.solution AS solution
     WHERE solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     ORDER BY solution.name, solution.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_reader;
ALTER FUNCTION kokonut_security.list_location_solution_funding_targets(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_funding_targets(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

CREATE OR REPLACE FUNCTION kokonut_security.propose_location_solution_funding(
    requested_location_id UUID,
    requested_solution_id UUID,
    requested_request_id UUID,
    requested_capital_stage TEXT,
    requested_funding_instrument TEXT,
    requested_amount NUMERIC,
    requested_minimum_viable_amount NUMERIC,
    requested_maximum_authorized_amount NUMERIC,
    requested_currency TEXT,
    requested_risk_adjusted_expected_value NUMERIC,
    requested_public_goods_value NUMERIC,
    requested_community_share NUMERIC,
    requested_downside_exposure NUMERIC,
    requested_rationale TEXT,
    requested_evidence JSONB,
    requested_tranches JSONB
)
RETURNS TABLE (
    funding_case_id UUID,
    decision_status TEXT,
    tranche_count INTEGER,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    proposer_party_id UUID;
    existing RECORD;
    existing_found BOOLEAN := FALSE;
    solution_record RECORD;
    request_payload JSONB;
    tranche_item JSONB;
    tranche_amount NUMERIC;
    tranche_total NUMERIC := 0;
    generated_case_id UUID;
    proposal_timestamp TIMESTAMPTZ;
    actual_tranche_count INTEGER;
    tranche_number INTEGER := 0;
    maximum_tranche_total NUMERIC;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_solution_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Funding proposal requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Funding proposal requires an active exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    SELECT binding.party_id
      INTO proposer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS proposer
        ON proposer.id = binding.party_id
       AND proposer.party_type = 'person'
       AND proposer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, proposer;
    IF proposer_party_id IS NULL THEN
        RAISE EXCEPTION 'Funding proposal requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.solution_id, receipt.proposer_party_id,
           receipt.funding_case_id, receipt.payload, receipt.created_at,
           receipt.tranche_count
      INTO existing
      FROM public.solution_funding_proposal_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    existing_found := FOUND;

    IF requested_capital_stage NOT IN (
           'discovery', 'experiment', 'pilot', 'replication', 'scale', 'maintenance'
       )
       OR requested_funding_instrument NOT IN (
           'grant', 'budget', 'bounty', 'loan', 'investment', 'community_fund', 'in_kind'
       )
       OR requested_amount IS NULL OR requested_amount < 0
       OR requested_amount::TEXT IN ('NaN', 'Infinity', '-Infinity')
       OR requested_amount <> pg_catalog.trunc(requested_amount, 2)
       OR (requested_minimum_viable_amount IS NOT NULL AND (
           requested_minimum_viable_amount < 0
           OR requested_minimum_viable_amount::TEXT IN ('NaN', 'Infinity', '-Infinity')
           OR requested_minimum_viable_amount <> pg_catalog.trunc(requested_minimum_viable_amount, 2)
       ))
       OR (requested_maximum_authorized_amount IS NOT NULL AND (
           requested_maximum_authorized_amount < requested_amount
           OR requested_maximum_authorized_amount::TEXT IN ('NaN', 'Infinity', '-Infinity')
           OR requested_maximum_authorized_amount <> pg_catalog.trunc(requested_maximum_authorized_amount, 2)
       ))
       OR (requested_risk_adjusted_expected_value IS NOT NULL AND (
           requested_risk_adjusted_expected_value::TEXT IN ('NaN', 'Infinity', '-Infinity')
           OR requested_risk_adjusted_expected_value <> pg_catalog.trunc(requested_risk_adjusted_expected_value, 2)
       ))
       OR (requested_public_goods_value IS NOT NULL AND (
           requested_public_goods_value::TEXT IN ('NaN', 'Infinity', '-Infinity')
           OR requested_public_goods_value <> pg_catalog.trunc(requested_public_goods_value, 2)
       ))
       OR (requested_community_share IS NOT NULL AND (
           requested_community_share::TEXT IN ('NaN', 'Infinity', '-Infinity')
           OR requested_community_share <> pg_catalog.trunc(requested_community_share, 2)
       ))
       OR (requested_downside_exposure IS NOT NULL AND (
           requested_downside_exposure::TEXT IN ('NaN', 'Infinity', '-Infinity')
           OR requested_downside_exposure <> pg_catalog.trunc(requested_downside_exposure, 2)
       ))
       OR requested_currency IS NULL
       OR requested_currency !~ '^[A-Za-z0-9._-]{2,10}$'
       OR requested_rationale IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_rationale)) NOT BETWEEN 1 AND 4000
       OR requested_evidence IS NULL
       OR pg_catalog.jsonb_typeof(requested_evidence) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_evidence) > 100
       OR pg_catalog.octet_length(requested_evidence::TEXT) > 65536
       OR requested_tranches IS NULL
       OR pg_catalog.jsonb_typeof(requested_tranches) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_tranches) > 50 THEN
        RAISE EXCEPTION 'Funding proposal input is invalid'
            USING ERRCODE = '22023';
    END IF;
    IF requested_minimum_viable_amount IS NOT NULL
       AND requested_maximum_authorized_amount IS NOT NULL
       AND requested_minimum_viable_amount > requested_maximum_authorized_amount THEN
        RAISE EXCEPTION 'Funding proposal amount bounds are inconsistent'
            USING ERRCODE = '22023';
    END IF;

    FOR tranche_item IN SELECT value FROM pg_catalog.jsonb_array_elements(requested_tranches)
    LOOP
        IF pg_catalog.jsonb_typeof(tranche_item) IS DISTINCT FROM 'object'
           OR (SELECT pg_catalog.count(*) FROM pg_catalog.jsonb_object_keys(tranche_item)) <> 2
           OR NOT (tranche_item ? 'amount')
           OR NOT (tranche_item ? 'milestone_conditions')
           OR pg_catalog.jsonb_typeof(tranche_item->'amount') IS DISTINCT FROM 'number'
           OR pg_catalog.jsonb_typeof(tranche_item->'milestone_conditions') IS DISTINCT FROM 'object'
           OR pg_catalog.octet_length((tranche_item->'milestone_conditions')::TEXT) > 8192 THEN
            RAISE EXCEPTION 'Funding tranche input is invalid'
                USING ERRCODE = '22023';
        END IF;
        tranche_amount := (tranche_item->>'amount')::NUMERIC;
        IF tranche_amount < 0
           OR tranche_amount::TEXT IN ('NaN', 'Infinity', '-Infinity')
           OR tranche_amount <> pg_catalog.trunc(tranche_amount, 2) THEN
            RAISE EXCEPTION 'Funding tranche amount must be finite, nonnegative, and precise to cents'
                USING ERRCODE = '22023';
        END IF;
        tranche_total := tranche_total + tranche_amount;
        tranche_number := tranche_number + 1;
    END LOOP;
    maximum_tranche_total := COALESCE(
        requested_maximum_authorized_amount, requested_amount
    );
    IF tranche_total > maximum_tranche_total THEN
        RAISE EXCEPTION 'Proposed tranche total exceeds the funding case ceiling'
            USING ERRCODE = '22023';
    END IF;
    actual_tranche_count := tranche_number;

    request_payload := pg_catalog.jsonb_build_object(
        'capital_stage', requested_capital_stage,
        'funding_instrument', requested_funding_instrument,
        'requested_amount', requested_amount,
        'minimum_viable_amount', requested_minimum_viable_amount,
        'maximum_authorized_amount', requested_maximum_authorized_amount,
        'currency', requested_currency,
        'risk_adjusted_expected_value', requested_risk_adjusted_expected_value,
        'public_goods_value', requested_public_goods_value,
        'community_share', requested_community_share,
        'downside_exposure', requested_downside_exposure,
        'rationale', requested_rationale,
        'evidence', requested_evidence,
        'tranches', requested_tranches
    );
    IF existing_found THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.solution_id IS DISTINCT FROM requested_solution_id
           OR existing.proposer_party_id IS DISTINCT FROM proposer_party_id
           OR existing.payload IS DISTINCT FROM request_payload THEN
            RAISE EXCEPTION 'Funding proposal request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT existing.funding_case_id, 'draft'::TEXT,
                            existing.tranche_count, existing.created_at, TRUE;
        RETURN;
    END IF;

    SELECT solution.id
      INTO solution_record
      FROM public.solution AS solution
     WHERE solution.id = requested_solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR KEY SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location-origin solution was not found'
            USING ERRCODE = 'P0002';
    END IF;

    INSERT INTO public.solution_funding_case (
        solution_id, capital_stage, funding_instrument, requested_amount,
        minimum_viable_amount, maximum_authorized_amount, currency,
        risk_adjusted_expected_value, public_goods_value, community_share,
        downside_exposure, decision_status, rationale, evidence, created_at
    ) VALUES (
        requested_solution_id, requested_capital_stage, requested_funding_instrument,
        requested_amount, requested_minimum_viable_amount,
        requested_maximum_authorized_amount, requested_currency,
        requested_risk_adjusted_expected_value, requested_public_goods_value,
        requested_community_share, requested_downside_exposure, 'draft',
        requested_rationale, requested_evidence, pg_catalog.clock_timestamp()
    ) RETURNING id, solution_funding_case.created_at
         INTO generated_case_id, proposal_timestamp;

    tranche_number := 0;
    FOR tranche_item IN SELECT value FROM pg_catalog.jsonb_array_elements(requested_tranches)
    LOOP
        tranche_number := tranche_number + 1;
        INSERT INTO public.solution_funding_tranche (
            funding_case_id, tranche_number, amount, milestone_conditions, status
        ) VALUES (
            generated_case_id, tranche_number, (tranche_item->>'amount')::NUMERIC,
            tranche_item->'milestone_conditions', 'proposed'
        );
    END LOOP;

    INSERT INTO public.solution_funding_proposal_receipt (
        operator_id, proposer_party_id, location_id, solution_id,
        funding_case_id, request_id, payload, created_at, tranche_count
    ) VALUES (
        context_record.actor_id, proposer_party_id, requested_location_id,
        requested_solution_id, generated_case_id, requested_request_id,
        request_payload, proposal_timestamp, actual_tranche_count
    );
    RETURN QUERY SELECT generated_case_id, 'draft'::TEXT,
                        actual_tranche_count, proposal_timestamp, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_funding_proposer;
ALTER FUNCTION kokonut_security.propose_location_solution_funding(
    UUID, UUID, UUID, TEXT, TEXT, NUMERIC, NUMERIC, NUMERIC, TEXT,
    NUMERIC, NUMERIC, NUMERIC, NUMERIC, TEXT, JSONB, JSONB
) OWNER TO kokonut_solution_funding_proposer;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_funding_proposer;
REVOKE ALL ON FUNCTION kokonut_security.propose_location_solution_funding(
    UUID, UUID, UUID, TEXT, TEXT, NUMERIC, NUMERIC, NUMERIC, TEXT,
    NUMERIC, NUMERIC, NUMERIC, NUMERIC, TEXT, JSONB, JSONB
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.propose_location_solution_funding(
            UUID, UUID, UUID, TEXT, TEXT, NUMERIC, NUMERIC, NUMERIC, TEXT,
            NUMERIC, NUMERIC, NUMERIC, NUMERIC, TEXT, JSONB, JSONB
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_funding_targets(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.propose_location_solution_funding(
            UUID, UUID, UUID, TEXT, TEXT, NUMERIC, NUMERIC, NUMERIC, TEXT,
            NUMERIC, NUMERIC, NUMERIC, NUMERIC, TEXT, JSONB, JSONB
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_funding_targets(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_funding_proposal_receipt IS
'Private immutable idempotency receipts for location-origin solution funding drafts and proposed tranches.';
COMMENT ON FUNCTION kokonut_security.list_location_solution_funding_targets(UUID, INTEGER, INTEGER) IS
'Returns bounded exact-location-origin solutions eligible to receive a funding draft under signed solution_lifecycle:read context.';
COMMENT ON FUNCTION kokonut_security.propose_location_solution_funding(
    UUID, UUID, UUID, TEXT, TEXT, NUMERIC, NUMERIC, NUMERIC, TEXT,
    NUMERIC, NUMERIC, NUMERIC, NUMERIC, TEXT, JSONB, JSONB
) IS
'Creates one exact-location-origin solution_funding_case in draft state plus optional proposed tranches under signed solution_lifecycle:create scope and active human attribution. It never submits, approves, releases, or advances the solution stage; exact retries return the original private case receipt.';

COMMIT;
