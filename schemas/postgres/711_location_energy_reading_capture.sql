-- Move energy readings to a signed exact-location Gateway operation. Keep the
-- stored lifecycle at its source-defined initial state and preserve the
-- existing Directus and maintenance paths.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_energy_reading_writer'
    ) THEN
        CREATE ROLE kokonut_energy_reading_writer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_energy_reading_writer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Energy reading function owner has unsafe role attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_energy_reading_writer'
            OR member_role.rolname = 'kokonut_energy_reading_writer'
    ) THEN
        RAISE EXCEPTION 'Energy reading function owner must not have role memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.energy_reading_capture_receipt (
    operator_id UUID NOT NULL,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    reading_id UUID NOT NULL,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    response JSONB NOT NULL CHECK (pg_catalog.jsonb_typeof(response) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS public.energy_reading_operator_audit (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    operator_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    reading_id UUID NOT NULL,
    action TEXT NOT NULL CHECK (action = 'recorded'),
    reason TEXT NOT NULL CHECK (
        reason = pg_catalog.btrim(reason)
        AND pg_catalog.char_length(reason) BETWEEN 1 AND 2000
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_energy_reading_operator_audit_location_time
    ON public.energy_reading_operator_audit (location_id, created_at DESC, id DESC);

REVOKE ALL ON TABLE public.energy_reading_capture_receipt,
    public.energy_reading_operator_audit FROM PUBLIC;
REVOKE ALL ON TABLE public.energy_reading_capture_receipt,
    public.energy_reading_operator_audit FROM kokonut_runtime, kokonut_directus_runtime;

INSERT INTO kokonut_security.directus_relation_privilege_policy
    (schema_name, relation_name, access_mode, source_migration)
VALUES
    ('public', 'energy_reading_capture_receipt', 'no_access', '711_location_energy_reading_capture.sql'),
    ('public', 'energy_reading_operator_audit', 'no_access', '711_location_energy_reading_capture.sql')
ON CONFLICT (schema_name, relation_name) DO UPDATE
    SET access_mode = EXCLUDED.access_mode,
        source_migration = EXCLUDED.source_migration;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_energy_reading_writer;
GRANT SELECT (id, location_id) ON TABLE public.energy_source
    TO kokonut_energy_reading_writer;
-- PostgreSQL needs UPDATE on a key column for FOR KEY SHARE source locking.
GRANT UPDATE (id) ON TABLE public.energy_source
    TO kokonut_energy_reading_writer;
GRANT INSERT (
    id, location_id, source_id, reading_date, reading_type, kwh,
    cost_per_kwh, total_cost, cost_currency_code, activity_type,
    equipment_id, notes, metadata, status
) ON TABLE public.energy_reading TO kokonut_energy_reading_writer;
GRANT SELECT (id, created_at) ON TABLE public.energy_reading
    TO kokonut_energy_reading_writer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_energy_reading_writer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_energy_reading_writer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_energy_reading_writer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_energy_reading_writer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_energy_reading_writer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_energy_reading_writer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_energy_reading_writer;
GRANT SELECT, INSERT ON TABLE public.energy_reading_capture_receipt,
    public.energy_reading_operator_audit TO kokonut_energy_reading_writer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_energy_reading_writer;

-- Migration 388's SECURITY INVOKER grant checker used unqualified relation
-- names without a pinned search path. A SECURITY DEFINER caller that pins its
-- path to pg_catalog must not broaden it to public just to invoke that helper.
-- Preserve its tenant checks with explicit relation qualification and a safe
-- catalog-only search path.
CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows(
    requested_operator_id UUID,
    requested_resource TEXT,
    requested_action TEXT,
    requested_location_id UUID
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY INVOKER
SET search_path = pg_catalog
AS $$
    SELECT EXISTS (
        SELECT 1
          FROM public.operator_scope_grant AS grant_row
          JOIN public.operator_identity AS identity
            ON identity.id = grant_row.operator_id AND identity.enabled
          JOIN public.location AS loc ON loc.id = grant_row.location_id
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location_id
           AND grant_row.revoked_at IS NULL
           AND (
               grant_row.organization_id IS NULL
               OR (
                   grant_row.organization_id IS NOT NULL
                   AND EXISTS (
                       SELECT 1
                         FROM public.operator_organization_membership AS membership
                         JOIN public.organization AS tenant
                           ON tenant.id = membership.organization_id
                          AND tenant.status = 'active'
                        WHERE membership.operator_id = grant_row.operator_id
                          AND membership.organization_id = grant_row.organization_id
                          AND membership.revoked_at IS NULL
                   )
                   AND EXISTS (
                       SELECT 1
                         FROM public.location_tenant_owner_verification AS owner
                        WHERE owner.location_id = loc.id
                          AND owner.organization_id = loc.organization_id
                          AND owner.revoked_at IS NULL
                          AND (
                              owner.organization_id = grant_row.organization_id
                              OR EXISTS (
                                  SELECT 1
                                    FROM public.location_organization_share AS share
                                   WHERE share.location_id = loc.id
                                     AND share.organization_id = grant_row.organization_id
                                     AND share.revoked_at IS NULL
                                     AND (share.expires_at IS NULL OR share.expires_at > pg_catalog.now())
                              )
                          )
                   )
               )
           )
    );
$$;

GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_energy_reading_writer;

CREATE OR REPLACE FUNCTION kokonut_security.record_location_energy_reading(
    requested_location_id UUID,
    requested_source_id UUID,
    requested_request_id UUID,
    requested_reading_date DATE,
    requested_reading_type TEXT,
    requested_kwh NUMERIC,
    requested_cost_per_kwh NUMERIC,
    requested_cost_currency_code TEXT,
    requested_activity_type TEXT,
    requested_equipment_id UUID,
    requested_notes TEXT,
    requested_metadata JSONB,
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
    prior_receipt public.energy_reading_capture_receipt%ROWTYPE;
    source_location_id UUID;
    reading_uuid UUID;
    reading_created_at TIMESTAMPTZ;
    normalized_kwh NUMERIC(10,2);
    normalized_cost NUMERIC(8,4);
    normalized_currency TEXT;
    computed_total_cost NUMERIC(10,2);
    input_digest BYTEA;
    response_payload JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_source_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Energy capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'energy_monitoring', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Energy capture requires an active exact-location create grant'
            USING ERRCODE = '42501';
    END IF;

    IF requested_reading_date IS NULL
       OR requested_reading_type NOT IN ('consumption', 'production')
       OR requested_kwh IS NULL
       OR pg_catalog.abs(requested_kwh) > 99999999.99
       OR requested_cost_per_kwh IS NOT NULL
          AND pg_catalog.abs(requested_cost_per_kwh) > 9999.9999
       OR (requested_cost_per_kwh IS NULL) <> (requested_cost_currency_code IS NULL)
       OR requested_cost_currency_code IS NOT NULL
          AND requested_cost_currency_code !~ '^[A-Z]{3}$'
       OR requested_activity_type IS NOT NULL
          AND requested_activity_type NOT IN (
              'irrigation', 'processing', 'storage', 'lighting', 'pump', 'other'
          )
       OR requested_notes IS NOT NULL
          AND pg_catalog.char_length(requested_notes) > 2000
       OR requested_metadata IS NULL
       OR pg_catalog.jsonb_typeof(requested_metadata) IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length(
            pg_catalog.convert_to(requested_metadata::TEXT, 'UTF8')
          ) > 16384
       OR requested_reason IS NULL
       OR requested_reason <> pg_catalog.btrim(requested_reason)
       OR pg_catalog.char_length(requested_reason) NOT BETWEEN 1 AND 2000 THEN
        RAISE EXCEPTION 'Energy reading input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    normalized_kwh := requested_kwh::NUMERIC(10,2);
    normalized_cost := requested_cost_per_kwh::NUMERIC(8,4);
    normalized_currency := requested_cost_currency_code;
    IF normalized_cost IS NOT NULL THEN
        computed_total_cost := pg_catalog.round(normalized_kwh * normalized_cost, 2);
        IF pg_catalog.abs(computed_total_cost) > 99999999.99 THEN
            RAISE EXCEPTION 'Energy reading cost is outside its supported bounds'
                USING ERRCODE = '22003';
        END IF;
    END IF;

    input_digest := pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'source_id', requested_source_id,
            'reading_date', requested_reading_date,
            'reading_type', requested_reading_type,
            'kwh', normalized_kwh,
            'cost_per_kwh', normalized_cost,
            'cost_currency_code', normalized_currency,
            'activity_type', requested_activity_type,
            'equipment_id', requested_equipment_id,
            'notes', requested_notes,
            'metadata', requested_metadata,
            'reason', requested_reason
        )::TEXT,
        'UTF8'
    ));

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.*
      INTO prior_receipt
      FROM public.energy_reading_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Energy request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN prior_receipt.response || pg_catalog.jsonb_build_object('replayed', TRUE);
    END IF;

    SELECT source.location_id
      INTO source_location_id
      FROM public.energy_source AS source
     WHERE source.id = requested_source_id
     FOR KEY SHARE;
    IF source_location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'Energy source is unavailable at this location'
            USING ERRCODE = '42501';
    END IF;

    reading_uuid := pg_catalog.gen_random_uuid();
    INSERT INTO public.energy_reading (
        id, location_id, source_id, reading_date, reading_type, kwh,
        cost_per_kwh, total_cost, cost_currency_code, activity_type,
        equipment_id, notes, metadata, status
    ) VALUES (
        reading_uuid, requested_location_id, requested_source_id,
        requested_reading_date, requested_reading_type, normalized_kwh,
        normalized_cost, computed_total_cost, normalized_currency,
        requested_activity_type, requested_equipment_id, requested_notes,
        requested_metadata, 'recorded'
    ) RETURNING created_at INTO reading_created_at;

    response_payload := pg_catalog.jsonb_build_object(
        'request_id', requested_request_id,
        'reading_id', reading_uuid,
        'location_id', requested_location_id,
        'source_id', requested_source_id,
        'reading_date', requested_reading_date,
        'reading_type', requested_reading_type,
        'kwh', normalized_kwh,
        'cost_per_kwh', normalized_cost,
        'total_cost', computed_total_cost,
        'cost_currency_code', normalized_currency,
        'activity_type', requested_activity_type,
        'status', 'recorded',
        'replayed', FALSE,
        'created_at', reading_created_at
    );
    INSERT INTO public.energy_reading_capture_receipt (
        operator_id, request_id, location_id, reading_id, input_digest, response
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        reading_uuid, input_digest, response_payload
    );
    INSERT INTO public.energy_reading_operator_audit (
        operator_id, location_id, request_id, reading_id, action, reason
    ) VALUES (
        context_record.actor_id, requested_location_id, requested_request_id,
        reading_uuid, 'recorded', requested_reason
    );

    RETURN response_payload;
END;
$$;

ALTER FUNCTION kokonut_security.record_location_energy_reading(
    UUID, UUID, UUID, DATE, TEXT, NUMERIC, NUMERIC, TEXT, TEXT, UUID, TEXT, JSONB, TEXT
) OWNER TO kokonut_energy_reading_writer;
REVOKE ALL ON FUNCTION kokonut_security.record_location_energy_reading(
    UUID, UUID, UUID, DATE, TEXT, NUMERIC, NUMERIC, TEXT, TEXT, UUID, TEXT, JSONB, TEXT
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.record_location_energy_reading(
            UUID, UUID, UUID, DATE, TEXT, NUMERIC, NUMERIC, TEXT, TEXT, UUID, TEXT, JSONB, TEXT
        ) TO kokonut_runtime;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
            ON TABLE public.energy_reading FROM kokonut_runtime;
        REVOKE INSERT (id, location_id, source_id, reading_date, reading_type, kwh,
            cost_per_kwh, total_cost, cost_currency_code, activity_type, equipment_id,
            notes, metadata, status),
            UPDATE (id, location_id, source_id, reading_date, reading_type, kwh,
            cost_per_kwh, total_cost, cost_currency_code, activity_type, equipment_id,
            notes, metadata, status), REFERENCES (id, location_id, source_id,
            reading_date, reading_type, kwh, cost_per_kwh, total_cost,
            cost_currency_code, activity_type, equipment_id, notes, metadata, status)
            ON TABLE public.energy_reading FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.record_location_energy_reading(
            UUID, UUID, UUID, DATE, TEXT, NUMERIC, NUMERIC, TEXT, TEXT, UUID, TEXT, JSONB, TEXT
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMIT;
