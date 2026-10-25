-- Add tenant-scoped pollution incident capture and resolution operations.
-- Narrative access and incident closure require a separate location review grant.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_incident_capture_writer'
    ) THEN
        CREATE ROLE kokonut_incident_capture_writer;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_incident_resolution_writer'
    ) THEN
        CREATE ROLE kokonut_incident_resolution_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_incident_capture_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE kokonut_incident_resolution_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

CREATE TABLE IF NOT EXISTS public.pollution_incident_operation_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('capture', 'resolve')),
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    incident_id UUID NOT NULL
        REFERENCES public.pollution_incident(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

DO $$
DECLARE column_name TEXT;
        role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        IF role_name = 'PUBLIC'
           OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
                'ON TABLE public.pollution_incident FROM %s',
                CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.pollution_incident'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                    'ON TABLE public.pollution_incident FROM %2$s',
                    column_name,
                    CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
                );
            END LOOP;
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.pollution_incident_operation_receipt FROM %s',
                CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.pollution_incident_operation_receipt'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE ALL (%1$I) ON TABLE public.pollution_incident_operation_receipt FROM %2$s',
                    column_name,
                    CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_incident_capture_writer, kokonut_incident_resolution_writer;
GRANT INSERT (
    id, location_id, incident_date, incident_type, severity, description,
    affected_area, notes, resolved, status, metadata, created_by
) ON TABLE public.pollution_incident TO kokonut_incident_capture_writer;
GRANT SELECT (
    id, location_id, status, resolved, incident_type, severity, incident_date
) ON TABLE public.pollution_incident TO kokonut_incident_resolution_writer;
GRANT UPDATE (
    status, resolved, remedial_action, resolution_date, updated_at, updated_by
) ON TABLE public.pollution_incident TO kokonut_incident_resolution_writer;

GRANT SELECT (
    operator_id, request_id, operation, location_id, incident_id, input_digest, created_at
) ON TABLE public.pollution_incident_operation_receipt
    TO kokonut_incident_capture_writer, kokonut_incident_resolution_writer;
GRANT INSERT (
    operator_id, request_id, operation, location_id, incident_id, input_digest
) ON TABLE public.pollution_incident_operation_receipt
    TO kokonut_incident_capture_writer, kokonut_incident_resolution_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_incident_capture_writer, kokonut_incident_resolution_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_incident_capture_writer, kokonut_incident_resolution_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_incident_capture_writer, kokonut_incident_resolution_writer;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_pollution_incident(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_incident_date DATE,
    requested_incident_type TEXT,
    requested_legacy_type TEXT,
    requested_severity TEXT,
    requested_description TEXT,
    requested_affected_area TEXT,
    requested_reported_by TEXT,
    requested_notes TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    effective_date DATE := coalesce(requested_incident_date, CURRENT_DATE);
    normalized_description TEXT := NULLIF(pg_catalog.btrim(requested_description), '');
    normalized_area TEXT := NULLIF(pg_catalog.btrim(requested_affected_area), '');
    normalized_reporter TEXT := NULLIF(pg_catalog.btrim(requested_reported_by), '');
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    receipt RECORD;
    metadata_value JSONB := '{}'::JSONB;
    input_digest BYTEA;
    new_incident_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Incident capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'waste_management', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Incident capture requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_incident_type IS NULL OR requested_incident_type NOT IN (
           'chemical_spill', 'runoff', 'air_emission', 'water_contamination',
           'waste_dumping', 'other'
       )
       OR requested_severity IS NULL
          OR requested_severity NOT IN ('low', 'medium', 'high', 'critical')
       OR normalized_description IS NULL
          OR pg_catalog.char_length(normalized_description) > 2500
       OR normalized_area IS NOT NULL AND pg_catalog.char_length(normalized_area) > 200
       OR normalized_reporter IS NOT NULL AND pg_catalog.char_length(normalized_reporter) > 200
       OR normalized_notes IS NOT NULL AND pg_catalog.char_length(normalized_notes) > 1000
       OR effective_date > CURRENT_DATE THEN
        RAISE EXCEPTION 'Incident capture input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    IF requested_legacy_type IS NOT NULL THEN
        IF pg_catalog.char_length(requested_legacy_type) > 100
           OR pg_catalog.btrim(requested_legacy_type) = '' THEN
            RAISE EXCEPTION 'Incident source type is outside its bounds'
                USING ERRCODE = '22023';
        END IF;
        metadata_value := pg_catalog.jsonb_build_object(
            'legacy_incident_type', requested_legacy_type
        );
    END IF;
    IF normalized_reporter IS NOT NULL THEN
        metadata_value := metadata_value || pg_catalog.jsonb_build_object(
            'reported_by', normalized_reporter
        );
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                'capture', requested_location_id::TEXT, effective_date,
                requested_incident_type, requested_legacy_type, requested_severity,
                normalized_description, normalized_area, normalized_reporter, normalized_notes
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
    SELECT receipt_row.operation, receipt_row.location_id,
           receipt_row.incident_id, receipt_row.input_digest
      INTO receipt
      FROM public.pollution_incident_operation_receipt
           AS receipt_row
     WHERE receipt_row.operator_id = context_record.actor_id
       AND receipt_row.request_id = requested_request_id;
    IF FOUND THEN
        IF receipt.operation IS DISTINCT FROM 'capture'
           OR receipt.location_id IS DISTINCT FROM requested_location_id
           OR receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Incident request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'incident_id', receipt.incident_id,
            'location_id', requested_location_id,
            'incident_date', effective_date,
            'status', 'open',
            'replayed', TRUE
        );
    END IF;

    new_incident_id := pg_catalog.gen_random_uuid();
    INSERT INTO public.pollution_incident (
        id, location_id, incident_date, incident_type, severity, description,
        affected_area, notes, resolved, status, metadata, created_by
    ) VALUES (
        new_incident_id, requested_location_id, effective_date, requested_incident_type,
        requested_severity, normalized_description, normalized_area, normalized_notes,
        FALSE, 'open', metadata_value, context_record.actor_id
    );
    INSERT INTO public.pollution_incident_operation_receipt (
        operator_id, request_id, operation, location_id, incident_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, 'capture', requested_location_id,
        new_incident_id, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'incident_id', new_incident_id,
        'location_id', requested_location_id,
        'incident_date', effective_date,
        'status', 'open',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_pollution_incident(
    UUID, UUID, DATE, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) OWNER TO kokonut_incident_capture_writer;
REVOKE ALL ON FUNCTION kokonut_security.create_location_pollution_incident(
    UUID, UUID, DATE, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;

CREATE OR REPLACE FUNCTION kokonut_security.resolve_location_pollution_incident(
    requested_location_id UUID,
    requested_incident_id UUID,
    requested_request_id UUID,
    requested_resolution_date DATE,
    requested_remedial_action TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    effective_date DATE := coalesce(requested_resolution_date, CURRENT_DATE);
    normalized_action TEXT := NULLIF(pg_catalog.btrim(requested_remedial_action), '');
    receipt RECORD;
    incident_record RECORD;
    input_digest BYTEA;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_incident_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Incident review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'waste_management', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Incident review requires an exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF normalized_action IS NULL
       OR pg_catalog.char_length(normalized_action) > 2000
       OR effective_date > CURRENT_DATE THEN
        RAISE EXCEPTION 'Incident resolution input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                'resolve', requested_location_id::TEXT, requested_incident_id::TEXT,
                effective_date, normalized_action
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
    SELECT receipt_row.operation, receipt_row.location_id,
           receipt_row.incident_id, receipt_row.input_digest
      INTO receipt
      FROM public.pollution_incident_operation_receipt
           AS receipt_row
     WHERE receipt_row.operator_id = context_record.actor_id
       AND receipt_row.request_id = requested_request_id;
    IF FOUND THEN
        IF receipt.operation IS DISTINCT FROM 'resolve'
           OR receipt.location_id IS DISTINCT FROM requested_location_id
           OR receipt.incident_id IS DISTINCT FROM requested_incident_id
           OR receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Incident request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'incident_id', requested_incident_id,
            'location_id', requested_location_id,
            'resolution_date', effective_date,
            'status', 'resolved',
            'replayed', TRUE
        );
    END IF;

    SELECT status, resolved
      INTO incident_record
      FROM public.pollution_incident
     WHERE id = requested_incident_id
       AND location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Incident is not available in this location'
            USING ERRCODE = '42501';
    END IF;
    IF incident_record.resolved IS TRUE
       OR incident_record.status NOT IN ('open', 'investigating', 'remediation') THEN
        RAISE EXCEPTION 'Only unresolved incidents can be resolved'
            USING ERRCODE = '23505';
    END IF;

    UPDATE public.pollution_incident
       SET status = 'resolved', resolved = TRUE,
           remedial_action = normalized_action,
           resolution_date = effective_date,
           updated_at = pg_catalog.clock_timestamp(),
           updated_by = context_record.actor_id
     WHERE id = requested_incident_id
       AND location_id = requested_location_id;
    INSERT INTO public.pollution_incident_operation_receipt (
        operator_id, request_id, operation, location_id, incident_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, 'resolve', requested_location_id,
        requested_incident_id, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'incident_id', requested_incident_id,
        'location_id', requested_location_id,
        'resolution_date', effective_date,
        'status', 'resolved',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.resolve_location_pollution_incident(
    UUID, UUID, UUID, DATE, TEXT
) OWNER TO kokonut_incident_resolution_writer;
REVOKE ALL ON FUNCTION kokonut_security.resolve_location_pollution_incident(
    UUID, UUID, UUID, DATE, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.create_location_pollution_incident('
            'UUID, UUID, DATE, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT) TO kokonut_runtime';
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.resolve_location_pollution_incident('
            'UUID, UUID, UUID, DATE, TEXT) TO kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.create_location_pollution_incident('
            'UUID, UUID, DATE, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT) FROM kokonut_directus_runtime';
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.resolve_location_pollution_incident('
            'UUID, UUID, UUID, DATE, TEXT) FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_pollution_incident(
    UUID, UUID, DATE, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) IS 'Creates a bounded open pollution incident with authenticated exact-location create scope and private idempotency receipt.';
COMMENT ON FUNCTION kokonut_security.resolve_location_pollution_incident(
    UUID, UUID, UUID, DATE, TEXT
) IS 'Resolves only an unresolved incident at the signed location with a separate exact-location review grant and private idempotency receipt.';

COMMIT;
