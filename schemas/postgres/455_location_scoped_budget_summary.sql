-- Bounded location budget projection; organization-only lines are not farm-attributed.
-- Plan labels, objectives, categories, transaction details, and scenario assumptions stay private.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_planning_reader'
    ) THEN
        CREATE ROLE kokonut_planning_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_planning_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Planning reader role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_planning_reader'
            OR member_role.rolname = 'kokonut_planning_reader'
    ) THEN
        RAISE EXCEPTION 'Planning reader role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_planning_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_planning_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_planning_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_planning_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_planning_reader;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_planning_reader;
GRANT SELECT ON TABLE
    public.financial_plan,
    public.budget_line,
    public.planning_scenario,
    public.expense_event,
    public.operator_scope_grant,
    public.operator_identity,
    public.location,
    public.location_tenant_owner_verification,
    public.location_organization_share,
    public.operator_organization_membership,
    public.organization
TO kokonut_planning_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_planning_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_planning_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_planning_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_budget_summaries(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 25,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    financial_plan_id UUID,
    plan_status TEXT,
    currency TEXT,
    period_start DATE,
    period_end DATE,
    has_objective BOOLEAN,
    budget_line_count BIGINT,
    planned_amount NUMERIC,
    verified_expense_amount NUMERIC,
    budget_variance NUMERIC,
    nonmatching_currency_expense_count BIGINT,
    planning_scenario_count BIGINT
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
        RAISE EXCEPTION 'Budget projection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'planning_budget', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Budget projection requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Budget projection page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT plan.id,
           plan.status::TEXT,
           COALESCE(plan.currency, 'USD')::TEXT,
           plan.period_start,
           plan.period_end,
           plan.objective_id IS NOT NULL,
           budget.budget_line_count,
           budget.planned_amount,
           actuals.verified_expense_amount,
           budget.planned_amount - actuals.verified_expense_amount,
           actuals.nonmatching_currency_expense_count,
           scenarios.planning_scenario_count
      FROM public.financial_plan AS plan
      JOIN public.location AS farm
        ON farm.id = requested_location_id
       AND farm.organization_id = plan.organization_id
      JOIN LATERAL (
          SELECT count(*)::BIGINT AS budget_line_count,
                 COALESCE(sum(line.amount), 0)::NUMERIC AS planned_amount
            FROM public.budget_line AS line
           WHERE line.plan_id = plan.id
             AND line.location_id = requested_location_id
      ) AS budget ON budget.budget_line_count > 0
      JOIN LATERAL (
          SELECT COALESCE(sum(expense.amount) FILTER (
                     WHERE expense.currency = COALESCE(plan.currency, 'USD')
                 ), 0)::NUMERIC AS verified_expense_amount,
                 count(*) FILTER (
                     WHERE expense.currency IS DISTINCT FROM COALESCE(plan.currency, 'USD')
                 )::BIGINT AS nonmatching_currency_expense_count
            FROM public.expense_event AS expense
           WHERE expense.location_id = requested_location_id
             AND expense.status = 'verified'
             AND expense.expense_date BETWEEN plan.period_start AND plan.period_end
             AND EXISTS (
                 SELECT 1
                   FROM public.budget_line AS scoped_line
                  WHERE scoped_line.plan_id = plan.id
                    AND scoped_line.location_id = requested_location_id
                    AND scoped_line.category = expense.category
             )
      ) AS actuals ON TRUE
      JOIN LATERAL (
          SELECT count(*)::BIGINT AS planning_scenario_count
            FROM public.planning_scenario AS scenario
           WHERE scenario.plan_id = plan.id
      ) AS scenarios ON TRUE
     ORDER BY plan.period_end DESC, plan.updated_at DESC, plan.id DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

ALTER FUNCTION kokonut_security.list_location_budget_summaries(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_planning_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_planning_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_budget_summaries(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_budget_summaries(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_budget_summaries(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_budget_summaries(UUID, INTEGER, INTEGER) IS
    'Returns bounded budget and verified same-currency expense aggregates for exact location-assigned lines under signed operator planning_budget:read; org-only lines and transaction details are excluded.';

COMMIT;
