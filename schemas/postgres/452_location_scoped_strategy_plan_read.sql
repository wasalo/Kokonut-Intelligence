-- Bounded location-scoped strategy plan projection for the Kernel Gateway.
-- Free-text diagnosis, policy, rationale, and party identities stay private.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_strategy_reader'
    ) THEN
        CREATE ROLE kokonut_strategy_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_strategy_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Strategy reader role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_strategy_reader'
            OR member_role.rolname = 'kokonut_strategy_reader'
    ) THEN
        RAISE EXCEPTION 'Strategy reader role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_strategy_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_strategy_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_strategy_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_strategy_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_strategy_reader;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_strategy_reader;
GRANT SELECT ON TABLE
    public.strategy_plan,
    public.strategy_review_task,
    public.strategy_allocation_decision,
    public.v_strategy_kernel_execution,
    public.v_strategy_gate_status,
    public.operator_scope_grant,
    public.operator_identity,
    public.location,
    public.location_tenant_owner_verification,
    public.location_organization_share,
    public.operator_organization_membership,
    public.organization
TO kokonut_strategy_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_strategy_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_strategy_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_strategy_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_strategy_plan_summaries(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 50,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    strategy_plan_id UUID,
    plan_name TEXT,
    version INTEGER,
    plan_status TEXT,
    visibility TEXT,
    planning_horizon_start DATE,
    planning_horizon_end DATE,
    updated_at TIMESTAMPTZ,
    cascade_mode TEXT,
    cascade_status TEXT,
    has_parent_strategy BOOLEAN,
    objective_count BIGINT,
    initiative_count BIGINT,
    completed_initiative_count BIGINT,
    investment_case_count BIGINT,
    recommended_investment_count BIGINT,
    open_coherence_finding_count BIGINT,
    blocking_finding_count BIGINT,
    structural_gate_status TEXT,
    open_review_task_count BIGINT,
    submitted_allocation_count BIGINT,
    approved_allocation_count BIGINT
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
        RAISE EXCEPTION 'Strategy projection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'strategy', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Strategy projection requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Strategy projection page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT plan.id,
           plan.name::TEXT,
           plan.version,
           plan.status::TEXT,
           plan.visibility::TEXT,
           plan.planning_horizon_start,
           plan.planning_horizon_end,
           plan.updated_at,
           plan.cascade_mode::TEXT,
           plan.cascade_status::TEXT,
           plan.parent_strategy_plan_id IS NOT NULL,
           COALESCE(execution.objective_count, 0)::BIGINT,
           COALESCE(execution.initiative_count, 0)::BIGINT,
           COALESCE(execution.completed_initiative_count, 0)::BIGINT,
           COALESCE(execution.investment_case_count, 0)::BIGINT,
           COALESCE(execution.recommended_investment_count, 0)::BIGINT,
           COALESCE(execution.open_coherence_finding_count, 0)::BIGINT,
           COALESCE(gates.blocking_finding_count, 0)::BIGINT,
           COALESCE(gates.gate_status, 'blocked')::TEXT,
           COALESCE(review_tasks.open_task_count, 0)::BIGINT,
           COALESCE(allocation_decisions.submitted_count, 0)::BIGINT,
           COALESCE(allocation_decisions.approved_count, 0)::BIGINT
      FROM public.strategy_plan AS plan
      LEFT JOIN public.v_strategy_kernel_execution AS execution
        ON execution.strategy_plan_id = plan.id
      LEFT JOIN public.v_strategy_gate_status AS gates
        ON gates.strategy_plan_id = plan.id
      LEFT JOIN LATERAL (
          SELECT count(*) AS open_task_count
            FROM public.strategy_review_task AS task
           WHERE task.strategy_plan_id = plan.id
             AND task.status IN ('pending', 'in_progress', 'overdue')
      ) AS review_tasks ON true
      LEFT JOIN LATERAL (
          SELECT count(*) FILTER (WHERE decision.decision_status = 'submitted')
                     AS submitted_count,
                 count(*) FILTER (WHERE decision.decision_status = 'approved')
                     AS approved_count
            FROM public.strategy_allocation_decision AS decision
           WHERE decision.strategy_plan_id = plan.id
      ) AS allocation_decisions ON true
     WHERE plan.scope_type = 'location'
       AND plan.scope_id = requested_location_id
     ORDER BY plan.updated_at DESC, plan.id DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

ALTER FUNCTION kokonut_security.list_location_strategy_plan_summaries(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_strategy_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_strategy_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_strategy_plan_summaries(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_strategy_plan_summaries(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_strategy_plan_summaries(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_strategy_plan_summaries(UUID, INTEGER, INTEGER) IS
    'Returns bounded metadata and aggregate execution/gate counts for location strategy plans under a signed operator strategy:read grant; free text and identities are excluded.';

COMMIT;
