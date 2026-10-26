-- Location-scoped, draft-only Kernel edits with optimistic concurrency and history.
-- Existing CLI/Directus canvas DML is retained as a compatibility path.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_business_canvas_editor'
    ) THEN
        CREATE ROLE kokonut_business_canvas_editor
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_business_canvas_editor'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Business canvas editor role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_business_canvas_editor'
            OR member_role.rolname = 'kokonut_business_canvas_editor'
    ) THEN
        RAISE EXCEPTION 'Business canvas editor role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.business_model_canvas_kernel_edit_request (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    canvas_id UUID NOT NULL REFERENCES public.business_model_canvas(id) ON DELETE RESTRICT,
    prior_version INTEGER NOT NULL CHECK (prior_version > 0),
    resulting_version INTEGER NOT NULL CHECK (resulting_version = prior_version + 1),
    expected_updated_at TIMESTAMPTZ NOT NULL,
    result_updated_at TIMESTAMPTZ NOT NULL,
    block_name TEXT NOT NULL CHECK (block_name IN (
        'key_partners', 'key_activities', 'key_resources', 'value_propositions',
        'customer_relationships', 'channels', 'customer_segments', 'revenue_streams',
        'cost_structure'
    )),
    snapshot JSONB NOT NULL,
    change_reason TEXT NOT NULL CHECK (pg_catalog.char_length(change_reason) BETWEEN 1 AND 500),
    request_digest TEXT NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id),
    UNIQUE (canvas_id, prior_version)
);

CREATE INDEX IF NOT EXISTS idx_business_canvas_kernel_edit_history
    ON public.business_model_canvas_kernel_edit_request(canvas_id, prior_version DESC);

CREATE OR REPLACE FUNCTION public.prevent_business_canvas_kernel_edit_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'business canvas Kernel edit history is append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_business_canvas_kernel_edit_immutable
    ON public.business_model_canvas_kernel_edit_request;
CREATE TRIGGER trg_business_canvas_kernel_edit_immutable
    BEFORE UPDATE OR DELETE ON public.business_model_canvas_kernel_edit_request
    FOR EACH ROW EXECUTE FUNCTION public.prevent_business_canvas_kernel_edit_mutation();

REVOKE ALL ON TABLE public.business_model_canvas_kernel_edit_request FROM PUBLIC;
REVOKE ALL ON FUNCTION public.prevent_business_canvas_kernel_edit_mutation() FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'REVOKE ALL ON TABLE public.business_model_canvas_kernel_edit_request FROM kokonut_runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        EXECUTE 'REVOKE ALL ON TABLE public.business_model_canvas_kernel_edit_request FROM kokonut_directus_runtime';
    END IF;
END;
$$;
GRANT SELECT (
    canvas_id, prior_version, resulting_version, snapshot, change_reason, created_at
) ON TABLE public.business_model_canvas_kernel_edit_request
    TO kokonut_business_planning_reader;

GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_business_canvas_editor;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_business_canvas_editor;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_business_canvas_editor;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_business_canvas_editor;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership TO kokonut_business_canvas_editor;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_business_canvas_editor;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification TO kokonut_business_canvas_editor;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share TO kokonut_business_canvas_editor;
GRANT SELECT (
    id, location_id, entity_type, entity_id, key_partners, key_activities,
    key_resources, value_propositions, customer_relationships, channels,
    customer_segments, revenue_streams, cost_structure, canvas_name, description,
    fiscal_year, tags, status, version, updated_at
) ON TABLE public.business_model_canvas TO kokonut_business_canvas_editor;
GRANT UPDATE (
    key_partners, key_activities, key_resources, value_propositions,
    customer_relationships, channels, customer_segments, revenue_streams,
    cost_structure, version, updated_at, updated_by
) ON TABLE public.business_model_canvas TO kokonut_business_canvas_editor;
GRANT SELECT, INSERT ON TABLE public.business_model_canvas_kernel_edit_request
    TO kokonut_business_canvas_editor;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_business_canvas_editor;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_business_canvas_editor;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_business_canvas_editor;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_business_canvas_editor;

CREATE OR REPLACE FUNCTION kokonut_security.update_location_business_model_canvas_block(
    requested_location_id UUID,
    requested_canvas_id UUID,
    requested_request_id UUID,
    requested_expected_version INTEGER,
    requested_expected_updated_at TIMESTAMPTZ,
    requested_block_name TEXT,
    requested_items JSONB,
    requested_change_reason TEXT
)
RETURNS TABLE (
    canvas_id UUID,
    status TEXT,
    version INTEGER,
    updated_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    canvas_row RECORD;
    prior_request public.business_model_canvas_kernel_edit_request%ROWTYPE;
    prior_snapshot JSONB;
    digest_value TEXT;
    normalized_reason TEXT;
    next_version INTEGER;
    result_time TIMESTAMPTZ;
    affected_rows INTEGER;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Business canvas edit requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'business_planning', 'update', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Business canvas edit requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;

    normalized_reason := NULLIF(pg_catalog.btrim(requested_change_reason), '');
    IF requested_request_id IS NULL
       OR requested_canvas_id IS NULL
       OR requested_expected_version IS NULL
       OR requested_expected_version < 1
       OR requested_expected_updated_at IS NULL
       OR requested_block_name IS NULL
       OR requested_block_name <> ALL (ARRAY[
            'key_partners', 'key_activities', 'key_resources', 'value_propositions',
            'customer_relationships', 'channels', 'customer_segments', 'revenue_streams',
            'cost_structure'
       ]::TEXT[])
       OR requested_items IS NULL
       OR pg_catalog.pg_column_size(requested_items) > 65536
       OR (requested_block_name = 'cost_structure'
           AND pg_catalog.jsonb_typeof(requested_items) IS DISTINCT FROM 'object')
       OR (requested_block_name <> 'cost_structure'
           AND pg_catalog.jsonb_typeof(requested_items) IS DISTINCT FROM 'array')
       OR normalized_reason IS NULL
       OR pg_catalog.char_length(normalized_reason) > 500 THEN
        RAISE EXCEPTION 'Business canvas edit fields are invalid'
            USING ERRCODE = '22023';
    END IF;

    digest_value := pg_catalog.encode(public.digest(
        pg_catalog.convert_to(pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'canvas_id', requested_canvas_id,
            'expected_version', requested_expected_version,
            'expected_updated_at', requested_expected_updated_at,
            'block_name', requested_block_name,
            'items', requested_items,
            'change_reason', normalized_reason
        )::TEXT, 'UTF8'), 'sha256'), 'hex');
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0)
    );

    SELECT * INTO prior_request
      FROM public.business_model_canvas_kernel_edit_request AS edit_row
     WHERE edit_row.operator_id = context_record.actor_id
       AND edit_row.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_request.location_id IS DISTINCT FROM requested_location_id
           OR prior_request.canvas_id IS DISTINCT FROM requested_canvas_id
           OR prior_request.request_digest IS DISTINCT FROM digest_value THEN
            RAISE EXCEPTION 'Business canvas edit request id was reused with different content'
                USING ERRCODE = '23505';
        END IF;
        canvas_id := prior_request.canvas_id;
        status := 'draft';
        version := prior_request.resulting_version;
        updated_at := prior_request.result_updated_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT canvas.id, canvas.location_id, canvas.entity_type, canvas.entity_id,
           canvas.key_partners, canvas.key_activities, canvas.key_resources,
           canvas.value_propositions, canvas.customer_relationships, canvas.channels,
           canvas.customer_segments, canvas.revenue_streams, canvas.cost_structure,
           canvas.canvas_name, canvas.description, canvas.fiscal_year, canvas.tags,
           canvas.status, canvas.version, canvas.updated_at
      INTO canvas_row
      FROM public.business_model_canvas AS canvas
     WHERE canvas.id = requested_canvas_id
       AND canvas.location_id = requested_location_id
       AND canvas.entity_type = 'location'
       AND canvas.entity_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location business canvas was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF canvas_row.status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Only draft business canvases can be edited through the Kernel'
            USING ERRCODE = '55000';
    END IF;
    IF canvas_row.version IS DISTINCT FROM requested_expected_version
       OR canvas_row.updated_at IS DISTINCT FROM requested_expected_updated_at THEN
        RAISE EXCEPTION 'Business canvas changed since it was read; reload before editing'
            USING ERRCODE = '40001';
    END IF;

    prior_snapshot := pg_catalog.jsonb_build_object(
        'canvas_name', canvas_row.canvas_name,
        'description', canvas_row.description,
        'fiscal_year', canvas_row.fiscal_year,
        'tags', canvas_row.tags,
        'blocks', pg_catalog.jsonb_build_object(
            'key_partners', canvas_row.key_partners,
            'key_activities', canvas_row.key_activities,
            'key_resources', canvas_row.key_resources,
            'value_propositions', canvas_row.value_propositions,
            'customer_relationships', canvas_row.customer_relationships,
            'channels', canvas_row.channels,
            'customer_segments', canvas_row.customer_segments,
            'revenue_streams', canvas_row.revenue_streams,
            'cost_structure', canvas_row.cost_structure
        )
    );
    next_version := canvas_row.version + 1;
    result_time := pg_catalog.clock_timestamp();
    INSERT INTO public.business_model_canvas_kernel_edit_request (
        operator_id, request_id, location_id, canvas_id, prior_version,
        resulting_version, expected_updated_at, result_updated_at, block_name,
        snapshot, change_reason, request_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        requested_canvas_id, canvas_row.version, next_version,
        requested_expected_updated_at, result_time, requested_block_name,
        prior_snapshot, normalized_reason, digest_value
    );

    EXECUTE pg_catalog.format(
        'UPDATE public.business_model_canvas SET %I = $1, version = $2, updated_at = $3, updated_by = $4 WHERE id = $5',
        requested_block_name
    ) USING requested_items, next_version, result_time, context_record.actor_id, requested_canvas_id;
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    IF affected_rows <> 1 THEN
        RAISE EXCEPTION 'Business canvas changed during edit';
    END IF;

    canvas_id := requested_canvas_id;
    status := canvas_row.status::TEXT;
    version := next_version;
    updated_at := result_time;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_business_model_canvas_versions(
    requested_location_id UUID,
    requested_canvas_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    canvas_id UUID,
    version INTEGER,
    snapshot JSONB,
    change_reason TEXT,
    changed_at TIMESTAMPTZ,
    is_current BOOLEAN
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Business canvas history requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'business_planning', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Business canvas history requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_canvas_id IS NULL OR requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Business canvas history page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM public.business_model_canvas AS canvas
         WHERE canvas.id = requested_canvas_id
           AND canvas.location_id = requested_location_id
           AND canvas.entity_type = 'location'
           AND canvas.entity_id = requested_location_id
    ) THEN
        RAISE EXCEPTION 'Location business canvas was not found'
            USING ERRCODE = 'P0002';
    END IF;

    RETURN QUERY
    WITH matching_canvas AS (
        SELECT canvas.*
          FROM public.business_model_canvas AS canvas
         WHERE canvas.id = requested_canvas_id
           AND canvas.location_id = requested_location_id
           AND canvas.entity_type = 'location'
           AND canvas.entity_id = requested_location_id
    ), candidates AS (
        SELECT history.version,
               pg_catalog.jsonb_build_object(
                   'canvas_name', history.snapshot -> 'canvas_name',
                   'description', history.snapshot -> 'description',
                   'fiscal_year', history.snapshot -> 'fiscal_year',
                   'tags', history.snapshot -> 'tags',
                   'blocks', pg_catalog.jsonb_build_object(
                       'key_partners', COALESCE(history.snapshot -> 'blocks' -> 'key_partners', history.snapshot -> 'key_partners', '[]'::JSONB),
                       'key_activities', COALESCE(history.snapshot -> 'blocks' -> 'key_activities', history.snapshot -> 'key_activities', '[]'::JSONB),
                       'key_resources', COALESCE(history.snapshot -> 'blocks' -> 'key_resources', history.snapshot -> 'key_resources', '[]'::JSONB),
                       'value_propositions', COALESCE(history.snapshot -> 'blocks' -> 'value_propositions', history.snapshot -> 'value_propositions', '[]'::JSONB),
                       'customer_relationships', COALESCE(history.snapshot -> 'blocks' -> 'customer_relationships', history.snapshot -> 'customer_relationships', '[]'::JSONB),
                       'channels', COALESCE(history.snapshot -> 'blocks' -> 'channels', history.snapshot -> 'channels', '[]'::JSONB),
                       'customer_segments', COALESCE(history.snapshot -> 'blocks' -> 'customer_segments', history.snapshot -> 'customer_segments', '[]'::JSONB),
                       'revenue_streams', COALESCE(history.snapshot -> 'blocks' -> 'revenue_streams', history.snapshot -> 'revenue_streams', '[]'::JSONB),
                       'cost_structure', COALESCE(history.snapshot -> 'blocks' -> 'cost_structure', history.snapshot -> 'cost_structure', '{}'::JSONB)
                   )
               ) AS snapshot,
               history.change_reason::TEXT AS change_reason,
               history.created_at AS changed_at,
               1 AS priority,
               FALSE AS is_current
          FROM matching_canvas AS canvas
          JOIN public.canvas_version AS history ON history.canvas_id = canvas.id
         WHERE history.version < canvas.version
        UNION ALL
        SELECT edit.prior_version,
               edit.snapshot,
               edit.change_reason::TEXT,
               edit.created_at,
               2,
               FALSE
          FROM matching_canvas AS canvas
          JOIN public.business_model_canvas_kernel_edit_request AS edit
            ON edit.canvas_id = canvas.id
         WHERE edit.prior_version < canvas.version
        UNION ALL
        SELECT canvas.version,
               pg_catalog.jsonb_build_object(
                   'canvas_name', canvas.canvas_name,
                   'description', canvas.description,
                   'fiscal_year', canvas.fiscal_year,
                   'tags', canvas.tags,
                   'blocks', pg_catalog.jsonb_build_object(
                       'key_partners', canvas.key_partners,
                       'key_activities', canvas.key_activities,
                       'key_resources', canvas.key_resources,
                       'value_propositions', canvas.value_propositions,
                       'customer_relationships', canvas.customer_relationships,
                       'channels', canvas.channels,
                       'customer_segments', canvas.customer_segments,
                       'revenue_streams', canvas.revenue_streams,
                       'cost_structure', canvas.cost_structure
                   )
               ),
               NULL::TEXT,
               canvas.updated_at,
               3,
               TRUE
          FROM matching_canvas AS canvas
    ), deduplicated AS (
        SELECT DISTINCT ON (candidate.version)
               candidate.version, candidate.snapshot, candidate.change_reason,
               candidate.changed_at, candidate.is_current
          FROM candidates AS candidate
         ORDER BY candidate.version, candidate.priority DESC
    )
    SELECT requested_canvas_id, history.version, history.snapshot,
           history.change_reason, history.changed_at, history.is_current
      FROM deduplicated AS history
     ORDER BY history.version DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

GRANT SELECT (
    canvas_id, version, snapshot, changes, change_reason, created_at
) ON TABLE public.canvas_version TO kokonut_business_planning_reader;
GRANT SELECT (id, location_id, entity_type, entity_id, key_partners, key_activities,
    key_resources, value_propositions, customer_relationships, channels,
    customer_segments, revenue_streams, cost_structure, canvas_name, description,
    fiscal_year, tags, version, status, updated_at)
    ON TABLE public.business_model_canvas TO kokonut_business_planning_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_business_planning_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_business_planning_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_business_planning_reader;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_business_canvas_editor;
ALTER FUNCTION kokonut_security.update_location_business_model_canvas_block(
    UUID, UUID, UUID, INTEGER, TIMESTAMPTZ, TEXT, JSONB, TEXT
) OWNER TO kokonut_business_canvas_editor;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_business_canvas_editor;
REVOKE ALL ON FUNCTION kokonut_security.update_location_business_model_canvas_block(
    UUID, UUID, UUID, INTEGER, TIMESTAMPTZ, TEXT, JSONB, TEXT
) FROM PUBLIC;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_business_planning_reader;
ALTER FUNCTION kokonut_security.list_location_business_model_canvas_versions(
    UUID, UUID, INTEGER, INTEGER
) OWNER TO kokonut_business_planning_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_business_planning_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_business_model_canvas_versions(
    UUID, UUID, INTEGER, INTEGER
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.update_location_business_model_canvas_block(
            UUID, UUID, UUID, INTEGER, TIMESTAMPTZ, TEXT, JSONB, TEXT
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_business_model_canvas_versions(
            UUID, UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.update_location_business_model_canvas_block(
            UUID, UUID, UUID, INTEGER, TIMESTAMPTZ, TEXT, JSONB, TEXT
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_business_model_canvas_versions(
            UUID, UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.update_location_business_model_canvas_block(
    UUID, UUID, UUID, INTEGER, TIMESTAMPTZ, TEXT, JSONB, TEXT
) IS 'Atomically updates one exact-location draft BMC block under signed business_planning:update context, version/timestamp concurrency, an idempotency key, and append-only prior-state history; lifecycle does not change.';

COMMENT ON FUNCTION kokonut_security.list_location_business_model_canvas_versions(
    UUID, UUID, INTEGER, INTEGER
) IS 'Returns bounded current and historical BMC snapshots for one exact location canvas under signed business_planning:read context; actor identifiers are excluded.';

COMMIT;
