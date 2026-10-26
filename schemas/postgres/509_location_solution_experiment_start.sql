-- Start an independently approved exact-location experiment under a bounded Gateway action.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_starter'
    ) THEN
        CREATE ROLE kokonut_solution_experiment_starter
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_starter'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution experiment starter role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_experiment_starter'
            OR member_role.rolname = 'kokonut_solution_experiment_starter'
    ) THEN
        RAISE EXCEPTION 'Solution experiment starter role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_experiment_start_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    experiment_id UUID NOT NULL UNIQUE REFERENCES public.solution_experiment(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    started_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_experiment_start_receipt FROM PUBLIC;
DO $$
DECLARE target_role TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime',
        'kokonut_solution_experiment_starter'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.solution_experiment_start_receipt FROM %I',
                target_role
            );
        END IF;
    END LOOP;
END;
$$;

-- Protocol review and start use SECURITY DEFINER owners. The shared runtime
-- role no longer needs direct lifecycle updates that would bypass their
-- signed location scope, reviewer checks, or immutable receipts.
DO $$
DECLARE target_role TEXT; target_column TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role
        ) THEN
            EXECUTE pg_catalog.format(
                'REVOKE UPDATE ON TABLE public.solution_experiment FROM %I',
                target_role
            );
            FOR target_column IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.solution_experiment'::regclass
                   AND attribute.attnum > 0 AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE UPDATE (%I) ON TABLE public.solution_experiment FROM %I',
                    target_column, target_role
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_experiment_starter;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_experiment_starter;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_experiment_starter;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_experiment_starter;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_experiment_starter;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_experiment_starter;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_starter;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_starter;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_starter;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_starter;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_experiment_starter;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_experiment_starter;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_experiment_starter;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_experiment_starter;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_experiment_starter;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_experiment_starter;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_experiment_starter;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_experiment_starter;
GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage, status)
    ON TABLE public.solution TO kokonut_solution_experiment_starter;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_experiment_starter;
GRANT SELECT (
    id, solution_id, owner_party_id, approved_by_party_id, approved_at,
    status, started_at
) ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_starter;
GRANT UPDATE (status, started_at, updated_at)
    ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_starter;
GRANT SELECT (location_id, solution_id, experiment_id, reviewer_party_id)
    ON TABLE public.solution_experiment_protocol_approval_receipt
    TO kokonut_solution_experiment_starter;
GRANT SELECT (
    id, operator_id, actor_party_id, location_id, solution_id, experiment_id,
    request_id, payload_digest, started_at
) ON TABLE public.solution_experiment_start_receipt
    TO kokonut_solution_experiment_starter;
GRANT INSERT (
    operator_id, actor_party_id, location_id, solution_id, experiment_id,
    request_id, payload_digest, started_at
) ON TABLE public.solution_experiment_start_receipt
    TO kokonut_solution_experiment_starter;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_experiment_starter;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_experiment_starter;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_experiment_starter;

CREATE OR REPLACE FUNCTION kokonut_security.start_location_solution_experiment(
    requested_location_id UUID,
    requested_experiment_id UUID,
    requested_request_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    experiment_id UUID,
    solution_id UUID,
    experiment_status TEXT,
    started_at TIMESTAMPTZ,
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
    experiment_record RECORD;
    approval_record RECORD;
    prior_receipt RECORD;
    payload_digest BYTEA;
    start_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_experiment_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Experiment start requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'transition', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Experiment start requires an active exact location transition grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Experiment start requires explicit acknowledgement'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id
      INTO actor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id
       AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, actor;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Experiment start requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'experiment_id', requested_experiment_id,
                'acknowledged', requested_acknowledged
            )::TEXT,
            'UTF8'
        ),
        'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.solution_id, receipt.actor_party_id,
           receipt.experiment_id, receipt.payload_digest, receipt.started_at
      INTO prior_receipt
      FROM public.solution_experiment_start_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.experiment_id IS DISTINCT FROM requested_experiment_id
           OR prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Experiment start request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT requested_experiment_id, prior_receipt.solution_id,
                            'active'::TEXT, prior_receipt.started_at, TRUE;
        RETURN;
    END IF;

    SELECT experiment.id, experiment.solution_id, experiment.status,
           experiment.approved_by_party_id, experiment.approved_at,
           solution.current_stage, solution.status AS solution_status
      INTO experiment_record
      FROM public.solution_experiment AS experiment
      JOIN public.solution AS solution ON solution.id = experiment.solution_id
     WHERE experiment.id = requested_experiment_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR UPDATE OF experiment, solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location experiment was not found'
            USING ERRCODE = 'P0002';
    END IF;
    SELECT receipt.location_id, receipt.solution_id, receipt.reviewer_party_id
      INTO approval_record
      FROM public.solution_experiment_protocol_approval_receipt AS receipt
     WHERE receipt.experiment_id = requested_experiment_id
       AND receipt.location_id = requested_location_id
       AND receipt.solution_id = experiment_record.solution_id;
    IF experiment_record.status IS DISTINCT FROM 'protocol_approved'
       OR experiment_record.approved_at IS NULL
       OR experiment_record.approved_by_party_id IS DISTINCT FROM approval_record.reviewer_party_id
       OR experiment_record.solution_status IS DISTINCT FROM 'active'
       OR experiment_record.current_stage NOT IN ('experiment_ready', 'testing')
       OR NOT FOUND THEN
        RAISE EXCEPTION 'Only an independently approved, eligible protocol can start'
            USING ERRCODE = '55000';
    END IF;

    start_time := pg_catalog.clock_timestamp();
    UPDATE public.solution_experiment AS experiment
       SET status = 'active', started_at = start_time, updated_at = start_time
     WHERE experiment.id = requested_experiment_id
       AND experiment.status = 'protocol_approved';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Experiment protocol changed before start'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.solution_experiment_start_receipt (
        operator_id, actor_party_id, location_id, solution_id, experiment_id,
        request_id, payload_digest, started_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        experiment_record.solution_id, requested_experiment_id,
        requested_request_id, payload_digest, start_time
    );
    RETURN QUERY SELECT requested_experiment_id, experiment_record.solution_id,
                        'active'::TEXT, start_time, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_experiment_starter;
ALTER FUNCTION kokonut_security.start_location_solution_experiment(
    UUID, UUID, UUID, BOOLEAN
) OWNER TO kokonut_solution_experiment_starter;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_experiment_starter;
REVOKE ALL ON FUNCTION kokonut_security.start_location_solution_experiment(
    UUID, UUID, UUID, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.start_location_solution_experiment(
            UUID, UUID, UUID, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.start_location_solution_experiment(
            UUID, UUID, UUID, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_experiment_start_receipt IS
    'Private append-only receipts for exact-location start of independently approved experiment protocols.';
COMMENT ON FUNCTION kokonut_security.start_location_solution_experiment(UUID, UUID, UUID, BOOLEAN) IS
    'Starts an independently approved exact-location experiment under signed transition scope. It records no participant consent, observations, analysis, or solution-stage transition.';

COMMIT;
