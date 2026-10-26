-- Close only analyses that meet the approved sequential stopping policy.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_analyst'
           AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'The bounded experiment analyst role must exist before completion is installed';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_experiment_completion_receipt (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    experiment_id UUID NOT NULL UNIQUE REFERENCES public.solution_experiment(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    protocol_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(protocol_digest) = 32),
    analysis_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(analysis_digest) = 32),
    completion_basis TEXT NOT NULL CHECK (
        completion_basis IN ('safety_stop', 'duration_elapsed', 'sequential_threshold')
    ),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_experiment_completion_receipt
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_experiment_observer,
         kokonut_solution_experiment_reviewer,
         kokonut_solution_experiment_analyst;
GRANT SELECT, INSERT ON TABLE public.solution_experiment_completion_receipt
    TO kokonut_solution_experiment_analyst;
GRANT UPDATE (status, completed_at, updated_at)
    ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_analyst;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_experiment_analyst;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_experiment_analyst;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_experiment_analyst;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_experiment_analyst;

ALTER TABLE public.solution_experiment_completion_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_experiment_completion_receipt FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_experiment_completion_receipt_scoped_read
    ON public.solution_experiment_completion_receipt;
CREATE POLICY solution_experiment_completion_receipt_scoped_read
    ON public.solution_experiment_completion_receipt
    FOR SELECT TO kokonut_solution_experiment_analyst
    USING (
        EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
             WHERE context.actor_type = 'operator'
               AND context.actor_id = solution_experiment_completion_receipt.operator_id
               AND context.location_id = solution_experiment_completion_receipt.location_id
               AND public.operator_scope_grant_allows(
                    context.actor_id, 'solution_lifecycle', 'transition', context.location_id
               )
               AND public.operator_scope_grant_allows(
                    context.actor_id, 'solution_lifecycle', 'analyze', context.location_id
               )
        )
    );
DROP POLICY IF EXISTS solution_experiment_completion_receipt_scoped_insert
    ON public.solution_experiment_completion_receipt;
CREATE POLICY solution_experiment_completion_receipt_scoped_insert
    ON public.solution_experiment_completion_receipt
    FOR INSERT TO kokonut_solution_experiment_analyst
    WITH CHECK (
        EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
             WHERE context.actor_type = 'operator'
               AND context.actor_id = solution_experiment_completion_receipt.operator_id
               AND context.location_id = solution_experiment_completion_receipt.location_id
               AND public.operator_scope_grant_allows(
                    context.actor_id, 'solution_lifecycle', 'transition', context.location_id
               )
               AND public.operator_scope_grant_allows(
                    context.actor_id, 'solution_lifecycle', 'analyze', context.location_id
               )
        )
    );

CREATE OR REPLACE FUNCTION kokonut_security.complete_location_solution_experiment(
    requested_location_id UUID,
    requested_experiment_id UUID,
    requested_request_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    experiment_id UUID,
    status TEXT,
    completion_basis TEXT,
    completed_at TIMESTAMPTZ,
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
    receipt_record RECORD;
    metric_record RECORD;
    analysis_record RECORD;
    protocol_digest_value BYTEA;
    analysis_digest_value BYTEA;
    analysis_digest_material TEXT := '';
    payload_digest_value BYTEA;
    current_source_digest BYTEA;
    current_source_count INTEGER;
    primary_metric_count INTEGER := 0;
    completed_time TIMESTAMPTZ := pg_catalog.clock_timestamp();
    basis_value TEXT;
    saw_safety_stop BOOLEAN := FALSE;
    saw_duration_elapsed BOOLEAN := FALSE;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_experiment_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Experiment completion requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'transition', requested_location_id
    ) OR NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'analyze', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Experiment completion requires active exact-location transition and analyze grants'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Experiment completion requires explicit acknowledgement'
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
        RAISE EXCEPTION 'Experiment completion requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.experiment_id, receipt.actor_party_id,
           receipt.payload_digest, receipt.protocol_digest, receipt.analysis_digest,
           receipt.completion_basis, receipt.completed_at
      INTO receipt_record
      FROM public.solution_experiment_completion_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF receipt_record.location_id IS DISTINCT FROM requested_location_id
           OR receipt_record.experiment_id IS DISTINCT FROM requested_experiment_id
           OR receipt_record.actor_party_id IS DISTINCT FROM actor_party_id THEN
            RAISE EXCEPTION 'Experiment completion request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT receipt_record.experiment_id, 'completed'::TEXT,
            receipt_record.completion_basis, receipt_record.completed_at, TRUE;
        RETURN;
    END IF;

    SELECT experiment.id, experiment.solution_id, experiment.status,
           experiment.protocol_version, experiment.sample_plan,
           experiment.primary_metric_keys, experiment.secondary_metric_keys,
           experiment.stopping_rules, experiment.consent_requirements,
           experiment.duration_days, experiment.started_at,
           solution.originating_scope_type, solution.originating_scope_id
      INTO experiment_record
      FROM public.solution_experiment AS experiment
      JOIN public.solution AS solution ON solution.id = experiment.solution_id
     WHERE experiment.id = requested_experiment_id
       AND solution.status = 'active'
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR UPDATE OF experiment;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location active solution experiment was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF experiment_record.status IS DISTINCT FROM 'active'
       OR experiment_record.started_at IS NULL THEN
        RAISE EXCEPTION 'Only started, active exact-location experiments can be completed'
            USING ERRCODE = '55000';
    END IF;
    IF pg_catalog.jsonb_typeof(experiment_record.primary_metric_keys) IS DISTINCT FROM 'array'
       OR pg_catalog.jsonb_array_length(experiment_record.primary_metric_keys) = 0 THEN
        RAISE EXCEPTION 'Experiment protocol must declare primary metrics before completion'
            USING ERRCODE = '55000';
    END IF;

    protocol_digest_value := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'protocol_version', experiment_record.protocol_version,
                'sample_plan', experiment_record.sample_plan,
                'primary_metric_keys', experiment_record.primary_metric_keys,
                'secondary_metric_keys', experiment_record.secondary_metric_keys,
                'stopping_rules', experiment_record.stopping_rules,
                'consent_requirements', experiment_record.consent_requirements
            )::TEXT,
            'UTF8'
        ), 'sha256'
    );

    FOR metric_record IN
        SELECT metrics.metric_key
          FROM pg_catalog.jsonb_array_elements_text(experiment_record.primary_metric_keys)
               AS metrics(metric_key)
    LOOP
        primary_metric_count := primary_metric_count + 1;
        SELECT analysis.id, analysis.metric_key, analysis.decision,
               analysis.analysis_as_of, analysis.analysis_version,
               analysis.source_observation_count, analysis.source_observation_digest,
               analysis.protocol_digest, analysis.benefit_direction,
               analysis.minimum_sample, analysis.benefit_threshold,
               analysis.posterior_threshold, analysis.safety_event_limit,
               analysis.baseline_count, analysis.treatment_count
          INTO analysis_record
          FROM public.solution_experiment_analysis_run AS analysis
         WHERE analysis.experiment_id = requested_experiment_id
           AND analysis.location_id = requested_location_id
           AND analysis.metric_key = metric_record.metric_key
           AND analysis.consent_validation_status = 'assessed'
         ORDER BY analysis.analysis_as_of DESC, analysis.created_at DESC, analysis.id DESC
         LIMIT 1;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Every primary metric needs a current consent-aware analysis before completion'
                USING ERRCODE = '55000';
        END IF;

        SELECT count(*)::INTEGER,
               public.digest(
                   pg_catalog.convert_to(
                       COALESCE(pg_catalog.string_agg(observation.id::TEXT, ',' ORDER BY observation.id), ''),
                       'UTF8'
                   ),
                   'sha256'
               )
          INTO current_source_count, current_source_digest
          FROM public.solution_experiment_observation AS observation
         WHERE observation.experiment_id = requested_experiment_id
           AND (observation.metric_key = metric_record.metric_key OR observation.adverse_event);

        IF analysis_record.analysis_version IS DISTINCT FROM 'sequential-v2-consent'
           OR analysis_record.protocol_digest IS DISTINCT FROM protocol_digest_value
           OR analysis_record.source_observation_count IS DISTINCT FROM current_source_count
           OR analysis_record.source_observation_digest IS DISTINCT FROM current_source_digest
           OR analysis_record.analysis_as_of > completed_time
           OR analysis_record.benefit_direction IS DISTINCT FROM
                (experiment_record.stopping_rules->'benefit_direction_by_metric'
                    ->> metric_record.metric_key)
           OR analysis_record.minimum_sample IS DISTINCT FROM
                COALESCE((experiment_record.sample_plan->>'minimum_sample')::INTEGER, 2)
           OR analysis_record.benefit_threshold IS DISTINCT FROM
                COALESCE((experiment_record.stopping_rules->>'benefit_threshold')::NUMERIC, 0)
           OR analysis_record.posterior_threshold IS DISTINCT FROM
                COALESCE((experiment_record.stopping_rules->>'posterior_threshold')::NUMERIC, 0.9)
           OR analysis_record.safety_event_limit IS DISTINCT FROM
                (experiment_record.stopping_rules->>'safety_event_limit')::INTEGER THEN
            RAISE EXCEPTION 'Primary metric analysis is stale or does not match the approved protocol'
                USING ERRCODE = '55000';
        END IF;
        IF analysis_record.decision NOT IN ('benefit', 'futility', 'safety_stop', 'max_duration') THEN
            RAISE EXCEPTION 'Every primary metric must reach a protocol stopping boundary before completion'
                USING ERRCODE = '55000';
        END IF;
        IF analysis_record.decision IN ('benefit', 'futility')
           AND (analysis_record.baseline_count < analysis_record.minimum_sample
                OR analysis_record.treatment_count < analysis_record.minimum_sample) THEN
            RAISE EXCEPTION 'Primary metric analysis is below its approved minimum sample'
                USING ERRCODE = '55000';
        END IF;
        IF analysis_record.decision = 'max_duration'
           AND (experiment_record.duration_days IS NULL
                OR completed_time < experiment_record.started_at
                                  + experiment_record.duration_days * INTERVAL '1 day') THEN
            RAISE EXCEPTION 'The approved experiment duration has not elapsed'
                USING ERRCODE = '55000';
        END IF;
        IF analysis_record.decision = 'safety_stop' THEN
            saw_safety_stop := TRUE;
        ELSIF analysis_record.decision = 'max_duration' THEN
            saw_duration_elapsed := TRUE;
        END IF;
        analysis_digest_material := analysis_digest_material
            || metric_record.metric_key || ':' || analysis_record.id::TEXT || ':'
            || pg_catalog.encode(analysis_record.source_observation_digest, 'hex') || ':'
            || analysis_record.decision || '|';
    END LOOP;

    IF primary_metric_count <> pg_catalog.jsonb_array_length(experiment_record.primary_metric_keys) THEN
        RAISE EXCEPTION 'Primary metrics must be unique before experiment completion'
            USING ERRCODE = '55000';
    END IF;
    basis_value := CASE
        WHEN saw_safety_stop THEN 'safety_stop'
        WHEN saw_duration_elapsed THEN 'duration_elapsed'
        ELSE 'sequential_threshold'
    END;
    analysis_digest_value := public.digest(
        pg_catalog.convert_to(analysis_digest_material, 'UTF8'), 'sha256'
    );
    payload_digest_value := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'experiment_id', requested_experiment_id,
                'acknowledged', requested_acknowledged,
                'protocol_digest', pg_catalog.encode(protocol_digest_value, 'hex'),
                'analysis_digest', pg_catalog.encode(analysis_digest_value, 'hex')
            )::TEXT,
            'UTF8'
        ), 'sha256'
    );

    UPDATE public.solution_experiment AS experiment
       SET status = 'completed',
           completed_at = completed_time,
           updated_at = completed_time
     WHERE experiment.id = requested_experiment_id
       AND experiment.status = 'active';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Experiment changed before completion was recorded'
            USING ERRCODE = '40001';
    END IF;
    INSERT INTO public.solution_experiment_completion_receipt (
        operator_id, actor_party_id, location_id, experiment_id, request_id,
        payload_digest, protocol_digest, analysis_digest, completion_basis, completed_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        requested_experiment_id, requested_request_id, payload_digest_value,
        protocol_digest_value, analysis_digest_value, basis_value, completed_time
    );

    RETURN QUERY SELECT requested_experiment_id, 'completed'::TEXT,
        basis_value, completed_time, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_experiment_analyst;
ALTER FUNCTION kokonut_security.complete_location_solution_experiment(UUID, UUID, UUID, BOOLEAN)
    OWNER TO kokonut_solution_experiment_analyst;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_experiment_analyst;
REVOKE ALL ON FUNCTION kokonut_security.complete_location_solution_experiment(UUID, UUID, UUID, BOOLEAN)
    FROM PUBLIC, kokonut_directus_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.complete_location_solution_experiment(UUID, UUID, UUID, BOOLEAN)
    TO kokonut_runtime;

COMMENT ON TABLE public.solution_experiment_completion_receipt IS
    'Private immutable completion receipt. Completion requires current analyses for every primary metric at a protocol-defined stopping boundary.';
COMMENT ON FUNCTION kokonut_security.complete_location_solution_experiment(UUID, UUID, UUID, BOOLEAN) IS
    'Completes one exact-origin experiment only when every primary metric has a current consent-aware terminal analysis matching the approved protocol; result review remains independent.';

COMMIT;
