-- Bounded location-only competitive landscape and advantage outcome projection.
-- Actor identity, evidence, narrative, and individual outcome values stay private.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_competitive_reader'
    ) THEN
        CREATE ROLE kokonut_competitive_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_competitive_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Competitive reader role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_competitive_reader'
            OR member_role.rolname = 'kokonut_competitive_reader'
    ) THEN
        RAISE EXCEPTION 'Competitive reader role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_competitive_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_competitive_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_competitive_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_competitive_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_competitive_reader;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_competitive_reader;
GRANT SELECT ON TABLE
    public.competitive_landscape,
    public.competitive_actor,
    public.competitive_force_observation,
    public.competitive_signal,
    public.strategy_plan,
    public.strategy_advantage,
    public.strategy_advantage_outcome,
    public.operator_scope_grant,
    public.operator_identity,
    public.location,
    public.location_tenant_owner_verification,
    public.location_organization_share,
    public.operator_organization_membership,
    public.organization
TO kokonut_competitive_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_competitive_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_competitive_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_competitive_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_competitive_landscape_summaries(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 50,
    requested_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    landscape_id UUID,
    strategy_plan_id UUID,
    industry TEXT,
    geography TEXT,
    period_start DATE,
    period_end DATE,
    landscape_status TEXT,
    confidence TEXT,
    updated_at TIMESTAMPTZ,
    actor_count BIGINT,
    high_or_critical_actor_count BIGINT,
    force_observation_count BIGINT,
    average_force_pressure NUMERIC,
    worsening_force_count BIGINT,
    signal_count BIGINT,
    unreviewed_critical_signal_count BIGINT,
    verified_advantage_count BIGINT,
    average_verified_defensibility NUMERIC,
    verified_advantage_outcome_count BIGINT,
    latest_verified_outcome_period_end DATE
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
        RAISE EXCEPTION 'Competitive projection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'competitive_landscape', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Competitive projection requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Competitive projection page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT landscape.id,
           plan.id,
           landscape.industry::TEXT,
           landscape.geography::TEXT,
           landscape.period_start,
           landscape.period_end,
           landscape.status::TEXT,
           landscape.confidence::TEXT,
           landscape.updated_at,
           COALESCE(actors.actor_count, 0)::BIGINT,
           COALESCE(actors.high_or_critical_count, 0)::BIGINT,
           COALESCE(forces.observation_count, 0)::BIGINT,
           forces.average_pressure,
           COALESCE(forces.worsening_count, 0)::BIGINT,
           COALESCE(signals.signal_count, 0)::BIGINT,
           COALESCE(signals.unreviewed_critical_count, 0)::BIGINT,
           COALESCE(advantages.verified_count, 0)::BIGINT,
           advantages.average_defensibility,
           COALESCE(outcomes.verified_count, 0)::BIGINT,
           outcomes.latest_period_end
      FROM public.competitive_landscape AS landscape
      JOIN public.strategy_plan AS plan
        ON plan.id = landscape.strategy_plan_id
       AND plan.scope_type = 'location'
       AND plan.scope_id = requested_location_id
     CROSS JOIN LATERAL (
          SELECT count(*) AS actor_count,
                 count(*) FILTER (WHERE actor.threat_level IN ('high', 'critical'))
                     AS high_or_critical_count
            FROM public.competitive_actor AS actor
           WHERE actor.landscape_id = landscape.id
      ) AS actors
     CROSS JOIN LATERAL (
          SELECT count(*) AS observation_count,
                 round(avg(force.pressure_score), 2) AS average_pressure,
                 count(*) FILTER (WHERE force.trend = 'worsening') AS worsening_count
            FROM public.competitive_force_observation AS force
           WHERE force.landscape_id = landscape.id
      ) AS forces
     CROSS JOIN LATERAL (
          SELECT count(*) AS signal_count,
                 count(*) FILTER (
                     WHERE signal.materiality = 'critical' AND signal.reviewed_at IS NULL
                 ) AS unreviewed_critical_count
            FROM public.competitive_signal AS signal
           WHERE signal.landscape_id = landscape.id
      ) AS signals
     CROSS JOIN LATERAL (
          SELECT count(*) AS verified_count,
                 round(avg(advantage.defensibility_score), 2) AS average_defensibility
            FROM public.strategy_advantage AS advantage
           WHERE advantage.strategy_plan_id = plan.id
             AND advantage.status = 'verified'
      ) AS advantages
     CROSS JOIN LATERAL (
          SELECT count(*) FILTER (WHERE outcome.status = 'verified') AS verified_count,
                 max(outcome.period_end) FILTER (WHERE outcome.status = 'verified') AS latest_period_end
            FROM public.strategy_advantage AS advantage
            JOIN public.strategy_advantage_outcome AS outcome
              ON outcome.advantage_id = advantage.id
           WHERE advantage.strategy_plan_id = plan.id
             AND outcome.status IN ('submitted', 'verified')
      ) AS outcomes
     WHERE landscape.scope_type = 'location'
       AND landscape.scope_id = requested_location_id
     ORDER BY landscape.period_end DESC, landscape.updated_at DESC, landscape.id DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

ALTER FUNCTION kokonut_security.list_location_competitive_landscape_summaries(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_competitive_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_competitive_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_competitive_landscape_summaries(UUID, INTEGER, INTEGER)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_competitive_landscape_summaries(UUID, INTEGER, INTEGER)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_competitive_landscape_summaries(UUID, INTEGER, INTEGER)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_competitive_landscape_summaries(UUID, INTEGER, INTEGER) IS
    'Returns bounded location-only competitive landscape and verified advantage aggregates under a signed operator competitive_landscape:read grant; raw actor identity, evidence, narrative, and outcome values are excluded.';

COMMIT;
