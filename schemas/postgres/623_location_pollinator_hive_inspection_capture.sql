-- Move hive inspection capture and its inventory snapshot update behind a
-- signed, location-scoped Gateway function with an append-only private receipt.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_pollinator_inspection_writer'
    ) THEN
        CREATE ROLE kokonut_pollinator_inspection_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_pollinator_inspection_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

ALTER TABLE public.pollinator_hive_inspection
    ADD COLUMN IF NOT EXISTS created_by_operator_id UUID
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_pollinator_hive_inspection_creator
    ON public.pollinator_hive_inspection (created_by_operator_id, created_at DESC)
    WHERE created_by_operator_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.pollinator_hive_inspection_capture_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    hive_record_id UUID NOT NULL
        REFERENCES public.hive_record(id) ON DELETE RESTRICT,
    inspection_id UUID NOT NULL UNIQUE
        REFERENCES public.pollinator_hive_inspection(id) ON DELETE RESTRICT,
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
                'ON TABLE public.pollinator_hive_inspection FROM %s', role_sql
            );
            EXECUTE pg_catalog.format(
                'REVOKE UPDATE ON TABLE public.hive_record FROM %s', role_sql
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.pollinator_hive_inspection'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I) ON TABLE public.pollinator_hive_inspection FROM %2$s',
                    column_name, role_sql
                );
                EXECUTE pg_catalog.format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.pollinator_hive_inspection FROM %2$s',
                    column_name, role_sql
                );
                EXECUTE pg_catalog.format(
                    'REVOKE REFERENCES (%1$I) ON TABLE public.pollinator_hive_inspection FROM %2$s',
                    column_name, role_sql
                );
            END LOOP;
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.hive_record'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.hive_record FROM %2$s',
                    column_name, role_sql
                );
            END LOOP;
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.pollinator_hive_inspection_capture_receipt FROM %s',
                role_sql
            );
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_pollinator_inspection_writer;
GRANT SELECT (id, location_id, hive_id, status)
    ON TABLE public.hive_record TO kokonut_pollinator_inspection_writer;
GRANT SELECT (
    colony_strength, colony_strength_score, queen_status, varroa_count,
    inspection_date, updated_at
) ON TABLE public.hive_record TO kokonut_pollinator_inspection_writer;
GRANT UPDATE (
    colony_strength, colony_strength_score, queen_status, varroa_count,
    inspection_date, updated_at
) ON TABLE public.hive_record TO kokonut_pollinator_inspection_writer;
GRANT INSERT (
    id, location_id, hive_record_id, inspection_date, colony_strength,
    colony_strength_score, queen_status, queen_seen, varroa_count,
    brood_pattern, honey_stores, disease_signs, temperament,
    population_estimate, swarm_cells, notes, status, created_by_operator_id
) ON TABLE public.pollinator_hive_inspection
    TO kokonut_pollinator_inspection_writer;
GRANT SELECT (id) ON TABLE public.pollinator_hive_inspection
    TO kokonut_pollinator_inspection_writer;
GRANT SELECT (
    operator_id, request_id, location_id, hive_record_id, inspection_id,
    input_digest, created_at
) ON TABLE public.pollinator_hive_inspection_capture_receipt
    TO kokonut_pollinator_inspection_writer;
GRANT INSERT (
    operator_id, request_id, location_id, hive_record_id, inspection_id, input_digest
) ON TABLE public.pollinator_hive_inspection_capture_receipt
    TO kokonut_pollinator_inspection_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_pollinator_inspection_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_pollinator_inspection_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_pollinator_inspection_writer;

CREATE OR REPLACE FUNCTION kokonut_security.record_location_pollinator_hive_inspection(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_hive_id TEXT,
    requested_inspection_date DATE,
    requested_colony_strength TEXT,
    requested_colony_strength_score SMALLINT,
    requested_queen_status TEXT,
    requested_queen_seen BOOLEAN,
    requested_varroa_count INTEGER,
    requested_brood_pattern TEXT,
    requested_honey_stores TEXT,
    requested_disease_signs TEXT,
    requested_temperament TEXT,
    requested_population_estimate INTEGER,
    requested_swarm_cells BOOLEAN,
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
    normalized_hive_id TEXT := NULLIF(pg_catalog.btrim(requested_hive_id), '');
    normalized_brood_pattern TEXT := NULLIF(pg_catalog.btrim(requested_brood_pattern), '');
    normalized_honey_stores TEXT := NULLIF(pg_catalog.btrim(requested_honey_stores), '');
    normalized_disease_signs TEXT := NULLIF(pg_catalog.btrim(requested_disease_signs), '');
    normalized_temperament TEXT := NULLIF(pg_catalog.btrim(requested_temperament), '');
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    effective_date DATE := coalesce(requested_inspection_date, CURRENT_DATE);
    input_digest BYTEA;
    existing_receipt RECORD;
    hive_uuid UUID;
    inspection_uuid UUID;
    matching_hives INTEGER;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Hive inspection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'pollinator_health', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Hive inspection requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF normalized_hive_id IS NULL OR pg_catalog.char_length(normalized_hive_id) > 100
       OR requested_hive_id ~ '[[:cntrl:]]'
       OR requested_inspection_date > CURRENT_DATE
       OR (requested_colony_strength IS NULL) = (requested_colony_strength_score IS NULL)
          AND requested_colony_strength IS NOT NULL
       OR requested_colony_strength IS NOT NULL AND requested_colony_strength NOT IN (
           'strong', 'moderate', 'weak', 'dead'
       )
       OR requested_colony_strength_score IS NOT NULL
          AND requested_colony_strength_score NOT BETWEEN 0 AND 10
       OR requested_queen_status IS NOT NULL AND requested_queen_status NOT IN (
           'present', 'absent', 'replaced', 'unknown'
       )
       OR requested_queen_seen IS NOT NULL
          AND pg_catalog.jsonb_typeof(pg_catalog.to_jsonb(requested_queen_seen)) IS DISTINCT FROM 'boolean'
       OR requested_varroa_count IS NOT NULL
          AND requested_varroa_count NOT BETWEEN 0 AND 100000
       OR requested_brood_pattern IS NOT NULL
          AND (pg_catalog.char_length(normalized_brood_pattern) > 100
               OR requested_brood_pattern ~ '[[:cntrl:]]')
       OR requested_honey_stores IS NOT NULL
          AND (pg_catalog.char_length(normalized_honey_stores) > 500
               OR requested_honey_stores ~ '[[:cntrl:]]')
       OR requested_disease_signs IS NOT NULL
          AND (pg_catalog.char_length(normalized_disease_signs) > 2000
               OR requested_disease_signs ~ '[[:cntrl:]]')
       OR requested_temperament IS NOT NULL
          AND (pg_catalog.char_length(normalized_temperament) > 100
               OR requested_temperament ~ '[[:cntrl:]]')
       OR requested_population_estimate IS NOT NULL
          AND requested_population_estimate NOT BETWEEN 0 AND 100000000
       OR requested_swarm_cells IS NULL
       OR requested_notes IS NOT NULL
          AND (pg_catalog.char_length(normalized_notes) > 2000
               OR requested_notes ~ '[[:cntrl:]]')
       OR requested_colony_strength IS NULL
          AND requested_colony_strength_score IS NULL
          AND requested_queen_status IS NULL
          AND requested_queen_seen IS NULL
          AND requested_varroa_count IS NULL
          AND normalized_brood_pattern IS NULL
          AND normalized_honey_stores IS NULL
          AND normalized_disease_signs IS NULL
          AND normalized_temperament IS NULL
          AND requested_population_estimate IS NULL
          AND NOT requested_swarm_cells
          AND normalized_notes IS NULL THEN
        RAISE EXCEPTION 'Hive inspection input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT, pg_catalog.lower(normalized_hive_id),
                requested_inspection_date, requested_colony_strength,
                requested_colony_strength_score, requested_queen_status,
                requested_queen_seen, requested_varroa_count, normalized_brood_pattern,
                normalized_honey_stores, normalized_disease_signs, normalized_temperament,
                requested_population_estimate, requested_swarm_cells, normalized_notes
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
    SELECT receipt.location_id, receipt.hive_record_id, receipt.inspection_id,
           receipt.input_digest
      INTO existing_receipt
      FROM public.pollinator_hive_inspection_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest
           OR existing_receipt.location_id IS DISTINCT FROM requested_location_id THEN
            RAISE EXCEPTION 'Hive inspection request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'inspection_id', existing_receipt.inspection_id,
            'location_id', requested_location_id,
            'status', 'recorded',
            'replayed', TRUE
        );
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            requested_location_id::TEXT || ':hive:' || pg_catalog.lower(normalized_hive_id), 0
        )
    );
    SELECT pg_catalog.count(*)::INTEGER
      INTO matching_hives
      FROM public.hive_record AS hive_row
     WHERE hive_row.location_id = requested_location_id
       AND pg_catalog.lower(hive_row.hive_id) = pg_catalog.lower(normalized_hive_id)
       AND hive_row.status = 'active';
    IF matching_hives <> 1 THEN
        RAISE EXCEPTION 'Hive identifier is missing, inactive, or ambiguous at this location'
            USING ERRCODE = '22023';
    END IF;
    SELECT hive_row.id INTO hive_uuid
      FROM public.hive_record AS hive_row
     WHERE hive_row.location_id = requested_location_id
       AND pg_catalog.lower(hive_row.hive_id) = pg_catalog.lower(normalized_hive_id)
       AND hive_row.status = 'active'
     FOR UPDATE;

    INSERT INTO public.pollinator_hive_inspection (
        location_id, hive_record_id, inspection_date, colony_strength,
        colony_strength_score, queen_status, queen_seen, varroa_count,
        brood_pattern, honey_stores, disease_signs, temperament,
        population_estimate, swarm_cells, notes, status, created_by_operator_id
    ) VALUES (
        requested_location_id, hive_uuid, effective_date, requested_colony_strength,
        requested_colony_strength_score, requested_queen_status, requested_queen_seen,
        requested_varroa_count, normalized_brood_pattern, normalized_honey_stores,
        normalized_disease_signs, normalized_temperament, requested_population_estimate,
        requested_swarm_cells, normalized_notes, 'recorded', context_record.actor_id
    ) RETURNING id INTO inspection_uuid;

    UPDATE public.hive_record
       SET colony_strength = CASE
               WHEN requested_colony_strength IS NOT NULL THEN requested_colony_strength
               ELSE colony_strength
           END,
           colony_strength_score = CASE
               WHEN requested_colony_strength_score IS NOT NULL THEN requested_colony_strength_score
               ELSE colony_strength_score
           END,
           queen_status = coalesce(requested_queen_status, queen_status),
           varroa_count = coalesce(requested_varroa_count, varroa_count),
           inspection_date = effective_date,
           updated_at = pg_catalog.now()
     WHERE id = hive_uuid AND location_id = requested_location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Hive changed or left the granted location during inspection'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.pollinator_hive_inspection_capture_receipt (
        operator_id, request_id, location_id, hive_record_id, inspection_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        hive_uuid, inspection_uuid, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'inspection_id', inspection_uuid,
        'location_id', requested_location_id,
        'status', 'recorded',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.record_location_pollinator_hive_inspection(
    UUID, UUID, TEXT, DATE, TEXT, SMALLINT, TEXT, BOOLEAN, INTEGER,
    TEXT, TEXT, TEXT, TEXT, INTEGER, BOOLEAN, TEXT
) OWNER TO kokonut_pollinator_inspection_writer;
REVOKE ALL ON FUNCTION kokonut_security.record_location_pollinator_hive_inspection(
    UUID, UUID, TEXT, DATE, TEXT, SMALLINT, TEXT, BOOLEAN, INTEGER,
    TEXT, TEXT, TEXT, TEXT, INTEGER, BOOLEAN, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.record_location_pollinator_hive_inspection('
            'UUID, UUID, TEXT, DATE, TEXT, SMALLINT, TEXT, BOOLEAN, INTEGER, '
            'TEXT, TEXT, TEXT, TEXT, INTEGER, BOOLEAN, TEXT'
            ') TO kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.record_location_pollinator_hive_inspection('
            'UUID, UUID, TEXT, DATE, TEXT, SMALLINT, TEXT, BOOLEAN, INTEGER, '
            'TEXT, TEXT, TEXT, TEXT, INTEGER, BOOLEAN, TEXT'
            ') FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.record_location_pollinator_hive_inspection(
    UUID, UUID, TEXT, DATE, TEXT, SMALLINT, TEXT, BOOLEAN, INTEGER,
    TEXT, TEXT, TEXT, TEXT, INTEGER, BOOLEAN, TEXT
) IS 'Appends a recorded hive inspection and updates its location-bound snapshot atomically under a signed exact-location create grant; it does not verify the inspection.';

COMMIT;
