-- Create canonical solutions only from an authenticated exact-location context.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_creator_owner'
    ) THEN
        CREATE ROLE kokonut_solution_creator_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_creator_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution creator owner role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_creator_owner'
            OR member_role.rolname = 'kokonut_solution_creator_owner'
    ) THEN
        RAISE EXCEPTION 'Solution creator owner role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.location_solution_creation_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL UNIQUE REFERENCES public.solution(id) ON DELETE RESTRICT,
    lifecycle_event_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_lifecycle_event(id) ON DELETE RESTRICT,
    canonical_key TEXT NOT NULL,
    solution_name TEXT NOT NULL,
    solution_type TEXT NOT NULL,
    current_stage TEXT NOT NULL DEFAULT 'discovered',
    solution_status TEXT NOT NULL DEFAULT 'active',
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.location_solution_creation_receipt FROM PUBLIC;
DO $$
DECLARE
    target_role TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime', 'kokonut_solution_reader',
        'kokonut_solution_nonpromotion_transition_owner', 'kokonut_solution_proposal_owner'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.location_solution_creation_receipt FROM %I',
                target_role
            );
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_creator_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_creator_owner;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_creator_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_creator_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_creator_owner;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_creator_owner;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_creator_owner;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_creator_owner;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_creator_owner;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_creator_owner;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_creator_owner;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_creator_owner;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_creator_owner;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_creator_owner;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_creator_owner;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_creator_owner;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_creator_owner;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_creator_owner;
GRANT INSERT (
    canonical_key, name, solution_type, problem_statement, theory_of_change,
    baseline_alternative, originating_scope_type, originating_scope_id,
    created_by_party_id, risk_class, reversibility, current_stage, status
) ON TABLE public.solution TO kokonut_solution_creator_owner;
GRANT SELECT (id, canonical_key, name, solution_type, originating_scope_type,
              originating_scope_id, current_stage, status, created_at)
    ON TABLE public.solution TO kokonut_solution_creator_owner;
GRANT INSERT (solution_id, from_stage, to_stage, rationale, evidence, actor_party_id)
    ON TABLE public.solution_lifecycle_event TO kokonut_solution_creator_owner;
GRANT SELECT (id, created_at) ON TABLE public.solution_lifecycle_event
    TO kokonut_solution_creator_owner;
GRANT SELECT (
    operator_id, actor_party_id, location_id, solution_id, lifecycle_event_id,
    canonical_key, solution_name, solution_type, current_stage, solution_status,
    request_id, payload_digest, created_at
) ON TABLE public.location_solution_creation_receipt
TO kokonut_solution_creator_owner;
GRANT INSERT (
    operator_id, actor_party_id, location_id, solution_id, lifecycle_event_id,
    canonical_key, solution_name, solution_type, current_stage, solution_status,
    request_id, payload_digest, created_at
) ON TABLE public.location_solution_creation_receipt
TO kokonut_solution_creator_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_creator_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_creator_owner;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_creator_owner;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_solution(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_canonical_key TEXT,
    requested_name TEXT,
    requested_solution_type TEXT,
    requested_problem_statement TEXT,
    requested_theory_of_change TEXT,
    requested_baseline_alternative TEXT,
    requested_risk_class TEXT,
    requested_reversibility TEXT,
    requested_rationale TEXT,
    requested_evidence JSONB,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    solution_id UUID,
    lifecycle_event_id UUID,
    canonical_key TEXT,
    solution_name TEXT,
    solution_type TEXT,
    current_stage TEXT,
    solution_status TEXT,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    payload_digest BYTEA;
    prior_receipt RECORD;
    solution_record RECORD;
    event_record RECORD;
    normalized_key TEXT;
    normalized_name TEXT;
    normalized_problem TEXT;
    normalized_rationale TEXT;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Solution creation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution creation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_request_id IS NULL
       OR requested_canonical_key IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_canonical_key)) NOT BETWEEN 2 AND 160
       OR requested_canonical_key !~ '^[a-z0-9][a-z0-9._:-]{1,159}$'
       OR requested_name IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_name)) NOT BETWEEN 1 AND 255
       OR requested_solution_type IS NULL
       OR requested_solution_type NOT IN (
           'practice', 'policy', 'technology', 'service', 'governance',
           'business_model', 'ecological_intervention', 'data_product', 'other'
       )
       OR requested_problem_statement IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_problem_statement)) NOT BETWEEN 1 AND 8000
       OR requested_theory_of_change IS NOT NULL
          AND pg_catalog.length(requested_theory_of_change) > 4000
       OR requested_baseline_alternative IS NOT NULL
          AND pg_catalog.length(requested_baseline_alternative) > 4000
       OR requested_risk_class IS NULL
       OR requested_risk_class NOT IN ('low', 'medium', 'high', 'critical')
       OR requested_reversibility IS NULL
       OR requested_reversibility NOT IN ('high', 'medium', 'low', 'unknown')
       OR requested_rationale IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_rationale)) NOT BETWEEN 10 AND 4000
       OR requested_evidence IS NULL
       OR pg_catalog.jsonb_typeof(requested_evidence) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_evidence) > 100
       OR pg_catalog.octet_length(requested_evidence::TEXT) > 65536
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Location solution creation input is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id
      INTO actor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id
       AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, actor;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Solution creation requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    normalized_key := pg_catalog.btrim(requested_canonical_key);
    normalized_name := pg_catalog.btrim(requested_name);
    normalized_problem := pg_catalog.btrim(requested_problem_statement);
    normalized_rationale := pg_catalog.btrim(requested_rationale);
    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'canonical_key', normalized_key,
                'name', normalized_name,
                'solution_type', requested_solution_type,
                'problem_statement', normalized_problem,
                'theory_of_change', requested_theory_of_change,
                'baseline_alternative', requested_baseline_alternative,
                'risk_class', requested_risk_class,
                'reversibility', requested_reversibility,
                'rationale', normalized_rationale,
                'evidence', requested_evidence,
                'acknowledged', requested_acknowledged
            )::TEXT,
            'UTF8'
        ),
        'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.actor_party_id, receipt.location_id, receipt.solution_id,
           receipt.lifecycle_event_id, receipt.canonical_key, receipt.solution_name,
           receipt.solution_type, receipt.current_stage, receipt.solution_status,
           receipt.payload_digest, receipt.created_at
      INTO prior_receipt
      FROM public.location_solution_creation_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Solution creation request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_receipt.solution_id,
                            prior_receipt.lifecycle_event_id,
                            prior_receipt.canonical_key::TEXT,
                            prior_receipt.solution_name::TEXT,
                            prior_receipt.solution_type::TEXT,
                            prior_receipt.current_stage::TEXT,
                            prior_receipt.solution_status::TEXT,
                            prior_receipt.created_at, TRUE;
        RETURN;
    END IF;

    INSERT INTO public.solution AS created_solution (
        canonical_key, name, solution_type, problem_statement, theory_of_change,
        baseline_alternative, originating_scope_type, originating_scope_id,
        created_by_party_id, risk_class, reversibility, current_stage, status
    ) VALUES (
        normalized_key, normalized_name, requested_solution_type,
        normalized_problem, requested_theory_of_change,
        requested_baseline_alternative, 'location', requested_location_id,
        actor_party_id, requested_risk_class, requested_reversibility,
        'discovered', 'active'
    ) RETURNING created_solution.id, created_solution.canonical_key,
               created_solution.name, created_solution.solution_type,
               created_solution.current_stage, created_solution.status,
               created_solution.created_at
      INTO solution_record;

    INSERT INTO public.solution_lifecycle_event AS created_event (
        solution_id, from_stage, to_stage, rationale, evidence, actor_party_id
    ) VALUES (
        solution_record.id, NULL, 'discovered', normalized_rationale,
        requested_evidence, actor_party_id
    ) RETURNING created_event.id, created_event.created_at INTO event_record;

    INSERT INTO public.location_solution_creation_receipt (
        operator_id, actor_party_id, location_id, solution_id, lifecycle_event_id,
        canonical_key, solution_name, solution_type, current_stage, solution_status,
        request_id, payload_digest, created_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        solution_record.id, event_record.id, solution_record.canonical_key,
        solution_record.name, solution_record.solution_type,
        solution_record.current_stage, solution_record.status, requested_request_id,
        payload_digest, event_record.created_at
    );

    RETURN QUERY SELECT solution_record.id, event_record.id,
                        solution_record.canonical_key::TEXT,
                        solution_record.name::TEXT,
                        solution_record.solution_type::TEXT,
                        solution_record.current_stage::TEXT,
                        solution_record.status::TEXT,
                        event_record.created_at, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_creator_owner;
ALTER FUNCTION kokonut_security.create_location_solution(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, BOOLEAN
) OWNER TO kokonut_solution_creator_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_creator_owner;
REVOKE ALL ON FUNCTION kokonut_security.create_location_solution(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_solution(
            UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_location_solution(
            UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_solution(
    UUID, UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, BOOLEAN
) IS 'Creates a discovered canonical solution with an exact location origin, attributed opening lifecycle event, and immutable retry receipt under signed solution_lifecycle:create context. It creates no cross-location link or stage gate.';

COMMIT;
