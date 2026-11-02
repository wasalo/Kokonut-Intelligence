-- Provide the signed, location-bound metric API used by the Kernel Gateway.
-- Legacy CLI writers remain available until their separate retirement gate.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_metric_value_manager'
    ) THEN
        CREATE ROLE kokonut_metric_value_manager
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_metric_value_manager'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Metric function owner has unsafe role attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_metric_value_manager'
            OR member_role.rolname = 'kokonut_metric_value_manager'
    ) THEN
        RAISE EXCEPTION 'Metric function owner must not have role memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.metric_value_compute_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    metric_value_id UUID NOT NULL UNIQUE REFERENCES public.metric_value(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    response JSONB NOT NULL CHECK (pg_catalog.jsonb_typeof(response) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS public.metric_value_verification_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    metric_value_id UUID NOT NULL UNIQUE REFERENCES public.metric_value(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    response JSONB NOT NULL CHECK (pg_catalog.jsonb_typeof(response) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS public.metric_value_operator_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    metric_value_id UUID NOT NULL REFERENCES public.metric_value(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('draft_computed', 'verified')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_metric_value_operator_audit_location_time
    ON public.metric_value_operator_audit (location_id, created_at DESC, id DESC);

REVOKE ALL ON TABLE public.metric_value_compute_receipt,
    public.metric_value_verification_receipt,
    public.metric_value_operator_audit FROM PUBLIC;
REVOKE ALL ON TABLE public.metric_value_compute_receipt,
    public.metric_value_verification_receipt,
    public.metric_value_operator_audit FROM kokonut_runtime, kokonut_directus_runtime;

REVOKE ALL ON FUNCTION kokonut_security.current_tenant_context()
    FROM kokonut_metric_value_manager;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_metric_value_manager;
GRANT SELECT ON TABLE public.metric_definition, public.metric_value
    TO kokonut_metric_value_manager;
-- operator_scope_grant_allows is SECURITY INVOKER. Keep tenant authorization
-- reads explicit and column-limited for this isolated function owner.
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_metric_value_manager;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_metric_value_manager;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_metric_value_manager;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_metric_value_manager;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_metric_value_manager;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_metric_value_manager;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_metric_value_manager;
GRANT INSERT ON TABLE public.metric_value TO kokonut_metric_value_manager;
GRANT UPDATE (verified, verified_by, verified_at, verification_notes)
    ON TABLE public.metric_value TO kokonut_metric_value_manager;
GRANT SELECT, INSERT ON TABLE public.metric_value_compute_receipt,
    public.metric_value_verification_receipt,
    public.metric_value_operator_audit TO kokonut_metric_value_manager;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_metric_value_manager;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_metric_value_manager;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_metric_value_draft(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_metric_definition_id UUID,
    requested_metric_key TEXT,
    requested_period_start DATE,
    requested_period_end DATE,
    requested_value NUMERIC,
    requested_unit TEXT,
    requested_computation_method TEXT,
    requested_source_record_ids UUID[],
    requested_metadata JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    definition_record public.metric_definition%ROWTYPE;
    metric_record public.metric_value%ROWTYPE;
    prior_receipt public.metric_value_compute_receipt%ROWTYPE;
    payload_digest BYTEA;
    response_payload JSONB;
    source_ids UUID[];
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Metric draft requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'metric_value', 'compute', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Metric draft requires an active exact-location compute grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_metric_definition_id IS NULL
       OR requested_metric_key IS NULL
       OR requested_metric_key !~ '^[a-z][a-z0-9_]{0,99}$'
       OR requested_period_start IS NOT NULL AND requested_period_end IS NOT NULL
          AND requested_period_start > requested_period_end
       OR requested_value IS NOT NULL
          AND (requested_value < -99999999999.9999
               OR requested_value > 99999999999.9999
               OR pg_catalog.scale(requested_value) > 4)
       OR requested_unit IS NOT NULL AND pg_catalog.char_length(requested_unit) > 50
       OR requested_computation_method IS NULL
          OR requested_computation_method <> pg_catalog.btrim(requested_computation_method)
          OR pg_catalog.char_length(requested_computation_method) NOT BETWEEN 1 AND 100
       OR requested_source_record_ids IS NULL
       OR pg_catalog.cardinality(requested_source_record_ids) > 100000
       OR requested_metadata IS NULL
       OR pg_catalog.jsonb_typeof(requested_metadata) IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length(pg_catalog.convert_to(requested_metadata::TEXT, 'UTF8')) > 24576 THEN
        RAISE EXCEPTION 'Metric draft input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.unnest(requested_source_record_ids) AS source_id
         WHERE source_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Metric source references must not contain null values'
            USING ERRCODE = '22023';
    END IF;

    SELECT definition.* INTO definition_record
      FROM public.metric_definition AS definition
     WHERE definition.id = requested_metric_definition_id
       AND definition.metric_key = requested_metric_key
       AND definition.active IS TRUE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active metric definition is unavailable'
            USING ERRCODE = 'P0002';
    END IF;
    IF requested_unit IS DISTINCT FROM definition_record.unit THEN
        RAISE EXCEPTION 'Metric unit does not match the active definition'
            USING ERRCODE = '22023';
    END IF;

    source_ids := COALESCE(requested_source_record_ids, ARRAY[]::UUID[]);
    payload_digest := pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'metric_definition_id', requested_metric_definition_id,
            'metric_key', requested_metric_key,
            'period_start', requested_period_start,
            'period_end', requested_period_end,
            'value', requested_value::NUMERIC(15,4),
            'unit', requested_unit,
            'computation_method', requested_computation_method,
            'source_record_ids', source_ids,
            'metadata', requested_metadata
        )::TEXT,
        'UTF8'
    ));

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.* INTO prior_receipt
      FROM public.metric_value_compute_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.input_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Metric request ID was reused with different input'
                USING ERRCODE = 'P0001';
        END IF;
        RETURN prior_receipt.response || pg_catalog.jsonb_build_object('created', FALSE);
    END IF;

    INSERT INTO public.metric_value (
        metric_id, location_id, period_start, period_end, value, unit,
        computation_method, source_record_ids, verified, metadata
    ) VALUES (
        requested_metric_definition_id, requested_location_id,
        requested_period_start, requested_period_end, requested_value,
        requested_unit, requested_computation_method, source_ids, FALSE,
        requested_metadata
    ) RETURNING * INTO metric_record;

    response_payload := pg_catalog.jsonb_build_object(
        'metric_value_id', metric_record.id,
        'metric_key', definition_record.metric_key,
        'display_name', definition_record.display_name,
        'location_id', requested_location_id,
        'period_start', metric_record.period_start,
        'period_end', metric_record.period_end,
        'value', metric_record.value,
        'unit', metric_record.unit,
        'status', 'draft',
        'verified', FALSE,
        'request_id', requested_request_id,
        'created_at', metric_record.computed_at,
        'created', TRUE
    );
    INSERT INTO public.metric_value_compute_receipt (
        operator_id, request_id, location_id, metric_value_id, input_digest, response
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        metric_record.id, payload_digest, response_payload
    );
    INSERT INTO public.metric_value_operator_audit (
        operator_id, location_id, metric_value_id, request_id, action
    ) VALUES (
        context_record.actor_id, requested_location_id, metric_record.id,
        requested_request_id, 'draft_computed'
    );
    RETURN response_payload;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.verify_location_metric_value(
    requested_location_id UUID,
    requested_metric_value_id UUID,
    requested_request_id UUID,
    requested_verification_notes TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    metric_record public.metric_value%ROWTYPE;
    creator_operator_id UUID;
    prior_receipt public.metric_value_verification_receipt%ROWTYPE;
    payload_digest BYTEA;
    response_payload JSONB;
    verification_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_metric_value_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Metric verification requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'metric_value', 'verify', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Metric verification requires an active exact-location verify grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_verification_notes IS NOT NULL
       AND pg_catalog.char_length(pg_catalog.btrim(requested_verification_notes)) > 2000 THEN
        RAISE EXCEPTION 'Metric verification notes are invalid or too long'
            USING ERRCODE = '22023';
    END IF;
    requested_verification_notes := NULLIF(pg_catalog.btrim(requested_verification_notes), '');
    payload_digest := pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'metric_value_id', requested_metric_value_id,
            'verification_notes', requested_verification_notes
        )::TEXT,
        'UTF8'
    ));

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.* INTO prior_receipt
      FROM public.metric_value_verification_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.metric_value_id IS DISTINCT FROM requested_metric_value_id
           OR prior_receipt.input_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Metric verification request ID was reused with different input'
                USING ERRCODE = 'P0001';
        END IF;
        RETURN prior_receipt.response || pg_catalog.jsonb_build_object('replayed', TRUE);
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended('metric-value:' || requested_metric_value_id::TEXT, 0)
    );
    SELECT metric.* INTO metric_record
      FROM public.metric_value AS metric
     WHERE metric.id = requested_metric_value_id
       AND metric.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Metric value is unavailable in this location'
            USING ERRCODE = 'P0002';
    END IF;
    IF metric_record.verified THEN
        RAISE EXCEPTION 'Metric value has already completed review'
            USING ERRCODE = 'P0001';
    END IF;
    SELECT receipt.operator_id INTO creator_operator_id
      FROM public.metric_value_compute_receipt AS receipt
     WHERE receipt.metric_value_id = requested_metric_value_id
       AND receipt.location_id = requested_location_id;
    IF creator_operator_id IS NULL OR creator_operator_id = context_record.actor_id THEN
        RAISE EXCEPTION 'Metric value requires independent review by another operator'
            USING ERRCODE = 'P0001';
    END IF;

    verification_time := pg_catalog.clock_timestamp();
    UPDATE public.metric_value
       SET verified = TRUE,
           verified_by = context_record.actor_id,
           verified_at = verification_time,
           verification_notes = requested_verification_notes
     WHERE id = requested_metric_value_id
       AND location_id = requested_location_id
       AND verified IS FALSE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Metric value changed during review'
            USING ERRCODE = 'P0001';
    END IF;
    response_payload := pg_catalog.jsonb_build_object(
        'metric_value_id', requested_metric_value_id,
        'location_id', requested_location_id,
        'metric_key', (
            SELECT definition.metric_key
              FROM public.metric_definition AS definition
             WHERE definition.id = metric_record.metric_id
        ),
        'status', 'verified',
        'verified', TRUE,
        'verified_at', verification_time,
        'request_id', requested_request_id,
        'replayed', FALSE
    );
    INSERT INTO public.metric_value_verification_receipt (
        operator_id, request_id, location_id, metric_value_id, input_digest, response
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_metric_value_id, payload_digest, response_payload
    );
    INSERT INTO public.metric_value_operator_audit (
        operator_id, location_id, metric_value_id, request_id, action
    ) VALUES (
        context_record.actor_id, requested_location_id, requested_metric_value_id,
        requested_request_id, 'verified'
    );
    RETURN response_payload;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_metric_values(
    requested_location_id UUID,
    requested_cursor TEXT,
    requested_limit INTEGER
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    page_items JSONB;
    item_count INTEGER;
    has_more BOOLEAN;
    offset_value INTEGER;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Metric list requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'metric_value', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Metric list requires an active exact-location read grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_cursor IS NULL
       OR requested_cursor !~ '^(0|[1-9][0-9]*)$'
       OR pg_catalog.char_length(requested_cursor) > 5
       OR requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 100 THEN
        RAISE EXCEPTION 'Metric list parameters are invalid'
            USING ERRCODE = '22023';
    END IF;
    offset_value := requested_cursor::INTEGER;
    IF offset_value > 10000 THEN
        RAISE EXCEPTION 'Metric list cursor exceeds its bound'
            USING ERRCODE = '22023';
    END IF;

    WITH candidates AS (
        SELECT metric.id, definition.metric_key, definition.display_name,
               metric.period_start, metric.period_end, metric.value, metric.unit,
               metric.verified, metric.computed_at, metric.verified_at
          FROM public.metric_value AS metric
          JOIN public.metric_definition AS definition ON definition.id = metric.metric_id
         WHERE metric.location_id = requested_location_id
         ORDER BY metric.computed_at DESC, metric.id DESC
         OFFSET offset_value LIMIT requested_limit + 1
    ), page AS (
        SELECT * FROM candidates
         ORDER BY computed_at DESC, id DESC
         LIMIT requested_limit
    )
    SELECT pg_catalog.count(*)::INTEGER,
           COALESCE(
               pg_catalog.jsonb_agg(
                   pg_catalog.jsonb_build_object(
                       'metric_value_id', page.id,
                       'metric_key', page.metric_key,
                       'display_name', page.display_name,
                       'period_start', page.period_start,
                       'period_end', page.period_end,
                       'value', page.value,
                       'unit', page.unit,
                       'status', CASE WHEN page.verified THEN 'verified' ELSE 'draft' END,
                       'computed_at', page.computed_at,
                       'verified_at', page.verified_at
                   ) ORDER BY page.computed_at DESC, page.id DESC
               ), '[]'::JSONB
           )
      INTO item_count, page_items
      FROM page;
    SELECT pg_catalog.count(*) > requested_limit
      INTO has_more
      FROM (
          SELECT 1
            FROM public.metric_value AS metric
           WHERE metric.location_id = requested_location_id
           ORDER BY metric.computed_at DESC, metric.id DESC
           OFFSET offset_value LIMIT requested_limit + 1
      ) AS page_candidates;
    has_more := COALESCE(has_more, FALSE) AND offset_value + requested_limit <= 10000;
    RETURN pg_catalog.jsonb_build_object(
        'location_id', requested_location_id,
        'cursor', requested_cursor,
        'limit', requested_limit,
        'next_cursor', CASE WHEN has_more THEN (offset_value + requested_limit)::TEXT ELSE NULL END,
        'has_more', has_more,
        'items', page_items
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_metric_value_draft(
    UUID, UUID, UUID, TEXT, DATE, DATE, NUMERIC, TEXT, TEXT, UUID[], JSONB
) OWNER TO kokonut_metric_value_manager;
ALTER FUNCTION kokonut_security.verify_location_metric_value(UUID, UUID, UUID, TEXT)
    OWNER TO kokonut_metric_value_manager;
ALTER FUNCTION kokonut_security.list_location_metric_values(UUID, TEXT, INTEGER)
    OWNER TO kokonut_metric_value_manager;

REVOKE ALL ON FUNCTION kokonut_security.create_location_metric_value_draft(
    UUID, UUID, UUID, TEXT, DATE, DATE, NUMERIC, TEXT, TEXT, UUID[], JSONB
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.verify_location_metric_value(UUID, UUID, UUID, TEXT)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_metric_values(UUID, TEXT, INTEGER)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.create_location_metric_value_draft(
    UUID, UUID, UUID, TEXT, DATE, DATE, NUMERIC, TEXT, TEXT, UUID[], JSONB
) TO kokonut_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.verify_location_metric_value(UUID, UUID, UUID, TEXT)
    TO kokonut_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.list_location_metric_values(UUID, TEXT, INTEGER)
    TO kokonut_runtime;

DO $$
DECLARE function_name TEXT;
BEGIN
    FOR function_name IN
        SELECT procedure.oid::REGPROCEDURE::TEXT
          FROM pg_catalog.pg_proc AS procedure
          JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
         WHERE namespace.nspname = 'kokonut_security'
           AND procedure.proname IN (
               'create_location_metric_value_draft',
               'verify_location_metric_value',
               'list_location_metric_values'
           )
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE ALL ON FUNCTION %s FROM PUBLIC, kokonut_directus_runtime',
            function_name
        );
    END LOOP;
END;
$$;

COMMENT ON TABLE public.metric_value_compute_receipt IS
    'Private idempotency and creator attribution for signed location metric draft computation.';
COMMENT ON TABLE public.metric_value_verification_receipt IS
    'Private idempotency receipts for independent signed metric verification.';
COMMENT ON TABLE public.metric_value_operator_audit IS
    'Append-only audit of signed location metric draft creation and independent verification.';

COMMIT;
