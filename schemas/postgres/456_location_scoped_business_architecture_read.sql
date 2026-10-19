-- Bounded location-scoped business architecture projection for the Kernel Gateway.
-- Only approved location roadmaps and approved current location statements are visible.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_business_architecture_reader'
    ) THEN
        CREATE ROLE kokonut_business_architecture_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_business_architecture_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Business architecture reader role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_business_architecture_reader'
            OR member_role.rolname = 'kokonut_business_architecture_reader'
    ) THEN
        RAISE EXCEPTION 'Business architecture reader role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_business_architecture_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_business_architecture_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_business_architecture_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_business_architecture_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_business_architecture_reader;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_business_architecture_reader;
GRANT SELECT ON TABLE
    public.vision_mission,
    public.technology_roadmap,
    public.technology_roadmap_requirement,
    public.business_capability,
    public.value_stream_definition,
    public.strategy_map,
    public.operator_scope_grant,
    public.operator_identity,
    public.location,
    public.location_tenant_owner_verification,
    public.location_organization_share,
    public.operator_organization_membership,
    public.organization
TO kokonut_business_architecture_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_business_architecture_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_business_architecture_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_business_architecture_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_business_architecture_mappings(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 26,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    roadmap_id UUID,
    roadmap_name TEXT,
    roadmap_status TEXT,
    planning_horizon_start DATE,
    planning_horizon_end DATE,
    requirement_id UUID,
    requirement_title TEXT,
    need_type TEXT,
    priority SMALLINT,
    requirement_status TEXT,
    capability_name TEXT,
    value_stream_name TEXT,
    strategy_perspective TEXT
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
        RAISE EXCEPTION 'Business architecture projection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'business_architecture', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Business architecture projection requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Business architecture projection page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT roadmap.id,
           roadmap.name::TEXT,
           roadmap.status::TEXT,
           roadmap.planning_horizon_start,
           roadmap.planning_horizon_end,
           requirement.id,
           requirement.title::TEXT,
           requirement.need_type::TEXT,
           requirement.priority,
           requirement.status::TEXT,
           capability.name::TEXT,
           value_stream.name::TEXT,
           strategy.perspective::TEXT
      FROM public.technology_roadmap AS roadmap
      LEFT JOIN public.technology_roadmap_requirement AS requirement
        ON requirement.roadmap_id = roadmap.id
       AND requirement.status <> 'retired'
      LEFT JOIN public.business_capability AS capability
        ON capability.id = requirement.capability_id
      LEFT JOIN public.value_stream_definition AS value_stream
        ON value_stream.id = requirement.value_stream_id
      LEFT JOIN public.strategy_map AS strategy
        ON strategy.id = requirement.strategy_map_id
       AND strategy.entity_type = 'location'
       AND strategy.entity_id = requested_location_id
     WHERE roadmap.entity_type = 'location'
       AND roadmap.entity_id = requested_location_id
       AND roadmap.status IN ('approved', 'active', 'reviewed')
     ORDER BY roadmap.updated_at DESC, roadmap.id, requirement.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_business_architecture_missions(
    requested_location_id UUID
)
RETURNS TABLE (
    statement_type TEXT,
    statement_text TEXT,
    effective_date DATE,
    review_date DATE
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
        RAISE EXCEPTION 'Business architecture projection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'business_architecture', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Business architecture projection requires an active location grant'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT DISTINCT ON (statement.statement_type)
           statement.statement_type::TEXT,
           statement.statement_text,
           statement.effective_date,
           statement.review_date
      FROM public.vision_mission AS statement
     WHERE statement.entity_type = 'location'
       AND statement.entity_id = requested_location_id
       AND statement.status = 'approved'
     ORDER BY statement.statement_type,
              statement.approved_at DESC NULLS LAST,
              statement.effective_date DESC,
              statement.created_at DESC,
              statement.id;
END;
$$;

ALTER FUNCTION kokonut_security.list_location_business_architecture_mappings(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_business_architecture_reader;
ALTER FUNCTION kokonut_security.list_location_business_architecture_missions(UUID)
    OWNER TO kokonut_business_architecture_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_business_architecture_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_business_architecture_mappings(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_business_architecture_missions(UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_business_architecture_mappings(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_business_architecture_missions(UUID)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_business_architecture_mappings(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_business_architecture_missions(UUID)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_business_architecture_mappings(UUID, INTEGER, INTEGER) IS
    'Lists bounded capability, value-stream, and location-strategy links from approved location roadmaps under a signed business_architecture:read grant; descriptions, evidence, and cross-scope strategy links are excluded.';
COMMENT ON FUNCTION kokonut_security.list_location_business_architecture_missions(UUID) IS
    'Lists only the latest approved vision, mission, or values statement for the exact granted location under a signed business_architecture:read grant.';

COMMIT;
