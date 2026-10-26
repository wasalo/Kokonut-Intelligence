-- Move managed-hive creation behind signed, location-scoped Gateway authorization.
-- Active is the legacy operational inventory state; it is not health verification.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_pollinator_hive_writer'
    ) THEN
        CREATE ROLE kokonut_pollinator_hive_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_pollinator_hive_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

ALTER TABLE public.hive_record
    ADD COLUMN IF NOT EXISTS created_by_operator_id UUID
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_hive_record_creator
    ON public.hive_record (created_by_operator_id, created_at DESC)
    WHERE created_by_operator_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.pollinator_hive_capture_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    hive_record_id UUID NOT NULL UNIQUE
        REFERENCES public.hive_record(id) ON DELETE RESTRICT,
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
                'REVOKE INSERT ON TABLE public.hive_record FROM %s', role_sql
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.hive_record'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I) ON TABLE public.hive_record FROM %2$s',
                    column_name, role_sql
                );
            END LOOP;
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.pollinator_hive_capture_receipt FROM %s',
                role_sql
            );
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_pollinator_hive_writer;
GRANT SELECT (id, location_id, hive_id)
    ON TABLE public.hive_record TO kokonut_pollinator_hive_writer;
GRANT INSERT (
    id, location_id, hive_id, hive_type, colony_strength, colony_strength_score,
    queen_status, frame_count, queen_year, notes, status, created_by_operator_id
) ON TABLE public.hive_record TO kokonut_pollinator_hive_writer;
GRANT SELECT (
    operator_id, request_id, location_id, hive_record_id, input_digest, created_at
) ON TABLE public.pollinator_hive_capture_receipt TO kokonut_pollinator_hive_writer;
GRANT INSERT (
    operator_id, request_id, location_id, hive_record_id, input_digest
) ON TABLE public.pollinator_hive_capture_receipt TO kokonut_pollinator_hive_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_pollinator_hive_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_pollinator_hive_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_pollinator_hive_writer;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_pollinator_hive(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_hive_id TEXT,
    requested_hive_type TEXT,
    requested_colony_strength TEXT,
    requested_colony_strength_score SMALLINT,
    requested_queen_status TEXT,
    requested_frame_count INTEGER,
    requested_queen_year SMALLINT,
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
    normalized_hive_type TEXT := NULLIF(pg_catalog.btrim(requested_hive_type), '');
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    input_digest BYTEA;
    existing_receipt RECORD;
    hive_uuid UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Pollinator hive capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'pollinator_health', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Pollinator hive capture requires an exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF normalized_hive_id IS NULL OR pg_catalog.char_length(normalized_hive_id) > 100
       OR requested_hive_id ~ '[[:cntrl:]]'
       OR normalized_hive_type IS NULL OR pg_catalog.char_length(normalized_hive_type) > 50
       OR requested_hive_type ~ '[[:cntrl:]]'
       OR (requested_colony_strength IS NULL) = (requested_colony_strength_score IS NULL)
       OR requested_colony_strength IS NOT NULL AND requested_colony_strength NOT IN (
           'strong', 'moderate', 'weak', 'dead'
       )
       OR requested_colony_strength_score IS NOT NULL
          AND requested_colony_strength_score NOT BETWEEN 0 AND 10
       OR requested_queen_status IS NULL OR requested_queen_status NOT IN (
           'present', 'absent', 'replaced', 'unknown'
       )
       OR requested_frame_count IS NULL OR requested_frame_count NOT BETWEEN 0 AND 500
       OR requested_queen_year IS NOT NULL
          AND requested_queen_year NOT BETWEEN 1800
              AND pg_catalog.date_part('year', CURRENT_DATE)::INTEGER
       OR normalized_notes IS NOT NULL
          AND (pg_catalog.char_length(normalized_notes) > 2000
               OR requested_notes ~ '[[:cntrl:]]') THEN
        RAISE EXCEPTION 'Pollinator hive input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT, normalized_hive_id, normalized_hive_type,
                requested_colony_strength, requested_colony_strength_score,
                requested_queen_status, requested_frame_count,
                requested_queen_year, normalized_notes
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
    SELECT receipt.location_id, receipt.hive_record_id, receipt.input_digest
      INTO existing_receipt
      FROM public.pollinator_hive_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest
           OR existing_receipt.location_id IS DISTINCT FROM requested_location_id THEN
            RAISE EXCEPTION 'Pollinator hive request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'hive_record_id', existing_receipt.hive_record_id,
            'location_id', requested_location_id,
            'hive_id', normalized_hive_id,
            'hive_type', normalized_hive_type,
            'colony_strength', requested_colony_strength,
            'colony_strength_score', requested_colony_strength_score,
            'queen_status', requested_queen_status,
            'frame_count', requested_frame_count,
            'status', 'active',
            'replayed', TRUE
        );
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            requested_location_id::TEXT || ':hive:' || pg_catalog.lower(normalized_hive_id), 0
        )
    );
    IF EXISTS (
        SELECT 1 FROM public.hive_record AS hive_row
         WHERE hive_row.location_id = requested_location_id
           AND pg_catalog.lower(hive_row.hive_id) = pg_catalog.lower(normalized_hive_id)
    ) THEN
        RAISE EXCEPTION 'Hive identifier already exists at this location'
            USING ERRCODE = '23505';
    END IF;

    hive_uuid := pg_catalog.gen_random_uuid();
    INSERT INTO public.hive_record (
        id, location_id, hive_id, hive_type, colony_strength,
        colony_strength_score, queen_status, frame_count, queen_year,
        notes, status, created_by_operator_id
    ) VALUES (
        hive_uuid, requested_location_id, normalized_hive_id, normalized_hive_type,
        requested_colony_strength, requested_colony_strength_score,
        requested_queen_status, requested_frame_count, requested_queen_year,
        normalized_notes, 'active', context_record.actor_id
    );
    INSERT INTO public.pollinator_hive_capture_receipt (
        operator_id, request_id, location_id, hive_record_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        hive_uuid, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'hive_record_id', hive_uuid,
        'location_id', requested_location_id,
        'hive_id', normalized_hive_id,
        'hive_type', normalized_hive_type,
        'colony_strength', requested_colony_strength,
        'colony_strength_score', requested_colony_strength_score,
        'queen_status', requested_queen_status,
        'frame_count', requested_frame_count,
        'status', 'active',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_pollinator_hive(
    UUID, UUID, TEXT, TEXT, TEXT, SMALLINT, TEXT, INTEGER, SMALLINT, TEXT
) OWNER TO kokonut_pollinator_hive_writer;
REVOKE ALL ON FUNCTION kokonut_security.create_location_pollinator_hive(
    UUID, UUID, TEXT, TEXT, TEXT, SMALLINT, TEXT, INTEGER, SMALLINT, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT EXECUTE ON FUNCTION kokonut_security.create_location_pollinator_hive('
            'UUID, UUID, TEXT, TEXT, TEXT, SMALLINT, TEXT, INTEGER, SMALLINT, TEXT'
            ') TO kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON FUNCTION kokonut_security.create_location_pollinator_hive('
            'UUID, UUID, TEXT, TEXT, TEXT, SMALLINT, TEXT, INTEGER, SMALLINT, TEXT'
            ') FROM kokonut_directus_runtime';
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_pollinator_hive(
    UUID, UUID, TEXT, TEXT, TEXT, SMALLINT, TEXT, INTEGER, SMALLINT, TEXT
) IS 'Creates a location-scoped managed-hive inventory entry under signed exact-location create authorization; active is operational inventory state and does not mean the hive health was verified.';

COMMIT;
