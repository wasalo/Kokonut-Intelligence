-- Bounded location-scoped adoption program status with small-cohort suppression.

BEGIN;

REVOKE ALL ON TABLE public.solution_adoption_program FROM kokonut_solution_reader;
GRANT SELECT (
    id, solution_id, target_scope_type, target_scope_id, status, created_at, updated_at
) ON TABLE public.solution_adoption_program TO kokonut_solution_reader;
REVOKE ALL ON TABLE public.solution_adoption_event FROM kokonut_solution_reader;
GRANT SELECT (program_id, adopter_ref, consent_checked)
    ON TABLE public.solution_adoption_event TO kokonut_solution_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_adoption(
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
    program_id UUID,
    program_status TEXT,
    program_created_at TIMESTAMPTZ,
    program_updated_at TIMESTAMPTZ,
    consented_adopter_reference_count BIGINT
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
        RAISE EXCEPTION 'Solution adoption read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution adoption read requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Solution adoption page bounds are invalid'
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
           program.id,
           program.status::TEXT,
           program.created_at,
           program.updated_at,
           CASE WHEN consented.adopter_count >= 5 THEN consented.adopter_count
                ELSE NULL END
      FROM scoped_solutions AS scoped
      JOIN public.solution_adoption_program AS program
        ON program.solution_id = scoped.id
       AND program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
      CROSS JOIN LATERAL (
          SELECT count(DISTINCT NULLIF(
                     pg_catalog.lower(pg_catalog.btrim(event.adopter_ref)), ''
                 )) AS adopter_count
            FROM public.solution_adoption_event AS event
           WHERE event.program_id = program.id
             AND event.consent_checked IS TRUE
      ) AS consented
     ORDER BY program.created_at DESC, program.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_reader;
ALTER FUNCTION kokonut_security.list_location_solution_adoption(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_adoption(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_adoption(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_adoption(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_solution_adoption(UUID, INTEGER, INTEGER) IS
'Returns bounded location-targeted adoption program lifecycle state and only the count of distinct nonempty normalized consent-checked adopter references when at least five are present for solutions originated in or explicitly linked to one location; exact solution_lifecycle:read and signed location context are rechecked, participant-level details are omitted.';

COMMIT;
