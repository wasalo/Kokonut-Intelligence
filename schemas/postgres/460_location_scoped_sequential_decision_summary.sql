-- Location-scoped, aggregate sequential evidence and decision projection.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_sequential_reader'
    ) THEN
        CREATE ROLE kokonut_sequential_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_sequential_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Sequential decision reader role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_sequential_reader'
            OR member_role.rolname = 'kokonut_sequential_reader'
    ) THEN
        RAISE EXCEPTION 'Sequential decision reader role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_sequential_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_sequential_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_sequential_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_sequential_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_sequential_reader;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_sequential_reader;
GRANT SELECT ON TABLE
    public.decision_hypothesis,
    public.decision_evidence_event,
    public.decision_posterior_update,
    public.decision_threshold_evaluation,
    public.strategy_plan,
    public.threat,
    public.solution,
    public.solution_link,
    public.operator_scope_grant,
    public.operator_identity,
    public.location,
    public.location_tenant_owner_verification,
    public.location_organization_share,
    public.operator_organization_membership,
    public.organization
TO kokonut_sequential_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_sequential_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_sequential_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_sequential_reader;

CREATE OR REPLACE FUNCTION kokonut_security.location_sequential_decision_summary(
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
        RAISE EXCEPTION 'Sequential decision projection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'sequential_evidence', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Sequential decision projection requires an active location grant'
            USING ERRCODE = '42501';
    END IF;

    WITH scoped_hypotheses AS (
        SELECT hypothesis.id, hypothesis.status
          FROM public.decision_hypothesis AS hypothesis
         WHERE (hypothesis.subject_type = 'strategy_plan' AND EXISTS (
                    SELECT 1 FROM public.strategy_plan AS plan
                     WHERE plan.id = hypothesis.subject_id
                       AND plan.scope_type = 'location'
                       AND plan.scope_id = requested_location_id
                ))
            OR (hypothesis.subject_type = 'threat' AND EXISTS (
                    SELECT 1 FROM public.threat AS item
                     WHERE item.id = hypothesis.subject_id
                       AND item.location_id = requested_location_id
                ))
            OR (hypothesis.subject_type = 'solution' AND EXISTS (
                    SELECT 1 FROM public.solution AS item
                     WHERE item.id = hypothesis.subject_id
                       AND ((item.originating_scope_type = 'location'
                             AND item.originating_scope_id = requested_location_id)
                            OR EXISTS (
                                SELECT 1 FROM public.solution_link AS location_link
                                 WHERE location_link.solution_id = item.id
                                   AND location_link.entity_type = 'location'
                                   AND location_link.entity_id = requested_location_id
                            ))
                ))
    )
    SELECT jsonb_build_object(
        'hypothesis_count', count(*)::BIGINT,
        'hypothesis_status_counts', jsonb_build_object(
            'draft', count(*) FILTER (WHERE status = 'draft')::BIGINT,
            'active', count(*) FILTER (WHERE status = 'active')::BIGINT,
            'resolved', count(*) FILTER (WHERE status = 'resolved')::BIGINT,
            'retired', count(*) FILTER (WHERE status = 'retired')::BIGINT
        ),
        'evidence_event_count', (
            SELECT count(*)::BIGINT FROM public.decision_evidence_event AS event
            JOIN scoped_hypotheses AS scoped ON scoped.id = event.hypothesis_id
        ),
        'evidence_quality_counts', (
            SELECT jsonb_build_object(
                'unverified', count(*) FILTER (WHERE event.quality_status = 'unverified')::BIGINT,
                'provisional', count(*) FILTER (WHERE event.quality_status = 'provisional')::BIGINT,
                'verified', count(*) FILTER (WHERE event.quality_status = 'verified')::BIGINT,
                'rejected', count(*) FILTER (WHERE event.quality_status = 'rejected')::BIGINT,
                'stale', count(*) FILTER (WHERE event.quality_status = 'stale')::BIGINT
            ) FROM public.decision_evidence_event AS event
            JOIN scoped_hypotheses AS scoped ON scoped.id = event.hypothesis_id
        ),
        'applied_evidence_event_count', (
            SELECT count(DISTINCT update_row.evidence_event_id)::BIGINT
              FROM public.decision_posterior_update AS update_row
              JOIN scoped_hypotheses AS scoped ON scoped.id = update_row.hypothesis_id
        ),
        'posterior_update_count', (
            SELECT count(*)::BIGINT FROM public.decision_posterior_update AS update_row
            JOIN scoped_hypotheses AS scoped ON scoped.id = update_row.hypothesis_id
        ),
        'latest_decision_action_counts', (
            SELECT jsonb_build_object(
                'continue', count(*) FILTER (WHERE latest.action = 'continue')::BIGINT,
                'act', count(*) FILTER (WHERE latest.action = 'act')::BIGINT,
                'escalate', count(*) FILTER (WHERE latest.action = 'escalate')::BIGINT,
                'stop', count(*) FILTER (WHERE latest.action = 'stop')::BIGINT,
                'reject', count(*) FILTER (WHERE latest.action = 'reject')::BIGINT,
                'insufficient_evidence', count(*) FILTER (WHERE latest.action = 'insufficient_evidence')::BIGINT
            ) FROM (
                SELECT DISTINCT ON (evaluation.hypothesis_id)
                       evaluation.hypothesis_id, evaluation.action
                  FROM public.decision_threshold_evaluation AS evaluation
                  JOIN scoped_hypotheses AS scoped ON scoped.id = evaluation.hypothesis_id
                 ORDER BY evaluation.hypothesis_id, evaluation.evaluated_at DESC, evaluation.id DESC
            ) AS latest
        )
    ) INTO summary
    FROM scoped_hypotheses;

    RETURN summary;
END;
$$;

ALTER FUNCTION kokonut_security.location_sequential_decision_summary(UUID)
    OWNER TO kokonut_sequential_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_sequential_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_sequential_decision_summary(UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_sequential_decision_summary(UUID)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_sequential_decision_summary(UUID)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.location_sequential_decision_summary(UUID) IS
    'Returns aggregate hypothesis, evidence quality, posterior update, and latest decision counts for exact location-linked strategy plans, threats, and solutions under signed sequential_evidence:read context; statements, event IDs, values, likelihoods, probabilities, and identities are excluded.';

COMMIT;
