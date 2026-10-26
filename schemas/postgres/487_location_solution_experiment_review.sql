-- Private exact-location experiment review and independent result recording.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_reviewer'
    ) THEN
        EXECUTE 'CREATE ROLE kokonut_solution_experiment_reviewer '
                'NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE '
                'NOREPLICATION NOBYPASSRLS';
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_reviewer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution experiment reviewer role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_experiment_reviewer'
            OR member_role.rolname = 'kokonut_solution_experiment_reviewer'
    ) THEN
        RAISE EXCEPTION 'Solution experiment reviewer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_experiment_review_submission_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    experiment_id UUID NOT NULL UNIQUE REFERENCES public.solution_experiment(id) ON DELETE RESTRICT,
    result_id UUID NOT NULL UNIQUE REFERENCES public.solution_experiment_result(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload JSONB NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_experiment_review_submission_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_experiment_review_submission_receipt
    FROM kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_experiment_reviewer;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_experiment_reviewer;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_experiment_reviewer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_experiment_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_experiment_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_experiment_reviewer;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_experiment_reviewer;

GRANT SELECT (id, name, solution_type, current_stage, originating_scope_type,
              originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_experiment_reviewer;
GRANT SELECT (id, solution_id, status, hypothesis, null_hypothesis,
              protocol_version, baseline_definition, treatment_definition,
              comparator_definition, unit_of_analysis, sample_plan,
              primary_metric_keys, secondary_metric_keys, stopping_rules,
              rollback_plan, safety_boundaries, consent_requirements,
              owner_party_id, approved_by_party_id, approved_at, started_at,
              completed_at, created_at, updated_at)
    ON TABLE public.solution_experiment TO kokonut_solution_experiment_reviewer;
GRANT UPDATE (id, status, updated_at)
    ON TABLE public.solution_experiment TO kokonut_solution_experiment_reviewer;
GRANT SELECT (experiment_id, observed_at, metric_key, value, arm, adverse_event,
              evidence)
    ON TABLE public.solution_experiment_observation
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (experiment_id, metric_key, baseline_count, treatment_count,
              baseline_mean, treatment_mean, effect_estimate, standard_error,
              lower_bound, upper_bound, posterior_probability_benefit,
              adverse_event_count, decision, stopping_reason, analysis_version,
              created_at, id)
    ON TABLE public.solution_experiment_analysis_run
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (id, experiment_id, reviewed_at)
    ON TABLE public.solution_experiment_result
    TO kokonut_solution_experiment_reviewer;
GRANT INSERT (experiment_id, outcome, primary_results, secondary_results,
              limitations, evidence, reviewed_by_party_id, reviewed_at)
    ON TABLE public.solution_experiment_result
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_experiment_reviewer;
-- PostgreSQL requires UPDATE on the locked key column for FOR KEY SHARE.
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding,
    public.operator_identity, public.party
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (id, operator_id, reviewer_party_id, location_id, experiment_id,
              result_id, request_id, payload, reviewed_at)
    ON TABLE public.solution_experiment_review_submission_receipt
    TO kokonut_solution_experiment_reviewer;
GRANT INSERT (operator_id, reviewer_party_id, location_id, experiment_id,
              result_id, request_id, payload, reviewed_at)
    ON TABLE public.solution_experiment_review_submission_receipt
    TO kokonut_solution_experiment_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_experiment_reviewer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_experiment_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_experiment_review(
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
    latest_analysis JSONB,
    observations JSONB,
    observation_count BIGINT,
    observations_truncated BOOLEAN
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
        RAISE EXCEPTION 'Solution experiment review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution experiment review requires an active exact location grant'
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
        RAISE EXCEPTION 'Solution experiment review requires an active human identity'
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
               'unit_of_analysis', pg_catalog.left(experiment.unit_of_analysis, 4000),
               'sample_plan', CASE WHEN pg_catalog.octet_length(experiment.sample_plan::TEXT) <= 8192
                                   THEN experiment.sample_plan ELSE '{"truncated":true}'::JSONB END,
               'primary_metric_keys', CASE WHEN pg_catalog.octet_length(experiment.primary_metric_keys::TEXT) <= 8192
                                           THEN experiment.primary_metric_keys ELSE '{"truncated":true}'::JSONB END,
               'secondary_metric_keys', CASE WHEN pg_catalog.octet_length(experiment.secondary_metric_keys::TEXT) <= 8192
                                             THEN experiment.secondary_metric_keys ELSE '{"truncated":true}'::JSONB END,
               'stopping_rules', CASE WHEN pg_catalog.octet_length(experiment.stopping_rules::TEXT) <= 8192
                                      THEN experiment.stopping_rules ELSE '{"truncated":true}'::JSONB END,
               'rollback_plan', pg_catalog.left(experiment.rollback_plan, 4000),
               'safety_boundaries', CASE WHEN pg_catalog.octet_length(experiment.safety_boundaries::TEXT) <= 8192
                                         THEN experiment.safety_boundaries ELSE '{"truncated":true}'::JSONB END,
               'consent_requirements', CASE WHEN pg_catalog.octet_length(experiment.consent_requirements::TEXT) <= 8192
                                            THEN experiment.consent_requirements ELSE '{"truncated":true}'::JSONB END,
               'status', experiment.status,
               'approved_at', experiment.approved_at,
               'started_at', experiment.started_at,
               'completed_at', experiment.completed_at
           ),
           analysis.detail,
           observations.detail,
           observations.total_count,
           observations.total_count > 100
      FROM public.solution_experiment AS experiment
      JOIN public.solution AS solution ON solution.id = experiment.solution_id
      LEFT JOIN LATERAL (
          SELECT pg_catalog.jsonb_build_object(
                     'metric_key', run.metric_key,
                     'baseline_count', run.baseline_count,
                     'treatment_count', run.treatment_count,
                     'baseline_mean', run.baseline_mean,
                     'treatment_mean', run.treatment_mean,
                     'effect_estimate', run.effect_estimate,
                     'standard_error', run.standard_error,
                     'lower_bound', run.lower_bound,
                     'upper_bound', run.upper_bound,
                     'posterior_probability_benefit', run.posterior_probability_benefit,
                     'adverse_event_count', run.adverse_event_count,
                     'decision', run.decision,
                     'stopping_reason', run.stopping_reason,
                     'analysis_version', run.analysis_version,
                     'created_at', run.created_at
                 ) AS detail
            FROM public.solution_experiment_analysis_run AS run
           WHERE run.experiment_id = experiment.id
           ORDER BY run.created_at DESC, run.id DESC
           LIMIT 1
      ) AS analysis ON TRUE
      CROSS JOIN LATERAL (
          SELECT (
                     SELECT COALESCE(
                                pg_catalog.jsonb_agg(sample.detail ORDER BY sample.observed_at DESC),
                                '[]'::JSONB
                            )
                       FROM (
                           SELECT source.observed_at,
                                  pg_catalog.jsonb_build_object(
                                      'observed_at', source.observed_at,
                                      'metric_key', source.metric_key,
                                      'value', source.value,
                                      'arm', source.arm,
                                      'adverse_event', source.adverse_event,
                                      'evidence', CASE
                                          WHEN pg_catalog.octet_length(source.evidence::TEXT) <= 1024
                                          THEN source.evidence
                                          ELSE '{"truncated":true}'::JSONB
                                      END
                                  ) AS detail
                             FROM public.solution_experiment_observation AS source
                            WHERE source.experiment_id = experiment.id
                            ORDER BY source.observed_at DESC
                            LIMIT 100
                       ) AS sample
                 ) AS detail,
                 (SELECT pg_catalog.count(*)
                    FROM public.solution_experiment_observation AS source
                   WHERE source.experiment_id = experiment.id) AS total_count
      ) AS observations
     WHERE experiment.id = requested_experiment_id
       AND experiment.status = 'completed'
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND NOT EXISTS (
           SELECT 1 FROM public.solution_experiment_result AS result
            WHERE result.experiment_id = experiment.id
       );
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pending exact-location solution experiment review was not found'
            USING ERRCODE = 'P0002';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_solution_experiment(
    requested_location_id UUID,
    requested_experiment_id UUID,
    requested_request_id UUID,
    requested_outcome TEXT,
    requested_primary_results JSONB,
    requested_secondary_results JSONB,
    requested_limitations TEXT,
    requested_evidence JSONB
)
RETURNS TABLE (
    experiment_id UUID,
    outcome TEXT,
    reviewed_at TIMESTAMPTZ,
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
    existing RECORD;
    saved_result RECORD;
    request_payload JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_experiment_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Solution experiment result requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution experiment result requires an active exact location grant'
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
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, reviewer;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Solution experiment result requires an active human reviewer'
            USING ERRCODE = '42501';
    END IF;
    IF requested_outcome IS NULL
       OR requested_outcome NOT IN ('validated', 'invalidated', 'inconclusive', 'requires_replication')
       OR requested_primary_results IS NULL
       OR pg_catalog.jsonb_typeof(requested_primary_results) IS DISTINCT FROM 'object'
       OR requested_secondary_results IS NULL
       OR pg_catalog.jsonb_typeof(requested_secondary_results) IS DISTINCT FROM 'object'
       OR requested_evidence IS NULL
       OR pg_catalog.jsonb_typeof(requested_evidence) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(requested_evidence) > 100
       OR pg_catalog.octet_length(requested_primary_results::TEXT) > 65536
       OR pg_catalog.octet_length(requested_secondary_results::TEXT) > 65536
       OR pg_catalog.octet_length(requested_evidence::TEXT) > 65536
       OR (requested_limitations IS NOT NULL AND pg_catalog.length(requested_limitations) > 4000) THEN
        RAISE EXCEPTION 'Solution experiment result payload is invalid'
            USING ERRCODE = '22023';
    END IF;
    request_payload := pg_catalog.jsonb_build_object(
        'outcome', requested_outcome,
        'primary_results', requested_primary_results,
        'secondary_results', requested_secondary_results,
        'limitations', requested_limitations,
        'evidence', requested_evidence
    );

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.experiment_id, receipt.reviewer_party_id,
           receipt.payload, receipt.reviewed_at
      INTO existing
      FROM public.solution_experiment_review_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.experiment_id IS DISTINCT FROM requested_experiment_id
           OR existing.reviewer_party_id IS DISTINCT FROM reviewer_party_id
           OR existing.payload IS DISTINCT FROM request_payload THEN
            RAISE EXCEPTION 'Solution experiment result request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT existing.experiment_id,
                            existing.payload->>'outcome', existing.reviewed_at, TRUE;
        RETURN;
    END IF;

    SELECT experiment.status, experiment.owner_party_id,
           experiment.approved_by_party_id
      INTO experiment_record
      FROM public.solution_experiment AS experiment
      JOIN public.solution AS solution ON solution.id = experiment.solution_id
     WHERE experiment.id = requested_experiment_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR UPDATE OF experiment;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location solution experiment was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF experiment_record.status IS DISTINCT FROM 'completed' THEN
        RAISE EXCEPTION 'Only completed exact-location experiments can be reviewed'
            USING ERRCODE = '55000';
    END IF;
    IF experiment_record.owner_party_id = reviewer_party_id
       OR experiment_record.approved_by_party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Experiment result review requires a human distinct from its owner and protocol approver'
            USING ERRCODE = '42501';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.solution_experiment_result AS result
         WHERE result.experiment_id = requested_experiment_id
    ) THEN
        RAISE EXCEPTION 'Solution experiment already has a result'
            USING ERRCODE = '55000';
    END IF;

    INSERT INTO public.solution_experiment_result (
        experiment_id, outcome, primary_results, secondary_results,
        limitations, evidence, reviewed_by_party_id, reviewed_at
    ) VALUES (
        requested_experiment_id, requested_outcome, requested_primary_results,
        requested_secondary_results, requested_limitations, requested_evidence,
        reviewer_party_id, pg_catalog.clock_timestamp()
    ) RETURNING id, solution_experiment_result.reviewed_at
         INTO saved_result;
    UPDATE public.solution_experiment AS experiment
       SET status = requested_outcome,
           updated_at = saved_result.reviewed_at
     WHERE experiment.id = requested_experiment_id
       AND experiment.status = 'completed';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Solution experiment changed before its result was recorded'
            USING ERRCODE = '40001';
    END IF;
    INSERT INTO public.solution_experiment_review_submission_receipt (
        operator_id, reviewer_party_id, location_id, experiment_id, result_id,
        request_id, payload, reviewed_at
    ) VALUES (
        context_record.actor_id, reviewer_party_id, requested_location_id,
        requested_experiment_id, saved_result.id, requested_request_id,
        request_payload, saved_result.reviewed_at
    );
    RETURN QUERY SELECT requested_experiment_id, requested_outcome,
                        saved_result.reviewed_at, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_experiment_reviewer;
ALTER FUNCTION kokonut_security.location_solution_experiment_review(UUID, UUID)
    OWNER TO kokonut_solution_experiment_reviewer;
ALTER FUNCTION kokonut_security.review_location_solution_experiment(
    UUID, UUID, UUID, TEXT, JSONB, JSONB, TEXT, JSONB
) OWNER TO kokonut_solution_experiment_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_experiment_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_experiment_review(UUID, UUID)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.review_location_solution_experiment(
    UUID, UUID, UUID, TEXT, JSONB, JSONB, TEXT, JSONB
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_solution_experiment_review(UUID, UUID)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.review_location_solution_experiment(
            UUID, UUID, UUID, TEXT, JSONB, JSONB, TEXT, JSONB
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_solution_experiment_review(UUID, UUID)
            FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.review_location_solution_experiment(
            UUID, UUID, UUID, TEXT, JSONB, JSONB, TEXT, JSONB
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_experiment_review_submission_receipt IS
'Private append-only idempotency receipts for exact-location independent experiment result review.';
COMMENT ON FUNCTION kokonut_security.location_solution_experiment_review(UUID, UUID) IS
'Returns private bounded protocol, analysis, and observation evidence only for a pending exact-location experiment under a signed exact solution_lifecycle:review grant and active human binding. Observation identifiers, unit references, recorder/reviewer identities, and raw result records are withheld.';
COMMENT ON FUNCTION kokonut_security.review_location_solution_experiment(
    UUID, UUID, UUID, TEXT, JSONB, JSONB, TEXT, JSONB
) IS
'Records one result for a completed exact-location experiment only under signed review context and an active human distinct from the experiment owner and protocol approver; result, experiment outcome, and immutable payload receipt are atomic and retry-safe.';

COMMIT;
