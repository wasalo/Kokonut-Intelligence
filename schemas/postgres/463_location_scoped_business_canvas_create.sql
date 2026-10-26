-- Location-scoped Kernel creation for business model canvas drafts.
-- Draft creation is idempotent and never verifies, submits, or publishes.
-- Existing CLI/Directus canvas DML grants are not changed by this slice.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_business_canvas_creator'
    ) THEN
        CREATE ROLE kokonut_business_canvas_creator
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_business_canvas_creator'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Business canvas creator role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_business_canvas_creator'
            OR member_role.rolname = 'kokonut_business_canvas_creator'
    ) THEN
        RAISE EXCEPTION 'Business canvas creator role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.business_model_canvas_create_request (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    canvas_id UUID NOT NULL UNIQUE
        REFERENCES public.business_model_canvas(id) ON DELETE RESTRICT,
    request_digest TEXT NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

CREATE INDEX IF NOT EXISTS idx_business_canvas_create_request_location
    ON public.business_model_canvas_create_request(location_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.prevent_business_canvas_create_request_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'business canvas create request history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_business_canvas_create_request_immutable
    ON public.business_model_canvas_create_request;
CREATE TRIGGER trg_business_canvas_create_request_immutable
    BEFORE UPDATE OR DELETE ON public.business_model_canvas_create_request
    FOR EACH ROW EXECUTE FUNCTION public.prevent_business_canvas_create_request_mutation();

REVOKE ALL ON TABLE public.business_model_canvas_create_request FROM PUBLIC;
REVOKE ALL ON FUNCTION public.prevent_business_canvas_create_request_mutation() FROM PUBLIC;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_business_canvas_creator;
-- operator_scope_grant_allows is SECURITY INVOKER; grant only the columns it
-- needs to establish a live tenant-qualified location grant.
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_business_canvas_creator;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_business_canvas_creator;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_business_canvas_creator;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership TO kokonut_business_canvas_creator;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_business_canvas_creator;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification TO kokonut_business_canvas_creator;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share TO kokonut_business_canvas_creator;
GRANT SELECT (
    id, location_id, organization_id, entity_type, entity_id,
    key_partners, key_activities, key_resources, value_propositions,
    customer_relationships, channels, customer_segments, revenue_streams,
    cost_structure, canvas_name, description, fiscal_year, tags, status,
    version, created_at
) ON TABLE public.business_model_canvas TO kokonut_business_canvas_creator;
GRANT INSERT (
    id, location_id, organization_id, entity_type, entity_id,
    key_partners, key_activities, key_resources, value_propositions,
    customer_relationships, channels, customer_segments, revenue_streams,
    cost_structure, canvas_name, description, fiscal_year, tags, status,
    schema_version, source_system, source_id, created_by
) ON TABLE public.business_model_canvas TO kokonut_business_canvas_creator;
GRANT SELECT, INSERT ON TABLE public.business_model_canvas_create_request
    TO kokonut_business_canvas_creator;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_business_canvas_creator;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_business_canvas_creator;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_business_canvas_creator;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_business_canvas_creator;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_business_model_canvas(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_canvas_name TEXT,
    requested_description TEXT,
    requested_fiscal_year INTEGER,
    requested_tags TEXT[],
    requested_blocks JSONB
)
RETURNS TABLE (
    canvas_id UUID,
    status TEXT,
    version INTEGER,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    normalized_name TEXT;
    normalized_description TEXT;
    normalized_tags TEXT[];
    normalized_blocks JSONB;
    digest_value TEXT;
    prior_request public.business_model_canvas_create_request%ROWTYPE;
    result_canvas_id UUID;
    result_status TEXT;
    result_version INTEGER;
    result_created_at TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Business canvas creation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'business_planning', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Business canvas creation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;

    normalized_name := NULLIF(pg_catalog.btrim(requested_canvas_name), '');
    normalized_description := NULLIF(pg_catalog.btrim(requested_description), '');
    normalized_tags := COALESCE(requested_tags, ARRAY[]::TEXT[]);
    normalized_blocks := requested_blocks;
    IF requested_request_id IS NULL
       OR normalized_name IS NULL
       OR pg_catalog.char_length(normalized_name) > 255
       OR (requested_description IS NOT NULL AND pg_catalog.char_length(requested_description) > 5000)
       OR (requested_fiscal_year IS NOT NULL AND requested_fiscal_year NOT BETWEEN 1900 AND 2200)
       OR pg_catalog.cardinality(normalized_tags) > 30
       OR EXISTS (
            SELECT 1 FROM pg_catalog.unnest(normalized_tags) AS tag
             WHERE tag IS NULL OR NULLIF(pg_catalog.btrim(tag), '') IS NULL
                OR pg_catalog.char_length(tag) > 80
       )
       OR (SELECT pg_catalog.count(*) FROM pg_catalog.unnest(normalized_tags) AS tag)
          <> (SELECT pg_catalog.count(DISTINCT tag) FROM pg_catalog.unnest(normalized_tags) AS tag)
       OR normalized_blocks IS NULL
       OR pg_catalog.jsonb_typeof(normalized_blocks) IS DISTINCT FROM 'object'
       OR pg_catalog.pg_column_size(normalized_blocks) > 65536
       OR EXISTS (
            SELECT 1 FROM pg_catalog.jsonb_object_keys(normalized_blocks) AS block_key
             WHERE block_key <> ALL (ARRAY[
                 'key_partners', 'key_activities', 'key_resources', 'value_propositions',
                 'customer_relationships', 'channels', 'customer_segments',
                 'revenue_streams', 'cost_structure'
             ]::TEXT[])
       ) THEN
        RAISE EXCEPTION 'Business canvas draft arguments are invalid'
            USING ERRCODE = '22023';
    END IF;

    normalized_blocks := pg_catalog.jsonb_build_object(
        'key_partners', COALESCE(normalized_blocks -> 'key_partners', '[]'::JSONB),
        'key_activities', COALESCE(normalized_blocks -> 'key_activities', '[]'::JSONB),
        'key_resources', COALESCE(normalized_blocks -> 'key_resources', '[]'::JSONB),
        'value_propositions', COALESCE(normalized_blocks -> 'value_propositions', '[]'::JSONB),
        'customer_relationships', COALESCE(normalized_blocks -> 'customer_relationships', '[]'::JSONB),
        'channels', COALESCE(normalized_blocks -> 'channels', '[]'::JSONB),
        'customer_segments', COALESCE(normalized_blocks -> 'customer_segments', '[]'::JSONB),
        'revenue_streams', COALESCE(normalized_blocks -> 'revenue_streams', '[]'::JSONB),
        'cost_structure', COALESCE(normalized_blocks -> 'cost_structure', '{}'::JSONB)
    );
    IF pg_catalog.jsonb_typeof(normalized_blocks -> 'key_partners') IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(normalized_blocks -> 'key_activities') IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(normalized_blocks -> 'key_resources') IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(normalized_blocks -> 'value_propositions') IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(normalized_blocks -> 'customer_relationships') IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(normalized_blocks -> 'channels') IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(normalized_blocks -> 'customer_segments') IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(normalized_blocks -> 'revenue_streams') IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_typeof(normalized_blocks -> 'cost_structure') IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'Business canvas block values have invalid shapes'
            USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.pg_column_size(normalized_blocks) > 65536 THEN
        RAISE EXCEPTION 'Business canvas block values exceed the size limit'
            USING ERRCODE = '22023';
    END IF;

    digest_value := pg_catalog.encode(public.digest(
        pg_catalog.convert_to(pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'canvas_name', normalized_name,
            'description', normalized_description,
            'fiscal_year', requested_fiscal_year,
            'tags', normalized_tags,
            'blocks', normalized_blocks
        )::TEXT, 'UTF8'), 'sha256'), 'hex');
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0)
    );

    SELECT * INTO prior_request
      FROM public.business_model_canvas_create_request AS request_row
     WHERE request_row.operator_id = context_record.actor_id
       AND request_row.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_request.location_id IS DISTINCT FROM requested_location_id
           OR prior_request.request_digest IS DISTINCT FROM digest_value THEN
            RAISE EXCEPTION 'Business canvas request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        SELECT canvas.id, canvas.status::TEXT, canvas.version, canvas.created_at
          INTO result_canvas_id, result_status, result_version, result_created_at
          FROM public.business_model_canvas AS canvas
         WHERE canvas.id = prior_request.canvas_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Business canvas request refers to a missing canvas'
                USING ERRCODE = '55000';
        END IF;
        canvas_id := result_canvas_id;
        status := result_status;
        version := result_version;
        created_at := result_created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    INSERT INTO public.business_model_canvas (
        id, location_id, organization_id, entity_type, entity_id,
        key_partners, key_activities, key_resources, value_propositions,
        customer_relationships, channels, customer_segments, revenue_streams,
        cost_structure, canvas_name, description, fiscal_year, tags, status,
        schema_version, source_system, source_id, created_by
    ) VALUES (
        pg_catalog.gen_random_uuid(), requested_location_id, NULL, 'location', requested_location_id,
        normalized_blocks -> 'key_partners', normalized_blocks -> 'key_activities',
        normalized_blocks -> 'key_resources', normalized_blocks -> 'value_propositions',
        normalized_blocks -> 'customer_relationships', normalized_blocks -> 'channels',
        normalized_blocks -> 'customer_segments', normalized_blocks -> 'revenue_streams',
        normalized_blocks -> 'cost_structure', normalized_name, normalized_description,
        requested_fiscal_year, normalized_tags, 'draft', 'business-model-canvas-v1',
        'kokonut_gateway', requested_request_id::TEXT, context_record.actor_id
    )
    RETURNING id, business_model_canvas.status::TEXT,
              business_model_canvas.version, business_model_canvas.created_at
         INTO result_canvas_id, result_status, result_version, result_created_at;

    INSERT INTO public.business_model_canvas_create_request (
        operator_id, request_id, location_id, canvas_id, request_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        result_canvas_id, digest_value
    );

    canvas_id := result_canvas_id;
    status := result_status;
    version := result_version;
    created_at := result_created_at;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_business_canvas_creator;
ALTER FUNCTION kokonut_security.create_location_business_model_canvas(UUID, UUID, TEXT, TEXT, INTEGER, TEXT[], JSONB)
    OWNER TO kokonut_business_canvas_creator;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_business_canvas_creator;
REVOKE ALL ON FUNCTION kokonut_security.create_location_business_model_canvas(UUID, UUID, TEXT, TEXT, INTEGER, TEXT[], JSONB)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        REVOKE ALL ON TABLE public.business_model_canvas_create_request
            FROM kokonut_runtime;
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_business_model_canvas(UUID, UUID, TEXT, TEXT, INTEGER, TEXT[], JSONB)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.business_model_canvas_create_request
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.create_location_business_model_canvas(UUID, UUID, TEXT, TEXT, INTEGER, TEXT[], JSONB)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_business_model_canvas(UUID, UUID, TEXT, TEXT, INTEGER, TEXT[], JSONB) IS
    'Creates an exact location-owned business model canvas draft under signed business_planning:create context. Request keys are idempotent; lifecycle remains draft.';

COMMIT;
