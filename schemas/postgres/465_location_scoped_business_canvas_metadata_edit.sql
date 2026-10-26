-- Location-scoped, draft-only business canvas metadata edits with shared version history.
-- This extends migration 464 without changing its checksum or its block edit contract.

BEGIN;

ALTER TABLE public.business_model_canvas_kernel_edit_request
    DROP CONSTRAINT IF EXISTS business_model_canvas_kernel_edit_request_block_name_check;
ALTER TABLE public.business_model_canvas_kernel_edit_request
    ADD CONSTRAINT business_model_canvas_kernel_edit_request_block_name_check
    CHECK (block_name IN (
        'key_partners', 'key_activities', 'key_resources', 'value_propositions',
        'customer_relationships', 'channels', 'customer_segments', 'revenue_streams',
        'cost_structure', 'metadata'
    ));

GRANT UPDATE (canvas_name, description, fiscal_year, tags)
    ON TABLE public.business_model_canvas TO kokonut_business_canvas_editor;

CREATE OR REPLACE FUNCTION kokonut_security.update_location_business_model_canvas_metadata(
    requested_location_id UUID,
    requested_canvas_id UUID,
    requested_request_id UUID,
    requested_expected_version INTEGER,
    requested_expected_updated_at TIMESTAMPTZ,
    requested_fields JSONB,
    requested_change_reason TEXT
)
RETURNS TABLE (
    canvas_id UUID,
    status TEXT,
    version INTEGER,
    updated_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    canvas_row RECORD;
    prior_request public.business_model_canvas_kernel_edit_request%ROWTYPE;
    normalized_fields JSONB;
    normalized_tags TEXT[];
    prior_snapshot JSONB;
    digest_value TEXT;
    normalized_reason TEXT;
    next_version INTEGER;
    result_time TIMESTAMPTZ;
    affected_rows INTEGER;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Business canvas metadata edit requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'business_planning', 'update', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Business canvas metadata edit requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;

    normalized_reason := NULLIF(pg_catalog.btrim(requested_change_reason), '');
    IF requested_request_id IS NULL
       OR requested_canvas_id IS NULL
       OR requested_expected_version IS NULL
       OR requested_expected_version < 1
       OR requested_expected_updated_at IS NULL
       OR requested_fields IS NULL
       OR pg_catalog.jsonb_typeof(requested_fields) IS DISTINCT FROM 'object'
       OR requested_fields = '{}'::JSONB
       OR pg_catalog.pg_column_size(requested_fields) > 32768
       OR (SELECT count(*) FROM pg_catalog.jsonb_object_keys(requested_fields)) > 4
       OR EXISTS (
            SELECT 1
              FROM pg_catalog.jsonb_object_keys(requested_fields) AS field(key_name)
             WHERE field.key_name NOT IN ('canvas_name', 'description', 'fiscal_year', 'tags')
       )
       OR normalized_reason IS NULL
       OR pg_catalog.char_length(normalized_reason) > 500 THEN
        RAISE EXCEPTION 'Business canvas metadata edit fields are invalid'
            USING ERRCODE = '22023';
    END IF;

    IF requested_fields ? 'canvas_name'
       AND (pg_catalog.jsonb_typeof(requested_fields -> 'canvas_name') IS DISTINCT FROM 'string'
            OR pg_catalog.char_length(pg_catalog.btrim(requested_fields ->> 'canvas_name')) NOT BETWEEN 1 AND 255) THEN
        RAISE EXCEPTION 'Canvas name must contain 1 to 255 characters'
            USING ERRCODE = '22023';
    END IF;
    IF requested_fields ? 'description'
       AND requested_fields -> 'description' <> 'null'::JSONB
       AND (pg_catalog.jsonb_typeof(requested_fields -> 'description') IS DISTINCT FROM 'string'
            OR pg_catalog.char_length(requested_fields ->> 'description') > 4000) THEN
        RAISE EXCEPTION 'Canvas description must be null or at most 4000 characters'
            USING ERRCODE = '22023';
    END IF;
    IF requested_fields ? 'fiscal_year'
       AND requested_fields -> 'fiscal_year' <> 'null'::JSONB
       AND (pg_catalog.jsonb_typeof(requested_fields -> 'fiscal_year') IS DISTINCT FROM 'number'
            OR (requested_fields ->> 'fiscal_year') !~ '^[0-9]{4}$'
            OR (requested_fields ->> 'fiscal_year')::NUMERIC NOT BETWEEN 1900 AND 2200) THEN
        RAISE EXCEPTION 'Fiscal year must be null or an integer from 1900 through 2200'
            USING ERRCODE = '22023';
    END IF;
    IF requested_fields ? 'tags' THEN
        IF pg_catalog.jsonb_typeof(requested_fields -> 'tags') IS DISTINCT FROM 'array'
           OR pg_catalog.jsonb_array_length(requested_fields -> 'tags') > 50
           OR EXISTS (
                SELECT 1
                  FROM pg_catalog.jsonb_array_elements(requested_fields -> 'tags') AS tag(value)
                 WHERE pg_catalog.jsonb_typeof(tag.value) IS DISTINCT FROM 'string'
                    OR pg_catalog.char_length(pg_catalog.btrim(tag.value #>> '{}')) NOT BETWEEN 1 AND 64
           ) THEN
            RAISE EXCEPTION 'Canvas tags must be up to 50 non-empty strings of at most 64 characters'
                USING ERRCODE = '22023';
        END IF;
        SELECT COALESCE(
                   pg_catalog.array_agg(pg_catalog.btrim(tag.value) ORDER BY tag.ordinality),
                   ARRAY[]::TEXT[]
               )
          INTO normalized_tags
          FROM pg_catalog.jsonb_array_elements_text(requested_fields -> 'tags')
               WITH ORDINALITY AS tag(value, ordinality);
        IF (SELECT count(*) <> count(DISTINCT pg_catalog.lower(tag_value))
              FROM pg_catalog.unnest(normalized_tags) AS tag(tag_value)) THEN
            RAISE EXCEPTION 'Canvas tags must not contain duplicates'
                USING ERRCODE = '22023';
        END IF;
    END IF;

    normalized_fields := requested_fields;
    IF requested_fields ? 'canvas_name' THEN
        normalized_fields := pg_catalog.jsonb_set(
            normalized_fields, '{canvas_name}',
            pg_catalog.to_jsonb(pg_catalog.btrim(requested_fields ->> 'canvas_name')), TRUE
        );
    END IF;
    IF requested_fields ? 'description'
       AND requested_fields -> 'description' <> 'null'::JSONB THEN
        normalized_fields := pg_catalog.jsonb_set(
            normalized_fields, '{description}',
            pg_catalog.to_jsonb(pg_catalog.btrim(requested_fields ->> 'description')), TRUE
        );
    END IF;
    IF requested_fields ? 'tags' THEN
        normalized_fields := pg_catalog.jsonb_set(
            normalized_fields, '{tags}', pg_catalog.to_jsonb(normalized_tags), TRUE
        );
    END IF;

    digest_value := pg_catalog.encode(public.digest(
        pg_catalog.convert_to(pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'canvas_id', requested_canvas_id,
            'expected_version', requested_expected_version,
            'expected_updated_at', requested_expected_updated_at,
            'fields', normalized_fields,
            'change_reason', normalized_reason
        )::TEXT, 'UTF8'), 'sha256'), 'hex');
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0)
    );

    SELECT * INTO prior_request
      FROM public.business_model_canvas_kernel_edit_request AS edit_row
     WHERE edit_row.operator_id = context_record.actor_id
       AND edit_row.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_request.block_name IS DISTINCT FROM 'metadata'
           OR prior_request.location_id IS DISTINCT FROM requested_location_id
           OR prior_request.canvas_id IS DISTINCT FROM requested_canvas_id
           OR prior_request.request_digest IS DISTINCT FROM digest_value THEN
            RAISE EXCEPTION 'Business canvas metadata request id was reused with different content'
                USING ERRCODE = '23505';
        END IF;
        canvas_id := prior_request.canvas_id;
        status := 'draft';
        version := prior_request.resulting_version;
        updated_at := prior_request.result_updated_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT canvas.id, canvas.location_id, canvas.entity_type, canvas.entity_id,
           canvas.key_partners, canvas.key_activities, canvas.key_resources,
           canvas.value_propositions, canvas.customer_relationships, canvas.channels,
           canvas.customer_segments, canvas.revenue_streams, canvas.cost_structure,
           canvas.canvas_name, canvas.description, canvas.fiscal_year, canvas.tags,
           canvas.status, canvas.version, canvas.updated_at
      INTO canvas_row
      FROM public.business_model_canvas AS canvas
     WHERE canvas.id = requested_canvas_id
       AND canvas.location_id = requested_location_id
       AND canvas.entity_type = 'location'
       AND canvas.entity_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location business canvas was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF canvas_row.status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Only draft business canvases can be edited through the Kernel'
            USING ERRCODE = '55000';
    END IF;
    IF canvas_row.version IS DISTINCT FROM requested_expected_version
       OR canvas_row.updated_at IS DISTINCT FROM requested_expected_updated_at THEN
        RAISE EXCEPTION 'Business canvas changed since it was read; reload before editing'
            USING ERRCODE = '40001';
    END IF;

    prior_snapshot := pg_catalog.jsonb_build_object(
        'canvas_name', canvas_row.canvas_name,
        'description', canvas_row.description,
        'fiscal_year', canvas_row.fiscal_year,
        'tags', canvas_row.tags,
        'blocks', pg_catalog.jsonb_build_object(
            'key_partners', canvas_row.key_partners,
            'key_activities', canvas_row.key_activities,
            'key_resources', canvas_row.key_resources,
            'value_propositions', canvas_row.value_propositions,
            'customer_relationships', canvas_row.customer_relationships,
            'channels', canvas_row.channels,
            'customer_segments', canvas_row.customer_segments,
            'revenue_streams', canvas_row.revenue_streams,
            'cost_structure', canvas_row.cost_structure
        )
    );
    next_version := canvas_row.version + 1;
    result_time := pg_catalog.clock_timestamp();
    INSERT INTO public.business_model_canvas_kernel_edit_request (
        operator_id, request_id, location_id, canvas_id, prior_version,
        resulting_version, expected_updated_at, result_updated_at, block_name,
        snapshot, change_reason, request_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_canvas_id, canvas_row.version, next_version,
        requested_expected_updated_at, result_time, 'metadata',
        prior_snapshot, normalized_reason, digest_value
    );

    UPDATE public.business_model_canvas AS canvas
       SET canvas_name = CASE WHEN normalized_fields ? 'canvas_name'
                              THEN normalized_fields ->> 'canvas_name'
                              ELSE canvas.canvas_name END,
           description = CASE WHEN normalized_fields ? 'description'
                              THEN normalized_fields ->> 'description'
                              ELSE canvas.description END,
           fiscal_year = CASE WHEN normalized_fields ? 'fiscal_year'
                              THEN (normalized_fields ->> 'fiscal_year')::INTEGER
                              ELSE canvas.fiscal_year END,
           tags = CASE WHEN normalized_fields ? 'tags'
                       THEN normalized_tags ELSE canvas.tags END,
           version = next_version,
           updated_at = result_time,
           updated_by = context_record.actor_id
     WHERE canvas.id = requested_canvas_id
       AND canvas.location_id = requested_location_id
       AND canvas.entity_type = 'location'
       AND canvas.entity_id = requested_location_id;
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    IF affected_rows <> 1 THEN
        RAISE EXCEPTION 'Business canvas changed during metadata edit';
    END IF;

    canvas_id := requested_canvas_id;
    status := canvas_row.status::TEXT;
    version := next_version;
    updated_at := result_time;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_business_canvas_editor;
ALTER FUNCTION kokonut_security.update_location_business_model_canvas_metadata(
    UUID, UUID, UUID, INTEGER, TIMESTAMPTZ, JSONB, TEXT
) OWNER TO kokonut_business_canvas_editor;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_business_canvas_editor;
REVOKE ALL ON FUNCTION kokonut_security.update_location_business_model_canvas_metadata(
    UUID, UUID, UUID, INTEGER, TIMESTAMPTZ, JSONB, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.update_location_business_model_canvas_metadata(
            UUID, UUID, UUID, INTEGER, TIMESTAMPTZ, JSONB, TEXT
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.update_location_business_model_canvas_metadata(
            UUID, UUID, UUID, INTEGER, TIMESTAMPTZ, JSONB, TEXT
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.update_location_business_model_canvas_metadata(
    UUID, UUID, UUID, INTEGER, TIMESTAMPTZ, JSONB, TEXT
) IS 'Atomically updates allowlisted metadata on one exact-location draft business canvas under signed business_planning:update context, optimistic concurrency, idempotency, and the shared append-only prior-state history.';

COMMIT;
