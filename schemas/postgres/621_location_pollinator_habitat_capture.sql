-- Add tenant-authorized self-reported pollinator habitat inventory capture.
-- The active value is the source domain state, not ecological verification.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_pollinator_habitat_writer'
    ) THEN
        CREATE ROLE kokonut_pollinator_habitat_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_pollinator_habitat_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

ALTER TABLE public.pollinator_habitat
    ADD COLUMN IF NOT EXISTS created_by_operator_id UUID
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_pollinator_habitat_creator
    ON public.pollinator_habitat (created_by_operator_id, created_at DESC)
    WHERE created_by_operator_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.pollinator_habitat_capture_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    habitat_id UUID NOT NULL UNIQUE
        REFERENCES public.pollinator_habitat(id) ON DELETE RESTRICT,
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
                'ON TABLE public.pollinator_habitat FROM %s', role_sql
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.pollinator_habitat'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I) ON TABLE public.pollinator_habitat FROM %2$s',
                    column_name, role_sql
                );
                EXECUTE pg_catalog.format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.pollinator_habitat FROM %2$s',
                    column_name, role_sql
                );
                EXECUTE pg_catalog.format(
                    'REVOKE REFERENCES (%1$I) ON TABLE public.pollinator_habitat FROM %2$s',
                    column_name, role_sql
                );
            END LOOP;
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.pollinator_habitat_capture_receipt FROM %s',
                role_sql
            );
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_pollinator_habitat_writer;
GRANT INSERT (
    id, location_id, habitat_name, habitat_type, area_m2, plant_species,
    bloom_start_month, bloom_end_month, water_source, nesting_sites, notes,
    status, created_by_operator_id
) ON TABLE public.pollinator_habitat TO kokonut_pollinator_habitat_writer;
GRANT SELECT (
    operator_id, request_id, location_id, habitat_id, input_digest, created_at
) ON TABLE public.pollinator_habitat_capture_receipt
    TO kokonut_pollinator_habitat_writer;
GRANT INSERT (
    operator_id, request_id, location_id, habitat_id, input_digest
) ON TABLE public.pollinator_habitat_capture_receipt
    TO kokonut_pollinator_habitat_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_pollinator_habitat_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_pollinator_habitat_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_pollinator_habitat_writer;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_pollinator_habitat(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_habitat_name TEXT,
    requested_habitat_type TEXT,
    requested_area_m2 NUMERIC,
    requested_plant_species JSONB,
    requested_bloom_start_month SMALLINT,
    requested_bloom_end_month SMALLINT,
    requested_water_source BOOLEAN,
    requested_nesting_sites TEXT,
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
    normalized_name TEXT := NULLIF(pg_catalog.btrim(requested_habitat_name), '');
    normalized_nesting_sites TEXT := NULLIF(pg_catalog.btrim(requested_nesting_sites), '');
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    normalized_plant_species JSONB;
    input_digest BYTEA;
    existing_receipt RECORD;
    habitat_uuid UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Pollinator habitat capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'pollinator_health', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Pollinator habitat capture requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF normalized_name IS NULL OR pg_catalog.char_length(normalized_name) > 200
       OR requested_habitat_name ~ '[[:cntrl:]]'
       OR requested_habitat_type IS NULL OR requested_habitat_type NOT IN (
           'wildflower_strip', 'hedgerow', 'nesting_site', 'water_source',
           'cover_crop', 'native_planting', 'other'
       )
       OR requested_area_m2 IS NULL OR requested_area_m2 < 0 OR requested_area_m2 > 99999999
       OR requested_plant_species IS NULL
       OR pg_catalog.jsonb_typeof(requested_plant_species) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_plant_species) > 50
       OR pg_catalog.pg_column_size(requested_plant_species) > 8192
       OR requested_bloom_start_month IS NOT NULL
          AND requested_bloom_start_month NOT BETWEEN 1 AND 12
       OR requested_bloom_end_month IS NOT NULL
          AND requested_bloom_end_month NOT BETWEEN 1 AND 12
       OR requested_water_source IS NULL
       OR normalized_nesting_sites IS NOT NULL
          AND (pg_catalog.char_length(normalized_nesting_sites) > 1000
               OR requested_nesting_sites ~ '[[:cntrl:]]')
       OR normalized_notes IS NOT NULL
          AND (pg_catalog.char_length(normalized_notes) > 2000
               OR requested_notes ~ '[[:cntrl:]]')
       OR EXISTS (
            SELECT 1
              FROM pg_catalog.jsonb_array_elements(requested_plant_species) AS species(value)
             WHERE pg_catalog.jsonb_typeof(species.value) IS DISTINCT FROM 'string'
                OR pg_catalog.char_length(pg_catalog.btrim(species.value #>> '{}')) > 100
                OR species.value #>> '{}' ~ '[[:cntrl:]]'
       ) THEN
        RAISE EXCEPTION 'Pollinator habitat input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    SELECT coalesce(
        pg_catalog.jsonb_agg(pg_catalog.to_jsonb(pg_catalog.btrim(species.value #>> '{}'))),
        '[]'::JSONB
    ) INTO normalized_plant_species
      FROM pg_catalog.jsonb_array_elements(requested_plant_species) AS species(value)
     WHERE pg_catalog.btrim(species.value #>> '{}') <> '';
    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT,
                normalized_name,
                requested_habitat_type,
                requested_area_m2,
                normalized_plant_species,
                requested_bloom_start_month,
                requested_bloom_end_month,
                requested_water_source,
                normalized_nesting_sites,
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
    SELECT receipt.location_id, receipt.habitat_id, receipt.input_digest
      INTO existing_receipt
      FROM public.pollinator_habitat_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest
           OR existing_receipt.location_id IS DISTINCT FROM requested_location_id THEN
            RAISE EXCEPTION 'Pollinator habitat request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'habitat_id', existing_receipt.habitat_id,
            'location_id', requested_location_id,
            'habitat_type', requested_habitat_type,
            'area_m2', requested_area_m2,
            'status', 'active',
            'replayed', TRUE
        );
    END IF;

    habitat_uuid := pg_catalog.gen_random_uuid();
    INSERT INTO public.pollinator_habitat (
        id, location_id, habitat_name, habitat_type, area_m2, plant_species,
        bloom_start_month, bloom_end_month, water_source, nesting_sites,
        notes, status, created_by_operator_id
    ) VALUES (
        habitat_uuid, requested_location_id, normalized_name, requested_habitat_type,
        requested_area_m2, normalized_plant_species, requested_bloom_start_month,
        requested_bloom_end_month, requested_water_source, normalized_nesting_sites,
        normalized_notes, 'active', context_record.actor_id
    );
    INSERT INTO public.pollinator_habitat_capture_receipt (
        operator_id, request_id, location_id, habitat_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        habitat_uuid, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'habitat_id', habitat_uuid,
        'location_id', requested_location_id,
        'habitat_type', requested_habitat_type,
        'area_m2', requested_area_m2,
        'status', 'active',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_pollinator_habitat(
    UUID, UUID, TEXT, TEXT, NUMERIC, JSONB, SMALLINT, SMALLINT, BOOLEAN, TEXT, TEXT
) OWNER TO kokonut_pollinator_habitat_writer;
REVOKE ALL ON FUNCTION kokonut_security.create_location_pollinator_habitat(
    UUID, UUID, TEXT, TEXT, NUMERIC, JSONB, SMALLINT, SMALLINT, BOOLEAN, TEXT, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.create_location_pollinator_habitat('
            'UUID, UUID, TEXT, TEXT, NUMERIC, JSONB, SMALLINT, SMALLINT, BOOLEAN, TEXT, TEXT'
            ') TO kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.create_location_pollinator_habitat('
            'UUID, UUID, TEXT, TEXT, NUMERIC, JSONB, SMALLINT, SMALLINT, BOOLEAN, TEXT, TEXT'
            ') FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_pollinator_habitat(
    UUID, UUID, TEXT, TEXT, NUMERIC, JSONB, SMALLINT, SMALLINT, BOOLEAN, TEXT, TEXT
) IS 'Creates a self-reported location habitat inventory under signed exact-location create authorization; active is its domain inventory status and does not indicate ecological verification.';

COMMIT;
