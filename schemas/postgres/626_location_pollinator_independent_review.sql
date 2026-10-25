-- Add independent, location-scoped review for captured pollinator observations
-- and completed pesticide-impact reports. Review is not pesticide approval or
-- a claim that an ecological outcome has been verified.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_pollinator_review_writer'
    ) THEN
        CREATE ROLE kokonut_pollinator_review_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_pollinator_review_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

CREATE TABLE IF NOT EXISTS public.pollinator_review_decision (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    reviewer_operator_id UUID NOT NULL
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    record_type TEXT NOT NULL CHECK (record_type IN ('observation', 'pesticide_impact')),
    record_id UUID NOT NULL,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    expected_updated_at TIMESTAMPTZ NOT NULL,
    status_before TEXT NOT NULL CHECK (status_before = 'recorded'),
    status_after TEXT NOT NULL CHECK (status_after IN ('reviewed', 'dismissed')),
    reason TEXT NOT NULL CHECK (
        pg_catalog.char_length(reason) BETWEEN 1 AND 500
        AND reason !~ '[[:cntrl:]]'
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT uq_pollinator_review_reviewer_request
        UNIQUE (reviewer_operator_id, request_id)
);

CREATE INDEX IF NOT EXISTS idx_pollinator_review_decision_location_time
    ON public.pollinator_review_decision (location_id, created_at DESC, id DESC);

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
                'REVOKE UPDATE (status, updated_at) ON TABLE public.pollinator_observation FROM %s',
                role_sql
            );
            EXECUTE pg_catalog.format(
                'REVOKE UPDATE (status, updated_at) ON TABLE public.pesticide_impact_log FROM %s',
                role_sql
            );
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.pollinator_review_decision FROM %s', role_sql
            );
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_pollinator_review_writer;
GRANT SELECT (
    id, location_id, status, created_by_operator_id, observation_date,
    pollinator_type, count, observation_method, duration_minutes, species_name,
    notes, created_at, updated_at
) ON TABLE public.pollinator_observation
    TO kokonut_pollinator_review_writer;
GRANT UPDATE (status, updated_at) ON TABLE public.pollinator_observation
    TO kokonut_pollinator_review_writer;
GRANT SELECT (
    id, location_id, status, created_by_operator_id, application_date,
    product_name, active_ingredient, toxicity_class, application_rate, rate_unit,
    area_treated_m2, bloom_stage_at_application, pollinator_distance_m,
    pollinator_safe_period_days, pollinator_mortality_observed, mortality_pct,
    notes, created_at, updated_at
) ON TABLE public.pesticide_impact_log
    TO kokonut_pollinator_review_writer;
GRANT UPDATE (status, updated_at) ON TABLE public.pesticide_impact_log
    TO kokonut_pollinator_review_writer;
GRANT SELECT (
    id, reviewer_operator_id, request_id, location_id, record_type, record_id,
    input_digest, expected_updated_at, status_before, status_after, reason, created_at
) ON TABLE public.pollinator_review_decision
    TO kokonut_pollinator_review_writer;
GRANT INSERT (
    reviewer_operator_id, request_id, location_id, record_type, record_id,
    input_digest, expected_updated_at, status_before, status_after, reason
) ON TABLE public.pollinator_review_decision
    TO kokonut_pollinator_review_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_pollinator_review_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_pollinator_review_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_pollinator_review_writer;

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
           AND observation.created_by_operator_id IS DISTINCT FROM context_record.actor_id
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
           AND pesticide.created_by_operator_id IS DISTINCT FROM context_record.actor_id
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

CREATE OR REPLACE FUNCTION kokonut_security.review_location_pollinator_record(
    requested_location_id UUID,
    requested_record_type TEXT,
    requested_record_id UUID,
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
       OR requested_record_id IS NULL
       OR requested_request_id IS NULL
       OR expected_updated_at IS NULL THEN
        RAISE EXCEPTION 'Pollinator review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'pollinator_health', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Pollinator review requires an exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_record_type IS NULL
       OR requested_record_type NOT IN ('observation', 'pesticide_impact')
       OR requested_decision IS NULL
       OR requested_decision NOT IN ('reviewed', 'dismissed')
       OR normalized_reason IS NULL
       OR pg_catalog.char_length(normalized_reason) > 500
       OR requested_reason ~ '[[:cntrl:]]' THEN
        RAISE EXCEPTION 'Pollinator review decision or reason is invalid'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT, requested_record_type,
                requested_record_id::TEXT, requested_request_id::TEXT,
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
           OR existing_decision.record_type IS DISTINCT FROM requested_record_type
           OR existing_decision.record_id IS DISTINCT FROM requested_record_id
           OR existing_decision.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Pollinator review request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'decision_id', existing_decision.id,
            'location_id', requested_location_id,
            'record_type', requested_record_type,
            'record_id', requested_record_id,
            'status', existing_decision.status_after,
            'replayed', TRUE
        );
    END IF;

    IF requested_record_type = 'observation' THEN
        SELECT observation.status, observation.updated_at,
               observation.created_by_operator_id
          INTO source_record
          FROM public.pollinator_observation AS observation
         WHERE observation.id = requested_record_id
           AND observation.location_id = requested_location_id
         FOR UPDATE;
    ELSE
        SELECT pesticide.status, pesticide.updated_at,
               pesticide.created_by_operator_id
          INTO source_record
          FROM public.pesticide_impact_log AS pesticide
         WHERE pesticide.id = requested_record_id
           AND pesticide.location_id = requested_location_id
         FOR UPDATE;
    END IF;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Recorded pollinator item is unavailable for review'
            USING ERRCODE = 'P0002';
    END IF;
    IF source_record.created_by_operator_id = context_record.actor_id THEN
        RAISE EXCEPTION 'Pollinator reviewers cannot review their own submissions'
            USING ERRCODE = '42501';
    END IF;
    IF source_record.status IS DISTINCT FROM 'recorded'
       OR source_record.updated_at IS DISTINCT FROM expected_updated_at THEN
        RAISE EXCEPTION 'Pollinator item changed before review decision'
            USING ERRCODE = '40001';
    END IF;

    IF requested_record_type = 'observation' THEN
        UPDATE public.pollinator_observation
           SET status = requested_decision,
               updated_at = pg_catalog.clock_timestamp()
         WHERE id = requested_record_id
           AND location_id = requested_location_id
           AND status = 'recorded'
           AND updated_at = expected_updated_at
        RETURNING updated_at INTO result_updated_at;
    ELSE
        UPDATE public.pesticide_impact_log
           SET status = requested_decision,
               updated_at = pg_catalog.clock_timestamp()
         WHERE id = requested_record_id
           AND location_id = requested_location_id
           AND status = 'recorded'
           AND updated_at = expected_updated_at
        RETURNING updated_at INTO result_updated_at;
    END IF;
    IF result_updated_at IS NULL THEN
        RAISE EXCEPTION 'Pollinator item changed before review decision'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.pollinator_review_decision (
        reviewer_operator_id, request_id, location_id, record_type, record_id,
        input_digest, expected_updated_at, status_before, status_after, reason
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_record_type, requested_record_id, input_digest,
        expected_updated_at, 'recorded', requested_decision, normalized_reason
    ) RETURNING id INTO decision_uuid;

    RETURN pg_catalog.jsonb_build_object(
        'decision_id', decision_uuid,
        'location_id', requested_location_id,
        'record_type', requested_record_type,
        'record_id', requested_record_id,
        'status', requested_decision,
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.review_location_pollinator_record(
    UUID, TEXT, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) OWNER TO kokonut_pollinator_review_writer;
REVOKE ALL ON FUNCTION kokonut_security.review_location_pollinator_record(
    UUID, TEXT, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.review_location_pollinator_record(
    UUID, TEXT, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
) TO kokonut_runtime;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime'
    ) THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_pollinator_review_queue(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.review_location_pollinator_record(
            UUID, TEXT, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

REVOKE ALL ON TABLE public.pollinator_review_decision FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE public.pollinator_review_decision
    FROM kokonut_pollinator_review_writer;

COMMENT ON TABLE public.pollinator_review_decision IS
    'Immutable exact-location human review decisions for captured pollinator observations and completed pesticide-impact reports; pesticide review never authorizes use.';
COMMENT ON FUNCTION kokonut_security.list_location_pollinator_review_queue(UUID, INTEGER, INTEGER) IS
    'Returns a bounded exact-location queue of recorded pollinator observations and completed pesticide reports; excludes the caller''s own submissions.';
COMMENT ON FUNCTION kokonut_security.review_location_pollinator_record(UUID, TEXT, UUID, UUID, TIMESTAMPTZ, TEXT, TEXT) IS
    'Independently marks a recorded observation or pesticide-impact report reviewed or dismissed with optimistic concurrency and an immutable reason; review is not ecological or pesticide safety approval.';

COMMIT;
