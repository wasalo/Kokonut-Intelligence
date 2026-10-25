-- Add a bounded, tenant-scoped Gateway writer for waste-stream capture.
-- Captures stay recorded until a separate human verification workflow exists.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_waste_stream_writer'
    ) THEN
        CREATE ROLE kokonut_waste_stream_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_waste_stream_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

CREATE TABLE IF NOT EXISTS public.waste_stream_capture_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    waste_stream_id UUID NOT NULL UNIQUE
        REFERENCES public.waste_stream(id) ON DELETE CASCADE,
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
                'REVOKE ALL ON TABLE public.waste_stream_capture_receipt FROM %s',
                CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid =
                       'public.waste_stream_capture_receipt'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE ALL (%1$I) ON TABLE public.waste_stream_capture_receipt FROM %2$s',
                    column_name,
                    CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_waste_stream_writer;
GRANT INSERT (
    id, location_id, waste_type, waste_name, quantity_kg, quantity_unit,
    record_date, disposal_method, notes, status, created_by
) ON TABLE public.waste_stream TO kokonut_waste_stream_writer;
GRANT SELECT (
    operator_id, request_id, location_id, waste_stream_id, input_digest, created_at
) ON TABLE public.waste_stream_capture_receipt TO kokonut_waste_stream_writer;
GRANT INSERT (
    operator_id, request_id, location_id, waste_stream_id, input_digest
) ON TABLE public.waste_stream_capture_receipt TO kokonut_waste_stream_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_waste_stream_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_waste_stream_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_waste_stream_writer;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_waste_stream_record(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_waste_type TEXT,
    requested_waste_name TEXT,
    requested_quantity_kg NUMERIC,
    requested_record_date DATE,
    requested_disposal_method TEXT,
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
    normalized_name TEXT := NULLIF(pg_catalog.btrim(requested_waste_name), '');
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    input_digest BYTEA;
    existing_receipt RECORD;
    record_id UUID;
    effective_date DATE := coalesce(requested_record_date, CURRENT_DATE);
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Waste capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'waste_management', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Waste capture requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF requested_waste_type IS NULL OR requested_waste_type NOT IN (
           'crop_residue', 'processing_waste', 'packaging', 'chemical_container',
           'organic_waste', 'wastewater', 'other'
       )
       OR normalized_name IS NULL
       OR pg_catalog.char_length(normalized_name) > 200
       OR requested_waste_name ~ '[[:cntrl:]]'
       OR requested_quantity_kg IS NULL
       OR requested_quantity_kg <= 0
       OR requested_quantity_kg > 99999999.99
       OR pg_catalog.scale(requested_quantity_kg) > 2
       OR effective_date > CURRENT_DATE
       OR requested_disposal_method IS NOT NULL AND requested_disposal_method NOT IN (
           'composting', 'burning', 'landfill', 'recycling', 'animal_feed',
           'biogas', 'mulching', 'other'
       )
       OR requested_notes IS NOT NULL
          AND (pg_catalog.char_length(requested_notes) > 1000
               OR requested_notes ~ '[[:cntrl:]]') THEN
        RAISE EXCEPTION 'Waste capture input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT,
                requested_waste_type,
                normalized_name,
                requested_quantity_kg,
                effective_date,
                requested_disposal_method,
                normalized_notes
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

    SELECT receipt.location_id, receipt.waste_stream_id, receipt.input_digest
      INTO existing_receipt
      FROM public.waste_stream_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest
           OR existing_receipt.location_id IS DISTINCT FROM requested_location_id THEN
            RAISE EXCEPTION 'Waste capture request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'record_id', existing_receipt.waste_stream_id,
            'location_id', requested_location_id,
            'status', 'recorded',
            'record_date', effective_date,
            'replayed', TRUE
        );
    END IF;

    record_id := pg_catalog.gen_random_uuid();
    INSERT INTO public.waste_stream (
        id, location_id, waste_type, waste_name, quantity_kg, quantity_unit,
        record_date, disposal_method, notes, status, created_by
    ) VALUES (
        record_id, requested_location_id, requested_waste_type, normalized_name,
        requested_quantity_kg, 'kg', effective_date, requested_disposal_method,
        normalized_notes, 'recorded', context_record.actor_id
    );
    INSERT INTO public.waste_stream_capture_receipt (
        operator_id, request_id, location_id, waste_stream_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        record_id, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'record_id', record_id,
        'location_id', requested_location_id,
        'status', 'recorded',
        'record_date', effective_date,
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_waste_stream_record(
    UUID, UUID, TEXT, TEXT, NUMERIC, DATE, TEXT, TEXT
) OWNER TO kokonut_waste_stream_writer;
REVOKE ALL ON FUNCTION kokonut_security.create_location_waste_stream_record(
    UUID, UUID, TEXT, TEXT, NUMERIC, DATE, TEXT, TEXT
) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.create_location_waste_stream_record('
            'UUID, UUID, TEXT, TEXT, NUMERIC, DATE, TEXT, TEXT) TO kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.create_location_waste_stream_record('
            'UUID, UUID, TEXT, TEXT, NUMERIC, DATE, TEXT, TEXT) FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_waste_stream_record(
    UUID, UUID, TEXT, TEXT, NUMERIC, DATE, TEXT, TEXT
) IS 'Creates a bounded recorded-only waste stream row after signed exact-location create authorization; retries are idempotent.';

COMMIT;
