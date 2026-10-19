-- Location-scoped, aggregate-only solution lifecycle projection for the Kernel Gateway.

BEGIN;

ALTER TABLE public.solution_link
    DROP CONSTRAINT IF EXISTS solution_link_entity_type_check;
ALTER TABLE public.solution_link
    ADD CONSTRAINT solution_link_entity_type_check
    CHECK (entity_type IN (
        'location', 'opportunity', 'strategy_plan', 'strategy_choice',
        'strategy_investment', 'technology_alternative', 'experiment',
        'funding_case', 'pilot', 'adoption_program', 'scale_gate',
        'artifact', 'evidence'
    ));

CREATE INDEX IF NOT EXISTS idx_solution_link_location
    ON public.solution_link(entity_id, solution_id)
    WHERE entity_type = 'location';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_reader'
    ) THEN
        CREATE ROLE kokonut_solution_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution reader role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_reader'
            OR member_role.rolname = 'kokonut_solution_reader'
    ) THEN
        RAISE EXCEPTION 'Solution reader role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_solution_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_solution_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_solution_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_solution_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_solution_reader;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_solution_reader;
GRANT SELECT ON TABLE
    public.solution,
    public.solution_link,
    public.solution_stage_gate,
    public.solution_gate_evaluation,
    public.solution_experiment,
    public.solution_experiment_result,
    public.solution_replication,
    public.solution_funding_case,
    public.solution_adoption_program,
    public.solution_configuration,
    public.solution_adopter_readiness,
    public.solution_scale_gate,
    public.solution_learning_record,
    public.solution_retirement,
    public.operator_scope_grant,
    public.operator_identity,
    public.location,
    public.location_tenant_owner_verification,
    public.location_organization_share,
    public.operator_organization_membership,
    public.organization
TO kokonut_solution_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_reader;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_lifecycle_summary(
    requested_location_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    summary JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Solution lifecycle projection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution lifecycle projection requires an active location grant'
            USING ERRCODE = '42501';
    END IF;

    WITH scoped_solutions AS (
        SELECT solution.*
          FROM public.solution AS solution
         WHERE (solution.originating_scope_type = 'location'
                AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1
                  FROM public.solution_link AS location_link
                 WHERE location_link.solution_id = solution.id
                   AND location_link.entity_type = 'location'
                   AND location_link.entity_id = requested_location_id
            )
    )
    SELECT jsonb_build_object(
        'solution_count', count(*)::BIGINT,
        'stage_counts', jsonb_build_object(
            'discovered', count(*) FILTER (WHERE current_stage = 'discovered')::BIGINT,
            'triaged', count(*) FILTER (WHERE current_stage = 'triaged')::BIGINT,
            'framed', count(*) FILTER (WHERE current_stage = 'framed')::BIGINT,
            'experiment_ready', count(*) FILTER (WHERE current_stage = 'experiment_ready')::BIGINT,
            'testing', count(*) FILTER (WHERE current_stage = 'testing')::BIGINT,
            'validated', count(*) FILTER (WHERE current_stage = 'validated')::BIGINT,
            'investment_ready', count(*) FILTER (WHERE current_stage = 'investment_ready')::BIGINT,
            'funded', count(*) FILTER (WHERE current_stage = 'funded')::BIGINT,
            'pilot_active', count(*) FILTER (WHERE current_stage = 'pilot_active')::BIGINT,
            'adoption_ready', count(*) FILTER (WHERE current_stage = 'adoption_ready')::BIGINT,
            'adopting', count(*) FILTER (WHERE current_stage = 'adopting')::BIGINT,
            'scaled', count(*) FILTER (WHERE current_stage = 'scaled')::BIGINT,
            'maintained', count(*) FILTER (WHERE current_stage = 'maintained')::BIGINT,
            'paused', count(*) FILTER (WHERE current_stage = 'paused')::BIGINT,
            'superseded', count(*) FILTER (WHERE current_stage = 'superseded')::BIGINT,
            'retired', count(*) FILTER (WHERE current_stage = 'retired')::BIGINT,
            'failed', count(*) FILTER (WHERE current_stage = 'failed')::BIGINT
        ),
        'solution_status_counts', jsonb_build_object(
            'active', count(*) FILTER (WHERE status = 'active')::BIGINT,
            'paused', count(*) FILTER (WHERE status = 'paused')::BIGINT,
            'retired', count(*) FILTER (WHERE status = 'retired')::BIGINT,
            'superseded', count(*) FILTER (WHERE status = 'superseded')::BIGINT
        ),
        'stage_gate_status_counts', (
            SELECT jsonb_build_object(
                'draft', count(*) FILTER (WHERE gate.status = 'draft')::BIGINT,
                'ready', count(*) FILTER (WHERE gate.status = 'ready')::BIGINT,
                'approved', count(*) FILTER (WHERE gate.status = 'approved')::BIGINT,
                'failed', count(*) FILTER (WHERE gate.status = 'failed')::BIGINT,
                'retired', count(*) FILTER (WHERE gate.status = 'retired')::BIGINT
            ) FROM public.solution_stage_gate AS gate
            JOIN scoped_solutions AS scoped ON scoped.id = gate.solution_id
        ),
        'latest_gate_evaluation_counts', (
            SELECT jsonb_build_object(
                'passed', count(*) FILTER (WHERE latest.passed)::BIGINT,
                'failed', count(*) FILTER (WHERE NOT latest.passed)::BIGINT
            ) FROM (
                SELECT DISTINCT ON (evaluation.gate_id) evaluation.passed
                  FROM public.solution_gate_evaluation AS evaluation
                  JOIN public.solution_stage_gate AS gate ON gate.id = evaluation.gate_id
                  JOIN scoped_solutions AS scoped ON scoped.id = gate.solution_id
                 ORDER BY evaluation.gate_id, evaluation.evaluated_at DESC, evaluation.id DESC
            ) AS latest
        ),
        'experiment_status_counts', (
            SELECT jsonb_build_object(
                'draft', count(*) FILTER (WHERE experiment.status = 'draft')::BIGINT,
                'submitted', count(*) FILTER (WHERE experiment.status = 'submitted')::BIGINT,
                'protocol_approved', count(*) FILTER (WHERE experiment.status = 'protocol_approved')::BIGINT,
                'baseline_ready', count(*) FILTER (WHERE experiment.status = 'baseline_ready')::BIGINT,
                'active', count(*) FILTER (WHERE experiment.status = 'active')::BIGINT,
                'paused', count(*) FILTER (WHERE experiment.status = 'paused')::BIGINT,
                'completed', count(*) FILTER (WHERE experiment.status = 'completed')::BIGINT,
                'results_review', count(*) FILTER (WHERE experiment.status = 'results_review')::BIGINT,
                'validated', count(*) FILTER (WHERE experiment.status = 'validated')::BIGINT,
                'invalidated', count(*) FILTER (WHERE experiment.status = 'invalidated')::BIGINT,
                'inconclusive', count(*) FILTER (WHERE experiment.status = 'inconclusive')::BIGINT,
                'requires_replication', count(*) FILTER (WHERE experiment.status = 'requires_replication')::BIGINT
            ) FROM public.solution_experiment AS experiment
            JOIN scoped_solutions AS scoped ON scoped.id = experiment.solution_id
        ),
        'experiment_result_counts', (
            SELECT jsonb_build_object(
                'validated', count(*) FILTER (WHERE result.outcome = 'validated')::BIGINT,
                'invalidated', count(*) FILTER (WHERE result.outcome = 'invalidated')::BIGINT,
                'inconclusive', count(*) FILTER (WHERE result.outcome = 'inconclusive')::BIGINT,
                'requires_replication', count(*) FILTER (WHERE result.outcome = 'requires_replication')::BIGINT
            ) FROM public.solution_experiment_result AS result
            JOIN public.solution_experiment AS experiment ON experiment.id = result.experiment_id
            JOIN scoped_solutions AS scoped ON scoped.id = experiment.solution_id
        ),
        'replication_status_counts', (
            SELECT jsonb_build_object(
                'proposed', count(*) FILTER (WHERE replication.status = 'proposed')::BIGINT,
                'approved', count(*) FILTER (WHERE replication.status = 'approved')::BIGINT,
                'active', count(*) FILTER (WHERE replication.status = 'active')::BIGINT,
                'completed', count(*) FILTER (WHERE replication.status = 'completed')::BIGINT,
                'failed', count(*) FILTER (WHERE replication.status = 'failed')::BIGINT
            ) FROM public.solution_replication AS replication
            JOIN scoped_solutions AS scoped ON scoped.id = replication.solution_id
        ),
        'funding_decision_counts', (
            SELECT jsonb_build_object(
                'draft', count(*) FILTER (WHERE funding.decision_status = 'draft')::BIGINT,
                'submitted', count(*) FILTER (WHERE funding.decision_status = 'submitted')::BIGINT,
                'approved', count(*) FILTER (WHERE funding.decision_status = 'approved')::BIGINT,
                'rejected', count(*) FILTER (WHERE funding.decision_status = 'rejected')::BIGINT,
                'closed', count(*) FILTER (WHERE funding.decision_status = 'closed')::BIGINT
            ) FROM public.solution_funding_case AS funding
            JOIN scoped_solutions AS scoped ON scoped.id = funding.solution_id
        ),
        'adoption_program_status_counts', (
            SELECT jsonb_build_object(
                'draft', count(*) FILTER (WHERE program.status = 'draft')::BIGINT,
                'community_review', count(*) FILTER (WHERE program.status = 'community_review')::BIGINT,
                'enablement_ready', count(*) FILTER (WHERE program.status = 'enablement_ready')::BIGINT,
                'launch', count(*) FILTER (WHERE program.status = 'launch')::BIGINT,
                'onboarding', count(*) FILTER (WHERE program.status = 'onboarding')::BIGINT,
                'active', count(*) FILTER (WHERE program.status = 'active')::BIGINT,
                'paused', count(*) FILTER (WHERE program.status = 'paused')::BIGINT,
                'assessed', count(*) FILTER (WHERE program.status = 'assessed')::BIGINT,
                'expand', count(*) FILTER (WHERE program.status = 'expand')::BIGINT,
                'redesign', count(*) FILTER (WHERE program.status = 'redesign')::BIGINT,
                'retired', count(*) FILTER (WHERE program.status = 'retired')::BIGINT
            ) FROM public.solution_adoption_program AS program
            JOIN scoped_solutions AS scoped ON scoped.id = program.solution_id
            WHERE program.target_scope_type = 'location'
              AND program.target_scope_id = requested_location_id
        ),
        'configuration_approval_counts', (
            SELECT jsonb_build_object(
                'draft', count(*) FILTER (WHERE configuration.approval_status = 'draft')::BIGINT,
                'submitted', count(*) FILTER (WHERE configuration.approval_status = 'submitted')::BIGINT,
                'approved', count(*) FILTER (WHERE configuration.approval_status = 'approved')::BIGINT,
                'rejected', count(*) FILTER (WHERE configuration.approval_status = 'rejected')::BIGINT
            ) FROM public.solution_configuration AS configuration
            JOIN scoped_solutions AS scoped ON scoped.id = configuration.solution_id
            WHERE configuration.scope_type = 'location'
              AND configuration.scope_id = requested_location_id
        ),
        'adopter_readiness_counts', (
            SELECT jsonb_build_object(
                'not_ready', count(*) FILTER (WHERE readiness.readiness_status = 'not_ready')::BIGINT,
                'remediating', count(*) FILTER (WHERE readiness.readiness_status = 'remediating')::BIGINT,
                'ready', count(*) FILTER (WHERE readiness.readiness_status = 'ready')::BIGINT,
                'expired', count(*) FILTER (WHERE readiness.readiness_status = 'expired')::BIGINT
            ) FROM public.solution_adopter_readiness AS readiness
            JOIN scoped_solutions AS scoped ON scoped.id = readiness.solution_id
            WHERE readiness.adopter_scope_type = 'location'
              AND readiness.adopter_scope_id = requested_location_id
        ),
        'scale_gate_status_counts', (
            SELECT jsonb_build_object(
                'pending', count(*) FILTER (WHERE gate.status = 'pending')::BIGINT,
                'passed', count(*) FILTER (WHERE gate.status = 'passed')::BIGINT,
                'failed', count(*) FILTER (WHERE gate.status = 'failed')::BIGINT,
                'waived', count(*) FILTER (WHERE gate.status = 'waived')::BIGINT
            ) FROM public.solution_scale_gate AS gate
            JOIN scoped_solutions AS scoped ON scoped.id = gate.solution_id
            WHERE gate.scope_type = 'location'
              AND gate.scope_id = requested_location_id
        ),
        'learning_decision_counts', (
            SELECT jsonb_build_object(
                'proposed', count(*) FILTER (WHERE learning.decision_status = 'proposed')::BIGINT,
                'accepted', count(*) FILTER (WHERE learning.decision_status = 'accepted')::BIGINT,
                'rejected', count(*) FILTER (WHERE learning.decision_status = 'rejected')::BIGINT,
                'applied', count(*) FILTER (WHERE learning.decision_status = 'applied')::BIGINT
            ) FROM public.solution_learning_record AS learning
            JOIN scoped_solutions AS scoped ON scoped.id = learning.solution_id
        ),
        'retirement_status_counts', (
            SELECT jsonb_build_object(
                'proposed', count(*) FILTER (WHERE retirement.status = 'proposed')::BIGINT,
                'impact_review', count(*) FILTER (WHERE retirement.status = 'impact_review')::BIGINT,
                'approved', count(*) FILTER (WHERE retirement.status = 'approved')::BIGINT,
                'migration', count(*) FILTER (WHERE retirement.status = 'migration')::BIGINT,
                'sunset', count(*) FILTER (WHERE retirement.status = 'sunset')::BIGINT,
                'completed', count(*) FILTER (WHERE retirement.status = 'completed')::BIGINT,
                'rejected', count(*) FILTER (WHERE retirement.status = 'rejected')::BIGINT
            ) FROM public.solution_retirement AS retirement
            JOIN scoped_solutions AS scoped ON scoped.id = retirement.solution_id
        )
    ) INTO summary
    FROM scoped_solutions;

    RETURN summary;
END;
$$;

ALTER FUNCTION kokonut_security.location_solution_lifecycle_summary(UUID)
    OWNER TO kokonut_solution_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_lifecycle_summary(UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_solution_lifecycle_summary(UUID)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_solution_lifecycle_summary(UUID)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.location_solution_lifecycle_summary(UUID) IS
    'Returns aggregate lifecycle, gate, experiment, funding-decision, adoption, scale, learning, and retirement counts for explicitly location-linked solutions under signed solution_lifecycle:read context; identifiers, narratives, evidence, and funding amounts are excluded.';

COMMIT;
