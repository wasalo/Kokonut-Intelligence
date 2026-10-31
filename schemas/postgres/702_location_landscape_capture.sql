-- Add the exact-location Gateway capture path for landscape records.
-- These writes create source-domain inventory in its initial state only.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_landscape_capture_writer'
    ) THEN
        CREATE ROLE kokonut_landscape_capture_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_landscape_capture_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_landscape_capture_writer'
            OR member_role.rolname = 'kokonut_landscape_capture_writer'
    ) THEN
        RAISE EXCEPTION 'Landscape capture writer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.landscape_capture_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    record_type TEXT NOT NULL CHECK (record_type IN (
        'habitat_zone', 'wildlife_corridor', 'hedgerow_record',
        'buffer_zone_monitoring', 'landscape_biodiversity_score'
    )),
    record_id UUID NOT NULL,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    reason TEXT NOT NULL CHECK (pg_catalog.char_length(reason) BETWEEN 1 AND 2000),
    status TEXT NOT NULL CHECK (status IN ('active', 'recorded')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

REVOKE ALL ON TABLE public.landscape_capture_receipt FROM PUBLIC;
DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.landscape_capture_receipt FROM %I', role_name
            );
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_landscape_capture_writer;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_landscape_capture_writer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_landscape_capture_writer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_landscape_capture_writer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_landscape_capture_writer;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_landscape_capture_writer;

GRANT SELECT (id, organization_id, boundary) ON TABLE public.location
    TO kokonut_landscape_capture_writer;
-- operator_scope_grant_allows is SECURITY INVOKER. The bounded capture owner
-- needs only the authorization columns it reads while evaluating a grant.
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_landscape_capture_writer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_landscape_capture_writer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_landscape_capture_writer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_landscape_capture_writer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_landscape_capture_writer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_landscape_capture_writer;
-- PostgreSQL requires UPDATE on a key column to take FOR KEY SHARE locks.
GRANT UPDATE (id) ON TABLE public.location
    TO kokonut_landscape_capture_writer;
GRANT SELECT (id, location_id) ON TABLE public.habitat_zone
    TO kokonut_landscape_capture_writer;
GRANT UPDATE (id) ON TABLE public.habitat_zone
    TO kokonut_landscape_capture_writer;

GRANT INSERT (
    id, location_id, zone_name, habitat_type, area_ha, perimeter_m, description,
    biodiversity_value, gps_boundary, status, metadata
) ON TABLE public.habitat_zone TO kokonut_landscape_capture_writer;
GRANT INSERT (
    id, location_id, corridor_name, source_habitat_id, target_habitat_id,
    width_m, length_m, vegetation_type, condition, notes, status, metadata
) ON TABLE public.wildlife_corridor TO kokonut_landscape_capture_writer;
GRANT INSERT (
    id, location_id, hedgerow_name, species_mix, length_m, height_m, age_years,
    planting_date, condition, purpose, notes, status, metadata
) ON TABLE public.hedgerow_record TO kokonut_landscape_capture_writer;
GRANT INSERT (
    id, location_id, habitat_zone_id, check_date, buffer_width_m,
    minimum_required_m, compliant, vegetation_coverage_pct, erosion_observed,
    notes, status, metadata
) ON TABLE public.buffer_zone_monitoring TO kokonut_landscape_capture_writer;
GRANT INSERT (
    id, location_id, assessment_date, species_richness, shannon_index,
    habitat_diversity_index, connectivity_score, overall_score, assessor,
    notes, status, metadata
) ON TABLE public.landscape_biodiversity_score TO kokonut_landscape_capture_writer;
GRANT SELECT (
    operator_id, request_id, location_id, record_type, record_id,
    input_digest, reason, status, created_at
) ON TABLE public.landscape_capture_receipt TO kokonut_landscape_capture_writer;
GRANT INSERT (
    operator_id, request_id, location_id, record_type, record_id,
    input_digest, reason, status, created_at
) ON TABLE public.landscape_capture_receipt TO kokonut_landscape_capture_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_landscape_capture_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_landscape_capture_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_landscape_capture_writer;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_landscape_record(
    requested_location_id UUID,
    requested_record_type TEXT,
    requested_request_id UUID,
    requested_content JSONB,
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
    location_boundary public.geometry;
    capture_geometry public.geometry;
    input_digest BYTEA;
    existing_receipt RECORD;
    record_uuid UUID := pg_catalog.gen_random_uuid();
    effective_status TEXT;
    captured_at TIMESTAMPTZ;
    normalized_metadata JSONB;
    normalized_name TEXT;
    habitat_id UUID;
    source_habitat_id UUID;
    target_habitat_id UUID;
    effective_date DATE;
    species JSONB;
    purpose_values JSONB;
    buffer_width NUMERIC;
    minimum_width NUMERIC;
    is_compliant BOOLEAN;
    allowed_keys TEXT[];
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Landscape capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'landscape_conservation', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Landscape capture requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF requested_record_type IS NULL OR requested_record_type NOT IN (
           'habitat_zone', 'wildlife_corridor', 'hedgerow_record',
           'buffer_zone_monitoring', 'landscape_biodiversity_score'
       )
       OR requested_content IS NULL
       OR pg_catalog.jsonb_typeof(requested_content) IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length(requested_content::TEXT) > 24576
       OR requested_reason IS NULL
       OR pg_catalog.char_length(pg_catalog.btrim(requested_reason)) NOT BETWEEN 1 AND 2000
       OR pg_catalog.octet_length(requested_reason) > 8000
       OR requested_content->'metadata' IS NULL
       OR pg_catalog.jsonb_typeof(requested_content->'metadata') IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length((requested_content->'metadata')::TEXT) > 8192 THEN
        RAISE EXCEPTION 'Landscape capture input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    SELECT location.boundary INTO location_boundary
      FROM public.location AS location
     WHERE location.id = requested_location_id
     FOR KEY SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Landscape capture location does not exist'
            USING ERRCODE = 'P0002';
    END IF;

    CASE requested_record_type
    WHEN 'habitat_zone' THEN
        allowed_keys := ARRAY[
            'zone_name', 'habitat_type', 'area_ha', 'biodiversity_value',
            'perimeter_m', 'description', 'gps_boundary_wkt', 'metadata'
        ];
        effective_status := 'active';
    WHEN 'wildlife_corridor' THEN
        allowed_keys := ARRAY[
            'corridor_name', 'source_habitat_id', 'target_habitat_id',
            'width_m', 'length_m', 'vegetation_type', 'notes', 'metadata'
        ];
        effective_status := 'active';
    WHEN 'hedgerow_record' THEN
        allowed_keys := ARRAY[
            'hedgerow_name', 'species_mix', 'length_m', 'height_m', 'age_years',
            'planting_date', 'purpose', 'notes', 'metadata'
        ];
        effective_status := 'active';
    WHEN 'buffer_zone_monitoring' THEN
        allowed_keys := ARRAY[
            'habitat_zone_id', 'check_date', 'buffer_width_m',
            'minimum_required_m', 'vegetation_coverage_pct', 'erosion_observed',
            'notes', 'metadata'
        ];
        effective_status := 'recorded';
    WHEN 'landscape_biodiversity_score' THEN
        allowed_keys := ARRAY[
            'assessment_date', 'species_richness', 'shannon_index',
            'habitat_diversity_index', 'connectivity_score', 'overall_score',
            'assessor', 'notes', 'metadata'
        ];
        effective_status := 'recorded';
    END CASE;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.jsonb_object_keys(requested_content) AS item(key)
         WHERE NOT (item.key = ANY (allowed_keys))
    ) THEN
        RAISE EXCEPTION 'Landscape capture contains unsupported fields'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT, requested_record_type,
                requested_content, pg_catalog.btrim(requested_reason)
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
    SELECT receipt.location_id, receipt.record_type, receipt.record_id,
           receipt.input_digest, receipt.status, receipt.created_at
      INTO existing_receipt
      FROM public.landscape_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest
           OR existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.record_type IS DISTINCT FROM requested_record_type THEN
            RAISE EXCEPTION 'Landscape capture request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'record_id', existing_receipt.record_id,
            'record_type', requested_record_type,
            'request_id', requested_request_id,
            'status', existing_receipt.status,
            'created_at', existing_receipt.created_at,
            'replayed', TRUE
        );
    END IF;

    normalized_metadata := requested_content->'metadata';
    CASE requested_record_type
    WHEN 'habitat_zone' THEN
        normalized_name := NULLIF(pg_catalog.btrim(requested_content->>'zone_name'), '');
        IF normalized_name IS NULL OR pg_catalog.char_length(normalized_name) > 200
           OR requested_content->>'habitat_type' IS NULL
           OR requested_content->>'habitat_type' NOT IN (
               'wetland', 'riparian', 'forest_patch', 'grassland', 'hedgerow',
               'orchard', 'agroforestry', 'other'
           )
           OR (requested_content->>'area_ha') IS NULL
           OR (requested_content->>'area_ha')::NUMERIC NOT BETWEEN 0 AND 999999.99
           OR coalesce(requested_content->>'biodiversity_value', 'medium') NOT IN (
               'low', 'medium', 'high', 'critical'
           )
           OR requested_content->>'perimeter_m' IS NOT NULL
              AND (requested_content->>'perimeter_m')::NUMERIC NOT BETWEEN 0 AND 99999999.99
           OR requested_content->>'description' IS NOT NULL
              AND pg_catalog.char_length(requested_content->>'description') > 4000
           OR requested_content->>'gps_boundary_wkt' IS NOT NULL
              AND pg_catalog.char_length(requested_content->>'gps_boundary_wkt') > 16000 THEN
            RAISE EXCEPTION 'Habitat zone capture is invalid or outside its bounds'
                USING ERRCODE = '22023';
        END IF;
        IF requested_content->>'gps_boundary_wkt' IS NOT NULL THEN
            capture_geometry := public.ST_GeomFromText(requested_content->>'gps_boundary_wkt', 4326);
            IF public.ST_IsEmpty(capture_geometry)
               OR NOT public.ST_IsValid(capture_geometry)
               OR public.ST_GeometryType(capture_geometry) NOT IN ('ST_Polygon', 'ST_MultiPolygon')
               OR location_boundary IS NOT NULL
                  AND NOT public.ST_Covers(location_boundary, capture_geometry) THEN
                RAISE EXCEPTION 'Habitat geometry must be a valid polygon within the location boundary'
                    USING ERRCODE = '22023';
            END IF;
        END IF;
        INSERT INTO public.habitat_zone (
            id, location_id, zone_name, habitat_type, area_ha, perimeter_m,
            description, biodiversity_value, gps_boundary, status, metadata
        ) VALUES (
            record_uuid, requested_location_id, normalized_name,
            requested_content->>'habitat_type', (requested_content->>'area_ha')::NUMERIC,
            NULLIF(requested_content->>'perimeter_m', '')::NUMERIC,
            requested_content->>'description', coalesce(requested_content->>'biodiversity_value', 'medium'),
            capture_geometry, 'active', normalized_metadata
        );
    WHEN 'wildlife_corridor' THEN
        normalized_name := NULLIF(pg_catalog.btrim(requested_content->>'corridor_name'), '');
        source_habitat_id := NULLIF(requested_content->>'source_habitat_id', '')::UUID;
        target_habitat_id := NULLIF(requested_content->>'target_habitat_id', '')::UUID;
        IF normalized_name IS NULL OR pg_catalog.char_length(normalized_name) > 200
           OR requested_content->>'width_m' IS NOT NULL
              AND (requested_content->>'width_m')::NUMERIC NOT BETWEEN 0 AND 999999.99
           OR requested_content->>'length_m' IS NOT NULL
              AND (requested_content->>'length_m')::NUMERIC NOT BETWEEN 0 AND 99999999.99
           OR requested_content->>'vegetation_type' IS NOT NULL
              AND pg_catalog.char_length(requested_content->>'vegetation_type') > 100
           OR requested_content->>'notes' IS NOT NULL
              AND pg_catalog.char_length(requested_content->>'notes') > 4000 THEN
            RAISE EXCEPTION 'Wildlife corridor capture is invalid or outside its bounds'
                USING ERRCODE = '22023';
        END IF;
        IF source_habitat_id IS NOT NULL THEN
            PERFORM 1 FROM public.habitat_zone AS habitat
             WHERE habitat.id = source_habitat_id AND habitat.location_id = requested_location_id
             FOR KEY SHARE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Source habitat must belong to the requested location'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
        IF target_habitat_id IS NOT NULL THEN
            PERFORM 1 FROM public.habitat_zone AS habitat
             WHERE habitat.id = target_habitat_id AND habitat.location_id = requested_location_id
             FOR KEY SHARE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Target habitat must belong to the requested location'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
        INSERT INTO public.wildlife_corridor (
            id, location_id, corridor_name, source_habitat_id, target_habitat_id,
            width_m, length_m, vegetation_type, condition, notes, status, metadata
        ) VALUES (
            record_uuid, requested_location_id, normalized_name, source_habitat_id,
            target_habitat_id, NULLIF(requested_content->>'width_m', '')::NUMERIC,
            NULLIF(requested_content->>'length_m', '')::NUMERIC,
            requested_content->>'vegetation_type', 'fair', requested_content->>'notes',
            'active', normalized_metadata
        );
    WHEN 'hedgerow_record' THEN
        normalized_name := NULLIF(pg_catalog.btrim(requested_content->>'hedgerow_name'), '');
        species := coalesce(requested_content->'species_mix', '[]'::JSONB);
        purpose_values := coalesce(requested_content->'purpose', '[]'::JSONB);
        IF requested_content->>'hedgerow_name' IS NOT NULL
           AND pg_catalog.char_length(requested_content->>'hedgerow_name') > 200
           OR pg_catalog.jsonb_typeof(species) IS DISTINCT FROM 'array'
           OR pg_catalog.jsonb_array_length(species) > 100
           OR pg_catalog.jsonb_typeof(purpose_values) IS DISTINCT FROM 'array'
           OR pg_catalog.jsonb_array_length(purpose_values) > 100
           OR requested_content->>'length_m' IS NOT NULL
              AND (requested_content->>'length_m')::NUMERIC NOT BETWEEN 0 AND 99999999.99
           OR requested_content->>'height_m' IS NOT NULL
              AND (requested_content->>'height_m')::NUMERIC NOT BETWEEN 0 AND 999.99
           OR requested_content->>'age_years' IS NOT NULL
              AND (requested_content->>'age_years')::BIGINT NOT BETWEEN 0 AND 2147483647
           OR requested_content->>'planting_date' IS NOT NULL
              AND (requested_content->>'planting_date')::DATE > CURRENT_DATE
           OR requested_content->>'notes' IS NOT NULL
              AND pg_catalog.char_length(requested_content->>'notes') > 4000
           OR EXISTS (
                SELECT 1 FROM pg_catalog.jsonb_array_elements(species) AS item(value)
                 WHERE pg_catalog.jsonb_typeof(item.value) IS DISTINCT FROM 'string'
                    OR pg_catalog.char_length(item.value #>> '{}') > 200
           )
           OR EXISTS (
                SELECT 1 FROM pg_catalog.jsonb_array_elements(purpose_values) AS item(value)
                 WHERE pg_catalog.jsonb_typeof(item.value) IS DISTINCT FROM 'string'
                    OR pg_catalog.char_length(item.value #>> '{}') > 200
           ) THEN
            RAISE EXCEPTION 'Hedgerow capture is invalid or outside its bounds'
                USING ERRCODE = '22023';
        END IF;
        INSERT INTO public.hedgerow_record (
            id, location_id, hedgerow_name, species_mix, length_m, height_m,
            age_years, planting_date, condition, purpose, notes, status, metadata
        ) VALUES (
            record_uuid, requested_location_id, normalized_name, species,
            NULLIF(requested_content->>'length_m', '')::NUMERIC,
            NULLIF(requested_content->>'height_m', '')::NUMERIC,
            NULLIF(requested_content->>'age_years', '')::INTEGER,
            NULLIF(requested_content->>'planting_date', '')::DATE,
            'fair', purpose_values, requested_content->>'notes', 'active', normalized_metadata
        );
    WHEN 'buffer_zone_monitoring' THEN
        habitat_id := NULLIF(requested_content->>'habitat_zone_id', '')::UUID;
        effective_date := coalesce(NULLIF(requested_content->>'check_date', '')::DATE, CURRENT_DATE);
        buffer_width := NULLIF(requested_content->>'buffer_width_m', '')::NUMERIC;
        minimum_width := NULLIF(requested_content->>'minimum_required_m', '')::NUMERIC;
        IF buffer_width IS NOT NULL AND buffer_width NOT BETWEEN 0 AND 999999.99
           OR minimum_width IS NOT NULL AND minimum_width NOT BETWEEN 0 AND 999999.99
           OR requested_content->>'vegetation_coverage_pct' IS NOT NULL
              AND (requested_content->>'vegetation_coverage_pct')::NUMERIC NOT BETWEEN 0 AND 100
           OR requested_content->>'erosion_observed' IS NOT NULL
              AND pg_catalog.jsonb_typeof(requested_content->'erosion_observed') IS DISTINCT FROM 'boolean'
           OR requested_content->>'notes' IS NOT NULL
              AND pg_catalog.char_length(requested_content->>'notes') > 4000 THEN
            RAISE EXCEPTION 'Buffer check is invalid or outside its bounds'
                USING ERRCODE = '22023';
        END IF;
        IF habitat_id IS NOT NULL THEN
            PERFORM 1 FROM public.habitat_zone AS habitat
             WHERE habitat.id = habitat_id AND habitat.location_id = requested_location_id
             FOR KEY SHARE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Buffer habitat must belong to the requested location'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
        is_compliant := CASE
            WHEN buffer_width IS NOT NULL AND minimum_width IS NOT NULL
            THEN buffer_width >= minimum_width
            ELSE NULL
        END;
        INSERT INTO public.buffer_zone_monitoring (
            id, location_id, habitat_zone_id, check_date, buffer_width_m,
            minimum_required_m, compliant, vegetation_coverage_pct,
            erosion_observed, notes, status, metadata
        ) VALUES (
            record_uuid, requested_location_id, habitat_id, effective_date,
            buffer_width, minimum_width, is_compliant,
            NULLIF(requested_content->>'vegetation_coverage_pct', '')::NUMERIC,
            coalesce((requested_content->>'erosion_observed')::BOOLEAN, FALSE),
            requested_content->>'notes', 'recorded', normalized_metadata
        );
    WHEN 'landscape_biodiversity_score' THEN
        effective_date := coalesce(NULLIF(requested_content->>'assessment_date', '')::DATE, CURRENT_DATE);
        IF requested_content->>'species_richness' IS NOT NULL
           AND (requested_content->>'species_richness')::BIGINT NOT BETWEEN 0 AND 2147483647
           OR requested_content->>'shannon_index' IS NOT NULL
              AND (requested_content->>'shannon_index')::NUMERIC NOT BETWEEN 0 AND 99.999
           OR requested_content->>'habitat_diversity_index' IS NOT NULL
              AND (requested_content->>'habitat_diversity_index')::NUMERIC NOT BETWEEN 0 AND 99.999
           OR requested_content->>'connectivity_score' IS NOT NULL
              AND (requested_content->>'connectivity_score')::NUMERIC NOT BETWEEN 0 AND 999.99
           OR requested_content->>'overall_score' IS NOT NULL
              AND (requested_content->>'overall_score')::NUMERIC NOT BETWEEN 0 AND 999.99
           OR requested_content->>'assessor' IS NOT NULL
              AND pg_catalog.char_length(requested_content->>'assessor') > 200
           OR requested_content->>'notes' IS NOT NULL
              AND pg_catalog.char_length(requested_content->>'notes') > 4000 THEN
            RAISE EXCEPTION 'Biodiversity assessment is invalid or outside its bounds'
                USING ERRCODE = '22023';
        END IF;
        INSERT INTO public.landscape_biodiversity_score (
            id, location_id, assessment_date, species_richness, shannon_index,
            habitat_diversity_index, connectivity_score, overall_score, assessor,
            notes, status, metadata
        ) VALUES (
            record_uuid, requested_location_id, effective_date,
            NULLIF(requested_content->>'species_richness', '')::INTEGER,
            NULLIF(requested_content->>'shannon_index', '')::NUMERIC,
            NULLIF(requested_content->>'habitat_diversity_index', '')::NUMERIC,
            NULLIF(requested_content->>'connectivity_score', '')::NUMERIC,
            NULLIF(requested_content->>'overall_score', '')::NUMERIC,
            requested_content->>'assessor', requested_content->>'notes',
            'recorded', normalized_metadata
        );
    END CASE;

    captured_at := pg_catalog.clock_timestamp();
    INSERT INTO public.landscape_capture_receipt (
        operator_id, request_id, location_id, record_type, record_id,
        input_digest, reason, status, created_at
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_record_type, record_uuid, input_digest,
        pg_catalog.btrim(requested_reason), effective_status, captured_at
    );
    RETURN pg_catalog.jsonb_build_object(
        'location_id', requested_location_id,
        'record_id', record_uuid,
        'record_type', requested_record_type,
        'request_id', requested_request_id,
        'status', effective_status,
        'created_at', captured_at,
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_landscape_record(
    UUID, TEXT, UUID, JSONB, TEXT
) OWNER TO kokonut_landscape_capture_writer;
REVOKE ALL ON FUNCTION kokonut_security.create_location_landscape_record(
    UUID, TEXT, UUID, JSONB, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.create_location_landscape_record('
            'UUID, TEXT, UUID, JSONB, TEXT) TO kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.create_location_landscape_record('
            'UUID, TEXT, UUID, JSONB, TEXT) FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_landscape_record(
    UUID, TEXT, UUID, JSONB, TEXT
) IS 'Creates one location-scoped landscape record in its source-defined initial state, with signed operator authorization and an atomic private idempotency/audit receipt.';

COMMIT;
