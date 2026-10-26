-- Bounded, exact-origin solution choices for location-scoped retirement proposals.

BEGIN;

GRANT SELECT (
    id, name, solution_type, current_stage, status,
    originating_scope_type, originating_scope_id
) ON TABLE public.solution TO kokonut_solution_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_retirement_candidates(
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
        RAISE EXCEPTION 'Retirement candidate read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Retirement candidate read requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Retirement candidate page bounds are invalid'
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
     ORDER BY pg_catalog.lower(solution.name), solution.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

ALTER FUNCTION kokonut_security.list_location_solution_retirement_candidates(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_retirement_candidates(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_retirement_candidates(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_retirement_candidates(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_solution_retirement_candidates(UUID, INTEGER, INTEGER) IS
'Returns a bounded list of solution identifiers and fixed labels only when the solution originated at the exact requested location; exact solution_lifecycle:read and signed location context are rechecked. Shared location links alone do not make a solution eligible for a retirement proposal.';

COMMIT;
