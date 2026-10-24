-- Submit an authored experiment protocol for separate human approval.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_submitter'
    ) THEN
        CREATE ROLE kokonut_solution_experiment_submitter
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_submitter'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution experiment submitter role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_experiment_submitter'
            OR member_role.rolname = 'kokonut_solution_experiment_submitter'
    ) THEN
        RAISE EXCEPTION 'Solution experiment submitter role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_experiment_submission_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    experiment_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_experiment(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    submitted_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_experiment_submission_receipt FROM PUBLIC;
DO $$
DECLARE target_role TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime',
        'kokonut_solution_experiment_submitter'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.solution_experiment_submission_receipt FROM %I',
                target_role
            );
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_experiment_submitter;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_experiment_submitter;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_experiment_submitter;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_experiment_submitter;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_experiment_submitter;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_experiment_submitter;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_submitter;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_submitter;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_experiment_submitter;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage, status)
    ON TABLE public.solution TO kokonut_solution_experiment_submitter;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (id, solution_id, owner_party_id, status)
    ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_submitter;
GRANT UPDATE (status, updated_at)
    ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_submitter;
GRANT SELECT (
    id, operator_id, actor_party_id, location_id, solution_id, experiment_id,
    request_id, payload_digest, submitted_at
) ON TABLE public.solution_experiment_submission_receipt
    TO kokonut_solution_experiment_submitter;
GRANT INSERT (
    operator_id, actor_party_id, location_id, solution_id, experiment_id,
    request_id, payload_digest, submitted_at
) ON TABLE public.solution_experiment_submission_receipt
    TO kokonut_solution_experiment_submitter;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_experiment_submitter;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_experiment_submitter;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_experiment_submitter;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_solution_experiment_protocol(
    requested_location_id UUID,
    requested_experiment_id UUID,
    requested_request_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    experiment_id UUID,
    solution_id UUID,
    experiment_status TEXT,
    submitted_at TIMESTAMPTZ,
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
    prior_receipt RECORD;
    payload_digest BYTEA;
    submission_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_experiment_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Experiment submission requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'submit', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Experiment submission requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Experiment submission requires explicit acknowledgement'
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
        RAISE EXCEPTION 'Experiment submission requires an active human identity'
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
           receipt.experiment_id, receipt.payload_digest, receipt.submitted_at
      INTO prior_receipt
      FROM public.solution_experiment_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.experiment_id IS DISTINCT FROM requested_experiment_id
           OR prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Experiment submission request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT requested_experiment_id, prior_receipt.solution_id,
                            'submitted'::TEXT, prior_receipt.submitted_at, TRUE;
        RETURN;
    END IF;

    SELECT experiment.id, experiment.solution_id, experiment.owner_party_id,
           experiment.status, solution.current_stage, solution.status AS solution_status
      INTO experiment_record
      FROM public.solution_experiment AS experiment
      JOIN public.solution AS solution ON solution.id = experiment.solution_id
     WHERE experiment.id = requested_experiment_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR UPDATE OF experiment, solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location experiment protocol was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF experiment_record.owner_party_id IS DISTINCT FROM actor_party_id THEN
        RAISE EXCEPTION 'Only the active human protocol owner can submit this experiment'
            USING ERRCODE = '42501';
    END IF;
    IF experiment_record.status IS DISTINCT FROM 'draft'
       OR experiment_record.solution_status IS DISTINCT FROM 'active'
       OR experiment_record.current_stage NOT IN ('experiment_ready', 'testing') THEN
        RAISE EXCEPTION 'Only an eligible draft protocol can be submitted'
            USING ERRCODE = '55000';
    END IF;

    submission_time := pg_catalog.clock_timestamp();
    UPDATE public.solution_experiment AS experiment
       SET status = 'submitted', updated_at = submission_time
     WHERE experiment.id = requested_experiment_id
       AND experiment.status = 'draft';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Experiment protocol changed before submission'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.solution_experiment_submission_receipt (
        operator_id, actor_party_id, location_id, solution_id, experiment_id,
        request_id, payload_digest, submitted_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        experiment_record.solution_id, requested_experiment_id,
        requested_request_id, payload_digest, submission_time
    );
    RETURN QUERY SELECT requested_experiment_id, experiment_record.solution_id,
                        'submitted'::TEXT, submission_time, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_experiment_submitter;
ALTER FUNCTION kokonut_security.submit_location_solution_experiment_protocol(
    UUID, UUID, UUID, BOOLEAN
) OWNER TO kokonut_solution_experiment_submitter;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_experiment_submitter;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_experiment_protocol(
    UUID, UUID, UUID, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_solution_experiment_protocol(
            UUID, UUID, UUID, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_experiment_protocol(
            UUID, UUID, UUID, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_experiment_submission_receipt IS
    'Private append-only idempotency receipts for exact-location owner-submitted experiment protocols.';
COMMENT ON FUNCTION kokonut_security.submit_location_solution_experiment_protocol(
    UUID, UUID, UUID, BOOLEAN
) IS 'Submits an exact-location experiment draft owned by the active bound human under signed solution_lifecycle:submit context. Submission does not approve, consent, start, observe, analyze, or complete the experiment.';

COMMIT;
