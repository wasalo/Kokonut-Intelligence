-- Bounded location-scoped management workload, SLA, claim, and escalation summary.
-- Work-item text, assignee identities, and audit notes stay private.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_management_reader'
    ) THEN
        CREATE ROLE kokonut_management_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_management_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Management reader role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_management_reader'
            OR member_role.rolname = 'kokonut_management_reader'
    ) THEN
        RAISE EXCEPTION 'Management reader role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_management_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_management_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_management_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_management_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_management_reader;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_management_reader;
GRANT SELECT ON TABLE
    public.work_item,
    public.work_item_event,
    public.work_item_claim,
    public.process_escalation,
    public.operator_scope_grant,
    public.operator_identity,
    public.location,
    public.location_tenant_owner_verification,
    public.location_organization_share,
    public.operator_organization_membership,
    public.organization
TO kokonut_management_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_management_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_management_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_management_reader;

CREATE OR REPLACE FUNCTION kokonut_security.location_management_work_summary(
    requested_location_id UUID
)
RETURNS TABLE (
    work_item_count BIGINT,
    open_work_item_count BIGINT,
    draft_count BIGINT,
    assigned_count BIGINT,
    in_progress_count BIGINT,
    blocked_count BIGINT,
    done_count BIGINT,
    cancelled_count BIGINT,
    high_priority_open_count BIGINT,
    critical_priority_open_count BIGINT,
    overdue_count BIGINT,
    sla_breached_count BIGINT,
    pending_claim_count BIGINT,
    accepted_claim_count BIGINT,
    open_escalation_count BIGINT,
    resolved_escalation_count BIGINT,
    latest_work_event_at TIMESTAMPTZ
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
        RAISE EXCEPTION 'Management summary requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'management_workflow', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Management summary requires an active location grant'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    WITH scoped_work AS MATERIALIZED (
        SELECT item.id, item.status::TEXT AS status,
               item.priority::TEXT AS priority, item.due_at, item.sla_at
          FROM public.work_item AS item
         WHERE item.location_id = requested_location_id
    ), work_counts AS (
        SELECT count(*)::BIGINT AS work_item_count,
               count(*) FILTER (WHERE status NOT IN ('done', 'cancelled'))::BIGINT
                   AS open_work_item_count,
               count(*) FILTER (WHERE status = 'draft')::BIGINT AS draft_count,
               count(*) FILTER (WHERE status = 'assigned')::BIGINT AS assigned_count,
               count(*) FILTER (WHERE status = 'in_progress')::BIGINT AS in_progress_count,
               count(*) FILTER (WHERE status = 'blocked')::BIGINT AS blocked_count,
               count(*) FILTER (WHERE status = 'done')::BIGINT AS done_count,
               count(*) FILTER (WHERE status = 'cancelled')::BIGINT AS cancelled_count,
               count(*) FILTER (WHERE priority = 'high' AND status NOT IN ('done', 'cancelled'))::BIGINT
                   AS high_priority_open_count,
               count(*) FILTER (WHERE priority = 'critical' AND status NOT IN ('done', 'cancelled'))::BIGINT
                   AS critical_priority_open_count,
               count(*) FILTER (
                   WHERE due_at < CURRENT_TIMESTAMP AND status NOT IN ('done', 'cancelled')
               )::BIGINT AS overdue_count,
               count(*) FILTER (
                   WHERE sla_at < CURRENT_TIMESTAMP AND status NOT IN ('done', 'cancelled')
               )::BIGINT AS sla_breached_count
          FROM scoped_work
    ), claim_counts AS (
        SELECT count(*) FILTER (WHERE claim.status = 'proposed')::BIGINT
                   AS pending_claim_count,
               count(*) FILTER (WHERE claim.status = 'accepted')::BIGINT
                   AS accepted_claim_count
          FROM public.work_item_claim AS claim
          JOIN scoped_work AS item ON item.id = claim.work_item_id
    ), escalation_counts AS (
        SELECT count(*) FILTER (WHERE escalation.resolved_at IS NULL)::BIGINT
                   AS open_escalation_count,
               count(*) FILTER (WHERE escalation.resolved_at IS NOT NULL)::BIGINT
                   AS resolved_escalation_count
          FROM public.process_escalation AS escalation
         WHERE EXISTS (
             SELECT 1
               FROM scoped_work AS item
              WHERE item.id = escalation.work_item_id
                 OR (escalation.entity_type = 'work_item' AND item.id = escalation.entity_id)
         )
    ), event_counts AS (
        SELECT max(event.created_at) AS latest_work_event_at
          FROM public.work_item_event AS event
          JOIN scoped_work AS item ON item.id = event.work_item_id
    )
    SELECT work_counts.work_item_count,
           work_counts.open_work_item_count,
           work_counts.draft_count,
           work_counts.assigned_count,
           work_counts.in_progress_count,
           work_counts.blocked_count,
           work_counts.done_count,
           work_counts.cancelled_count,
           work_counts.high_priority_open_count,
           work_counts.critical_priority_open_count,
           work_counts.overdue_count,
           work_counts.sla_breached_count,
           claim_counts.pending_claim_count,
           claim_counts.accepted_claim_count,
           escalation_counts.open_escalation_count,
           escalation_counts.resolved_escalation_count,
           event_counts.latest_work_event_at
      FROM work_counts
     CROSS JOIN claim_counts
     CROSS JOIN escalation_counts
     CROSS JOIN event_counts;
END;
$$;

ALTER FUNCTION kokonut_security.location_management_work_summary(UUID)
    OWNER TO kokonut_management_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_management_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_management_work_summary(UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_management_work_summary(UUID)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_management_work_summary(UUID)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.location_management_work_summary(UUID) IS
    'Returns bounded location work lifecycle, SLA, claim, event recency, and escalation totals under signed operator management_workflow:read; task text, assignee identity, and audit notes are excluded.';

COMMIT;
