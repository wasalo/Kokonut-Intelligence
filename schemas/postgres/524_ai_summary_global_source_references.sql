-- Add location-linked IDs for shared crop and expense-category references.
-- The caller sees only reference rows that contributed to the exact location's
-- generated summary; storage remains private and exact-grant scoped.

BEGIN;

ALTER TABLE kokonut_security.ai_summary_source_manifest
    DROP CONSTRAINT IF EXISTS ai_summary_source_manifest_source_table_check;
ALTER TABLE kokonut_security.ai_summary_source_manifest
    ADD CONSTRAINT ai_summary_source_manifest_source_table_check CHECK (source_table IN (
        'harvest_event', 'sales_event', 'crop_cycle', 'sensor_reading',
        'expense_event', 'noi_snapshot', 'soil_carbon_measurement',
        'species_observation', 'remote_sensing_observation', 'weather_observation',
        'crop', 'expense_category'
    ));

-- The SECURITY DEFINER setter validates references through their location-owned
-- relationship. Grant only the columns required for those checks.
GRANT SELECT (id) ON TABLE public.crop TO kokonut_ai_summary_drafter;
GRANT SELECT (crop_id) ON TABLE public.crop_cycle TO kokonut_ai_summary_drafter;
GRANT SELECT (crop_cycle_id, status) ON TABLE public.sales_event TO kokonut_ai_summary_drafter;
GRANT SELECT (category, status, amount) ON TABLE public.expense_event TO kokonut_ai_summary_drafter;
GRANT SELECT (id, name) ON TABLE public.expense_category TO kokonut_ai_summary_drafter;

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
            'species_observation', 'remote_sensing_observation', 'weather_observation', 'crop', 'expense_category'
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

        IF source_entry.source_table = 'crop' THEN
            SELECT pg_catalog.count(DISTINCT crop.id)
              INTO matching_count
              FROM public.crop AS crop
              JOIN public.crop_cycle AS cycle ON cycle.crop_id = crop.id
              JOIN public.sales_event AS sale ON sale.crop_cycle_id = cycle.id
             WHERE cycle.location_id = requested_location_id
               AND sale.location_id = requested_location_id
               AND cycle.location_id = sale.location_id
               AND sale.status IN ('verified', 'published')
               AND crop.id = ANY(source_ids);
        ELSIF source_entry.source_table = 'expense_category' THEN
            SELECT pg_catalog.count(DISTINCT category.id)
              INTO matching_count
              FROM public.expense_category AS category
             WHERE category.id = ANY(source_ids)
               AND category.id IN (
                    SELECT selected.id
                      FROM (
                          SELECT top_category.id, top_category.name,
                                 pg_catalog.sum(expense.amount) AS category_total
                            FROM public.expense_category AS top_category
                            JOIN public.expense_event AS expense
                              ON expense.category = top_category.name
                           WHERE expense.location_id = requested_location_id
                             AND expense.status IN ('verified', 'published')
                           GROUP BY top_category.id, top_category.name
                           ORDER BY category_total DESC, top_category.name
                           LIMIT 5
                      ) AS selected
               );
        ELSE
            EXECUTE pg_catalog.format(
                'SELECT pg_catalog.count(*) FROM public.%I WHERE location_id = $1 AND id = ANY($2)',
                source_entry.source_table
            ) INTO matching_count USING requested_location_id, source_ids;
        END IF;
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

COMMENT ON FUNCTION kokonut_security.set_location_ai_summary_source_references(UUID, UUID, UUID, JSONB) IS
'Attaches immutable, bounded source references to an authenticated operator draft after checking location-owned rows and location-linked shared catalog rows.';

COMMIT;
