-- Move managed-hive operational status and maintenance changes behind a signed,
-- location-scoped Gateway function with an immutable operator-attributed ledger.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_pollinator_hive_lifecycle_writer'
    ) THEN
        CREATE ROLE kokonut_pollinator_hive_lifecycle_writer;
    END IF;
END;
$$;

ALTER ROLE kokonut_pollinator_hive_lifecycle_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

ALTER TABLE public.hive_record
    ADD COLUMN IF NOT EXISTS last_maintenance_date DATE,
    ADD COLUMN IF NOT EXISTS updated_by_operator_id UUID
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT;

CREATE TABLE IF NOT EXISTS public.pollinator_hive_lifecycle_event (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    hive_record_id UUID NOT NULL,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    reason TEXT NOT NULL CHECK (
        pg_catalog.char_length(reason) BETWEEN 1 AND 500
        AND reason !~ '[[:cntrl:]]'
    ),
    status_before TEXT NOT NULL CHECK (status_before IN ('active', 'inactive', 'decommissioned')),
    status_after TEXT NOT NULL CHECK (status_after IN ('active', 'inactive', 'decommissioned')),
    last_maintenance_before DATE,
    last_maintenance_after DATE,
    updated_at_after TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    CONSTRAINT uq_pollinator_hive_lifecycle_operator_request
        UNIQUE (operator_id, request_id),
    CONSTRAINT fk_pollinator_hive_lifecycle_location_hive
        FOREIGN KEY (location_id, hive_record_id)
        REFERENCES public.hive_record (location_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_pollinator_hive_lifecycle_location_time
    ON public.pollinator_hive_lifecycle_event (location_id, created_at DESC, id DESC);

DO $$
DECLARE
    column_name TEXT;
    role_name TEXT;
    role_sql TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF role_name = 'PUBLIC'
           OR EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            role_sql := CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC'
                             ELSE pg_catalog.quote_ident(role_name) END;
            EXECUTE pg_catalog.format(
                'REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER '
                'ON TABLE public.hive_record FROM %s', role_sql
            );
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.hive_record'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                    'ON TABLE public.hive_record FROM %2$s',
                    column_name, role_sql
                );
            END LOOP;
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.pollinator_hive_lifecycle_event FROM %s', role_sql
            );
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_pollinator_hive_lifecycle_writer;
GRANT SELECT (id, location_id, status, last_maintenance_date, updated_at)
    ON TABLE public.hive_record TO kokonut_pollinator_hive_lifecycle_writer;
GRANT UPDATE (status, last_maintenance_date, updated_at, updated_by_operator_id)
    ON TABLE public.hive_record TO kokonut_pollinator_hive_lifecycle_writer;
GRANT SELECT (
    id, operator_id, request_id, location_id, hive_record_id, input_digest, reason,
    status_before, status_after, last_maintenance_before, last_maintenance_after,
    updated_at_after, created_at
) ON TABLE public.pollinator_hive_lifecycle_event
    TO kokonut_pollinator_hive_lifecycle_writer;
GRANT INSERT (
    operator_id, request_id, location_id, hive_record_id, input_digest, reason,
    status_before, status_after, last_maintenance_before, last_maintenance_after,
    updated_at_after
) ON TABLE public.pollinator_hive_lifecycle_event
    TO kokonut_pollinator_hive_lifecycle_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_pollinator_hive_lifecycle_writer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_pollinator_hive_lifecycle_writer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_pollinator_hive_lifecycle_writer;

CREATE OR REPLACE FUNCTION kokonut_security.update_location_pollinator_hive(
    requested_location_id UUID,
    requested_hive_record_id UUID,
    requested_request_id UUID,
    expected_updated_at TIMESTAMPTZ,
    requested_status TEXT,
    status_supplied BOOLEAN,
    requested_last_maintenance DATE,
    maintenance_supplied BOOLEAN,
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
    normalized_reason TEXT := NULLIF(pg_catalog.btrim(requested_reason), '');
    input_digest BYTEA;
    existing_event RECORD;
    hive_row RECORD;
    changed_status TEXT;
    changed_maintenance DATE;
    changed_updated_at TIMESTAMPTZ;
    event_uuid UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_hive_record_id IS NULL
       OR requested_request_id IS NULL
       OR expected_updated_at IS NULL THEN
        RAISE EXCEPTION 'Hive lifecycle update requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'pollinator_health', 'edit', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Hive lifecycle update requires an exact location edit grant'
            USING ERRCODE = '42501';
    END IF;

    IF status_supplied IS NULL OR maintenance_supplied IS NULL
       OR NOT (status_supplied OR maintenance_supplied)
       OR status_supplied AND (
           requested_status IS NULL OR requested_status NOT IN ('active', 'inactive', 'decommissioned')
       )
       OR NOT status_supplied AND requested_status IS NOT NULL
       OR maintenance_supplied AND requested_last_maintenance > CURRENT_DATE
       OR NOT maintenance_supplied AND requested_last_maintenance IS NOT NULL
       OR normalized_reason IS NULL OR pg_catalog.char_length(normalized_reason) > 500
       OR requested_reason ~ '[[:cntrl:]]' THEN
        RAISE EXCEPTION 'Hive lifecycle update input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT, requested_hive_record_id::TEXT,
                expected_updated_at::TEXT, requested_status, status_supplied,
                requested_last_maintenance, maintenance_supplied, normalized_reason
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
    SELECT event.id, event.location_id, event.hive_record_id, event.input_digest,
           event.status_after, event.last_maintenance_after, event.updated_at_after
      INTO existing_event
      FROM public.pollinator_hive_lifecycle_event AS event
     WHERE event.operator_id = context_record.actor_id
       AND event.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_event.input_digest IS DISTINCT FROM input_digest
           OR existing_event.location_id IS DISTINCT FROM requested_location_id
           OR existing_event.hive_record_id IS DISTINCT FROM requested_hive_record_id THEN
            RAISE EXCEPTION 'Hive lifecycle request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'event_id', existing_event.id,
            'location_id', requested_location_id,
            'hive_record_id', requested_hive_record_id,
            'status', existing_event.status_after,
            'last_maintenance_date', existing_event.last_maintenance_after,
            'updated_at', existing_event.updated_at_after,
            'replayed', TRUE
        );
    END IF;

    SELECT hive.id, hive.location_id, hive.status, hive.last_maintenance_date, hive.updated_at
      INTO hive_row
      FROM public.hive_record AS hive
     WHERE hive.id = requested_hive_record_id
       AND hive.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Managed hive not found in this location' USING ERRCODE = 'P0002';
    END IF;
    IF hive_row.updated_at IS DISTINCT FROM expected_updated_at THEN
        RAISE EXCEPTION 'Managed hive changed since it was read' USING ERRCODE = '40001';
    END IF;

    changed_status := CASE WHEN status_supplied THEN requested_status ELSE hive_row.status END;
    changed_maintenance := CASE
        WHEN maintenance_supplied THEN requested_last_maintenance
        ELSE hive_row.last_maintenance_date
    END;
    IF changed_status IS NOT DISTINCT FROM hive_row.status
       AND changed_maintenance IS NOT DISTINCT FROM hive_row.last_maintenance_date THEN
        RAISE EXCEPTION 'Managed hive lifecycle update makes no change' USING ERRCODE = '22023';
    END IF;

    UPDATE public.hive_record AS hive
       SET status = changed_status,
           last_maintenance_date = changed_maintenance,
           updated_at = pg_catalog.clock_timestamp(),
           updated_by_operator_id = context_record.actor_id
     WHERE hive.id = requested_hive_record_id
       AND hive.location_id = requested_location_id
    RETURNING hive.updated_at INTO changed_updated_at;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Managed hive changed or left the granted location during update'
            USING ERRCODE = 'P0002';
    END IF;

    INSERT INTO public.pollinator_hive_lifecycle_event (
        operator_id, request_id, location_id, hive_record_id, input_digest, reason,
        status_before, status_after, last_maintenance_before,
        last_maintenance_after, updated_at_after
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_hive_record_id, input_digest, normalized_reason,
        hive_row.status, changed_status, hive_row.last_maintenance_date,
        changed_maintenance, changed_updated_at
    ) RETURNING id INTO event_uuid;

    RETURN pg_catalog.jsonb_build_object(
        'event_id', event_uuid,
        'location_id', requested_location_id,
        'hive_record_id', requested_hive_record_id,
        'status', changed_status,
        'last_maintenance_date', changed_maintenance,
        'updated_at', changed_updated_at,
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.update_location_pollinator_hive(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, BOOLEAN, DATE, BOOLEAN, TEXT
) OWNER TO kokonut_pollinator_hive_lifecycle_writer;
REVOKE ALL ON FUNCTION kokonut_security.update_location_pollinator_hive(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, BOOLEAN, DATE, BOOLEAN, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.update_location_pollinator_hive(
    UUID, UUID, UUID, TIMESTAMPTZ, TEXT, BOOLEAN, DATE, BOOLEAN, TEXT
) TO kokonut_runtime;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE EXECUTE ON FUNCTION kokonut_security.update_location_pollinator_hive(
            UUID, UUID, UUID, TIMESTAMPTZ, TEXT, BOOLEAN, DATE, BOOLEAN, TEXT
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMIT;
