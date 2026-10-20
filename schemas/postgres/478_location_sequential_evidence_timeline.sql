-- Bounded, redacted evidence and posterior sequence metadata for one location.

BEGIN;

CREATE OR REPLACE FUNCTION kokonut_security.location_sequential_evidence_timeline(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    timeline JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Sequential evidence timeline requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'sequential_evidence', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Sequential evidence timeline requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Sequential evidence timeline page is outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    WITH scoped_hypotheses AS (
        SELECT hypothesis.id,
               hypothesis.subject_type,
               row_number() OVER (ORDER BY hypothesis.created_at, hypothesis.id)::INTEGER
                   AS hypothesis_sequence
          FROM public.decision_hypothesis AS hypothesis
         WHERE (hypothesis.subject_type = 'strategy_plan' AND EXISTS (
                    SELECT 1 FROM public.strategy_plan AS plan
                     WHERE plan.id = hypothesis.subject_id
                       AND plan.scope_type = 'location'
                       AND plan.scope_id = requested_location_id
                ))
            OR (hypothesis.subject_type = 'threat' AND EXISTS (
                    SELECT 1 FROM public.threat AS item
                     WHERE item.id = hypothesis.subject_id
                       AND item.location_id = requested_location_id
                ))
            OR (hypothesis.subject_type = 'solution' AND EXISTS (
                    SELECT 1 FROM public.solution AS item
                     WHERE item.id = hypothesis.subject_id
                       AND ((item.originating_scope_type = 'location'
                             AND item.originating_scope_id = requested_location_id)
                            OR EXISTS (
                                SELECT 1 FROM public.solution_link AS location_link
                                 WHERE location_link.solution_id = item.id
                                   AND location_link.entity_type = 'location'
                                   AND location_link.entity_id = requested_location_id
                            ))
                ))
    ), scoped_updates AS (
        SELECT update_row.hypothesis_id,
               update_row.evidence_event_id,
               row_number() OVER (
                   PARTITION BY update_row.hypothesis_id
                   ORDER BY update_row.created_at, update_row.id
               )::INTEGER AS posterior_update_sequence,
               update_row.calculation_version,
               update_row.created_at AS posterior_updated_at
          FROM public.decision_posterior_update AS update_row
          JOIN scoped_hypotheses AS scoped ON scoped.id = update_row.hypothesis_id
    ), scoped_events AS (
        SELECT scoped.hypothesis_sequence,
               scoped.subject_type,
               row_number() OVER (
                   PARTITION BY event.hypothesis_id
                   ORDER BY event.observed_at, event.ingested_at, event.created_at, event.id
               )::INTEGER AS evidence_sequence,
               event.observed_at,
               event.ingested_at,
               event.evidence_class,
               event.quality_status,
               posterior.posterior_update_sequence,
               posterior.calculation_version,
               posterior.posterior_updated_at,
               event.created_at AS event_created_at,
               event.id AS ordering_id
          FROM public.decision_evidence_event AS event
          JOIN scoped_hypotheses AS scoped ON scoped.id = event.hypothesis_id
          LEFT JOIN scoped_updates AS posterior
            ON posterior.hypothesis_id = event.hypothesis_id
           AND posterior.evidence_event_id = event.id
    ), page_window AS (
        SELECT *
          FROM scoped_events
         ORDER BY hypothesis_sequence, observed_at, ingested_at, event_created_at, ordering_id
         OFFSET requested_offset
         LIMIT requested_limit + 1
    ), page_rows AS (
        SELECT page_window.*,
               row_number() OVER (
                   ORDER BY hypothesis_sequence, observed_at, ingested_at,
                            event_created_at, ordering_id
               )::INTEGER AS page_sequence
          FROM page_window
    )
    SELECT jsonb_build_object(
        'limit', requested_limit,
        'offset', requested_offset,
        'items', COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'hypothesis_sequence', page.hypothesis_sequence,
                    'subject_type', page.subject_type,
                    'evidence_sequence', page.evidence_sequence,
                    'observed_at', page.observed_at,
                    'ingested_at', page.ingested_at,
                    'evidence_class', page.evidence_class,
                    'quality_status', page.quality_status,
                    'posterior_update_sequence', page.posterior_update_sequence,
                    'calculation_version', page.calculation_version,
                    'posterior_updated_at', page.posterior_updated_at
                ) ORDER BY page.page_sequence
            ) FILTER (WHERE page.page_sequence <= requested_limit),
            '[]'::JSONB
        ),
        'has_more', COALESCE(bool_or(page.page_sequence > requested_limit), FALSE),
        'next_offset', CASE
            WHEN COALESCE(bool_or(page.page_sequence > requested_limit), FALSE)
                THEN requested_offset + requested_limit
            ELSE NULL
        END
    )
      INTO timeline
      FROM page_rows AS page;

    RETURN timeline;
END;
$$;

ALTER FUNCTION kokonut_security.location_sequential_evidence_timeline(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_sequential_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_sequential_evidence_timeline(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_sequential_evidence_timeline(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_sequential_evidence_timeline(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.location_sequential_evidence_timeline(
    UUID, INTEGER, INTEGER
) IS
'Returns a bounded location-scoped evidence sequence using opaque hypothesis/event ordinals and review metadata only; omits statements, source references/IDs, evidence values, likelihoods, posterior probabilities, and identities.';

COMMIT;
