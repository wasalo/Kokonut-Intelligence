-- Add independent review for captured hive inspections and harden legacy
-- pollinator review queues so records without known submitter attribution are
-- withheld from independent decisions.

BEGIN;

ALTER TABLE public.pollinator_hive_inspection
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
UPDATE public.pollinator_hive_inspection
   SET updated_at = created_at
 WHERE updated_at IS NULL;
ALTER TABLE public.pollinator_hive_inspection
    ALTER COLUMN updated_at SET DEFAULT pg_catalog.clock_timestamp(),
    ALTER COLUMN updated_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pollinator_hive_inspection_review_queue
    ON public.pollinator_hive_inspection (location_id, created_at DESC, id DESC)
    WHERE status = 'recorded' AND created_by_operator_id IS NOT NULL;

ALTER TABLE public.pollinator_review_decision
    DROP CONSTRAINT IF EXISTS pollinator_review_decision_record_type_check;
ALTER TABLE public.pollinator_review_decision
    ADD CONSTRAINT pollinator_review_decision_record_type_check
    CHECK (record_type IN ('observation', 'pesticide_impact', 'hive_inspection'));

DO $$
DECLARE
    role_name TEXT;
    role_sql TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF role_name = 'PUBLIC'
           OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            role_sql := CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC'
                             ELSE pg_catalog.quote_ident(role_name) END;
            EXECUTE pg_catalog.format(
                'REVOKE UPDATE (status, updated_at) ON TABLE public.pollinator_hive_inspection FROM %s',
                role_sql
            );
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_pollinator_review_writer;
GRANT SELECT (
    id, location_id, hive_record_id, inspection_date, colony_strength,
    colony_strength_score, queen_status, queen_seen, varroa_count, brood_pattern,
    honey_stores, disease_signs, temperament, population_estimate, swarm_cells,
    notes, status, created_by_operator_id, created_at, updated_at
) ON TABLE public.pollinator_hive_inspection
    TO kokonut_pollinator_review_writer;
GRANT UPDATE (status, updated_at) ON TABLE public.pollinator_hive_inspection
    TO kokonut_pollinator_review_writer;
GRANT SELECT (id, location_id, hive_id)
    ON TABLE public.hive_record TO kokonut_pollinator_review_writer;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_pollinator_review_queue(
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
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Pollinator review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'pollinator_health', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Pollinator review queue requires an exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Pollinator review page is outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    WITH eligible AS MATERIALIZED (
        SELECT observation.id AS record_id,
               'observation'::TEXT AS record_type,
               observation.observation_date AS occurred_on,
               observation.created_at,
               observation.updated_at,
               pg_catalog.jsonb_build_object(
                   'pollinator_type', observation.pollinator_type,
                   'count', observation.count,
                   'method', observation.observation_method,
                   'duration_minutes', observation.duration_minutes,
                   'species_name', observation.species_name,
                   'notes', pg_catalog.left(observation.notes, 2000)
               ) AS details
          FROM public.pollinator_observation AS observation
         WHERE observation.location_id = requested_location_id
           AND observation.status = 'recorded'
           AND observation.created_by_operator_id IS NOT NULL
           AND observation.created_by_operator_id <> context_record.actor_id
        UNION ALL
        SELECT pesticide.id AS record_id,
               'pesticide_impact'::TEXT AS record_type,
               pesticide.application_date AS occurred_on,
               pesticide.created_at,
               pesticide.updated_at,
               pg_catalog.jsonb_build_object(
                   'product_name', pesticide.product_name,
                   'active_ingredient', pesticide.active_ingredient,
                   'toxicity_class', pesticide.toxicity_class,
                   'application_rate', pesticide.application_rate,
                   'rate_unit', pesticide.rate_unit,
                   'area_treated_m2', pesticide.area_treated_m2,
                   'bloom_stage_at_application', pesticide.bloom_stage_at_application,
                   'pollinator_distance_m', pesticide.pollinator_distance_m,
                   'pollinator_safe_period_days', pesticide.pollinator_safe_period_days,
                   'mortality_observed', pesticide.pollinator_mortality_observed,
                   'mortality_pct', pesticide.mortality_pct,
                   'notes', pg_catalog.left(pesticide.notes, 2000)
               ) AS details
          FROM public.pesticide_impact_log AS pesticide
         WHERE pesticide.location_id = requested_location_id
           AND pesticide.status = 'recorded'
           AND pesticide.created_by_operator_id IS NOT NULL
           AND pesticide.created_by_operator_id <> context_record.actor_id
        UNION ALL
        SELECT inspection.id AS record_id,
               'hive_inspection'::TEXT AS record_type,
               inspection.inspection_date AS occurred_on,
               inspection.created_at,
               inspection.updated_at,
               pg_catalog.jsonb_build_object(
                   'hive_id', pg_catalog.left(hive.hive_id, 120),
                   'colony_strength', inspection.colony_strength,
                   'colony_strength_score', inspection.colony_strength_score,
                   'queen_status', inspection.queen_status,
                   'queen_seen', inspection.queen_seen,
                   'varroa_count', inspection.varroa_count,
                   'brood_pattern', pg_catalog.left(inspection.brood_pattern, 500),
                   'honey_stores', pg_catalog.left(inspection.honey_stores, 500),
                   'disease_signs', pg_catalog.left(inspection.disease_signs, 500),
                   'temperament', pg_catalog.left(inspection.temperament, 200),
                   'population_estimate', inspection.population_estimate,
                   'swarm_cells', inspection.swarm_cells,
                   'notes', pg_catalog.left(inspection.notes, 2000)
               ) AS details
          FROM public.pollinator_hive_inspection AS inspection
          JOIN public.hive_record AS hive
            ON hive.id = inspection.hive_record_id
           AND hive.location_id = inspection.location_id
         WHERE inspection.location_id = requested_location_id
           AND inspection.status = 'recorded'
           AND inspection.created_by_operator_id IS NOT NULL
           AND inspection.created_by_operator_id <> context_record.actor_id
    ), selected AS (
        SELECT eligible.*
          FROM eligible
         ORDER BY eligible.created_at DESC, eligible.record_id DESC, eligible.record_type
         LIMIT requested_limit + 1 OFFSET requested_offset
    ), page AS (
        SELECT selected.*,
               pg_catalog.row_number() OVER (
                   ORDER BY selected.created_at DESC, selected.record_id DESC, selected.record_type
               ) AS page_row
          FROM selected
    ), page_result AS (
        SELECT coalesce(
                   pg_catalog.jsonb_agg(
                       pg_catalog.jsonb_build_object(
                           'record_id', page.record_id,
                           'record_type', page.record_type,
                           'occurred_on', page.occurred_on,
                           'status', 'recorded',
                           'created_at', page.created_at,
                           'updated_at', page.updated_at,
                           'details', page.details
                       ) ORDER BY page.page_row
                   ) FILTER (WHERE page.page_row <= requested_limit),
                   '[]'::JSONB
               ) AS items,
               pg_catalog.count(*) > requested_limit AS has_more
          FROM page
    )
    SELECT pg_catalog.jsonb_build_object(
               'location_id', requested_location_id,
               'items', page_result.items,
               'limit', requested_limit,
               'offset', requested_offset,
               'has_more', page_result.has_more,
               'next_offset', CASE
                   WHEN page_result.has_more THEN requested_offset + requested_limit
                   ELSE NULL
               END,
               'total', (SELECT pg_catalog.count(*) FROM eligible)
           )
      INTO result
      FROM page_result;

    RETURN result;
END;
$$;


ALTER FUNCTION kokonut_security.list_location_pollinator_review_queue(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_pollinator_review_writer;
REVOKE ALL ON FUNCTION kokonut_security.list_location_pollinator_review_queue(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.list_location_pollinator_review_queue(UUID, INTEGER, INTEGER)
    TO kokonut_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.enforce_independent_pollinator_review()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    submitting_operator UUID;
BEGIN
    IF NEW.record_type = 'observation' THEN
        SELECT observation.created_by_operator_id
          INTO submitting_operator
          FROM public.pollinator_observation AS observation
         WHERE observation.id = NEW.record_id
           AND observation.location_id = NEW.location_id;
    ELSIF NEW.record_type = 'pesticide_impact' THEN
        SELECT pesticide.created_by_operator_id
          INTO submitting_operator
          FROM public.pesticide_impact_log AS pesticide
         WHERE pesticide.id = NEW.record_id
           AND pesticide.location_id = NEW.location_id;
    ELSIF NEW.record_type = 'hive_inspection' THEN
        SELECT inspection.created_by_operator_id
          INTO submitting_operator
          FROM public.pollinator_hive_inspection AS inspection
         WHERE inspection.id = NEW.record_id
           AND inspection.location_id = NEW.location_id;
    ELSE
        RAISE EXCEPTION 'Unsupported pollinator review record type'
            USING ERRCODE = '22023';
    END IF;
    IF NOT FOUND OR submitting_operator IS NULL THEN
        RAISE EXCEPTION 'Pollinator review requires a known submitting operator'
            USING ERRCODE = '42501';
    END IF;
    IF submitting_operator = NEW.reviewer_operator_id THEN
        RAISE EXCEPTION 'Pollinator reviewers cannot review their own submissions'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;
ALTER FUNCTION kokonut_security.enforce_independent_pollinator_review()
    OWNER TO kokonut_pollinator_review_writer;
REVOKE ALL ON FUNCTION kokonut_security.enforce_independent_pollinator_review()
    FROM PUBLIC;
DROP TRIGGER IF EXISTS trg_pollinator_review_submitter_guard
    ON public.pollinator_review_decision;
CREATE TRIGGER trg_pollinator_review_submitter_guard
    BEFORE INSERT ON public.pollinator_review_decision
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.enforce_independent_pollinator_review();

CREATE OR REPLACE FUNCTION kokonut_security.review_location_pollinator_hive_inspection(
    requested_location_id UUID,
    requested_inspection_id UUID,
    requested_request_id UUID,
    expected_updated_at TIMESTAMPTZ,
    requested_decision TEXT,
    requested_reason TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    normalized_reason TEXT := NULLIF(
        pg_catalog.btrim(requested_reason, ' ' || pg_catalog.chr(9) || pg_catalog.chr(10) || pg_catalog.chr(13)),
        ''
    );
    input_digest BYTEA;
    existing_decision RECORD;
    source_record RECORD;
    result_updated_at TIMESTAMPTZ;
    decision_uuid UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_inspection_id IS NULL
       OR requested_request_id IS NULL
       OR expected_updated_at IS NULL THEN
        RAISE EXCEPTION 'Hive inspection review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'pollinator_health', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Hive inspection review requires an exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision IS NULL
       OR requested_decision NOT IN ('reviewed', 'dismissed')
       OR normalized_reason IS NULL
       OR pg_catalog.char_length(normalized_reason) > 500
       OR requested_reason ~ '[[:cntrl:]]' THEN
        RAISE EXCEPTION 'Hive inspection review decision or reason is invalid'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT, 'hive_inspection',
                requested_inspection_id::TEXT, requested_request_id::TEXT,
                expected_updated_at AT TIME ZONE 'UTC', requested_decision, normalized_reason
            )::TEXT,
            'UTF8'
        ),
        'sha256'::TEXT
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT decision.id, decision.location_id, decision.record_type,
           decision.record_id, decision.input_digest, decision.status_after
      INTO existing_decision
      FROM public.pollinator_review_decision AS decision
     WHERE decision.reviewer_operator_id = context_record.actor_id
       AND decision.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_decision.location_id IS DISTINCT FROM requested_location_id
           OR existing_decision.record_type IS DISTINCT FROM 'hive_inspection'
           OR existing_decision.record_id IS DISTINCT FROM requested_inspection_id
           OR existing_decision.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Pollinator review request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'decision_id', existing_decision.id,
            'location_id', requested_location_id,
            'record_type', 'hive_inspection',
            'record_id', requested_inspection_id,
            'status', existing_decision.status_after,
            'replayed', TRUE
        );
    END IF;

    SELECT inspection.status, inspection.updated_at,
           inspection.created_by_operator_id
      INTO source_record
      FROM public.pollinator_hive_inspection AS inspection
     WHERE inspection.id = requested_inspection_id
       AND inspection.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Hive inspection is unavailable for review'
            USING ERRCODE = 'P0002';
    END IF;
    IF source_record.created_by_operator_id IS NULL
       OR source_record.created_by_operator_id = context_record.actor_id THEN
        RAISE EXCEPTION 'Hive inspection submitter is unknown or matches the reviewer'
            USING ERRCODE = '42501';
    END IF;
    IF source_record.status IS DISTINCT FROM 'recorded'
       OR source_record.updated_at IS DISTINCT FROM expected_updated_at THEN
        RAISE EXCEPTION 'Hive inspection changed before review decision'
            USING ERRCODE = '40001';
    END IF;

    UPDATE public.pollinator_hive_inspection
       SET status = requested_decision,
           updated_at = pg_catalog.clock_timestamp()
     WHERE id = requested_inspection_id
       AND location_id = requested_location_id
       AND status = 'recorded'
       AND updated_at = expected_updated_at
    RETURNING updated_at INTO result_updated_at;
    IF result_updated_at IS NULL THEN
        RAISE EXCEPTION 'Hive inspection changed before review decision'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.pollinator_review_decision (
        reviewer_operator_id, request_id, location_id, record_type, record_id,
        input_digest, expected_updated_at, status_before, status_after, reason
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        'hive_inspection', requested_inspection_id, input_digest,
        expected_updated_at, 'recorded', requested_decision, normalized_reason
    ) RETURNING id INTO decision_uuid;

    RETURN pg_catalog.jsonb_build_object(
        'decision_id', decision_uuid,
        'location_id', requested_location_id,
        'record_type', 'hive_inspection',
        'record_id', requested_inspection_id,
        'status', requested_decision,
        'replayed', FALSE
    );
END;
$$;
ALTER FUNCTION kokonut_security.review_location_pollinator_hive_inspection(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) OWNER TO kokonut_pollinator_review_writer;
REVOKE ALL ON FUNCTION kokonut_security.review_location_pollinator_hive_inspection(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.review_location_pollinator_hive_inspection(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) TO kokonut_runtime;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime'
    ) THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_pollinator_review_queue(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.review_location_pollinator_hive_inspection(
            UUID, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.enforce_independent_pollinator_review()
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON COLUMN public.pollinator_hive_inspection.updated_at IS
    'Last change to the review lifecycle state; inspection measurements remain a recorded observation.';
COMMENT ON FUNCTION kokonut_security.list_location_pollinator_review_queue(UUID, INTEGER, INTEGER) IS
    'Returns bounded same-location recorded observations, pesticide-impact reports, and hive inspections with known submitter attribution, excluding the caller''s own submissions.';
COMMENT ON FUNCTION kokonut_security.review_location_pollinator_hive_inspection(UUID, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT) IS
    'Independently marks a recorded hive inspection reviewed or dismissed with optimistic concurrency and immutable reasoned history; this is not colony-health certification.';

COMMIT;
