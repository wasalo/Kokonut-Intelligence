-- Bounded status for replications targeting an exact location.

BEGIN;

REVOKE ALL ON TABLE public.solution_replication FROM kokonut_solution_reader;
GRANT SELECT (
    id, solution_id, target_scope_type, target_scope_id, result,
    evidence_maturity, status, reviewed_by_party_id, created_at, completed_at
) ON TABLE public.solution_replication TO kokonut_solution_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_replications(
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
    replication_id UUID,
    replication_status TEXT,
    replication_result TEXT,
    evidence_maturity INTEGER,
    has_review BOOLEAN,
    replication_created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
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
        RAISE EXCEPTION 'Solution replication read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution replication read requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Solution replication page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    WITH scoped_solutions AS (
        SELECT solution.id, solution.name, solution.solution_type,
               solution.current_stage, solution.status
          FROM public.solution AS solution
         WHERE (solution.originating_scope_type = 'location'
                AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1
                  FROM public.solution_link AS location_link
                 WHERE location_link.solution_id = solution.id
                   AND location_link.entity_type = 'location'
                   AND location_link.entity_id = requested_location_id
            )
    )
    SELECT scoped.id,
           pg_catalog.left(scoped.name, 255)::TEXT,
           scoped.solution_type::TEXT,
           scoped.current_stage::TEXT,
           scoped.status::TEXT,
           replication.id,
           replication.status::TEXT,
           replication.result::TEXT,
           replication.evidence_maturity,
           replication.reviewed_by_party_id IS NOT NULL,
           replication.created_at,
           replication.completed_at
      FROM scoped_solutions AS scoped
      JOIN public.solution_replication AS replication
        ON replication.solution_id = scoped.id
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
     ORDER BY replication.created_at DESC, replication.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_reader;
ALTER FUNCTION kokonut_security.list_location_solution_replications(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_replications(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_replications(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_replications(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_solution_replications(UUID, INTEGER, INTEGER) IS
'Returns bounded lifecycle status for replications targeting the exact location and belonging to solutions originated in or explicitly linked to that location; exact solution_lifecycle:read and signed location context are rechecked, and target narratives, adaptation plans, protocols, evidence, source-experiment IDs, and reviewer identities are omitted.';

COMMIT;
