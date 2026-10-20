-- Privately review and independently approve submitted experiment protocols.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_protocol_reviewer'
    ) THEN
        CREATE ROLE kokonut_solution_experiment_protocol_reviewer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_protocol_reviewer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution experiment protocol reviewer role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_experiment_protocol_reviewer'
            OR member_role.rolname = 'kokonut_solution_experiment_protocol_reviewer'
    ) THEN
        RAISE EXCEPTION 'Solution experiment protocol reviewer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_experiment_protocol_approval_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    submitter_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    experiment_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_experiment(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    approved_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_experiment_protocol_approval_receipt FROM PUBLIC;
DO $$
DECLARE target_role TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime',
        'kokonut_solution_experiment_protocol_reviewer'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.solution_experiment_protocol_approval_receipt FROM %I',
                target_role
            );
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_experiment_protocol_reviewer;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_experiment_protocol_reviewer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_experiment_protocol_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_experiment_protocol_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_experiment_protocol_reviewer;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_experiment_protocol_reviewer;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (id, name, solution_type, originating_scope_type, originating_scope_id,
              current_stage, status)
    ON TABLE public.solution TO kokonut_solution_experiment_protocol_reviewer;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (
    id, solution_id, hypothesis, null_hypothesis, protocol_version,
    baseline_definition, treatment_definition, comparator_definition,
    unit_of_analysis, sample_plan, primary_metric_keys, secondary_metric_keys,
    minimum_detectable_effect, confidence_target, duration_days, stopping_rules,
    rollback_plan, safety_boundaries, consent_requirements, owner_party_id, status,
    approved_by_party_id, approved_at, created_at
) ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT UPDATE (status, approved_by_party_id, approved_at, updated_at)
    ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (
    operator_id, actor_party_id, location_id, solution_id, experiment_id,
    request_id, payload_digest, submitted_at
) ON TABLE public.solution_experiment_submission_receipt
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT SELECT (
    id, operator_id, reviewer_party_id, submitter_party_id, location_id,
    solution_id, experiment_id, request_id, payload_digest, approved_at
) ON TABLE public.solution_experiment_protocol_approval_receipt
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT INSERT (
    operator_id, reviewer_party_id, submitter_party_id, location_id,
    solution_id, experiment_id, request_id, payload_digest, approved_at
) ON TABLE public.solution_experiment_protocol_approval_receipt
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_experiment_protocol_reviewer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_experiment_protocol_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_experiment_protocol_review(
    requested_location_id UUID,
    requested_experiment_id UUID
)
RETURNS TABLE (
    experiment_id UUID,
    solution_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    current_stage TEXT,
    protocol JSONB,
    submitted_at TIMESTAMPTZ,
    owner_is_reviewer BOOLEAN,
    submitter_is_reviewer BOOLEAN
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    reviewer_party_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_experiment_id IS NULL THEN
        RAISE EXCEPTION 'Protocol review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Protocol review requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id
      INTO reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id
       AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Protocol review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT experiment.id,
           solution.id,
           pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT,
           solution.current_stage::TEXT,
           pg_catalog.jsonb_build_object(
               'hypothesis', pg_catalog.left(experiment.hypothesis, 4000),
               'null_hypothesis', pg_catalog.left(experiment.null_hypothesis, 4000),
               'protocol_version', pg_catalog.left(experiment.protocol_version, 40),
               'baseline_definition', pg_catalog.left(experiment.baseline_definition, 4000),
               'treatment_definition', pg_catalog.left(experiment.treatment_definition, 4000),
               'comparator_definition', pg_catalog.left(experiment.comparator_definition, 4000),
               'unit_of_analysis', pg_catalog.left(experiment.unit_of_analysis, 255),
               'sample_plan', CASE WHEN pg_catalog.octet_length(experiment.sample_plan::TEXT) <= 8192
                                   THEN experiment.sample_plan ELSE '{"truncated":true}'::JSONB END,
               'primary_metric_keys', CASE WHEN pg_catalog.octet_length(experiment.primary_metric_keys::TEXT) <= 8192
                                           THEN experiment.primary_metric_keys ELSE '{"truncated":true}'::JSONB END,
               'secondary_metric_keys', CASE WHEN pg_catalog.octet_length(experiment.secondary_metric_keys::TEXT) <= 8192
                                             THEN experiment.secondary_metric_keys ELSE '{"truncated":true}'::JSONB END,
               'minimum_detectable_effect', experiment.minimum_detectable_effect,
               'confidence_target', experiment.confidence_target,
               'duration_days', experiment.duration_days,
               'stopping_rules', CASE WHEN pg_catalog.octet_length(experiment.stopping_rules::TEXT) <= 8192
                                      THEN experiment.stopping_rules ELSE '{"truncated":true}'::JSONB END,
               'rollback_plan', pg_catalog.left(experiment.rollback_plan, 4000),
               'safety_boundaries', CASE WHEN pg_catalog.octet_length(experiment.safety_boundaries::TEXT) <= 8192
                                         THEN experiment.safety_boundaries ELSE '{"truncated":true}'::JSONB END,
               'consent_requirements', CASE WHEN pg_catalog.octet_length(experiment.consent_requirements::TEXT) <= 8192
                                            THEN experiment.consent_requirements ELSE '{"truncated":true}'::JSONB END,
               'status', experiment.status,
               'created_at', experiment.created_at
           ),
           submission.submitted_at,
           experiment.owner_party_id = reviewer_party_id,
           submission.actor_party_id = reviewer_party_id
      FROM public.solution_experiment AS experiment
      JOIN public.solution AS solution ON solution.id = experiment.solution_id
      JOIN public.solution_experiment_submission_receipt AS submission
        ON submission.experiment_id = experiment.id
       AND submission.location_id = requested_location_id
     WHERE experiment.id = requested_experiment_id
       AND experiment.status = 'submitted'
       AND solution.status = 'active'
       AND solution.current_stage IN ('experiment_ready', 'testing')
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submitted exact-location experiment protocol was not found'
            USING ERRCODE = 'P0002';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.approve_location_solution_experiment_protocol(
    requested_location_id UUID,
    requested_experiment_id UUID,
    requested_request_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    experiment_id UUID,
    solution_id UUID,
    experiment_status TEXT,
    approved_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    reviewer_party_id UUID;
    experiment_record RECORD;
    submission_record RECORD;
    prior_receipt RECORD;
    payload_digest BYTEA;
    approval_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_experiment_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Protocol approval requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Protocol approval requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Protocol approval requires explicit acknowledgement'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id
      INTO reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id
       AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, reviewer;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Protocol approval requires an active human identity'
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
    SELECT receipt.location_id, receipt.solution_id, receipt.reviewer_party_id,
           receipt.experiment_id, receipt.payload_digest, receipt.approved_at
      INTO prior_receipt
      FROM public.solution_experiment_protocol_approval_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.experiment_id IS DISTINCT FROM requested_experiment_id
           OR prior_receipt.reviewer_party_id IS DISTINCT FROM reviewer_party_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Protocol approval request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT requested_experiment_id, prior_receipt.solution_id,
                            'protocol_approved'::TEXT, prior_receipt.approved_at, TRUE;
        RETURN;
    END IF;

    SELECT experiment.id, experiment.solution_id, experiment.owner_party_id,
           solution.current_stage, solution.status AS solution_status
      INTO experiment_record
      FROM public.solution_experiment AS experiment
      JOIN public.solution AS solution ON solution.id = experiment.solution_id
     WHERE experiment.id = requested_experiment_id
       AND experiment.status = 'submitted'
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR UPDATE OF experiment, solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Submitted exact-location experiment protocol was not found'
            USING ERRCODE = 'P0002';
    END IF;
    SELECT submission.actor_party_id
      INTO submission_record
      FROM public.solution_experiment_submission_receipt AS submission
     WHERE submission.experiment_id = requested_experiment_id
       AND submission.location_id = requested_location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Protocol has no attributable Kernel submission'
            USING ERRCODE = '55000';
    END IF;
    IF reviewer_party_id = experiment_record.owner_party_id
       OR reviewer_party_id = submission_record.actor_party_id THEN
        RAISE EXCEPTION 'Protocol approval requires a reviewer independent from owner and submitter'
            USING ERRCODE = '42501';
    END IF;
    IF experiment_record.solution_status IS DISTINCT FROM 'active'
       OR experiment_record.current_stage NOT IN ('experiment_ready', 'testing') THEN
        RAISE EXCEPTION 'The source solution is no longer eligible for experiment approval'
            USING ERRCODE = '55000';
    END IF;

    approval_time := pg_catalog.clock_timestamp();
    UPDATE public.solution_experiment AS experiment
       SET status = 'protocol_approved',
           approved_by_party_id = reviewer_party_id,
           approved_at = approval_time,
           updated_at = approval_time
     WHERE experiment.id = requested_experiment_id
       AND experiment.status = 'submitted';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Experiment protocol changed before approval'
            USING ERRCODE = '40001';
    END IF;

    INSERT INTO public.solution_experiment_protocol_approval_receipt (
        operator_id, reviewer_party_id, submitter_party_id, location_id,
        solution_id, experiment_id, request_id, payload_digest, approved_at
    ) VALUES (
        context_record.actor_id, reviewer_party_id, submission_record.actor_party_id,
        requested_location_id, experiment_record.solution_id, requested_experiment_id,
        requested_request_id, payload_digest, approval_time
    );
    RETURN QUERY SELECT requested_experiment_id, experiment_record.solution_id,
                        'protocol_approved'::TEXT, approval_time, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_experiment_protocol_reviewer;
ALTER FUNCTION kokonut_security.location_solution_experiment_protocol_review(UUID, UUID)
    OWNER TO kokonut_solution_experiment_protocol_reviewer;
ALTER FUNCTION kokonut_security.approve_location_solution_experiment_protocol(
    UUID, UUID, UUID, BOOLEAN
) OWNER TO kokonut_solution_experiment_protocol_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_experiment_protocol_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_experiment_protocol_review(UUID, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.approve_location_solution_experiment_protocol(
    UUID, UUID, UUID, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.location_solution_experiment_protocol_review(
            UUID, UUID
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.approve_location_solution_experiment_protocol(
            UUID, UUID, UUID, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_solution_experiment_protocol_review(
            UUID, UUID
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.approve_location_solution_experiment_protocol(
            UUID, UUID, UUID, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_experiment_protocol_approval_receipt IS
    'Private append-only receipts for independent exact-location experiment protocol approval.';
COMMENT ON FUNCTION kokonut_security.location_solution_experiment_protocol_review(UUID, UUID) IS
    'Returns bounded private protocol details only for a submitted Kernel protocol under an exact signed location review grant; party identities are withheld and reviewer conflicts are returned as booleans.';
COMMENT ON FUNCTION kokonut_security.approve_location_solution_experiment_protocol(UUID, UUID, UUID, BOOLEAN) IS
    'Approves an attributable exact-location submitted protocol only under signed location review context and an active human distinct from owner and submitter. Approval does not start the experiment or change the solution stage.';

COMMIT;
