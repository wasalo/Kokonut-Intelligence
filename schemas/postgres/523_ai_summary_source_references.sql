-- Persist bounded, location-checked record references for generated summaries.
-- The source set remains review evidence, not a verification or publication.

BEGIN;

CREATE TABLE IF NOT EXISTS kokonut_security.ai_summary_source_manifest (
    summary_id UUID NOT NULL REFERENCES public.ai_summary(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    source_table TEXT NOT NULL CHECK (source_table IN (
        'harvest_event', 'sales_event', 'crop_cycle', 'sensor_reading',
        'expense_event', 'noi_snapshot', 'soil_carbon_measurement',
        'species_observation', 'remote_sensing_observation', 'weather_observation'
    )),
    source_row_count BIGINT NOT NULL CHECK (source_row_count >= 0),
    truncated BOOLEAN NOT NULL,
    sample_count SMALLINT NOT NULL CHECK (sample_count BETWEEN 0 AND 50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (summary_id, source_table),
    CHECK (source_row_count >= sample_count),
    CHECK (truncated = (source_row_count > sample_count))
);

CREATE TABLE IF NOT EXISTS kokonut_security.ai_summary_source_reference (
    summary_id UUID NOT NULL,
    source_table TEXT NOT NULL,
    source_record_id UUID NOT NULL,
    ordinal SMALLINT NOT NULL CHECK (ordinal BETWEEN 1 AND 50),
    PRIMARY KEY (summary_id, source_table, source_record_id),
    UNIQUE (summary_id, source_table, ordinal),
    FOREIGN KEY (summary_id, source_table)
        REFERENCES kokonut_security.ai_summary_source_manifest(summary_id, source_table)
        ON DELETE RESTRICT
);

CREATE OR REPLACE FUNCTION public.prevent_ai_summary_source_reference_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'AI-summary source references are append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_summary_source_manifest_immutable
    ON kokonut_security.ai_summary_source_manifest;
CREATE TRIGGER trg_ai_summary_source_manifest_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.ai_summary_source_manifest
    FOR EACH ROW EXECUTE FUNCTION public.prevent_ai_summary_source_reference_mutation();

DROP TRIGGER IF EXISTS trg_ai_summary_source_reference_immutable
    ON kokonut_security.ai_summary_source_reference;
CREATE TRIGGER trg_ai_summary_source_reference_immutable
    BEFORE UPDATE OR DELETE ON kokonut_security.ai_summary_source_reference
    FOR EACH ROW EXECUTE FUNCTION public.prevent_ai_summary_source_reference_mutation();

CREATE OR REPLACE FUNCTION kokonut_security.set_location_ai_summary_source_references(
    requested_location_id UUID,
    requested_summary_id UUID,
    requested_request_id UUID,
    requested_manifest JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    summary_record RECORD;
    source_entry RECORD;
    source_ids UUID[];
    source_row_count BIGINT;
    source_truncated BOOLEAN;
    matching_count BIGINT;
    expected_keys INTEGER;
    entry_key_count INTEGER;
    existing_count INTEGER;
    manifest_result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'AI-summary source references require signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'ai_summary', 'draft', requested_location_id
    ) THEN
        RAISE EXCEPTION 'AI-summary source references require an active draft grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_summary_id IS NULL OR requested_request_id IS NULL
       OR requested_manifest IS NULL
       OR pg_catalog.jsonb_typeof(requested_manifest) IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length(requested_manifest::TEXT) > 64000 THEN
        RAISE EXCEPTION 'AI-summary source-reference manifest is invalid'
            USING ERRCODE = '22023';
    END IF;
    SELECT pg_catalog.count(*) INTO expected_keys
      FROM pg_catalog.jsonb_object_keys(requested_manifest);
    IF expected_keys NOT BETWEEN 1 AND 10 THEN
        RAISE EXCEPTION 'AI-summary source-reference manifest is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT summary.id, summary.subject_id, summary.created_by, summary.source_tables
      INTO summary_record
      FROM public.ai_summary AS summary
      JOIN public.ai_summary_draft_request AS draft_request
        ON draft_request.summary_id = summary.id
     WHERE summary.id = requested_summary_id
       AND summary.subject_type = 'location'
       AND summary.subject_id = requested_location_id
       AND summary.created_by = context_record.actor_id
       AND draft_request.operator_id = context_record.actor_id
       AND draft_request.request_id = requested_request_id
       AND draft_request.location_id = requested_location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'AI-summary draft does not match the authenticated request'
            USING ERRCODE = '42501';
    END IF;

    SELECT pg_catalog.count(*) INTO existing_count
      FROM kokonut_security.ai_summary_source_manifest AS source_manifest
     WHERE source_manifest.summary_id = requested_summary_id;
    IF existing_count > 0 THEN
        SELECT pg_catalog.jsonb_object_agg(
                   source_manifest.source_table,
                   pg_catalog.jsonb_build_object(
                       'record_ids', COALESCE(reference_rows.record_ids, '[]'::JSONB),
                       'row_count', source_manifest.source_row_count,
                       'truncated', source_manifest.truncated
                   )
               )
          INTO manifest_result
          FROM kokonut_security.ai_summary_source_manifest AS source_manifest
          LEFT JOIN LATERAL (
              SELECT pg_catalog.jsonb_agg(source_reference.source_record_id ORDER BY source_reference.ordinal) AS record_ids
                FROM kokonut_security.ai_summary_source_reference AS source_reference
               WHERE source_reference.summary_id = source_manifest.summary_id
                 AND source_reference.source_table = source_manifest.source_table
          ) AS reference_rows ON TRUE
         WHERE source_manifest.summary_id = requested_summary_id;
        RETURN COALESCE(manifest_result, '{}'::JSONB);
    END IF;

    FOR source_entry IN
        SELECT entry.key AS source_table, entry.value AS source_payload
          FROM pg_catalog.jsonb_each(requested_manifest) AS entry
    LOOP
        IF pg_catalog.jsonb_typeof(source_entry.source_payload) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'AI-summary source-reference entry is invalid'
                USING ERRCODE = '22023';
        END IF;
        SELECT pg_catalog.count(*) INTO entry_key_count
          FROM pg_catalog.jsonb_object_keys(source_entry.source_payload);
        IF source_entry.source_table NOT IN (
            'harvest_event', 'sales_event', 'crop_cycle', 'sensor_reading',
            'expense_event', 'noi_snapshot', 'soil_carbon_measurement',
            'species_observation', 'remote_sensing_observation', 'weather_observation'
        ) OR NOT (source_entry.source_table = ANY(summary_record.source_tables))
           OR entry_key_count <> 3
           OR pg_catalog.jsonb_typeof(source_entry.source_payload -> 'record_ids') IS DISTINCT FROM 'array'
           OR pg_catalog.jsonb_typeof(source_entry.source_payload -> 'row_count') IS DISTINCT FROM 'number'
           OR (source_entry.source_payload ->> 'row_count') !~ '^[0-9]+$'
           OR pg_catalog.jsonb_typeof(source_entry.source_payload -> 'truncated') IS DISTINCT FROM 'boolean' THEN
            RAISE EXCEPTION 'AI-summary source-reference entry is invalid'
                USING ERRCODE = '22023';
        END IF;
        source_row_count := (source_entry.source_payload ->> 'row_count')::BIGINT;
        source_truncated := (source_entry.source_payload ->> 'truncated')::BOOLEAN;
        IF source_row_count < 0
           OR pg_catalog.jsonb_array_length(source_entry.source_payload -> 'record_ids') > 50 THEN
            RAISE EXCEPTION 'AI-summary source-reference bounds are invalid'
                USING ERRCODE = '22023';
        END IF;
        SELECT COALESCE(pg_catalog.array_agg(record_id::UUID ORDER BY ordinal), ARRAY[]::UUID[])
          INTO source_ids
          FROM pg_catalog.jsonb_array_elements_text(source_entry.source_payload -> 'record_ids')
               WITH ORDINALITY AS source_rows(record_id, ordinal);
        IF pg_catalog.cardinality(source_ids) <> pg_catalog.cardinality(
            ARRAY(SELECT DISTINCT source_row.source_id
                    FROM pg_catalog.unnest(source_ids) AS source_row(source_id))
        ) OR source_row_count < pg_catalog.cardinality(source_ids)
           OR source_truncated IS DISTINCT FROM (source_row_count > pg_catalog.cardinality(source_ids)) THEN
            RAISE EXCEPTION 'AI-summary source-reference counts do not match the sample'
                USING ERRCODE = '22023';
        END IF;

        EXECUTE pg_catalog.format(
            'SELECT pg_catalog.count(*) FROM public.%I WHERE location_id = $1 AND id = ANY($2)',
            source_entry.source_table
        ) INTO matching_count USING requested_location_id, source_ids;
        IF matching_count <> pg_catalog.cardinality(source_ids) THEN
            RAISE EXCEPTION 'AI-summary source references must identify rows at the requested location'
                USING ERRCODE = '22023';
        END IF;

        INSERT INTO kokonut_security.ai_summary_source_manifest (
            summary_id, location_id, source_table, source_row_count, truncated, sample_count
        ) VALUES (
            requested_summary_id, requested_location_id, source_entry.source_table,
            source_row_count, source_truncated, pg_catalog.cardinality(source_ids)
        );
        INSERT INTO kokonut_security.ai_summary_source_reference (
            summary_id, source_table, source_record_id, ordinal
        )
        SELECT requested_summary_id, source_entry.source_table, source_rows.source_id,
               source_rows.ordinal::SMALLINT
          FROM pg_catalog.unnest(source_ids) WITH ORDINALITY AS source_rows(source_id, ordinal);
    END LOOP;

    SELECT pg_catalog.jsonb_object_agg(
               source_manifest.source_table,
               pg_catalog.jsonb_build_object(
                   'record_ids', COALESCE(reference_rows.record_ids, '[]'::JSONB),
                   'row_count', source_manifest.source_row_count,
                   'truncated', source_manifest.truncated
               )
           )
      INTO manifest_result
      FROM kokonut_security.ai_summary_source_manifest AS source_manifest
      LEFT JOIN LATERAL (
          SELECT pg_catalog.jsonb_agg(source_reference.source_record_id ORDER BY source_reference.ordinal) AS record_ids
            FROM kokonut_security.ai_summary_source_reference AS source_reference
           WHERE source_reference.summary_id = source_manifest.summary_id
             AND source_reference.source_table = source_manifest.source_table
      ) AS reference_rows ON TRUE
     WHERE source_manifest.summary_id = requested_summary_id;
    RETURN COALESCE(manifest_result, '{}'::JSONB);
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_ai_summary_source_references(
    requested_location_id UUID,
    requested_summary_id UUID,
    requested_action TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    manifest_result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_summary_id IS NULL
       OR requested_action NOT IN ('draft', 'review') THEN
        RAISE EXCEPTION 'AI-summary source-reference scope is invalid'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'ai_summary', requested_action, requested_location_id
    ) THEN
        RAISE EXCEPTION 'AI-summary source references require an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.ai_summary AS summary
         WHERE summary.id = requested_summary_id
           AND summary.subject_type = 'location'
           AND summary.subject_id = requested_location_id
    ) THEN
        RAISE EXCEPTION 'AI-summary source references are unavailable'
            USING ERRCODE = '42501';
    END IF;

    SELECT pg_catalog.jsonb_object_agg(
               source_manifest.source_table,
               pg_catalog.jsonb_build_object(
                   'record_ids', COALESCE(reference_rows.record_ids, '[]'::JSONB),
                   'row_count', source_manifest.source_row_count,
                   'truncated', source_manifest.truncated
               )
           )
      INTO manifest_result
      FROM kokonut_security.ai_summary_source_manifest AS source_manifest
      LEFT JOIN LATERAL (
          SELECT pg_catalog.jsonb_agg(source_reference.source_record_id ORDER BY source_reference.ordinal) AS record_ids
            FROM kokonut_security.ai_summary_source_reference AS source_reference
           WHERE source_reference.summary_id = source_manifest.summary_id
             AND source_reference.source_table = source_manifest.source_table
      ) AS reference_rows ON TRUE
     WHERE source_manifest.summary_id = requested_summary_id
       AND source_manifest.location_id = requested_location_id;
    RETURN COALESCE(manifest_result, '{}'::JSONB);
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_ai_summary_reviews_with_sources(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 51,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    summary_id UUID,
    summary_type TEXT,
    content TEXT,
    content_truncated BOOLEAN,
    source_tables TEXT[],
    model_version TEXT,
    created_at TIMESTAMPTZ,
    review_ready BOOLEAN,
    blocked_reasons TEXT[],
    source_references JSONB
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
       OR requested_location_id IS NULL
       OR NOT public.operator_scope_grant_allows(
            context_record.actor_id, 'ai_summary', 'review', requested_location_id
       ) THEN
        RAISE EXCEPTION 'AI-summary source review requires signed exact-location review scope'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT review.summary_id, review.summary_type, review.content,
           review.content_truncated, review.source_tables, review.model_version,
           review.created_at, review.review_ready, review.blocked_reasons,
           COALESCE(
               (
                   SELECT pg_catalog.jsonb_object_agg(
                              source_manifest.source_table,
                              pg_catalog.jsonb_build_object(
                                  'record_ids', COALESCE(reference_rows.record_ids, '[]'::JSONB),
                                  'row_count', source_manifest.source_row_count,
                                  'truncated', source_manifest.truncated
                              )
                          )
                     FROM kokonut_security.ai_summary_source_manifest AS source_manifest
                     LEFT JOIN LATERAL (
                         SELECT pg_catalog.jsonb_agg(source_reference.source_record_id ORDER BY source_reference.ordinal) AS record_ids
                           FROM kokonut_security.ai_summary_source_reference AS source_reference
                          WHERE source_reference.summary_id = source_manifest.summary_id
                            AND source_reference.source_table = source_manifest.source_table
                     ) AS reference_rows ON TRUE
                    WHERE source_manifest.summary_id = review.summary_id
                      AND source_manifest.location_id = requested_location_id
               ),
               '{}'::JSONB
           ) AS source_references
      FROM kokonut_security.list_location_ai_summary_reviews(
               requested_location_id, requested_limit, requested_offset
           ) AS review;
END;
$$;

REVOKE ALL ON TABLE kokonut_security.ai_summary_source_manifest,
    kokonut_security.ai_summary_source_reference FROM PUBLIC;
REVOKE ALL ON FUNCTION public.prevent_ai_summary_source_reference_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.set_location_ai_summary_source_references(UUID, UUID, UUID, JSONB)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_ai_summary_source_references(UUID, UUID, TEXT)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_sources(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

GRANT SELECT (id, location_id) ON TABLE
    public.harvest_event, public.sales_event, public.crop_cycle, public.sensor_reading,
    public.expense_event, public.noi_snapshot, public.soil_carbon_measurement,
    public.species_observation, public.remote_sensing_observation, public.weather_observation
    TO kokonut_ai_summary_drafter;
GRANT SELECT, INSERT ON TABLE
    kokonut_security.ai_summary_source_manifest,
    kokonut_security.ai_summary_source_reference
    TO kokonut_ai_summary_drafter;
GRANT SELECT ON TABLE
    kokonut_security.ai_summary_source_manifest,
    kokonut_security.ai_summary_source_reference
    TO kokonut_ai_summary_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.get_location_ai_summary_source_references(UUID, UUID, TEXT)
    TO kokonut_ai_summary_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.list_location_ai_summary_reviews(UUID, INTEGER, INTEGER)
    TO kokonut_ai_summary_reviewer;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_ai_summary_drafter;
ALTER FUNCTION kokonut_security.set_location_ai_summary_source_references(UUID, UUID, UUID, JSONB)
    OWNER TO kokonut_ai_summary_drafter;
ALTER FUNCTION kokonut_security.get_location_ai_summary_source_references(UUID, UUID, TEXT)
    OWNER TO kokonut_ai_summary_reviewer;
ALTER FUNCTION kokonut_security.list_location_ai_summary_reviews_with_sources(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_ai_summary_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_ai_summary_drafter;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION
            kokonut_security.set_location_ai_summary_source_references(UUID, UUID, UUID, JSONB),
            kokonut_security.get_location_ai_summary_source_references(UUID, UUID, TEXT),
            kokonut_security.list_location_ai_summary_reviews_with_sources(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
        REVOKE ALL ON TABLE
            kokonut_security.ai_summary_source_manifest,
            kokonut_security.ai_summary_source_reference
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'directus') THEN
        REVOKE ALL ON TABLE
            kokonut_security.ai_summary_source_manifest,
            kokonut_security.ai_summary_source_reference
            FROM directus;
        REVOKE ALL ON FUNCTION
            kokonut_security.set_location_ai_summary_source_references(UUID, UUID, UUID, JSONB),
            kokonut_security.get_location_ai_summary_source_references(UUID, UUID, TEXT),
            kokonut_security.list_location_ai_summary_reviews_with_sources(UUID, INTEGER, INTEGER)
            FROM directus;
    END IF;
END;
$$;

COMMENT ON TABLE kokonut_security.ai_summary_source_manifest IS
'Private bounded source-record manifests for AI summaries. Counts are exact; record IDs are capped to 50 per source table.';
COMMENT ON TABLE kokonut_security.ai_summary_source_reference IS
'Private ordered samples of location-qualified source records for AI-summary human review.';
COMMENT ON FUNCTION kokonut_security.set_location_ai_summary_source_references(UUID, UUID, UUID, JSONB) IS
'Attaches immutable, bounded source references to an authenticated operator draft after checking every record belongs to the exact location.';
COMMENT ON FUNCTION kokonut_security.get_location_ai_summary_source_references(UUID, UUID, TEXT) IS
'Returns a private bounded AI-summary source manifest only with an exact location draft or review grant.';
COMMENT ON FUNCTION kokonut_security.list_location_ai_summary_reviews_with_sources(UUID, INTEGER, INTEGER) IS
'Returns the bounded exact-location AI-summary review queue with its private source-record references.';

COMMIT;
