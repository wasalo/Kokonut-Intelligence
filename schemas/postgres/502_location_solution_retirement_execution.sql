-- Add exact-location retirement migration, sunset, and post-retirement review.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_retirement_execution_owner'
    ) THEN
        CREATE ROLE kokonut_solution_retirement_execution_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_retirement_execution_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution retirement execution owner role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_retirement_execution_owner'
            OR member_role.rolname = 'kokonut_solution_retirement_execution_owner'
    ) THEN
        RAISE EXCEPTION 'Solution retirement execution owner role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_retirement_transition_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    retirement_id UUID NOT NULL REFERENCES public.solution_retirement(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('migration_started', 'sunset', 'post_retirement_review')),
    previous_status TEXT NOT NULL,
    resulting_status TEXT NOT NULL,
    resulting_solution_stage TEXT NOT NULL,
    effective_at TIMESTAMPTZ NOT NULL,
    post_retirement_review_at DATE,
    note TEXT NOT NULL CHECK (pg_catalog.char_length(pg_catalog.btrim(note)) BETWEEN 10 AND 4000),
    evidence_refs JSONB NOT NULL
        CHECK (pg_catalog.jsonb_typeof(evidence_refs) = 'array'
               AND pg_catalog.jsonb_array_length(evidence_refs) BETWEEN 1 AND 100
               AND pg_catalog.octet_length(evidence_refs::TEXT) <= 65536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id),
    UNIQUE (retirement_id, action),
    CHECK (
        (action = 'migration_started' AND previous_status = 'approved'
         AND resulting_status = 'migration' AND post_retirement_review_at IS NULL)
        OR (action = 'sunset' AND previous_status = 'migration'
            AND resulting_status = 'sunset' AND resulting_solution_stage = 'retired'
            AND post_retirement_review_at IS NULL)
        OR (action = 'post_retirement_review' AND previous_status = 'sunset'
            AND resulting_status = 'completed' AND resulting_solution_stage = 'retired'
            AND post_retirement_review_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_solution_retirement_transition_timeline
    ON public.solution_retirement_transition_event (retirement_id, created_at, id);

REVOKE ALL ON TABLE public.solution_retirement_transition_event FROM PUBLIC;
DO $$
DECLARE
    target_role TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime', 'kokonut_solution_reader',
        'kokonut_solution_reviewer', 'kokonut_solution_action_owner',
        'kokonut_solution_proposal_owner'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.solution_retirement_transition_event FROM %I',
                target_role
            );
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_retirement_execution_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_retirement_execution_owner;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_retirement_execution_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_retirement_execution_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_retirement_execution_owner;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_retirement_execution_owner;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_retirement_execution_owner;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_retirement_execution_owner;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_retirement_execution_owner;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_retirement_execution_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_retirement_execution_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_retirement_execution_owner;

GRANT SELECT (id, originating_scope_type, originating_scope_id,
              current_stage, status, retired_at)
    ON TABLE public.solution TO kokonut_solution_retirement_execution_owner;
GRANT UPDATE (current_stage, status, retired_at, updated_at)
    ON TABLE public.solution TO kokonut_solution_retirement_execution_owner;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (id, solution_id, retirement_type, evidence_refs, migration_plan,
              status, created_by_party_id, approved_by_party_id, approved_at,
              effective_at, post_retirement_review_at)
    ON TABLE public.solution_retirement TO kokonut_solution_retirement_execution_owner;
GRANT UPDATE (status, effective_at, post_retirement_review_at)
    ON TABLE public.solution_retirement TO kokonut_solution_retirement_execution_owner;
GRANT UPDATE (id) ON TABLE public.solution_retirement
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (operator_id, proposer_party_id, location_id, retirement_id)
    ON TABLE public.solution_retirement_proposal_event
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT (operator_id, reviewer_party_id, location_id, retirement_id)
    ON TABLE public.solution_retirement_review_event
    TO kokonut_solution_retirement_execution_owner;
GRANT SELECT, INSERT ON TABLE public.solution_retirement_transition_event
    TO kokonut_solution_retirement_execution_owner;
GRANT INSERT (solution_id, from_stage, to_stage, rationale, evidence,
              actor_party_id, approved_by_party_id, created_at)
    ON TABLE public.solution_lifecycle_event
    TO kokonut_solution_retirement_execution_owner;

CREATE OR REPLACE FUNCTION kokonut_security.transition_location_solution_retirement(
    requested_location_id UUID,
    requested_retirement_id UUID,
    requested_request_id UUID,
    requested_action TEXT,
    requested_note TEXT,
    requested_evidence_refs JSONB,
    requested_effective_at TIMESTAMPTZ
)
RETURNS TABLE (
    event_id UUID,
    retirement_id UUID,
    action TEXT,
    retirement_status TEXT,
    solution_stage TEXT,
    effective_at TIMESTAMPTZ,
    post_retirement_review_at DATE,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    action_scope TEXT;
    prior_event RECORD;
    retirement RECORD;
    solution RECORD;
    migration_event_id UUID;
    sunset_actor_party_id UUID;
    resulting_status_value TEXT;
    resulting_stage_value TEXT;
    scheduled_effective_at TIMESTAMPTZ;
    completed_review_date DATE;
    transition_timestamp TIMESTAMPTZ;
    saved_event_id UUID;
BEGIN
    action_scope := CASE requested_action
        WHEN 'post_retirement_review' THEN 'review'
        WHEN 'migration_started' THEN 'transition'
        WHEN 'sunset' THEN 'transition'
        ELSE NULL
    END;
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF action_scope IS NULL OR context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_retirement_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Retirement transition requires a supported action and signed location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', action_scope, requested_location_id
    ) THEN
        RAISE EXCEPTION 'Retirement transition requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_note IS NULL
       OR pg_catalog.char_length(pg_catalog.btrim(requested_note)) NOT BETWEEN 10 AND 4000
       OR requested_evidence_refs IS NULL
       OR pg_catalog.jsonb_typeof(requested_evidence_refs) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_evidence_refs) NOT BETWEEN 1 AND 100
       OR pg_catalog.octet_length(requested_evidence_refs::TEXT) > 65536
       OR ((requested_action = 'migration_started') <> (requested_effective_at IS NOT NULL)) THEN
        RAISE EXCEPTION 'Retirement transition input is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id
      INTO actor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS human
        ON human.id = binding.party_id
       AND human.party_type = 'person' AND human.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, operator, human;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Retirement transition requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    SELECT transition.id, transition.location_id, transition.retirement_id,
           transition.action, transition.actor_party_id, transition.note,
           transition.evidence_refs, transition.effective_at,
           transition.previous_status, transition.resulting_status,
           transition.resulting_solution_stage, transition.post_retirement_review_at
      INTO prior_event
      FROM public.solution_retirement_transition_event AS transition
     WHERE transition.operator_id = context_record.actor_id
       AND transition.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_event.location_id IS DISTINCT FROM requested_location_id
           OR prior_event.retirement_id IS DISTINCT FROM requested_retirement_id
           OR prior_event.action IS DISTINCT FROM requested_action
           OR prior_event.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_event.note IS DISTINCT FROM pg_catalog.btrim(requested_note)
           OR prior_event.evidence_refs IS DISTINCT FROM requested_evidence_refs
           OR (requested_action = 'migration_started'
               AND prior_event.effective_at IS DISTINCT FROM requested_effective_at) THEN
            RAISE EXCEPTION 'Retirement transition request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        event_id := prior_event.id;
        retirement_id := prior_event.retirement_id;
        action := prior_event.action;
        retirement_status := prior_event.resulting_status;
        solution_stage := prior_event.resulting_solution_stage;
        effective_at := prior_event.effective_at;
        post_retirement_review_at := prior_event.post_retirement_review_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT item.id, item.solution_id, item.retirement_type, item.evidence_refs,
           item.migration_plan, item.status, item.created_by_party_id,
           item.approved_by_party_id, item.approved_at, item.effective_at,
           item.post_retirement_review_at, solution.current_stage,
           solution.status AS solution_status, solution.retired_at
      INTO retirement
      FROM public.solution_retirement AS item
      JOIN public.solution AS solution
        ON solution.id = item.solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     WHERE item.id = requested_retirement_id
     FOR UPDATE OF item, solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Retirement was not found for this location'
            USING ERRCODE = 'P0002';
    END IF;

    SELECT transition.id, transition.location_id, transition.retirement_id,
           transition.action, transition.actor_party_id, transition.note,
           transition.evidence_refs, transition.effective_at,
           transition.previous_status, transition.resulting_status,
           transition.resulting_solution_stage, transition.post_retirement_review_at
      INTO prior_event
      FROM public.solution_retirement_transition_event AS transition
     WHERE transition.operator_id = context_record.actor_id
       AND transition.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_event.location_id IS DISTINCT FROM requested_location_id
           OR prior_event.retirement_id IS DISTINCT FROM requested_retirement_id
           OR prior_event.action IS DISTINCT FROM requested_action
           OR prior_event.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_event.note IS DISTINCT FROM pg_catalog.btrim(requested_note)
           OR prior_event.evidence_refs IS DISTINCT FROM requested_evidence_refs
           OR (requested_action = 'migration_started'
               AND prior_event.effective_at IS DISTINCT FROM requested_effective_at) THEN
            RAISE EXCEPTION 'Retirement transition request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        event_id := prior_event.id;
        retirement_id := prior_event.retirement_id;
        action := prior_event.action;
        retirement_status := prior_event.resulting_status;
        solution_stage := prior_event.resulting_solution_stage;
        effective_at := prior_event.effective_at;
        post_retirement_review_at := prior_event.post_retirement_review_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    IF retirement.approved_at IS NULL OR retirement.approved_by_party_id IS NULL
       OR retirement.created_by_party_id IS NULL
       OR retirement.created_by_party_id = retirement.approved_by_party_id
       OR actor_party_id IN (retirement.created_by_party_id, retirement.approved_by_party_id) THEN
        RAISE EXCEPTION 'Retirement execution requires an independently approved proposal and a separate human actor'
            USING ERRCODE = '42501';
    END IF;
    IF pg_catalog.jsonb_typeof(retirement.evidence_refs) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(retirement.evidence_refs) = 0
       OR retirement.migration_plan IS NULL
       OR pg_catalog.btrim(retirement.migration_plan) = '' THEN
        RAISE EXCEPTION 'Retirement execution requires the approved evidence and migration plan'
            USING ERRCODE = '55000';
    END IF;

    transition_timestamp := pg_catalog.clock_timestamp();
    CASE requested_action
        WHEN 'migration_started' THEN
            IF retirement.status <> 'approved'
               OR requested_effective_at < transition_timestamp THEN
                RAISE EXCEPTION 'Only an approved retirement can begin migration with a current or future effective date'
                    USING ERRCODE = '55000';
            END IF;
            resulting_status_value := 'migration';
            resulting_stage_value := retirement.current_stage;
            scheduled_effective_at := requested_effective_at;
            completed_review_date := NULL;
            UPDATE public.solution_retirement AS item
               SET status = 'migration', effective_at = requested_effective_at
             WHERE item.id = requested_retirement_id AND item.status = 'approved';
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Retirement changed before migration began'
                    USING ERRCODE = '40001';
            END IF;
        WHEN 'sunset' THEN
            IF retirement.status <> 'migration'
               OR retirement.effective_at IS NULL
               OR retirement.effective_at > transition_timestamp THEN
                RAISE EXCEPTION 'Retirement cannot sunset before its approved effective date'
                    USING ERRCODE = '55000';
            END IF;
            SELECT transition.id INTO migration_event_id
              FROM public.solution_retirement_transition_event AS transition
             WHERE transition.retirement_id = requested_retirement_id
               AND transition.action = 'migration_started';
            IF NOT FOUND OR migration_event_id IS NULL THEN
                RAISE EXCEPTION 'Retirement migration-start record is missing'
                    USING ERRCODE = '55000';
            END IF;
            SELECT current_stage, status, retired_at
              INTO solution
              FROM public.solution
             WHERE id = retirement.solution_id
               AND originating_scope_type = 'location'
               AND originating_scope_id = requested_location_id
             FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Solution is not active for this retirement sunset'
                    USING ERRCODE = '55000';
            END IF;
            IF solution.current_stage = 'retired'
               OR solution.status NOT IN ('active', 'paused')
               OR solution.retired_at IS NOT NULL THEN
                RAISE EXCEPTION 'Solution is not active for this retirement sunset'
                    USING ERRCODE = '55000';
            END IF;
            resulting_status_value := 'sunset';
            resulting_stage_value := 'retired';
            scheduled_effective_at := retirement.effective_at;
            completed_review_date := NULL;
            UPDATE public.solution AS current_solution
               SET current_stage = 'retired', status = 'retired',
                   retired_at = transition_timestamp, updated_at = transition_timestamp
             WHERE current_solution.id = retirement.solution_id
               AND current_solution.current_stage IS DISTINCT FROM 'retired'
               AND current_solution.status IN ('active', 'paused')
               AND current_solution.retired_at IS NULL;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Solution changed before retirement sunset'
                    USING ERRCODE = '40001';
            END IF;
            UPDATE public.solution_retirement AS item
               SET status = 'sunset'
             WHERE item.id = requested_retirement_id AND item.status = 'migration';
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Retirement changed before sunset'
                    USING ERRCODE = '40001';
            END IF;
            INSERT INTO public.solution_lifecycle_event (
                solution_id, from_stage, to_stage, rationale, evidence,
                actor_party_id, approved_by_party_id, created_at
            ) VALUES (
                retirement.solution_id, solution.current_stage, 'retired',
                pg_catalog.btrim(requested_note), requested_evidence_refs,
                actor_party_id, retirement.approved_by_party_id, transition_timestamp
            );
        WHEN 'post_retirement_review' THEN
            IF retirement.status <> 'sunset'
               OR retirement.effective_at IS NULL
               OR retirement.effective_at > transition_timestamp
               OR retirement.post_retirement_review_at IS NOT NULL THEN
                RAISE EXCEPTION 'Only a sunset retirement can receive its post-retirement review'
                    USING ERRCODE = '55000';
            END IF;
            SELECT transition.actor_party_id INTO sunset_actor_party_id
              FROM public.solution_retirement_transition_event AS transition
             WHERE transition.retirement_id = requested_retirement_id
               AND transition.action = 'sunset';
            IF NOT FOUND OR sunset_actor_party_id IS NULL THEN
                RAISE EXCEPTION 'Retirement sunset record is missing'
                    USING ERRCODE = '55000';
            END IF;
            IF sunset_actor_party_id = actor_party_id THEN
                RAISE EXCEPTION 'Post-retirement reviewer must be distinct from the sunset operator'
                    USING ERRCODE = '42501';
            END IF;
            IF retirement.current_stage <> 'retired'
               OR retirement.solution_status <> 'retired'
               OR retirement.retired_at IS NULL THEN
                RAISE EXCEPTION 'Solution must be retired before its post-retirement review'
                    USING ERRCODE = '55000';
            END IF;
            resulting_status_value := 'completed';
            resulting_stage_value := 'retired';
            scheduled_effective_at := retirement.effective_at;
            completed_review_date := transition_timestamp::DATE;
            UPDATE public.solution_retirement AS item
               SET status = 'completed', post_retirement_review_at = completed_review_date
             WHERE item.id = requested_retirement_id
               AND item.status = 'sunset'
               AND item.post_retirement_review_at IS NULL;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Retirement changed before post-retirement review completed'
                    USING ERRCODE = '40001';
            END IF;
        ELSE
            RAISE EXCEPTION 'Unsupported retirement transition'
                USING ERRCODE = '22023';
    END CASE;

    INSERT INTO public.solution_retirement_transition_event (
        operator_id, actor_party_id, location_id, retirement_id, request_id,
        action, previous_status, resulting_status, resulting_solution_stage,
        effective_at, post_retirement_review_at, note, evidence_refs, created_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        requested_retirement_id, requested_request_id, requested_action,
        retirement.status, resulting_status_value, resulting_stage_value,
        scheduled_effective_at, completed_review_date,
        pg_catalog.btrim(requested_note), requested_evidence_refs,
        transition_timestamp
    ) RETURNING id INTO saved_event_id;

    event_id := saved_event_id;
    retirement_id := requested_retirement_id;
    action := requested_action;
    retirement_status := resulting_status_value;
    solution_stage := resulting_stage_value;
    effective_at := scheduled_effective_at;
    post_retirement_review_at := completed_review_date;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_retirement_execution_owner;
ALTER FUNCTION kokonut_security.transition_location_solution_retirement(
    UUID, UUID, UUID, TEXT, TEXT, JSONB, TIMESTAMPTZ
) OWNER TO kokonut_solution_retirement_execution_owner;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_retirement_execution_owner;
REVOKE ALL ON FUNCTION kokonut_security.transition_location_solution_retirement(
    UUID, UUID, UUID, TEXT, TEXT, JSONB, TIMESTAMPTZ
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.transition_location_solution_retirement(
            UUID, UUID, UUID, TEXT, TEXT, JSONB, TIMESTAMPTZ
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.transition_location_solution_retirement(
            UUID, UUID, UUID, TEXT, TEXT, JSONB, TIMESTAMPTZ
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_retirement_transition_event IS
'Append-only, exact-location receipts for migration start, effective-date sunset, and post-retirement review; retention and legal-hold disposition are governed by separately configurable policy and this migration does not delete data.';
COMMENT ON FUNCTION kokonut_security.transition_location_solution_retirement(
    UUID, UUID, UUID, TEXT, TEXT, JSONB, TIMESTAMPTZ
) IS
'Advances only an independently approved exact-location retirement through migration, effective-date sunset, and evidence-backed post-retirement review under signed transition/review scope; sunset sets solution lifecycle/status retired, review completes the retirement, and no data is deleted.';

COMMIT;
