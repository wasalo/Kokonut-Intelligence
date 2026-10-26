-- Move pollinator observations to a tenant-authorized Gateway write boundary.
-- Captured observations remain recorded until independently reviewed.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_pollinator_observation_writer'
    ) THEN
        CREATE ROLE kokonut_pollinator_observation_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_pollinator_observation_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

ALTER TABLE public.pollinator_observation
    ADD COLUMN IF NOT EXISTS created_by_operator_id UUID
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_pollinator_observation_creator
    ON public.pollinator_observation (created_by_operator_id, created_at DESC)
    WHERE created_by_operator_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.pollinator_observation_capture_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    observation_id UUID NOT NULL UNIQUE
        REFERENCES public.pollinator_observation(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

DO $$
DECLARE
    column_name TEXT;
    role_name TEXT;
    role_sql TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        IF role_name = 'PUBLIC'
           OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            role_sql := CASE
                WHEN role_name = 'PUBLIC' THEN 'PUBLIC'
                ELSE pg_catalog.quote_ident(role_name)
            END;
            EXECUTE pg_catalog.format(
                'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
                'ON TABLE public.pollinator_observation FROM %s', role_sql
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.pollinator_observation'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I) ON TABLE public.pollinator_observation FROM %2$s',
                    column_name, role_sql
                );
                EXECUTE pg_catalog.format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.pollinator_observation FROM %2$s',
                    column_name, role_sql
                );
                EXECUTE pg_catalog.format(
                    'REVOKE REFERENCES (%1$I) ON TABLE public.pollinator_observation FROM %2$s',
                    column_name, role_sql
                );
            END LOOP;
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.pollinator_observation_capture_receipt FROM %s',
                role_sql
            );
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_pollinator_observation_writer;
GRANT INSERT (
    id, location_id, plot_id, observation_date, pollinator_type, species_name,
    count, observation_method, duration_minutes, weather_conditions,
    temperature_c, hive_record_id, notes, source_system, source_id, metadata,
    status, created_by_operator_id
) ON TABLE public.pollinator_observation
    TO kokonut_pollinator_observation_writer;
GRANT SELECT (
    operator_id, request_id, location_id, observation_id, input_digest, created_at
) ON TABLE public.pollinator_observation_capture_receipt
    TO kokonut_pollinator_observation_writer;
GRANT INSERT (
    operator_id, request_id, location_id, observation_id, input_digest
) ON TABLE public.pollinator_observation_capture_receipt
    TO kokonut_pollinator_observation_writer;
GRANT SELECT (id, farm_id) ON TABLE public.plot
    TO kokonut_pollinator_observation_writer;
GRANT SELECT (id, location_id) ON TABLE public.farm
    TO kokonut_pollinator_observation_writer;
GRANT SELECT (location_id, id) ON TABLE public.hive_record
    TO kokonut_pollinator_observation_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_pollinator_observation_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_pollinator_observation_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_pollinator_observation_writer;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_pollinator_observation(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_pollinator_type TEXT,
    requested_count INTEGER,
    requested_observation_method TEXT,
    requested_duration_minutes INTEGER,
    requested_plot_id UUID,
    requested_observation_date DATE,
    requested_species_name TEXT,
    requested_weather_conditions JSONB,
    requested_temperature_c NUMERIC,
    requested_hive_record_id UUID,
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
    effective_date DATE := coalesce(requested_observation_date, CURRENT_DATE);
    normalized_species TEXT := NULLIF(pg_catalog.btrim(requested_species_name), '');
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    normalized_weather JSONB := coalesce(requested_weather_conditions, '{}'::JSONB);
    input_digest BYTEA;
    existing_receipt RECORD;
    observation_uuid UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Pollinator capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'pollinator_health', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Pollinator capture requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF requested_pollinator_type IS NULL OR requested_pollinator_type NOT IN (
           'honeybee', 'wild_bee', 'butterfly', 'moth', 'beetle', 'fly', 'bird', 'bat', 'other'
       )
       OR requested_count IS NULL OR requested_count < 0
       OR requested_observation_method IS NULL OR requested_observation_method NOT IN (
           'transect', 'pan_trap', 'visual_count', 'hive_weight', 'other'
       )
       OR requested_duration_minutes IS NULL OR requested_duration_minutes < 0
       OR requested_species_name IS NOT NULL
          AND (pg_catalog.char_length(normalized_species) > 200
               OR requested_species_name ~ '[[:cntrl:]]')
       OR pg_catalog.jsonb_typeof(normalized_weather) IS DISTINCT FROM 'object'
       OR pg_catalog.pg_column_size(normalized_weather) > 4096
       OR requested_temperature_c IS NOT NULL
          AND (requested_temperature_c < -100 OR requested_temperature_c > 100)
       OR requested_notes IS NOT NULL
          AND (pg_catalog.char_length(normalized_notes) > 2000
               OR requested_notes ~ '[[:cntrl:]]') THEN
        RAISE EXCEPTION 'Pollinator observation input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    IF requested_plot_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
          FROM public.plot AS plot_row
          JOIN public.farm AS farm_row ON farm_row.id = plot_row.farm_id
         WHERE plot_row.id = requested_plot_id
           AND farm_row.location_id = requested_location_id
    ) THEN
        RAISE EXCEPTION 'Pollinator plot must belong to the granted location'
            USING ERRCODE = '22023';
    END IF;
    IF requested_hive_record_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.hive_record AS hive_row
         WHERE hive_row.id = requested_hive_record_id
           AND hive_row.location_id = requested_location_id
    ) THEN
        RAISE EXCEPTION 'Pollinator hive must belong to the granted location'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT,
                requested_pollinator_type,
                requested_count,
                requested_observation_method,
                requested_duration_minutes,
                requested_plot_id::TEXT,
                effective_date,
                normalized_species,
                normalized_weather,
                requested_temperature_c,
                requested_hive_record_id::TEXT,
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

    SELECT receipt.location_id, receipt.observation_id, receipt.input_digest
      INTO existing_receipt
      FROM public.pollinator_observation_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest
           OR existing_receipt.location_id IS DISTINCT FROM requested_location_id THEN
            RAISE EXCEPTION 'Pollinator request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'observation_id', existing_receipt.observation_id,
            'location_id', requested_location_id,
            'pollinator_type', requested_pollinator_type,
            'count', requested_count,
            'observation_method', requested_observation_method,
            'observation_date', effective_date,
            'duration_minutes', requested_duration_minutes,
            'status', 'recorded',
            'replayed', TRUE
        );
    END IF;

    observation_uuid := pg_catalog.gen_random_uuid();
    INSERT INTO public.pollinator_observation (
        id, location_id, plot_id, observation_date, pollinator_type, species_name,
        count, observation_method, duration_minutes, weather_conditions,
        temperature_c, hive_record_id, notes, status, created_by_operator_id
    ) VALUES (
        observation_uuid, requested_location_id, requested_plot_id, effective_date,
        requested_pollinator_type, normalized_species, requested_count,
        requested_observation_method, requested_duration_minutes, normalized_weather,
        requested_temperature_c, requested_hive_record_id, normalized_notes,
        'recorded', context_record.actor_id
    );
    INSERT INTO public.pollinator_observation_capture_receipt (
        operator_id, request_id, location_id, observation_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        observation_uuid, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'observation_id', observation_uuid,
        'location_id', requested_location_id,
        'pollinator_type', requested_pollinator_type,
        'count', requested_count,
        'observation_method', requested_observation_method,
        'observation_date', effective_date,
        'duration_minutes', requested_duration_minutes,
        'status', 'recorded',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_pollinator_observation(
    UUID, UUID, TEXT, INTEGER, TEXT, INTEGER, UUID, DATE, TEXT, JSONB, NUMERIC, UUID, TEXT
) OWNER TO kokonut_pollinator_observation_writer;
REVOKE ALL ON FUNCTION kokonut_security.create_location_pollinator_observation(
    UUID, UUID, TEXT, INTEGER, TEXT, INTEGER, UUID, DATE, TEXT, JSONB, NUMERIC, UUID, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.create_location_pollinator_observation('
            'UUID, UUID, TEXT, INTEGER, TEXT, INTEGER, UUID, DATE, TEXT, JSONB, NUMERIC, UUID, TEXT'
            ') TO kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.create_location_pollinator_observation('
            'UUID, UUID, TEXT, INTEGER, TEXT, INTEGER, UUID, DATE, TEXT, JSONB, NUMERIC, UUID, TEXT'
            ') FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_pollinator_observation(
    UUID, UUID, TEXT, INTEGER, TEXT, INTEGER, UUID, DATE, TEXT, JSONB, NUMERIC, UUID, TEXT
) IS 'Creates an append-only recorded pollinator observation after signed exact-location create authorization; retries are idempotent and plots/hives must match the granted location.';

COMMIT;
