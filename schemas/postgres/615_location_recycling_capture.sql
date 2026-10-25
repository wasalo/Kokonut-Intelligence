-- Add a bounded, tenant-scoped Gateway writer for recycling records.
-- Capture remains recorded; verification and financial classification stay separate.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_recycling_capture_writer'
    ) THEN
        CREATE ROLE kokonut_recycling_capture_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_recycling_capture_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

CREATE TABLE IF NOT EXISTS public.recycling_capture_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    recycling_log_id UUID NOT NULL UNIQUE
        REFERENCES public.recycling_log(id) ON DELETE CASCADE,
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
                'ON TABLE public.recycling_log FROM %s',
                CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.recycling_log'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                    'ON TABLE public.recycling_log FROM %2$s',
                    column_name,
                    CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
                );
            END LOOP;
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.recycling_capture_receipt FROM %s',
                CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.recycling_capture_receipt'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE ALL (%1$I) ON TABLE public.recycling_capture_receipt FROM %2$s',
                    column_name,
                    CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_recycling_capture_writer;
GRANT INSERT (
    id, location_id, record_date, material_type, quantity_kg, destination,
    revenue, notes, metadata, status, created_by
) ON TABLE public.recycling_log TO kokonut_recycling_capture_writer;
GRANT SELECT (
    operator_id, request_id, location_id, recycling_log_id, input_digest, created_at
) ON TABLE public.recycling_capture_receipt TO kokonut_recycling_capture_writer;
GRANT INSERT (
    operator_id, request_id, location_id, recycling_log_id, input_digest
) ON TABLE public.recycling_capture_receipt TO kokonut_recycling_capture_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_recycling_capture_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_recycling_capture_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_recycling_capture_writer;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_recycling_record(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_record_date DATE,
    requested_material_type TEXT,
    requested_material_label TEXT,
    requested_quantity_kg NUMERIC,
    requested_destination TEXT,
    requested_revenue NUMERIC,
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
    effective_date DATE := coalesce(requested_record_date, CURRENT_DATE);
    normalized_destination TEXT := NULLIF(pg_catalog.btrim(requested_destination), '');
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    normalized_metadata JSONB := '{}'::JSONB;
    input_digest BYTEA;
    existing_receipt RECORD;
    record_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Recycling capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'waste_management', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Recycling capture requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF requested_material_type IS NULL OR requested_material_type NOT IN (
           'plastic', 'metal', 'glass', 'paper', 'organic', 'other'
       )
       OR requested_material_label IS NOT NULL
          AND (pg_catalog.char_length(requested_material_label) > 100
               OR pg_catalog.btrim(requested_material_label) = ''
               OR requested_material_label ~ '[[:cntrl:]]')
       OR requested_quantity_kg IS NULL
       OR requested_quantity_kg <= 0
       OR requested_quantity_kg > 99999999.99
       OR pg_catalog.scale(requested_quantity_kg) > 2
       OR effective_date > CURRENT_DATE
       OR normalized_destination IS NULL
       OR pg_catalog.char_length(requested_destination) > 200
       OR requested_destination ~ '[[:cntrl:]]'
       OR requested_revenue IS NOT NULL
          AND (requested_revenue < -99999999.99 OR requested_revenue > 99999999.99
               OR pg_catalog.scale(requested_revenue) > 2)
       OR requested_notes IS NOT NULL
          AND (pg_catalog.char_length(requested_notes) > 1000
               OR requested_notes ~ '[[:cntrl:]]') THEN
        RAISE EXCEPTION 'Recycling capture input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    IF requested_material_label IS NOT NULL THEN
        normalized_metadata := pg_catalog.jsonb_build_object(
            'legacy_material_type', requested_material_label
        );
    END IF;
    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT,
                effective_date,
                requested_material_type,
                requested_material_label,
                requested_quantity_kg,
                normalized_destination,
                requested_revenue,
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

    SELECT receipt.location_id, receipt.recycling_log_id, receipt.input_digest
      INTO existing_receipt
      FROM public.recycling_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest
           OR existing_receipt.location_id IS DISTINCT FROM requested_location_id THEN
            RAISE EXCEPTION 'Recycling request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'record_id', existing_receipt.recycling_log_id,
            'location_id', requested_location_id,
            'record_date', effective_date,
            'status', 'recorded',
            'replayed', TRUE
        );
    END IF;

    record_id := pg_catalog.gen_random_uuid();
    INSERT INTO public.recycling_log (
        id, location_id, record_date, material_type, quantity_kg,
        destination, revenue, notes, metadata, status, created_by
    ) VALUES (
        record_id, requested_location_id, effective_date, requested_material_type,
        requested_quantity_kg, normalized_destination, requested_revenue,
        normalized_notes, normalized_metadata, 'recorded', context_record.actor_id
    );
    INSERT INTO public.recycling_capture_receipt (
        operator_id, request_id, location_id, recycling_log_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        record_id, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'record_id', record_id,
        'location_id', requested_location_id,
        'record_date', effective_date,
        'status', 'recorded',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_recycling_record(
    UUID, UUID, DATE, TEXT, TEXT, NUMERIC, TEXT, NUMERIC, TEXT
) OWNER TO kokonut_recycling_capture_writer;
REVOKE ALL ON FUNCTION kokonut_security.create_location_recycling_record(
    UUID, UUID, DATE, TEXT, TEXT, NUMERIC, TEXT, NUMERIC, TEXT
) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.create_location_recycling_record('
            'UUID, UUID, DATE, TEXT, TEXT, NUMERIC, TEXT, NUMERIC, TEXT) TO kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.create_location_recycling_record('
            'UUID, UUID, DATE, TEXT, TEXT, NUMERIC, TEXT, NUMERIC, TEXT) FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_recycling_record(
    UUID, UUID, DATE, TEXT, TEXT, NUMERIC, TEXT, NUMERIC, TEXT
) IS 'Creates a bounded recorded-only recycling row after signed exact-location create authorization; unknown material labels are retained in bounded metadata and retries are idempotent.';

COMMIT;
