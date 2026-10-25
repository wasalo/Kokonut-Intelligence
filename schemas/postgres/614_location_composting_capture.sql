-- Add a bounded, tenant-scoped Gateway writer for composting records.
-- Captures stay recorded; quality review and verification remain separate.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_composting_capture_writer'
    ) THEN
        CREATE ROLE kokonut_composting_capture_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_composting_capture_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

CREATE TABLE IF NOT EXISTS public.composting_capture_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    composting_record_id UUID NOT NULL UNIQUE
        REFERENCES public.composting_record(id) ON DELETE CASCADE,
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
                'REVOKE ALL ON TABLE public.composting_capture_receipt FROM %s',
                CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid =
                       'public.composting_capture_receipt'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE ALL (%1$I) ON TABLE public.composting_capture_receipt FROM %2$s',
                    column_name,
                    CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_composting_capture_writer;
GRANT INSERT (
    id, location_id, compost_date, feedstock_type, feedstock_kg, compost_method,
    temperature_c, moisture_pct, duration_days, finished_volume_kg, notes,
    metadata, status, created_by
) ON TABLE public.composting_record TO kokonut_composting_capture_writer;
GRANT SELECT (
    operator_id, request_id, location_id, composting_record_id, input_digest, created_at
) ON TABLE public.composting_capture_receipt TO kokonut_composting_capture_writer;
GRANT INSERT (
    operator_id, request_id, location_id, composting_record_id, input_digest
) ON TABLE public.composting_capture_receipt TO kokonut_composting_capture_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_composting_capture_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_composting_capture_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_composting_capture_writer;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_composting_record(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_compost_date DATE,
    requested_feedstock_type TEXT,
    requested_feedstock_label TEXT,
    requested_feedstock_kg NUMERIC,
    requested_compost_method TEXT,
    requested_compost_method_label TEXT,
    requested_temperature_c NUMERIC,
    requested_moisture_pct NUMERIC,
    requested_duration_days INTEGER,
    requested_finished_volume_kg NUMERIC,
    requested_ph NUMERIC,
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
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    effective_date DATE := coalesce(requested_compost_date, CURRENT_DATE);
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
        RAISE EXCEPTION 'Composting capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'waste_management', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Composting capture requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF requested_feedstock_type IS NULL OR requested_feedstock_type NOT IN (
           'crop_residue', 'manure', 'food_waste', 'green_waste', 'mixed', 'other'
       )
       OR requested_compost_method IS NULL OR requested_compost_method NOT IN (
           'heap', 'pit', 'vermiculture', 'bokashi', 'other'
       )
       OR requested_feedstock_label IS NOT NULL
          AND (pg_catalog.char_length(requested_feedstock_label) > 200
               OR pg_catalog.btrim(requested_feedstock_label) = ''
               OR requested_feedstock_label ~ '[[:cntrl:]]')
       OR requested_compost_method_label IS NOT NULL
          AND (pg_catalog.char_length(requested_compost_method_label) > 100
               OR pg_catalog.btrim(requested_compost_method_label) = ''
               OR requested_compost_method_label ~ '[[:cntrl:]]')
       OR requested_feedstock_kg IS NULL
       OR requested_feedstock_kg <= 0
       OR requested_feedstock_kg > 99999999.99
       OR pg_catalog.scale(requested_feedstock_kg) > 2
       OR effective_date > CURRENT_DATE
       OR requested_temperature_c IS NOT NULL
          AND (requested_temperature_c < -100 OR requested_temperature_c > 200
               OR pg_catalog.scale(requested_temperature_c) > 1)
       OR requested_moisture_pct IS NOT NULL
          AND (requested_moisture_pct < 0 OR requested_moisture_pct > 100
               OR pg_catalog.scale(requested_moisture_pct) > 1)
       OR requested_duration_days IS NOT NULL
          AND (requested_duration_days < 0 OR requested_duration_days > 36500)
       OR requested_finished_volume_kg IS NOT NULL
          AND (requested_finished_volume_kg < 0
               OR requested_finished_volume_kg > 99999999.99
               OR pg_catalog.scale(requested_finished_volume_kg) > 2)
       OR requested_ph IS NOT NULL
          AND (requested_ph < 0 OR requested_ph > 14
               OR pg_catalog.scale(requested_ph) > 2)
       OR requested_notes IS NOT NULL
          AND (pg_catalog.char_length(requested_notes) > 1000
               OR requested_notes ~ '[[:cntrl:]]') THEN
        RAISE EXCEPTION 'Composting capture input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    IF requested_ph IS NOT NULL THEN
        normalized_metadata := pg_catalog.jsonb_build_object('ph', requested_ph);
    END IF;
    IF requested_feedstock_label IS NOT NULL
       OR requested_compost_method_label IS NOT NULL THEN
        normalized_metadata := normalized_metadata || pg_catalog.jsonb_build_object(
            'legacy_composting_inputs',
            pg_catalog.jsonb_strip_nulls(pg_catalog.jsonb_build_object(
                'feedstock_type', requested_feedstock_label,
                'compost_method', requested_compost_method_label
            ))
        );
    END IF;
    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT,
                effective_date,
                requested_feedstock_type,
                requested_feedstock_label,
                requested_feedstock_kg,
                requested_compost_method,
                requested_compost_method_label,
                requested_temperature_c,
                requested_moisture_pct,
                requested_duration_days,
                requested_finished_volume_kg,
                requested_ph,
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

    SELECT receipt.location_id, receipt.composting_record_id, receipt.input_digest
      INTO existing_receipt
      FROM public.composting_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest
           OR existing_receipt.location_id IS DISTINCT FROM requested_location_id THEN
            RAISE EXCEPTION 'Composting request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'record_id', existing_receipt.composting_record_id,
            'location_id', requested_location_id,
            'compost_date', effective_date,
            'status', 'recorded',
            'replayed', TRUE
        );
    END IF;

    record_id := pg_catalog.gen_random_uuid();
    INSERT INTO public.composting_record (
        id, location_id, compost_date, feedstock_type, feedstock_kg,
        compost_method, temperature_c, moisture_pct, duration_days,
        finished_volume_kg, notes, metadata, status, created_by
    ) VALUES (
        record_id, requested_location_id, effective_date, requested_feedstock_type,
        requested_feedstock_kg, requested_compost_method, requested_temperature_c,
        requested_moisture_pct, requested_duration_days, requested_finished_volume_kg,
        normalized_notes, normalized_metadata, 'recorded', context_record.actor_id
    );
    INSERT INTO public.composting_capture_receipt (
        operator_id, request_id, location_id, composting_record_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        record_id, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'record_id', record_id,
        'location_id', requested_location_id,
        'compost_date', effective_date,
        'status', 'recorded',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_composting_record(
    UUID, UUID, DATE, TEXT, TEXT, NUMERIC, TEXT, TEXT, NUMERIC, NUMERIC, INTEGER, NUMERIC, NUMERIC, TEXT
) OWNER TO kokonut_composting_capture_writer;
REVOKE ALL ON FUNCTION kokonut_security.create_location_composting_record(
    UUID, UUID, DATE, TEXT, TEXT, NUMERIC, TEXT, TEXT, NUMERIC, NUMERIC, INTEGER, NUMERIC, NUMERIC, TEXT
) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.create_location_composting_record('
            'UUID, UUID, DATE, TEXT, TEXT, NUMERIC, TEXT, TEXT, NUMERIC, NUMERIC, INTEGER, NUMERIC, NUMERIC, TEXT) TO kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.create_location_composting_record('
            'UUID, UUID, DATE, TEXT, TEXT, NUMERIC, TEXT, TEXT, NUMERIC, NUMERIC, INTEGER, NUMERIC, NUMERIC, TEXT) FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_composting_record(
    UUID, UUID, DATE, TEXT, TEXT, NUMERIC, TEXT, TEXT, NUMERIC, NUMERIC, INTEGER, NUMERIC, NUMERIC, TEXT
) IS 'Creates a bounded recorded-only composting row after signed exact-location create authorization; original freeform labels are retained in bounded metadata and retries are idempotent.';

COMMIT;
