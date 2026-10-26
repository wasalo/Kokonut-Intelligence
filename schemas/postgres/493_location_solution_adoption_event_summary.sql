-- Bounded, small-cohort-suppressed adoption progress summary for one location program.

BEGIN;

GRANT SELECT (event_type) ON TABLE public.solution_adoption_event
    TO kokonut_solution_reader;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_solution_adoption_event_summary(
    requested_location_id UUID,
    requested_program_id UUID
)
RETURNS TABLE (
    program_id UUID,
    engagement_reference_count BIGINT,
    commitment_reference_count BIGINT,
    use_reference_count BIGINT,
    advocacy_reference_count BIGINT,
    paused_or_abandoned_reference_count BIGINT,
    breakdown_suppressed BOOLEAN
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    scoped_program_id UUID;
    engagement_count BIGINT;
    commitment_count BIGINT;
    use_count BIGINT;
    advocacy_count BIGINT;
    paused_or_abandoned_count BIGINT;
    suppress_breakdown BOOLEAN;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_program_id IS NULL THEN
        RAISE EXCEPTION 'Solution adoption detail requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution adoption detail requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;

    SELECT program.id
      INTO scoped_program_id
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
     WHERE program.id = requested_program_id
       AND program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
       AND (
           (solution.originating_scope_type = 'location'
            AND solution.originating_scope_id = requested_location_id)
           OR EXISTS (
               SELECT 1
                 FROM public.solution_link AS location_link
                WHERE location_link.solution_id = solution.id
                  AND location_link.entity_type = 'location'
                  AND location_link.entity_id = requested_location_id
           )
       );
    IF scoped_program_id IS NULL THEN
        RAISE EXCEPTION 'Exact-location adoption program was not found'
            USING ERRCODE = 'P0002';
    END IF;

    WITH normalized_events AS (
        SELECT pg_catalog.lower(pg_catalog.btrim(event.adopter_ref)) AS adopter_ref,
               CASE
                   WHEN event.event_type IN ('aware', 'interested', 'eligible') THEN 'engagement'
                   WHEN event.event_type IN ('committed', 'onboarded') THEN 'commitment'
                   WHEN event.event_type IN ('first_use', 'repeat_use', 'habitual_use') THEN 'use'
                   WHEN event.event_type = 'advocating' THEN 'advocacy'
                   WHEN event.event_type IN ('paused', 'abandoned') THEN 'paused_or_abandoned'
               END AS progress_phase
          FROM public.solution_adoption_event AS event
         WHERE event.program_id = scoped_program_id
           AND event.consent_checked IS TRUE
           AND NULLIF(pg_catalog.btrim(event.adopter_ref), '') IS NOT NULL
    ), phase_counts AS (
        SELECT count(DISTINCT adopter_ref) FILTER (WHERE progress_phase = 'engagement') AS engagement,
               count(DISTINCT adopter_ref) FILTER (WHERE progress_phase = 'commitment') AS commitment,
               count(DISTINCT adopter_ref) FILTER (WHERE progress_phase = 'use') AS usage,
               count(DISTINCT adopter_ref) FILTER (WHERE progress_phase = 'advocacy') AS advocacy,
               count(DISTINCT adopter_ref) FILTER (WHERE progress_phase = 'paused_or_abandoned') AS paused_or_abandoned
          FROM normalized_events
    )
    SELECT phase_counts.engagement,
           phase_counts.commitment,
           phase_counts.usage,
           phase_counts.advocacy,
           phase_counts.paused_or_abandoned,
           EXISTS (
               SELECT 1
                 FROM unnest(ARRAY[
                     phase_counts.engagement, phase_counts.commitment, phase_counts.usage,
                     phase_counts.advocacy, phase_counts.paused_or_abandoned
                 ]) AS phase_count
                WHERE phase_count BETWEEN 1 AND 4
           )
      INTO engagement_count, commitment_count, use_count,
           advocacy_count, paused_or_abandoned_count, suppress_breakdown
      FROM phase_counts;

    RETURN QUERY SELECT scoped_program_id,
        CASE WHEN suppress_breakdown THEN NULL ELSE engagement_count END,
        CASE WHEN suppress_breakdown THEN NULL ELSE commitment_count END,
        CASE WHEN suppress_breakdown THEN NULL ELSE use_count END,
        CASE WHEN suppress_breakdown THEN NULL ELSE advocacy_count END,
        CASE WHEN suppress_breakdown THEN NULL ELSE paused_or_abandoned_count END,
        suppress_breakdown;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_reader;
ALTER FUNCTION kokonut_security.get_location_solution_adoption_event_summary(UUID, UUID)
    OWNER TO kokonut_solution_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_reader;
REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_adoption_event_summary(UUID, UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.get_location_solution_adoption_event_summary(UUID, UUID)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_adoption_event_summary(UUID, UUID)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.get_location_solution_adoption_event_summary(UUID, UUID) IS
'Returns consent-checked distinct adopter reference counts in five coarse progress phases for one exact-location adoption program. The entire breakdown is suppressed if any nonzero phase has fewer than five references. No reference, cohort, event timestamp, fidelity, support, outcome, evidence, or identity detail is returned.';

COMMIT;
