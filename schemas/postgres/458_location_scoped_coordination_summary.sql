-- Location-scoped coordination governance summary for the Kernel Gateway.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_coordination_reader'
    ) THEN
        CREATE ROLE kokonut_coordination_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_coordination_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Coordination reader role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_coordination_reader'
            OR member_role.rolname = 'kokonut_coordination_reader'
    ) THEN
        RAISE EXCEPTION 'Coordination reader role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_coordination_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_coordination_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_coordination_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_coordination_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_coordination_reader;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_coordination_reader;
GRANT SELECT ON TABLE
    public.coordination_alliance,
    public.coordination_conflict_declaration,
    public.coordination_benefit_harm_analysis,
    public.coordination_appeal,
    public.coordination_remedy,
    public.coordination_minority_view,
    public.coordination_knowledge_exchange,
    public.coordination_learning_link,
    public.coordination_metric_observation,
    public.operator_scope_grant,
    public.operator_identity,
    public.location,
    public.location_tenant_owner_verification,
    public.location_organization_share,
    public.operator_organization_membership,
    public.organization
TO kokonut_coordination_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_coordination_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_coordination_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_coordination_reader;

CREATE OR REPLACE FUNCTION kokonut_security.location_coordination_governance_summary(
    requested_location_id UUID
)
RETURNS TABLE (
    alliance_count BIGINT,
    draft_alliance_count BIGINT,
    proposed_alliance_count BIGINT,
    approved_alliance_count BIGINT,
    active_alliance_count BIGINT,
    paused_alliance_count BIGINT,
    completed_alliance_count BIGINT,
    dissolved_alliance_count BIGINT,
    rejected_alliance_count BIGINT,
    overdue_review_count BIGINT,
    open_conflict_declaration_count BIGINT,
    unreviewed_harm_analysis_count BIGINT,
    open_appeal_count BIGINT,
    open_remedy_count BIGINT,
    preserved_minority_view_count BIGINT,
    completed_knowledge_exchange_count BIGINT,
    open_learning_link_count BIGINT,
    draft_metric_observation_count BIGINT,
    rejected_metric_observation_count BIGINT
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
        RAISE EXCEPTION 'Coordination projection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'coordination', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Coordination projection requires an active location grant'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    WITH scoped_alliances AS (
        SELECT alliance.id, alliance.status, alliance.review_due_at
          FROM public.coordination_alliance AS alliance
         WHERE alliance.scope_type = 'location'
           AND alliance.scope_id = requested_location_id
    )
    SELECT count(*)::BIGINT,
           count(*) FILTER (WHERE status = 'draft')::BIGINT,
           count(*) FILTER (WHERE status = 'proposed')::BIGINT,
           count(*) FILTER (WHERE status = 'approved')::BIGINT,
           count(*) FILTER (WHERE status = 'active')::BIGINT,
           count(*) FILTER (WHERE status = 'paused')::BIGINT,
           count(*) FILTER (WHERE status = 'completed')::BIGINT,
           count(*) FILTER (WHERE status = 'dissolved')::BIGINT,
           count(*) FILTER (WHERE status = 'rejected')::BIGINT,
           count(*) FILTER (WHERE review_due_at <= statement_timestamp()
                              AND status IN ('active', 'paused'))::BIGINT,
           (SELECT count(*) FROM public.coordination_conflict_declaration AS item
             JOIN scoped_alliances AS scoped ON scoped.id = item.alliance_id
            WHERE item.status = 'declared')::BIGINT,
           (SELECT count(*) FROM public.coordination_benefit_harm_analysis AS item
             JOIN scoped_alliances AS scoped ON scoped.id = item.alliance_id
            WHERE item.status = 'proposed')::BIGINT,
           (SELECT count(*) FROM public.coordination_appeal AS item
             JOIN scoped_alliances AS scoped ON scoped.id = item.alliance_id
            WHERE item.status IN ('open', 'investigating'))::BIGINT,
           (SELECT count(*) FROM public.coordination_remedy AS item
             JOIN scoped_alliances AS scoped ON scoped.id = item.alliance_id
            WHERE item.status IN ('proposed', 'approved', 'in_progress'))::BIGINT,
           (SELECT count(*) FROM public.coordination_minority_view AS item
             JOIN scoped_alliances AS scoped ON scoped.id = item.alliance_id
            WHERE item.preservation_status = 'preserved')::BIGINT,
           (SELECT count(*) FROM public.coordination_knowledge_exchange AS item
             JOIN scoped_alliances AS scoped ON scoped.id = item.alliance_id
            WHERE item.status = 'completed')::BIGINT,
           (SELECT count(*) FROM public.coordination_learning_link AS item
             JOIN scoped_alliances AS scoped ON scoped.id = item.alliance_id
            WHERE item.status IN ('proposed', 'active'))::BIGINT,
           (SELECT count(*) FROM public.coordination_metric_observation AS item
             JOIN scoped_alliances AS scoped ON scoped.id = item.alliance_id
            WHERE item.status = 'draft')::BIGINT,
           (SELECT count(*) FROM public.coordination_metric_observation AS item
             JOIN scoped_alliances AS scoped ON scoped.id = item.alliance_id
            WHERE item.status = 'rejected')::BIGINT
      FROM scoped_alliances;
END;
$$;

ALTER FUNCTION kokonut_security.location_coordination_governance_summary(UUID)
    OWNER TO kokonut_coordination_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_coordination_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_coordination_governance_summary(UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_coordination_governance_summary(UUID)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_coordination_governance_summary(UUID)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.location_coordination_governance_summary(UUID) IS
    'Returns aggregate lifecycle, integrity-review, remedy, and learning counts for exact location-scoped alliances under signed coordination:read context; party identities and narratives are excluded.';

COMMIT;
