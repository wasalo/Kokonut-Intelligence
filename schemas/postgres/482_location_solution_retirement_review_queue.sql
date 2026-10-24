-- Scoped reviewer inbox and detail reads for proposed location-origin retirements.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_reviewer'
    ) THEN
        CREATE ROLE kokonut_solution_reviewer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_reviewer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution reviewer role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_reviewer'
            OR member_role.rolname = 'kokonut_solution_reviewer'
    ) THEN
        RAISE EXCEPTION 'Solution reviewer role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_solution_reviewer;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_solution_reviewer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_solution_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_solution_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_solution_reviewer;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_solution_reviewer;

GRANT SELECT (id, name, solution_type, current_stage, status,
              originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_reviewer;
GRANT SELECT (id, solution_id, retirement_type, trigger_reason, evidence_refs,
              replacement_solution_id, migration_plan, status, created_by_party_id,
              created_at)
    ON TABLE public.solution_retirement TO kokonut_solution_reviewer;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding TO kokonut_solution_reviewer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity TO kokonut_solution_reviewer;
GRANT SELECT (id, party_type, status) ON TABLE public.party TO kokonut_solution_reviewer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_solution_reviewer;
GRANT SELECT (id, organization_id) ON TABLE public.location TO kokonut_solution_reviewer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership TO kokonut_solution_reviewer;
GRANT SELECT (id, status) ON TABLE public.organization TO kokonut_solution_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification TO kokonut_solution_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share TO kokonut_solution_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_reviewer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_reviewer;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_retirement_review_queue(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    retirement_id UUID,
    solution_id UUID,
    solution_name TEXT,
    retirement_type TEXT,
    retirement_status TEXT,
    created_at TIMESTAMPTZ,
    proposer_attributed BOOLEAN,
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
        RAISE EXCEPTION 'Retirement review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Retirement review queue requires an active exact location grant'
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
        RAISE EXCEPTION 'Operator has no active human governance-party binding'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Retirement review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT retirement.id,
           solution.id,
           pg_catalog.left(solution.name, 255)::TEXT,
           retirement.retirement_type::TEXT,
           retirement.status::TEXT,
           retirement.created_at,
           retirement.created_by_party_id IS NOT NULL,
           COALESCE(retirement.created_by_party_id = reviewer_party_id, FALSE)
      FROM public.solution_retirement AS retirement
      JOIN public.solution AS solution
        ON solution.id = retirement.solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     WHERE retirement.status IN ('proposed', 'impact_review')
     ORDER BY retirement.created_at DESC, retirement.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_solution_retirement_review_detail(
    requested_location_id UUID,
    requested_retirement_id UUID
)
RETURNS TABLE (
    retirement_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    current_stage TEXT,
    solution_status TEXT,
    retirement_type TEXT,
    retirement_status TEXT,
    trigger_reason TEXT,
    evidence_refs JSONB,
    migration_plan TEXT,
    replacement_solution_name TEXT,
    created_at TIMESTAMPTZ,
    proposer_attributed BOOLEAN,
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
       OR requested_location_id IS NULL
       OR requested_retirement_id IS NULL THEN
        RAISE EXCEPTION 'Retirement review detail requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Retirement review detail requires an active exact location grant'
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
        RAISE EXCEPTION 'Operator has no active human governance-party binding'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT retirement.id,
           pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT,
           solution.current_stage::TEXT,
           solution.status::TEXT,
           retirement.retirement_type::TEXT,
           retirement.status::TEXT,
           pg_catalog.left(retirement.trigger_reason, 2000)::TEXT,
           retirement.evidence_refs,
           pg_catalog.left(retirement.migration_plan, 4000)::TEXT,
           pg_catalog.left(replacement.name, 255)::TEXT,
           retirement.created_at,
           retirement.created_by_party_id IS NOT NULL,
           COALESCE(retirement.created_by_party_id = reviewer_party_id, FALSE)
      FROM public.solution_retirement AS retirement
      JOIN public.solution AS solution
        ON solution.id = retirement.solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
      LEFT JOIN public.solution AS replacement
        ON replacement.id = retirement.replacement_solution_id
       AND replacement.originating_scope_type = 'location'
       AND replacement.originating_scope_id = requested_location_id
     WHERE retirement.id = requested_retirement_id
       AND retirement.status IN ('proposed', 'impact_review');
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pending location-origin retirement review was not found'
            USING ERRCODE = 'P0002';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.enforce_location_retirement_replacement_scope()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    target_location_id UUID;
    target_scope_type TEXT;
    target_scope_id UUID;
    replacement_scope_type TEXT;
    replacement_scope_id UUID;
BEGIN
    IF NEW.status IS DISTINCT FROM 'approved'
       OR NEW.retirement_type IS DISTINCT FROM 'superseded' THEN
        RETURN NEW;
    END IF;

    SELECT solution.originating_scope_type, solution.originating_scope_id
      INTO target_scope_type, target_scope_id
      FROM public.solution AS solution
     WHERE solution.id = NEW.solution_id;
    IF target_scope_type IS DISTINCT FROM 'location' THEN
        RETURN NEW;
    END IF;
    target_location_id := target_scope_id;

    SELECT solution.originating_scope_type, solution.originating_scope_id
      INTO replacement_scope_type, replacement_scope_id
      FROM public.solution AS solution
     WHERE solution.id = NEW.replacement_solution_id;
    IF NEW.replacement_solution_id IS NULL
       OR NEW.replacement_solution_id = NEW.solution_id
       OR replacement_scope_type IS DISTINCT FROM 'location'
       OR replacement_scope_id IS DISTINCT FROM target_location_id THEN
        RAISE EXCEPTION 'Location-origin superseded retirement requires a distinct replacement from the same location'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_action_owner;
ALTER FUNCTION kokonut_security.enforce_location_retirement_replacement_scope()
    OWNER TO kokonut_solution_action_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_action_owner;

DROP TRIGGER IF EXISTS solution_retirement_replacement_scope_guard
    ON public.solution_retirement;
CREATE TRIGGER solution_retirement_replacement_scope_guard
    BEFORE INSERT OR UPDATE OF solution_id, retirement_type, replacement_solution_id, status
    ON public.solution_retirement
    FOR EACH ROW
    EXECUTE FUNCTION kokonut_security.enforce_location_retirement_replacement_scope();

ALTER FUNCTION kokonut_security.list_location_solution_retirement_review_queue(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_reviewer;
ALTER FUNCTION kokonut_security.get_location_solution_retirement_review_detail(UUID, UUID)
    OWNER TO kokonut_solution_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_retirement_review_queue(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_retirement_review_detail(UUID, UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_retirement_review_queue(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.get_location_solution_retirement_review_detail(UUID, UUID)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_retirement_review_queue(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_retirement_review_detail(UUID, UUID)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_solution_retirement_review_queue(UUID, INTEGER, INTEGER) IS
'Returns a bounded pending retirement queue only for exact location-origin solutions under an active exact solution_lifecycle:review grant and signed operator context. Exposes no proposer identity or proposal narrative; reports only whether the current reviewer is the proposer.';
COMMENT ON FUNCTION kokonut_security.get_location_solution_retirement_review_detail(UUID, UUID) IS
'Returns submitted trigger, evidence references, remedy plan, and bounded solution labels for one pending retirement of an exact location-origin solution under an active exact solution_lifecycle:review grant and signed operator context. Private detail is withheld from the general solution reader; party identities are omitted and self-authorship is reported only as a boolean.';
COMMENT ON FUNCTION kokonut_security.enforce_location_retirement_replacement_scope() IS
'Prevents approval of a location-origin superseded solution retirement unless its replacement is a distinct solution whose canonical origin is the same location.';

COMMIT;
