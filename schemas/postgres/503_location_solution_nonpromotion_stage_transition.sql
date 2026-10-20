-- Add exact-location, auditable transitions for non-promotion lifecycle stages.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_nonpromotion_transition_owner'
    ) THEN
        CREATE ROLE kokonut_solution_nonpromotion_transition_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_nonpromotion_transition_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Non-promotion transition owner role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_nonpromotion_transition_owner'
            OR member_role.rolname = 'kokonut_solution_nonpromotion_transition_owner'
    ) THEN
        RAISE EXCEPTION 'Non-promotion transition owner role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_nonpromotion_transition_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    lifecycle_event_id UUID NOT NULL UNIQUE REFERENCES public.solution_lifecycle_event(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    from_stage VARCHAR(30) NOT NULL,
    to_stage VARCHAR(30) NOT NULL,
    solution_status VARCHAR(20) NOT NULL,
    transitioned_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id),
    CHECK (to_stage IN (
        'discovered', 'triaged', 'framed', 'experiment_ready', 'testing',
        'investment_ready', 'pilot_active', 'adopting', 'maintained',
        'paused', 'failed'
    ))
);

REVOKE ALL ON TABLE public.solution_nonpromotion_transition_receipt FROM PUBLIC;
DO $$
DECLARE
    target_role TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime', 'kokonut_solution_reader',
        'kokonut_solution_reviewer', 'kokonut_solution_action_owner',
        'kokonut_solution_proposal_owner', 'kokonut_solution_gate_transitioner',
        'kokonut_solution_retirement_execution_owner'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.solution_nonpromotion_transition_receipt FROM %I',
                target_role
            );
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_nonpromotion_transition_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_nonpromotion_transition_owner;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_nonpromotion_transition_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_nonpromotion_transition_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_nonpromotion_transition_owner;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_nonpromotion_transition_owner;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage, status)
    ON TABLE public.solution TO kokonut_solution_nonpromotion_transition_owner;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT UPDATE (current_stage, updated_at)
    ON TABLE public.solution TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (solution_id, target_scope_type, target_scope_id, status)
    ON TABLE public.solution_adoption_program
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (solution_id, adopter_scope_type, adopter_scope_id, readiness_status,
              assessed_by_party_id)
    ON TABLE public.solution_adopter_readiness
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (solution_id, scope_type, scope_id, approval_status, approved_by_party_id)
    ON TABLE public.solution_configuration
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT INSERT (solution_id, from_stage, to_stage, rationale, evidence,
              rollback_plan, actor_party_id, approved_by_party_id)
    ON TABLE public.solution_lifecycle_event
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (id, created_at) ON TABLE public.solution_lifecycle_event
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT SELECT (operator_id, request_id, location_id, solution_id, lifecycle_event_id,
              payload_digest, from_stage, to_stage, solution_status, transitioned_at)
    ON TABLE public.solution_nonpromotion_transition_receipt
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT INSERT (operator_id, actor_party_id, location_id, solution_id,
              lifecycle_event_id, request_id, payload_digest, from_stage, to_stage,
              solution_status, transitioned_at)
    ON TABLE public.solution_nonpromotion_transition_receipt
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_nonpromotion_transition_owner;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_nonpromotion_transition_owner;

GRANT SELECT (
    id, name, solution_type, originating_scope_type, originating_scope_id,
    current_stage, status, updated_at
) ON TABLE public.solution TO kokonut_solution_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_stage_transition_targets(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    solution_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    current_stage TEXT,
    solution_status TEXT,
    updated_at TIMESTAMPTZ
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
        RAISE EXCEPTION 'Stage transition target read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Stage transition target read requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Stage transition target page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT solution.id,
           pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT,
           solution.current_stage::TEXT,
           solution.status::TEXT,
           solution.updated_at
      FROM public.solution AS solution
     WHERE solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.status NOT IN ('retired', 'superseded')
       AND solution.current_stage NOT IN ('retired', 'superseded')
     ORDER BY pg_catalog.lower(solution.name), solution.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

ALTER FUNCTION kokonut_security.list_location_solution_stage_transition_targets(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_solution_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_stage_transition_targets(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;

CREATE OR REPLACE FUNCTION kokonut_security.transition_location_solution_stage(
    requested_location_id UUID,
    requested_solution_id UUID,
    requested_expected_from_stage TEXT,
    requested_to_stage TEXT,
    requested_request_id UUID,
    requested_rationale TEXT,
    requested_evidence JSONB,
    requested_rollback_plan TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    lifecycle_event_id UUID,
    solution_id UUID,
    from_stage TEXT,
    to_stage TEXT,
    solution_status TEXT,
    transitioned_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    solution_record RECORD;
    prior_receipt RECORD;
    event_record RECORD;
    target_status TEXT;
    payload_digest BYTEA;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_solution_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Stage transition requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'transition', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Stage transition requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_expected_from_stage IS NULL
       OR requested_to_stage IS NULL
       OR requested_to_stage NOT IN (
           'discovered', 'triaged', 'framed', 'experiment_ready', 'testing',
           'investment_ready', 'pilot_active', 'adopting', 'maintained',
           'paused', 'failed'
       )
       OR requested_expected_from_stage NOT IN (
           'discovered', 'triaged', 'framed', 'experiment_ready', 'testing',
           'validated', 'investment_ready', 'funded', 'pilot_active',
           'adoption_ready', 'adopting', 'scaled', 'maintained', 'paused',
           'superseded', 'retired', 'failed'
       )
       OR requested_expected_from_stage = requested_to_stage
       OR requested_acknowledged IS DISTINCT FROM TRUE
       OR requested_rationale IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_rationale)) NOT BETWEEN 10 AND 4000
       OR requested_evidence IS NULL
       OR pg_catalog.jsonb_typeof(requested_evidence) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_evidence) NOT BETWEEN 1 AND 100
       OR pg_catalog.octet_length(requested_evidence::TEXT) > 65536
       OR requested_rollback_plan IS NOT NULL
          AND pg_catalog.length(requested_rollback_plan) > 4000 THEN
        RAISE EXCEPTION 'Non-promotion stage transition input is invalid'
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
        RAISE EXCEPTION 'Stage transition requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'solution_id', requested_solution_id,
                'expected_from_stage', requested_expected_from_stage,
                'to_stage', requested_to_stage,
                'rationale', requested_rationale,
                'evidence', requested_evidence,
                'rollback_plan', requested_rollback_plan,
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
    SELECT receipt.location_id, receipt.solution_id, receipt.lifecycle_event_id,
           receipt.payload_digest, receipt.from_stage, receipt.to_stage,
           receipt.solution_status, receipt.transitioned_at
      INTO prior_receipt
      FROM public.solution_nonpromotion_transition_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.solution_id IS DISTINCT FROM requested_solution_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Stage transition request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_receipt.lifecycle_event_id,
                            prior_receipt.solution_id,
                            prior_receipt.from_stage::TEXT,
                            prior_receipt.to_stage::TEXT,
                            prior_receipt.solution_status::TEXT,
                            prior_receipt.transitioned_at, TRUE;
        RETURN;
    END IF;

    SELECT solution.id, solution.current_stage, solution.status
      INTO solution_record
      FROM public.solution AS solution
     WHERE solution.id = requested_solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR UPDATE OF solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location-origin solution was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF solution_record.current_stage IS DISTINCT FROM requested_expected_from_stage
       OR solution_record.current_stage IN ('retired', 'superseded')
       OR solution_record.status IN ('retired', 'superseded') THEN
        RAISE EXCEPTION 'Solution stage changed or is terminal; refresh before transition'
            USING ERRCODE = '55000';
    END IF;

    IF requested_to_stage = 'adopting'
       AND NOT EXISTS (
           SELECT 1
             FROM public.solution_adoption_program AS program
             JOIN public.solution_adopter_readiness AS readiness
               ON readiness.solution_id = program.solution_id
              AND readiness.adopter_scope_type = program.target_scope_type
              AND readiness.adopter_scope_id = program.target_scope_id
             JOIN public.solution_configuration AS configuration
               ON configuration.solution_id = program.solution_id
              AND configuration.scope_type = program.target_scope_type
              AND configuration.scope_id = program.target_scope_id
            WHERE program.solution_id = solution_record.id
              AND program.target_scope_type = 'location'
              AND program.target_scope_id = requested_location_id
              AND program.status IN (
                  'enablement_ready', 'launch', 'onboarding', 'active', 'assessed', 'expand'
              )
              AND readiness.readiness_status = 'ready'
              AND readiness.assessed_by_party_id IS NOT NULL
              AND configuration.approval_status = 'approved'
              AND configuration.approved_by_party_id IS NOT NULL
       ) THEN
        RAISE EXCEPTION 'Approved location adoption configuration and readiness are required'
            USING ERRCODE = '55000';
    END IF;

    target_status := solution_record.status;
    UPDATE public.solution AS solution
       SET current_stage = requested_to_stage,
           updated_at = pg_catalog.clock_timestamp()
     WHERE solution.id = solution_record.id;

    INSERT INTO public.solution_lifecycle_event (
        solution_id, from_stage, to_stage, rationale, evidence, rollback_plan,
        actor_party_id, approved_by_party_id
    ) VALUES (
        solution_record.id, solution_record.current_stage, requested_to_stage,
        pg_catalog.btrim(requested_rationale), requested_evidence,
        requested_rollback_plan, actor_party_id, NULL
    ) RETURNING id, created_at INTO event_record;

    INSERT INTO public.solution_nonpromotion_transition_receipt (
        operator_id, actor_party_id, location_id, solution_id, lifecycle_event_id,
        request_id, payload_digest, from_stage, to_stage, solution_status,
        transitioned_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        solution_record.id, event_record.id, requested_request_id, payload_digest,
        solution_record.current_stage, requested_to_stage, target_status,
        event_record.created_at
    );
    RETURN QUERY SELECT event_record.id, solution_record.id,
                        solution_record.current_stage::TEXT, requested_to_stage,
                        target_status, event_record.created_at, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_nonpromotion_transition_owner;
ALTER FUNCTION kokonut_security.transition_location_solution_stage(
    UUID, UUID, TEXT, TEXT, UUID, TEXT, JSONB, TEXT, BOOLEAN
) OWNER TO kokonut_solution_nonpromotion_transition_owner;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_nonpromotion_transition_owner;
REVOKE ALL ON FUNCTION kokonut_security.transition_location_solution_stage(
    UUID, UUID, TEXT, TEXT, UUID, TEXT, JSONB, TEXT, BOOLEAN
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_stage_transition_targets(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.transition_location_solution_stage(
            UUID, UUID, TEXT, TEXT, UUID, TEXT, JSONB, TEXT, BOOLEAN
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_stage_transition_targets(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.transition_location_solution_stage(
            UUID, UUID, TEXT, TEXT, UUID, TEXT, JSONB, TEXT, BOOLEAN
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_stage_transition_targets(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_nonpromotion_transition_receipt IS
'Private append-only receipts for acknowledged, exact-location transitions to non-promotion solution stages.';
COMMENT ON FUNCTION kokonut_security.transition_location_solution_stage(
    UUID, UUID, TEXT, TEXT, UUID, TEXT, JSONB, TEXT, BOOLEAN
) IS
'Atomically records an exact-origin solution transition to a non-terminal, non-promotion stage after signed exact-location scope, active human identity, rationale, evidence, acknowledgement, and expected-stage checks. Promotion stages and terminal retirement/supersession remain on their dedicated guarded workflows; adopting also requires approved location readiness and configuration.';

COMMIT;
