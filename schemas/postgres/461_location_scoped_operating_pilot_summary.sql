-- Location-scoped, aggregate operating-pilot summary.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_operating_pilot_reader'
    ) THEN
        CREATE ROLE kokonut_operating_pilot_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_operating_pilot_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Operating pilot reader role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_operating_pilot_reader'
            OR member_role.rolname = 'kokonut_operating_pilot_reader'
    ) THEN
        RAISE EXCEPTION 'Operating pilot reader role must not have memberships';
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security FROM kokonut_operating_pilot_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM kokonut_operating_pilot_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM kokonut_operating_pilot_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM kokonut_operating_pilot_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security FROM kokonut_operating_pilot_reader;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_operating_pilot_reader;
GRANT SELECT (scope_type, scope_id, governance_circle_id, status)
    ON TABLE public.operating_pilot_scope TO kokonut_operating_pilot_reader;
GRANT SELECT (scope_type, scope_id, party_id, period_start, period_end, status,
              available_hours, committed_hours, protected_hours)
    ON TABLE public.operating_capacity_profile TO kokonut_operating_pilot_reader;
GRANT SELECT (scope_type, scope_id, period_start, period_end, status, required_hours)
    ON TABLE public.operating_demand_signal TO kokonut_operating_pilot_reader;
GRANT SELECT (party_id, governance_role_id, status, current_level, target_level)
    ON TABLE public.operating_competency_profile TO kokonut_operating_pilot_reader;
GRANT SELECT (party_id, scope_type, scope_id, status)
    ON TABLE public.operating_learning_plan TO kokonut_operating_pilot_reader;
GRANT SELECT (coachee_party_id, scope_type, scope_id, privacy_level)
    ON TABLE public.operating_coaching_session TO kokonut_operating_pilot_reader;
GRANT SELECT (requested_by_party_id, scope_type, scope_id, decision)
    ON TABLE public.operating_resource_request TO kokonut_operating_pilot_reader;
GRANT SELECT (id, circle_id, status)
    ON TABLE public.governance_role TO kokonut_operating_pilot_reader;
GRANT SELECT (id, location_id, status, allocation_status)
    ON TABLE public.work_item TO kokonut_operating_pilot_reader;
GRANT SELECT (work_item_id, claimant_party_id, status)
    ON TABLE public.work_item_claim TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, location_id, resource, action, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_operating_pilot_reader;
GRANT SELECT (id, enabled)
    ON TABLE public.operator_identity TO kokonut_operating_pilot_reader;
GRANT SELECT (id, organization_id)
    ON TABLE public.location TO kokonut_operating_pilot_reader;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification TO kokonut_operating_pilot_reader;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership TO kokonut_operating_pilot_reader;
GRANT SELECT (id, status)
    ON TABLE public.organization TO kokonut_operating_pilot_reader;
GRANT SELECT (id, location_id, status) ON TABLE public.farm
    TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_operating_pilot_reader;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_operating_pilot_reader;

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_summary(
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
        RAISE EXCEPTION 'Operating pilot projection requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Operating pilot projection requires an active location grant'
            USING ERRCODE = '42501';
    END IF;

    WITH active_scope AS (
        SELECT scope.scope_id, scope.governance_circle_id
          FROM public.operating_pilot_scope AS scope
          JOIN public.farm AS pilot_farm
            ON pilot_farm.id = scope.scope_id
           AND pilot_farm.location_id = requested_location_id
           AND pilot_farm.status = 'active'
         WHERE scope.scope_type = 'adelphi'
           AND scope.status = 'active'
    ),
    scoped_work AS (
        SELECT item.id, item.status::TEXT AS status, item.allocation_status
          FROM public.work_item AS item
         WHERE item.location_id = requested_location_id
           AND EXISTS (SELECT 1 FROM active_scope)
    )
    SELECT jsonb_build_object(
        'scope_configured', EXISTS (SELECT 1 FROM active_scope),
        'capacity_profiles', (
            SELECT jsonb_build_object(
                'as_of_date', CURRENT_DATE,
                'suppressed', aggregate.cohort_size BETWEEN 1 AND 2,
                'draft', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.draft END,
                'submitted', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.submitted END,
                'approved', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.approved END,
                'superseded', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.superseded END,
                'available_hours', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.available_hours END,
                'committed_hours', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.committed_hours END,
                'protected_hours', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.protected_hours END
            ) FROM (
                SELECT count(DISTINCT profile.party_id)::BIGINT AS cohort_size,
                    count(*) FILTER (WHERE profile.status = 'draft')::BIGINT AS draft,
                    count(*) FILTER (WHERE profile.status = 'submitted')::BIGINT AS submitted,
                    count(*) FILTER (WHERE profile.status = 'approved')::BIGINT AS approved,
                    count(*) FILTER (WHERE profile.status = 'superseded')::BIGINT AS superseded,
                    COALESCE(sum(profile.available_hours)
                        FILTER (WHERE profile.status IN ('submitted', 'approved')), 0) AS available_hours,
                    COALESCE(sum(profile.committed_hours)
                        FILTER (WHERE profile.status IN ('submitted', 'approved')), 0) AS committed_hours,
                    COALESCE(sum(profile.protected_hours)
                        FILTER (WHERE profile.status IN ('submitted', 'approved')), 0) AS protected_hours
                FROM public.operating_capacity_profile AS profile
                WHERE profile.scope_type = 'adelphi'
                  AND profile.scope_id IN (SELECT scope_id FROM active_scope)
                  AND profile.period_start <= CURRENT_DATE
                  AND profile.period_end >= CURRENT_DATE
                  AND EXISTS (SELECT 1 FROM active_scope)
            ) AS aggregate
        ),
        'demand_signals', (
            SELECT jsonb_build_object(
                'as_of_date', CURRENT_DATE,
                'draft', count(*) FILTER (WHERE signal.status = 'draft')::BIGINT,
                'submitted', count(*) FILTER (WHERE signal.status = 'submitted')::BIGINT,
                'approved', count(*) FILTER (WHERE signal.status = 'approved')::BIGINT,
                'fulfilled', count(*) FILTER (WHERE signal.status = 'fulfilled')::BIGINT,
                'cancelled', count(*) FILTER (WHERE signal.status = 'cancelled')::BIGINT,
                'required_hours', COALESCE(sum(signal.required_hours)
                    FILTER (WHERE signal.status IN ('submitted', 'approved')), 0)
            ) FROM public.operating_demand_signal AS signal
            WHERE signal.scope_type = 'adelphi'
              AND signal.scope_id IN (SELECT scope_id FROM active_scope)
              AND signal.period_start <= CURRENT_DATE
              AND signal.period_end >= CURRENT_DATE
              AND EXISTS (SELECT 1 FROM active_scope)
        ),
        'work_items', (
            SELECT jsonb_build_object(
                'total', count(*)::BIGINT,
                'open', count(*) FILTER (WHERE allocation_status = 'open')::BIGINT,
                'claimed', count(*) FILTER (WHERE allocation_status = 'claimed')::BIGINT,
                'allocated', count(*) FILTER (WHERE allocation_status = 'allocated')::BIGINT,
                'paused', count(*) FILTER (WHERE allocation_status = 'paused')::BIGINT,
                'closed', count(*) FILTER (WHERE allocation_status = 'closed')::BIGINT
            ) FROM scoped_work
        ),
        'work_claims', (
            SELECT jsonb_build_object(
                'suppressed', aggregate.cohort_size BETWEEN 1 AND 2,
                'proposed', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.proposed END,
                'accepted', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.accepted END,
                'rejected', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.rejected END,
                'withdrawn', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.withdrawn END
            ) FROM (
                SELECT count(DISTINCT claim.claimant_party_id)::BIGINT AS cohort_size,
                    count(*) FILTER (WHERE claim.status = 'proposed')::BIGINT AS proposed,
                    count(*) FILTER (WHERE claim.status = 'accepted')::BIGINT AS accepted,
                    count(*) FILTER (WHERE claim.status = 'rejected')::BIGINT AS rejected,
                    count(*) FILTER (WHERE claim.status = 'withdrawn')::BIGINT AS withdrawn
                FROM public.work_item_claim AS claim
                JOIN scoped_work AS work ON work.id = claim.work_item_id
            ) AS aggregate
        ),
        'competency_reviews', (
            SELECT jsonb_build_object(
                'suppressed', aggregate.cohort_size BETWEEN 1 AND 2,
                'submitted', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.submitted END,
                'verified', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.verified END,
                'open_gap', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.open_gap END
            ) FROM (
                SELECT count(DISTINCT profile.party_id)::BIGINT AS cohort_size,
                    count(*) FILTER (WHERE profile.status = 'submitted')::BIGINT AS submitted,
                    count(*) FILTER (WHERE profile.status = 'verified')::BIGINT AS verified,
                    count(*) FILTER (
                        WHERE profile.status IN ('submitted', 'verified')
                          AND profile.target_level > profile.current_level
                    )::BIGINT AS open_gap
                FROM public.operating_competency_profile AS profile
                JOIN public.governance_role AS role ON role.id = profile.governance_role_id
                JOIN active_scope AS scope ON scope.governance_circle_id = role.circle_id
                WHERE role.status = 'active'
            ) AS aggregate
        ),
        'learning_plans', (
            SELECT jsonb_build_object(
                'suppressed', aggregate.cohort_size BETWEEN 1 AND 2,
                'draft', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.draft END,
                'submitted', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.submitted END,
                'active', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.active END,
                'completed', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.completed END,
                'paused', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.paused END,
                'cancelled', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.cancelled END
            ) FROM (
                SELECT count(DISTINCT plan.party_id)::BIGINT AS cohort_size,
                    count(*) FILTER (WHERE plan.status = 'draft')::BIGINT AS draft,
                    count(*) FILTER (WHERE plan.status = 'submitted')::BIGINT AS submitted,
                    count(*) FILTER (WHERE plan.status = 'active')::BIGINT AS active,
                    count(*) FILTER (WHERE plan.status = 'completed')::BIGINT AS completed,
                    count(*) FILTER (WHERE plan.status = 'paused')::BIGINT AS paused,
                    count(*) FILTER (WHERE plan.status = 'cancelled')::BIGINT AS cancelled
                FROM public.operating_learning_plan AS plan
                WHERE plan.scope_type = 'adelphi'
                  AND plan.scope_id IN (SELECT scope_id FROM active_scope)
                  AND EXISTS (SELECT 1 FROM active_scope)
            ) AS aggregate
        ),
        'resource_requests', (
            SELECT jsonb_build_object(
                'suppressed', aggregate.cohort_size BETWEEN 1 AND 2,
                'pending', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.pending END,
                'approved', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.approved END,
                'partially_approved', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.partially_approved END,
                'declined', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.declined END,
                'fulfilled', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.fulfilled END
            ) FROM (
                SELECT count(DISTINCT request.requested_by_party_id)::BIGINT AS cohort_size,
                    count(*) FILTER (WHERE request.decision = 'pending')::BIGINT AS pending,
                    count(*) FILTER (WHERE request.decision = 'approved')::BIGINT AS approved,
                    count(*) FILTER (WHERE request.decision = 'partially_approved')::BIGINT AS partially_approved,
                    count(*) FILTER (WHERE request.decision = 'declined')::BIGINT AS declined,
                    count(*) FILTER (WHERE request.decision = 'fulfilled')::BIGINT AS fulfilled
                FROM public.operating_resource_request AS request
                WHERE request.scope_type = 'adelphi'
                  AND request.scope_id IN (SELECT scope_id FROM active_scope)
                  AND EXISTS (SELECT 1 FROM active_scope)
            ) AS aggregate
        ),
        'aggregate_only_coaching_sessions', (
            SELECT jsonb_build_object(
                'suppressed', aggregate.cohort_size BETWEEN 1 AND 2,
                'count', CASE WHEN aggregate.cohort_size BETWEEN 1 AND 2 THEN NULL
                    ELSE aggregate.session_count END
            ) FROM (
                SELECT count(DISTINCT session.coachee_party_id)::BIGINT AS cohort_size,
                    count(*)::BIGINT AS session_count
                FROM public.operating_coaching_session AS session
                WHERE session.scope_type = 'adelphi'
                  AND session.scope_id IN (SELECT scope_id FROM active_scope)
                  AND session.privacy_level = 'aggregate_only'
                  AND EXISTS (SELECT 1 FROM active_scope)
            ) AS aggregate
        )
    ) INTO summary;

    RETURN summary;
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_summary(UUID)
    OWNER TO kokonut_operating_pilot_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_summary(UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_summary(UUID)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_summary(UUID)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.location_operating_pilot_summary(UUID) IS
    'Returns aggregate Adelphi capacity, demand, work claims, competency review, learning, resource-request, and aggregate-only coaching state for a location whose active Adelphi pilot scope maps through an active farm row; sensitive participant cohorts below three and private coaching are excluded.';

COMMIT;
