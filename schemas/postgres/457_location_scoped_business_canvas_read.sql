-- Bounded location-scoped business model canvas projection for the Kernel Gateway.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_business_planning_reader'
    ) THEN
        CREATE ROLE kokonut_business_planning_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_business_planning_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Business planning reader role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_business_planning_reader'
            OR member_role.rolname = 'kokonut_business_planning_reader'
    ) THEN
        RAISE EXCEPTION 'Business planning reader role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_business_planning_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_business_planning_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_business_planning_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_business_planning_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_business_planning_reader;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_business_planning_reader;
GRANT SELECT ON TABLE
    public.business_model_canvas,
    public.operator_scope_grant,
    public.operator_identity,
    public.location,
    public.location_tenant_owner_verification,
    public.location_organization_share,
    public.operator_organization_membership,
    public.organization
TO kokonut_business_planning_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_business_planning_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_business_planning_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_business_planning_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_business_model_canvases(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 26,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    canvas_id UUID,
    canvas_name TEXT,
    canvas_description TEXT,
    lifecycle_status TEXT,
    fiscal_year INTEGER,
    schema_version TEXT,
    version INTEGER,
    health_score NUMERIC,
    tags TEXT[],
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    content JSONB,
    source_system TEXT,
    source_reference TEXT
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
        RAISE EXCEPTION 'Business canvas projection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'business_planning', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Business canvas projection requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Business canvas projection page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT canvas.id,
           canvas.canvas_name::TEXT,
           canvas.description::TEXT,
           canvas.status::TEXT,
           canvas.fiscal_year,
           canvas.schema_version::TEXT,
           canvas.version,
           canvas.health_score,
           canvas.tags,
           canvas.created_at,
           canvas.updated_at,
           jsonb_build_object(
               'key_partners', canvas.key_partners,
               'key_activities', canvas.key_activities,
               'key_resources', canvas.key_resources,
               'value_propositions', canvas.value_propositions,
               'customer_relationships', canvas.customer_relationships,
               'channels', canvas.channels,
               'customer_segments', canvas.customer_segments,
               'revenue_streams', canvas.revenue_streams,
               'cost_structure', canvas.cost_structure
           ),
           canvas.source_system::TEXT,
           canvas.source_id::TEXT
      FROM public.business_model_canvas AS canvas
     WHERE canvas.entity_type = 'location'
       AND canvas.entity_id = requested_location_id
       AND canvas.location_id = requested_location_id
     ORDER BY canvas.updated_at DESC, canvas.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

ALTER FUNCTION kokonut_security.list_location_business_model_canvases(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_business_planning_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_business_planning_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_business_model_canvases(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_business_model_canvases(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_business_model_canvases(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_business_model_canvases(UUID, INTEGER, INTEGER) IS
    'Returns bounded location-owned canvas lifecycle, content blocks, and source reference under signed business_planning:read context; actor identities and raw import blobs are excluded.';

COMMIT;
