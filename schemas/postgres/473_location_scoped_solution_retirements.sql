-- Bounded retirement status for solutions originated at the exact location.

BEGIN;

REVOKE ALL ON TABLE public.solution_retirement FROM kokonut_solution_reader;
GRANT SELECT (
    id, solution_id, retirement_type, status, approved_by_party_id,
    approved_at, effective_at, post_retirement_review_at, created_at
) ON TABLE public.solution_retirement TO kokonut_solution_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_retirements(
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
    retirement_id UUID,
    retirement_type TEXT,
    retirement_status TEXT,
    has_human_approval BOOLEAN,
    approved_at TIMESTAMPTZ,
    effective_at TIMESTAMPTZ,
    post_retirement_review_at DATE,
    created_at TIMESTAMPTZ
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
        RAISE EXCEPTION 'Solution retirement read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution retirement read requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Solution retirement page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    WITH scoped_solutions AS (
        SELECT solution.id, solution.name, solution.solution_type,
               solution.current_stage, solution.status
          FROM public.solution AS solution
         WHERE solution.originating_scope_type = 'location'
           AND solution.originating_scope_id = requested_location_id
    )
    SELECT scoped.id,
           pg_catalog.left(scoped.name, 255)::TEXT,
           scoped.solution_type::TEXT,
           scoped.current_stage::TEXT,
           scoped.status::TEXT,
           retirement.id,
           retirement.retirement_type::TEXT,
           retirement.status::TEXT,
           retirement.approved_by_party_id IS NOT NULL,
           retirement.approved_at,
           retirement.effective_at,
           retirement.post_retirement_review_at,
           retirement.created_at
      FROM scoped_solutions AS scoped
      JOIN public.solution_retirement AS retirement
        ON retirement.solution_id = scoped.id
     ORDER BY retirement.created_at DESC, retirement.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_reader;
ALTER FUNCTION kokonut_security.list_location_solution_retirements(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_retirements(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_retirements(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_retirements(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_solution_retirements(UUID, INTEGER, INTEGER) IS
'Returns bounded retirement metadata only for solutions originated at the exact requested location; exact solution_lifecycle:read and signed location context are rechecked, while trigger reasons, impact, affected-user lists, dependencies, replacement links, migration/remedy plans, evidence, and party identities are omitted. Explicit location links alone do not expose retirement records because the source table has no location target.';

COMMIT;
