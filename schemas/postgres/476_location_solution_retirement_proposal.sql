-- Location-granted, OIDC-attributed solution retirement proposal with an idempotent receipt.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_proposal_owner'
    ) THEN
        CREATE ROLE kokonut_solution_proposal_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_proposal_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution proposal owner role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_proposal_owner'
            OR member_role.rolname = 'kokonut_solution_proposal_owner'
    ) THEN
        RAISE EXCEPTION 'Solution proposal owner role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_retirement_proposal_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    proposer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    retirement_id UUID NOT NULL UNIQUE REFERENCES public.solution_retirement(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_retirement_proposal_event FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_retirement_proposal_event
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader;
REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_solution_proposal_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_solution_proposal_owner;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_solution_proposal_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_solution_proposal_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_solution_proposal_owner;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_solution_proposal_owner;
GRANT SELECT, INSERT ON TABLE public.solution_retirement_proposal_event
    TO kokonut_solution_proposal_owner;

GRANT SELECT (solution_id, entity_type, entity_id)
    ON TABLE public.solution_link TO kokonut_solution_proposal_owner;
GRANT SELECT (id, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_proposal_owner;
GRANT UPDATE (id) ON TABLE public.solution TO kokonut_solution_proposal_owner;
GRANT SELECT (id, solution_id, retirement_type, trigger_reason, evidence_refs,
              replacement_solution_id, migration_plan, status, created_by_party_id,
              created_at)
    ON TABLE public.solution_retirement TO kokonut_solution_proposal_owner;
GRANT INSERT (id, solution_id, status, retirement_type, trigger_reason, evidence_refs,
              replacement_solution_id, migration_plan, created_by_party_id, created_at)
    ON TABLE public.solution_retirement TO kokonut_solution_proposal_owner;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding TO kokonut_solution_proposal_owner;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity TO kokonut_solution_proposal_owner;
GRANT SELECT (id, party_type, status) ON TABLE public.party TO kokonut_solution_proposal_owner;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding,
    public.operator_identity, public.party TO kokonut_solution_proposal_owner;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_solution_proposal_owner;
GRANT SELECT (id, organization_id) ON TABLE public.location TO kokonut_solution_proposal_owner;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership TO kokonut_solution_proposal_owner;
GRANT SELECT (id, status) ON TABLE public.organization TO kokonut_solution_proposal_owner;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification TO kokonut_solution_proposal_owner;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share TO kokonut_solution_proposal_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_proposal_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_proposal_owner;

CREATE OR REPLACE FUNCTION kokonut_security.propose_location_solution_retirement(
    requested_location_id UUID,
    requested_solution_id UUID,
    requested_request_id UUID,
    requested_retirement_type TEXT,
    requested_trigger_reason TEXT,
    requested_evidence_refs JSONB,
    requested_migration_plan TEXT,
    requested_replacement_solution_id UUID DEFAULT NULL
)
RETURNS TABLE (
    event_id UUID,
    retirement_id UUID,
    retirement_status TEXT,
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
    existing_proposal RECORD;
    selected_solution RECORD;
    generated_retirement_id UUID;
    generated_event_id UUID;
    proposal_timestamp TIMESTAMPTZ;
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
        RAISE EXCEPTION 'Solution retirement proposal requires signed operator location context and request identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution retirement proposal requires an active exact location grant'
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
     FOR SHARE OF binding, operator, proposer;
    IF proposer_party_id IS NULL THEN
        RAISE EXCEPTION 'Operator has no active human governance-party binding'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || requested_request_id::TEXT, 0)
    );

    SELECT proposal.id, proposal.location_id, proposal.retirement_id,
           retirement.solution_id, retirement.retirement_type,
           retirement.trigger_reason, retirement.evidence_refs,
           retirement.replacement_solution_id, retirement.migration_plan,
           retirement.status, retirement.created_by_party_id, proposal.created_at
      INTO existing_proposal
      FROM public.solution_retirement_proposal_event AS proposal
      JOIN public.solution_retirement AS retirement
        ON retirement.id = proposal.retirement_id
     WHERE proposal.operator_id = context_record.actor_id
       AND proposal.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_proposal.location_id IS DISTINCT FROM requested_location_id
           OR existing_proposal.solution_id IS DISTINCT FROM requested_solution_id
           OR existing_proposal.retirement_type IS DISTINCT FROM requested_retirement_type
           OR existing_proposal.trigger_reason IS DISTINCT FROM requested_trigger_reason
           OR existing_proposal.evidence_refs IS DISTINCT FROM requested_evidence_refs
           OR existing_proposal.migration_plan IS DISTINCT FROM requested_migration_plan
           OR existing_proposal.replacement_solution_id IS DISTINCT FROM requested_replacement_solution_id
           OR existing_proposal.created_by_party_id IS DISTINCT FROM proposer_party_id THEN
            RAISE EXCEPTION 'Solution retirement proposal request id was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        event_id := existing_proposal.id;
        retirement_id := existing_proposal.retirement_id;
        retirement_status := existing_proposal.status;
        created_at := existing_proposal.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT solution.id
      INTO selected_solution
      FROM public.solution AS solution
     WHERE solution.id = requested_solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR SHARE OF solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Solution was not found as originating at this location'
            USING ERRCODE = 'P0002';
    END IF;

    IF requested_retirement_type IS NULL OR requested_retirement_type NOT IN (
        'unsafe', 'ineffective', 'too_costly', 'superseded', 'not_adopted',
        'context_invalidated', 'evidence_withdrawn', 'maintenance_failure',
        'governance_breach', 'mission_complete'
    ) THEN
        RAISE EXCEPTION 'Solution retirement type is invalid'
            USING ERRCODE = '22023';
    END IF;
    IF requested_trigger_reason IS NULL
       OR pg_catalog.btrim(requested_trigger_reason) = ''
       OR pg_catalog.char_length(requested_trigger_reason) > 2000 THEN
        RAISE EXCEPTION 'Solution retirement requires a bounded trigger reason'
            USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.jsonb_typeof(requested_evidence_refs) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Solution retirement requires bounded nonempty evidence references'
            USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.jsonb_array_length(requested_evidence_refs) = 0
       OR pg_catalog.jsonb_array_length(requested_evidence_refs) > 100
       OR pg_catalog.pg_column_size(requested_evidence_refs) > 65536 THEN
        RAISE EXCEPTION 'Solution retirement requires bounded nonempty evidence references'
            USING ERRCODE = '22023';
    END IF;
    IF requested_migration_plan IS NULL
       OR pg_catalog.btrim(requested_migration_plan) = ''
       OR pg_catalog.char_length(requested_migration_plan) > 4000 THEN
        RAISE EXCEPTION 'Solution retirement requires a bounded migration plan'
            USING ERRCODE = '22023';
    END IF;
    IF requested_replacement_solution_id IS NOT NULL THEN
        IF requested_replacement_solution_id = requested_solution_id
           OR NOT EXISTS (
               SELECT 1
                 FROM public.solution AS replacement
                WHERE replacement.id = requested_replacement_solution_id
                  AND (
                      (replacement.originating_scope_type = 'location'
                       AND replacement.originating_scope_id = requested_location_id)
                      OR EXISTS (
                          SELECT 1 FROM public.solution_link AS location_link
                           WHERE location_link.solution_id = replacement.id
                             AND location_link.entity_type = 'location'
                             AND location_link.entity_id = requested_location_id
                      )
                  )
           ) THEN
            RAISE EXCEPTION 'Replacement solution must be distinct and visible at this location'
                USING ERRCODE = '22023';
        END IF;
    END IF;
    IF requested_retirement_type = 'superseded'
       AND requested_replacement_solution_id IS NULL THEN
        RAISE EXCEPTION 'Superseded retirement requires a location-visible replacement solution'
            USING ERRCODE = '22023';
    END IF;

    generated_retirement_id := pg_catalog.gen_random_uuid();
    proposal_timestamp := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_retirement (
        id, solution_id, status, retirement_type, trigger_reason, evidence_refs,
        replacement_solution_id, migration_plan, created_by_party_id, created_at
    ) VALUES (
        generated_retirement_id, requested_solution_id, 'proposed',
        requested_retirement_type, requested_trigger_reason, requested_evidence_refs,
        requested_replacement_solution_id, requested_migration_plan,
        proposer_party_id, proposal_timestamp
    ) RETURNING id, solution_retirement.created_at
      INTO generated_retirement_id, proposal_timestamp;

    INSERT INTO public.solution_retirement_proposal_event (
        operator_id, proposer_party_id, location_id, retirement_id,
        request_id, created_at
    ) VALUES (
        context_record.actor_id, proposer_party_id, requested_location_id,
        generated_retirement_id, requested_request_id, proposal_timestamp
    ) RETURNING id INTO generated_event_id;

    event_id := generated_event_id;
    retirement_id := generated_retirement_id;
    retirement_status := 'proposed';
    created_at := proposal_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_proposal_owner;
ALTER FUNCTION kokonut_security.propose_location_solution_retirement(
    UUID, UUID, UUID, TEXT, TEXT, JSONB, TEXT, UUID
) OWNER TO kokonut_solution_proposal_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_proposal_owner;
REVOKE ALL ON FUNCTION kokonut_security.propose_location_solution_retirement(
    UUID, UUID, UUID, TEXT, TEXT, JSONB, TEXT, UUID
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.propose_location_solution_retirement(
            UUID, UUID, UUID, TEXT, TEXT, JSONB, TEXT, UUID
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.propose_location_solution_retirement(
            UUID, UUID, UUID, TEXT, TEXT, JSONB, TEXT, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_retirement_proposal_event IS
'Append-only receipt for location-scoped, OIDC-attributed solution retirement proposals; runtime and Directus access is through the bounded security-definer function only.';
COMMENT ON FUNCTION kokonut_security.propose_location_solution_retirement(
    UUID, UUID, UUID, TEXT, TEXT, JSONB, TEXT, UUID
) IS
'Creates a bounded retirement proposal only for a solution originating at the exact location under signed solution_lifecycle:create context and an active OIDC-to-person binding; the proposal and idempotent receipt are atomic.';

COMMIT;
