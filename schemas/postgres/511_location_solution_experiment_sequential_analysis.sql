-- Protocol-bound sequential experiment analysis with live consent lineage.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_analyst'
    ) THEN
        CREATE ROLE kokonut_solution_experiment_analyst
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_analyst'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution experiment analyst role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_experiment_analyst'
            OR member_role.rolname = 'kokonut_solution_experiment_analyst'
    ) THEN
        RAISE EXCEPTION 'Solution experiment analyst role must not have memberships';
    END IF;
END;
$$;

ALTER TABLE public.solution_experiment_analysis_run
    ADD COLUMN IF NOT EXISTS location_id UUID REFERENCES public.location(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS operator_id UUID REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS request_id UUID,
    ADD COLUMN IF NOT EXISTS consent_validation_status TEXT NOT NULL DEFAULT 'unassessed',
    ADD COLUMN IF NOT EXISTS source_observation_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS source_observation_digest BYTEA,
    ADD COLUMN IF NOT EXISTS protocol_digest BYTEA,
    ADD COLUMN IF NOT EXISTS benefit_direction TEXT,
    ADD COLUMN IF NOT EXISTS minimum_sample INTEGER,
    ADD COLUMN IF NOT EXISTS benefit_threshold NUMERIC,
    ADD COLUMN IF NOT EXISTS posterior_threshold NUMERIC,
    ADD COLUMN IF NOT EXISTS safety_event_limit INTEGER,
    ADD COLUMN IF NOT EXISTS analysis_as_of TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.solution_experiment_analysis_run'::regclass
           AND conname = 'solution_experiment_analysis_consent_state'
    ) THEN
        ALTER TABLE public.solution_experiment_analysis_run
            ADD CONSTRAINT solution_experiment_analysis_consent_state CHECK (
                consent_validation_status IN ('unassessed', 'assessed')
                AND source_observation_count >= 0
                AND (source_observation_digest IS NULL
                     OR pg_catalog.octet_length(source_observation_digest) = 32)
                AND (protocol_digest IS NULL OR pg_catalog.octet_length(protocol_digest) = 32)
                AND (benefit_direction IS NULL OR benefit_direction IN ('higher', 'lower'))
                AND (minimum_sample IS NULL OR minimum_sample BETWEEN 2 AND 10000)
                AND (benefit_threshold IS NULL OR abs(benefit_threshold) <= 1000000)
                AND (posterior_threshold IS NULL
                     OR (posterior_threshold > 0.5 AND posterior_threshold < 1))
                AND (safety_event_limit IS NULL OR safety_event_limit BETWEEN 0 AND 100000)
                AND (consent_validation_status = 'unassessed'
                     OR (location_id IS NOT NULL AND operator_id IS NOT NULL
                         AND request_id IS NOT NULL
                         AND source_observation_digest IS NOT NULL
                         AND protocol_digest IS NOT NULL
                         AND benefit_direction IS NOT NULL
                         AND minimum_sample IS NOT NULL
                         AND benefit_threshold IS NOT NULL
                         AND posterior_threshold IS NOT NULL
                         AND analysis_as_of IS NOT NULL))
            );
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_experiment_analysis_source (
    analysis_run_id UUID NOT NULL
        REFERENCES public.solution_experiment_analysis_run(id)
        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
    observation_id UUID NOT NULL
        REFERENCES public.solution_experiment_observation(id)
        ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    experiment_id UUID NOT NULL REFERENCES public.solution_experiment(id) ON DELETE RESTRICT,
    PRIMARY KEY (analysis_run_id, observation_id)
);

CREATE INDEX IF NOT EXISTS solution_experiment_analysis_source_observation_idx
    ON public.solution_experiment_analysis_source(observation_id);

CREATE TABLE IF NOT EXISTS public.solution_experiment_analysis_receipt (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    experiment_id UUID NOT NULL REFERENCES public.solution_experiment(id) ON DELETE RESTRICT,
    analysis_run_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_experiment_analysis_run(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_experiment_analysis_source,
    public.solution_experiment_analysis_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_experiment_analysis_run
    FROM PUBLIC, kokonut_solution_experiment_observer;
REVOKE ALL ON TABLE public.solution_experiment_analysis_source,
    public.solution_experiment_analysis_receipt
    FROM kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_experiment_observer,
         kokonut_solution_experiment_analyst,
         kokonut_solution_experiment_reviewer;

DO $$
DECLARE target_role TEXT; target_column TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.solution_experiment_analysis_run FROM %I', target_role
            );
            FOR target_column IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.solution_experiment_analysis_run'::regclass
                   AND attribute.attnum > 0 AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE SELECT (%1$I), INSERT (%1$I), UPDATE (%1$I) '
                    'ON TABLE public.solution_experiment_analysis_run FROM %2$I',
                    target_column, target_role
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_experiment_analyst;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_experiment_analyst;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_experiment_analyst;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_experiment_analyst;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_experiment_analyst;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_experiment_analyst;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_analyst;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_analyst;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_experiment_analyst;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (id, name, solution_type, current_stage, originating_scope_type,
              originating_scope_id, status)
    ON TABLE public.solution
    TO kokonut_solution_experiment_analyst;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (id, solution_id, status, protocol_version, sample_plan,
              primary_metric_keys, secondary_metric_keys, stopping_rules,
              consent_requirements, duration_days, started_at)
    ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_analyst;
GRANT UPDATE (id) ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (id, experiment_id, metric_key, value, arm, adverse_event,
              consent_validation_status, participant_link_id, consent_event_id)
    ON TABLE public.solution_experiment_observation
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (id, party_id, location_id, revoked_at)
    ON TABLE public.mobile_participant_link
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (id, party_id, event_type, data_category, purpose, scope_type,
              scope_id, recipient_party_id, recipient_type, consent_version,
              effective_at, expires_at, created_at)
    ON TABLE public.stakeholder_consent
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (analysis_run_id, experiment_id, location_id, observation_id)
    ON TABLE public.solution_experiment_analysis_source
    TO kokonut_solution_experiment_analyst, kokonut_solution_experiment_reviewer;
GRANT INSERT (analysis_run_id, observation_id, location_id, experiment_id)
    ON TABLE public.solution_experiment_analysis_source
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (operator_id, actor_party_id, location_id, experiment_id,
              analysis_run_id, request_id, payload_digest, created_at)
    ON TABLE public.solution_experiment_analysis_receipt
    TO kokonut_solution_experiment_analyst;
GRANT INSERT (operator_id, actor_party_id, location_id, experiment_id,
              analysis_run_id, request_id, payload_digest, created_at)
    ON TABLE public.solution_experiment_analysis_receipt
    TO kokonut_solution_experiment_analyst;
GRANT SELECT (
    id, experiment_id, metric_key, baseline_count, treatment_count,
    baseline_mean, treatment_mean, effect_estimate, standard_error,
    lower_bound, upper_bound, posterior_probability_benefit,
    adverse_event_count, decision, stopping_reason, analysis_version,
    created_at, location_id, operator_id, request_id,
    consent_validation_status, source_observation_count,
    source_observation_digest, protocol_digest, benefit_direction,
    minimum_sample, benefit_threshold, posterior_threshold,
    safety_event_limit, analysis_as_of
) ON TABLE public.solution_experiment_analysis_run
    TO kokonut_solution_experiment_analyst, kokonut_solution_experiment_reviewer;
GRANT INSERT (
    id, experiment_id, metric_key, baseline_count, treatment_count,
    baseline_mean, treatment_mean, effect_estimate, standard_error,
    lower_bound, upper_bound, posterior_probability_benefit,
    adverse_event_count, decision, stopping_reason, analysis_version,
    created_at, location_id, operator_id, request_id,
    consent_validation_status, source_observation_count,
    source_observation_digest, protocol_digest, benefit_direction,
    minimum_sample, benefit_threshold, posterior_threshold,
    safety_event_limit, analysis_as_of
) ON TABLE public.solution_experiment_analysis_run
    TO kokonut_solution_experiment_analyst;

CREATE OR REPLACE FUNCTION kokonut_security.solution_experiment_observation_consent_is_current(
    requested_experiment_id UUID,
    requested_link_id UUID,
    requested_consent_id UUID,
    requested_validation_status TEXT
)
RETURNS BOOLEAN
LANGUAGE SQL
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    SELECT CASE
        WHEN requested_validation_status = 'not_required' THEN EXISTS (
            SELECT 1
              FROM public.solution_experiment AS experiment
             WHERE experiment.id = requested_experiment_id
               AND experiment.consent_requirements->>'participant_consent_required' = 'false'
               AND experiment.consent_requirements->>'non_personal_basis'
                   IN ('environmental_measurement',
                       'non_personal_operational_measurement',
                       'infrastructure_measurement')
               AND requested_link_id IS NULL
               AND requested_consent_id IS NULL
        )
        WHEN requested_validation_status = 'granted'
             AND requested_link_id IS NOT NULL
             AND requested_consent_id IS NOT NULL THEN EXISTS (
            SELECT 1
              FROM public.solution_experiment AS experiment
              JOIN public.solution AS solution
                ON solution.id = experiment.solution_id
              JOIN public.mobile_participant_link AS participant
                ON participant.id = requested_link_id
               AND participant.location_id = solution.originating_scope_id
               AND participant.revoked_at IS NULL
              JOIN public.party AS participant_party
                ON participant_party.id = participant.party_id
               AND participant_party.party_type = 'person'
               AND participant_party.status = 'active'
              JOIN public.stakeholder_consent AS consent
                ON consent.id = requested_consent_id
               AND consent.party_id = participant.party_id
               AND consent.event_type = 'grant'
               AND consent.data_category = 'solution_experiment_participation'
               AND consent.purpose = experiment.consent_requirements->>'purpose'
               AND consent.scope_type = 'location'
               AND consent.scope_id = solution.originating_scope_id
               AND consent.recipient_party_id IS NULL
               AND consent.recipient_type = 'system'
               AND consent.consent_version = experiment.consent_requirements->>'consent_version'
               AND consent.effective_at <= pg_catalog.clock_timestamp()
               AND (consent.expires_at IS NULL
                    OR consent.expires_at > pg_catalog.clock_timestamp())
             WHERE experiment.id = requested_experiment_id
               AND solution.originating_scope_type = 'location'
               AND experiment.consent_requirements->>'participant_consent_required' = 'true'
               AND NOT EXISTS (
                    SELECT 1
                      FROM public.stakeholder_consent AS newer
                     WHERE newer.party_id = participant.party_id
                       AND newer.data_category = consent.data_category
                       AND newer.purpose = consent.purpose
                       AND newer.scope_type = consent.scope_type
                       AND newer.scope_id IS NOT DISTINCT FROM consent.scope_id
                       AND newer.recipient_party_id IS NOT DISTINCT FROM consent.recipient_party_id
                       AND newer.recipient_type = consent.recipient_type
                       AND newer.effective_at <= pg_catalog.clock_timestamp()
                       AND (newer.effective_at, newer.created_at, newer.id)
                           > (consent.effective_at, consent.created_at, consent.id)
               )
        )
        ELSE FALSE
    END
$$;

GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_experiment_analyst;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_experiment_analyst;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_experiment_analyst;
GRANT EXECUTE ON FUNCTION kokonut_security.solution_experiment_observation_consent_is_current(
    UUID, UUID, UUID, TEXT
) TO kokonut_solution_experiment_analyst, kokonut_solution_experiment_reviewer;
GRANT SELECT (id)
    ON TABLE public.solution_experiment_observation
    TO kokonut_solution_experiment_reviewer;

ALTER TABLE public.solution_experiment_observation ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_experiment_observation FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_experiment_observation_scoped_analysis
    ON public.solution_experiment_observation;
CREATE POLICY solution_experiment_observation_scoped_analysis
    ON public.solution_experiment_observation
    FOR SELECT TO kokonut_solution_experiment_analyst
    USING (
        EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
              JOIN public.solution_experiment AS experiment
                ON experiment.id = solution_experiment_observation.experiment_id
              JOIN public.solution AS solution
                ON solution.id = experiment.solution_id
             WHERE context.actor_type = 'operator'
               AND solution.originating_scope_type = 'location'
               AND solution.originating_scope_id = context.location_id
               AND public.operator_scope_grant_allows(
                    context.actor_id, 'solution_lifecycle', 'analyze',
                    context.location_id
               )
        )
        AND kokonut_security.solution_experiment_observation_consent_is_current(
            experiment_id, participant_link_id, consent_event_id,
            consent_validation_status
        )
    );

ALTER TABLE public.solution_experiment_analysis_source ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_experiment_analysis_source FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_experiment_analysis_source_scoped_read
    ON public.solution_experiment_analysis_source;
CREATE POLICY solution_experiment_analysis_source_scoped_read
    ON public.solution_experiment_analysis_source
    FOR SELECT TO kokonut_solution_experiment_analyst, kokonut_solution_experiment_reviewer
    USING (
        EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
              JOIN public.solution AS solution
                ON solution.originating_scope_type = 'location'
               AND solution.originating_scope_id = context.location_id
              JOIN public.solution_experiment AS experiment
                ON experiment.id = solution_experiment_analysis_source.experiment_id
               AND experiment.solution_id = solution.id
              JOIN public.solution_experiment_observation AS observation
                ON observation.id = solution_experiment_analysis_source.observation_id
               AND observation.experiment_id = experiment.id
             WHERE context.actor_type = 'operator'
               AND solution_experiment_analysis_source.location_id = context.location_id
               AND (
                    (current_user = 'kokonut_solution_experiment_analyst'
                     AND public.operator_scope_grant_allows(
                        context.actor_id, 'solution_lifecycle', 'analyze', context.location_id
                     ))
                    OR
                    (current_user = 'kokonut_solution_experiment_reviewer'
                     AND public.operator_scope_grant_allows(
                        context.actor_id, 'solution_lifecycle', 'review', context.location_id
                     ))
               )
        )
    );
DROP POLICY IF EXISTS solution_experiment_analysis_source_scoped_insert
    ON public.solution_experiment_analysis_source;
CREATE POLICY solution_experiment_analysis_source_scoped_insert
    ON public.solution_experiment_analysis_source
    FOR INSERT TO kokonut_solution_experiment_analyst
    WITH CHECK (
        EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
              JOIN public.solution AS solution
                ON solution.originating_scope_type = 'location'
               AND solution.originating_scope_id = context.location_id
              JOIN public.solution_experiment AS experiment
                ON experiment.id = solution_experiment_analysis_source.experiment_id
               AND experiment.solution_id = solution.id
              JOIN public.solution_experiment_observation AS observation
                ON observation.id = solution_experiment_analysis_source.observation_id
               AND observation.experiment_id = experiment.id
             WHERE context.actor_type = 'operator'
               AND solution_experiment_analysis_source.location_id = context.location_id
               AND public.operator_scope_grant_allows(
                    context.actor_id, 'solution_lifecycle', 'analyze', context.location_id
               )
        )
    );

ALTER TABLE public.solution_experiment_analysis_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_experiment_analysis_run FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_experiment_analysis_run_scoped_read
    ON public.solution_experiment_analysis_run;
CREATE POLICY solution_experiment_analysis_run_scoped_read
    ON public.solution_experiment_analysis_run
    FOR SELECT TO kokonut_solution_experiment_analyst, kokonut_solution_experiment_reviewer
    USING (
        consent_validation_status = 'assessed'
        AND source_observation_count = (
            SELECT count(*)
              FROM public.solution_experiment_analysis_source AS source
             WHERE source.analysis_run_id = solution_experiment_analysis_run.id
        )
        AND EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
              JOIN public.solution_experiment AS experiment
                ON experiment.id = solution_experiment_analysis_run.experiment_id
              JOIN public.solution AS solution
                ON solution.id = experiment.solution_id
             WHERE context.actor_type = 'operator'
               AND solution.originating_scope_type = 'location'
               AND solution.originating_scope_id = context.location_id
               AND solution_experiment_analysis_run.location_id = context.location_id
               AND (
                    (current_user = 'kokonut_solution_experiment_analyst'
                     AND public.operator_scope_grant_allows(
                        context.actor_id, 'solution_lifecycle', 'analyze', context.location_id
                     ))
                    OR
                    (current_user = 'kokonut_solution_experiment_reviewer'
                     AND public.operator_scope_grant_allows(
                        context.actor_id, 'solution_lifecycle', 'review', context.location_id
                     ))
               )
        )
    );
DROP POLICY IF EXISTS solution_experiment_analysis_run_scoped_insert
    ON public.solution_experiment_analysis_run;
CREATE POLICY solution_experiment_analysis_run_scoped_insert
    ON public.solution_experiment_analysis_run
    FOR INSERT TO kokonut_solution_experiment_analyst
    WITH CHECK (
        consent_validation_status = 'assessed'
        AND EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
              JOIN public.solution_experiment AS experiment
                ON experiment.id = solution_experiment_analysis_run.experiment_id
              JOIN public.solution AS solution
                ON solution.id = experiment.solution_id
             WHERE context.actor_type = 'operator'
               AND context.location_id = solution_experiment_analysis_run.location_id
               AND solution.originating_scope_type = 'location'
               AND solution.originating_scope_id = context.location_id
               AND public.operator_scope_grant_allows(
                    context.actor_id, 'solution_lifecycle', 'analyze', context.location_id
               )
        )
    );

CREATE OR REPLACE FUNCTION kokonut_security.analyze_location_solution_experiment(
    requested_location_id UUID,
    requested_experiment_id UUID,
    requested_request_id UUID,
    requested_metric_key TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    analysis_run_id UUID,
    experiment_id UUID,
    metric_key TEXT,
    benefit_direction TEXT,
    minimum_sample INTEGER,
    baseline_count INTEGER,
    treatment_count INTEGER,
    baseline_mean NUMERIC,
    treatment_mean NUMERIC,
    effect_estimate NUMERIC,
    standard_error NUMERIC,
    lower_bound NUMERIC,
    upper_bound NUMERIC,
    posterior_probability_benefit NUMERIC,
    adverse_event_count INTEGER,
    benefit_threshold NUMERIC,
    posterior_threshold NUMERIC,
    safety_event_limit INTEGER,
    source_observation_count INTEGER,
    analysis_as_of TIMESTAMPTZ,
    decision TEXT,
    stopping_reason TEXT,
    analysis_version TEXT,
    created_at TIMESTAMPTZ,
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
    run_record RECORD;
    run_id UUID := pg_catalog.gen_random_uuid();
    direction_value TEXT;
    direction_sign NUMERIC;
    min_sample INTEGER;
    benefit_limit NUMERIC;
    posterior_limit NUMERIC;
    safety_limit INTEGER;
    adverse_count INTEGER;
    source_count INTEGER;
    source_digest_value BYTEA;
    protocol_digest_value BYTEA;
    baseline_n INTEGER;
    treatment_n INTEGER;
    baseline_avg NUMERIC;
    treatment_avg NUMERIC;
    baseline_variance NUMERIC;
    treatment_variance NUMERIC;
    effect_value NUMERIC;
    standard_error_value NUMERIC;
    lower_value NUMERIC;
    upper_value NUMERIC;
    posterior_value NUMERIC;
    z_value DOUBLE PRECISION;
    t_value DOUBLE PRECISION;
    cdf_tail DOUBLE PRECISION;
    probability_value DOUBLE PRECISION;
    analysis_time TIMESTAMPTZ := pg_catalog.clock_timestamp();
    decision_value TEXT;
    reason_value TEXT;
    payload_digest_value BYTEA;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_experiment_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Experiment analysis requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'analyze', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Experiment analysis requires an active exact location analyze grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE
       OR requested_metric_key IS NULL
       OR requested_metric_key !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$' THEN
        RAISE EXCEPTION 'Experiment analysis acknowledgement or metric key is invalid'
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
        RAISE EXCEPTION 'Experiment analysis requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    payload_digest_value := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'experiment_id', requested_experiment_id,
                'metric_key', requested_metric_key,
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
    SELECT receipt.actor_party_id, receipt.location_id, receipt.experiment_id,
           receipt.analysis_run_id, receipt.payload_digest
      INTO receipt_record
      FROM public.solution_experiment_analysis_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF receipt_record.actor_party_id IS DISTINCT FROM actor_party_id
           OR receipt_record.location_id IS DISTINCT FROM requested_location_id
           OR receipt_record.experiment_id IS DISTINCT FROM requested_experiment_id
           OR receipt_record.payload_digest IS DISTINCT FROM payload_digest_value THEN
            RAISE EXCEPTION 'Experiment analysis request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        SELECT run.* INTO run_record
          FROM public.solution_experiment_analysis_run AS run
         WHERE run.id = receipt_record.analysis_run_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Prior analysis is no longer eligible under current consent'
                USING ERRCODE = '42501';
        END IF;
        RETURN QUERY SELECT run_record.id, run_record.experiment_id,
            run_record.metric_key, run_record.benefit_direction,
            run_record.minimum_sample, run_record.baseline_count,
            run_record.treatment_count, run_record.baseline_mean,
            run_record.treatment_mean, run_record.effect_estimate,
            run_record.standard_error, run_record.lower_bound,
            run_record.upper_bound, run_record.posterior_probability_benefit,
            run_record.adverse_event_count, run_record.benefit_threshold,
            run_record.posterior_threshold, run_record.safety_event_limit,
            run_record.source_observation_count, run_record.analysis_as_of,
            run_record.decision,
            run_record.stopping_reason, run_record.analysis_version,
            run_record.created_at, TRUE;
        RETURN;
    END IF;

    SELECT experiment.id, experiment.solution_id, experiment.status,
           experiment.protocol_version, experiment.sample_plan,
           experiment.primary_metric_keys, experiment.secondary_metric_keys,
           experiment.stopping_rules, experiment.consent_requirements,
           experiment.duration_days, experiment.started_at,
           solution.current_stage, solution.status AS solution_status
      INTO experiment_record
      FROM public.solution_experiment AS experiment
      JOIN public.solution AS solution ON solution.id = experiment.solution_id
     WHERE experiment.id = requested_experiment_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR SHARE OF experiment, solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location experiment was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF experiment_record.status IS DISTINCT FROM 'active'
       OR experiment_record.started_at IS NULL
       OR experiment_record.solution_status IS DISTINCT FROM 'active'
       OR experiment_record.current_stage NOT IN ('experiment_ready', 'testing') THEN
        RAISE EXCEPTION 'Experiment is not active in an eligible solution stage'
            USING ERRCODE = '55000';
    END IF;
    IF NOT (
        experiment_record.primary_metric_keys ? requested_metric_key
        OR experiment_record.secondary_metric_keys ? requested_metric_key
    ) THEN
        RAISE EXCEPTION 'Analysis metric is not declared by the protocol'
            USING ERRCODE = '22023';
    END IF;
    direction_value := experiment_record.stopping_rules->'benefit_direction_by_metric'
        ->> requested_metric_key;
    IF direction_value IS NULL OR direction_value NOT IN ('higher', 'lower') THEN
        RAISE EXCEPTION 'Approved protocol has no valid direction for this metric'
            USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.jsonb_typeof(experiment_record.sample_plan->'minimum_sample') IS DISTINCT FROM 'number'
       OR (experiment_record.sample_plan->>'minimum_sample') IS NULL
       OR (experiment_record.sample_plan->>'minimum_sample') !~ '^[0-9]{1,5}$' THEN
        RAISE EXCEPTION 'Approved protocol has no valid minimum sample'
            USING ERRCODE = '22023';
    END IF;
    min_sample := (experiment_record.sample_plan->>'minimum_sample')::INTEGER;
    IF min_sample NOT BETWEEN 2 AND 10000 THEN
        RAISE EXCEPTION 'Approved protocol minimum sample is outside supported bounds'
            USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.jsonb_typeof(experiment_record.stopping_rules->'benefit_threshold') IS DISTINCT FROM 'number'
       OR (experiment_record.stopping_rules->>'benefit_threshold') IS NULL
       OR (experiment_record.stopping_rules->>'benefit_threshold') !~ '^-?[0-9]+([.][0-9]+)?$' THEN
        RAISE EXCEPTION 'Approved protocol has no valid benefit threshold'
            USING ERRCODE = '22023';
    END IF;
    benefit_limit := (experiment_record.stopping_rules->>'benefit_threshold')::NUMERIC;
    IF abs(benefit_limit) > 1000000 THEN
        RAISE EXCEPTION 'Approved protocol benefit threshold is outside supported bounds'
            USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.jsonb_typeof(experiment_record.stopping_rules->'posterior_threshold') IS DISTINCT FROM 'number'
       OR (experiment_record.stopping_rules->>'posterior_threshold') IS NULL
       OR (experiment_record.stopping_rules->>'posterior_threshold') !~ '^[0-9]+([.][0-9]+)?$' THEN
        RAISE EXCEPTION 'Approved protocol has no valid posterior threshold'
            USING ERRCODE = '22023';
    END IF;
    posterior_limit := (experiment_record.stopping_rules->>'posterior_threshold')::NUMERIC;
    IF posterior_limit <= 0.5 OR posterior_limit >= 1 THEN
        RAISE EXCEPTION 'Approved protocol posterior threshold is outside supported bounds'
            USING ERRCODE = '22023';
    END IF;
    IF experiment_record.stopping_rules->'safety_event_limit' IS NULL
       OR pg_catalog.jsonb_typeof(experiment_record.stopping_rules->'safety_event_limit') = 'null' THEN
        safety_limit := NULL;
    ELSE
        IF pg_catalog.jsonb_typeof(experiment_record.stopping_rules->'safety_event_limit') <> 'number'
           OR (experiment_record.stopping_rules->>'safety_event_limit') !~ '^[0-9]{1,6}$' THEN
            RAISE EXCEPTION 'Approved protocol safety event limit is invalid'
                USING ERRCODE = '22023';
        END IF;
        safety_limit := (experiment_record.stopping_rules->>'safety_event_limit')::INTEGER;
        IF safety_limit NOT BETWEEN 0 AND 100000 THEN
            RAISE EXCEPTION 'Approved protocol safety event limit is outside supported bounds'
                USING ERRCODE = '22023';
        END IF;
    END IF;
    IF experiment_record.consent_requirements->>'participant_consent_required' IS NULL
       OR experiment_record.consent_requirements->>'participant_consent_required' NOT IN ('true', 'false') THEN
        RAISE EXCEPTION 'Experiment protocol has no recognized consent policy'
            USING ERRCODE = '55000';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.solution_experiment_observation AS observation
         WHERE observation.experiment_id = requested_experiment_id
           AND (observation.metric_key = requested_metric_key OR observation.adverse_event)
           AND observation.value IS NOT NULL
           AND (observation.value::TEXT IN ('NaN', 'Infinity', '-Infinity')
                OR abs(observation.value) > 1000000)
    ) THEN
        RAISE EXCEPTION 'Source observation is outside supported numeric analysis bounds'
            USING ERRCODE = '22023';
    END IF;

    SELECT count(*)::INTEGER,
           count(*) FILTER (WHERE observation.adverse_event)::INTEGER,
           count(observation.value) FILTER (
               WHERE observation.metric_key = requested_metric_key AND observation.arm = 'baseline'
           )::INTEGER,
           count(observation.value) FILTER (
               WHERE observation.metric_key = requested_metric_key AND observation.arm = 'treatment'
           )::INTEGER,
           avg(observation.value) FILTER (
               WHERE observation.metric_key = requested_metric_key
                 AND observation.arm = 'baseline' AND observation.value IS NOT NULL
           ),
           avg(observation.value) FILTER (
               WHERE observation.metric_key = requested_metric_key
                 AND observation.arm = 'treatment' AND observation.value IS NOT NULL
           ),
           var_samp(observation.value) FILTER (
               WHERE observation.metric_key = requested_metric_key
                 AND observation.arm = 'baseline' AND observation.value IS NOT NULL
           ),
           var_samp(observation.value) FILTER (
               WHERE observation.metric_key = requested_metric_key
                 AND observation.arm = 'treatment' AND observation.value IS NOT NULL
           ),
           public.digest(
               pg_catalog.convert_to(
                   COALESCE(pg_catalog.string_agg(observation.id::TEXT, ',' ORDER BY observation.id), ''),
                   'UTF8'
               ), 'sha256'
           )
      INTO source_count, adverse_count, baseline_n, treatment_n,
           baseline_avg, treatment_avg, baseline_variance, treatment_variance,
           source_digest_value
      FROM public.solution_experiment_observation AS observation
     WHERE observation.experiment_id = requested_experiment_id
       AND (observation.metric_key = requested_metric_key OR observation.adverse_event);

    IF baseline_n > 0 AND treatment_n > 0 THEN
        effect_value := treatment_avg - baseline_avg;
    END IF;
    IF baseline_n >= 2 AND treatment_n >= 2 THEN
        standard_error_value := pg_catalog.sqrt(
            COALESCE(baseline_variance, 0) / baseline_n
            + COALESCE(treatment_variance, 0) / treatment_n
        );
        IF standard_error_value > 0 THEN
            direction_sign := CASE WHEN direction_value = 'higher' THEN 1 ELSE -1 END;
            z_value := ((effect_value * direction_sign) / standard_error_value)::DOUBLE PRECISION;
            IF abs(z_value) >= 38 THEN
                probability_value := CASE WHEN z_value >= 0 THEN 1.0 ELSE 0.0 END;
            ELSE
                t_value := 1.0 / (1.0 + 0.2316419 * abs(z_value));
                cdf_tail := 0.3989422804014327 * pg_catalog.exp(-0.5 * z_value * z_value)
                    * t_value
                    * (0.319381530 + t_value * (-0.356563782 + t_value
                    * (1.781477937 + t_value * (-1.821255978 + 1.330274429 * t_value))));
                probability_value := CASE WHEN z_value >= 0
                    THEN 1.0 - cdf_tail ELSE cdf_tail END;
            END IF;
            posterior_value := greatest(0.0, least(1.0, probability_value))::NUMERIC;
            lower_value := effect_value - 1.96 * standard_error_value;
            upper_value := effect_value + 1.96 * standard_error_value;
        END IF;
    END IF;

    IF safety_limit IS NOT NULL AND adverse_count > safety_limit THEN
        decision_value := 'safety_stop';
        reason_value := 'Adverse-event count exceeded the approved protocol limit';
    ELSIF experiment_record.duration_days IS NOT NULL
       AND analysis_time >= experiment_record.started_at
                           + experiment_record.duration_days * INTERVAL '1 day' THEN
        decision_value := 'max_duration';
        reason_value := 'Approved protocol duration has elapsed; human review is required';
    ELSIF baseline_n < min_sample OR treatment_n < min_sample THEN
        decision_value := 'insufficient_data';
        reason_value := 'Baseline and treatment groups have not each reached the approved minimum sample';
    ELSIF standard_error_value IS NULL OR standard_error_value <= 0
       OR posterior_value IS NULL THEN
        decision_value := 'insufficient_data';
        reason_value := 'A positive within-group variance is required for sequential analysis';
    ELSIF posterior_value >= posterior_limit
       AND (effect_value * direction_sign) >= benefit_limit THEN
        decision_value := 'benefit';
        reason_value := 'Directional effect and posterior benefit probability reached approved thresholds';
    ELSIF posterior_value <= 1 - posterior_limit THEN
        decision_value := 'futility';
        reason_value := 'Posterior benefit probability reached the approved futility boundary';
    ELSE
        decision_value := 'continue';
        reason_value := 'Approved benefit and futility thresholds have not been reached';
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

    INSERT INTO public.solution_experiment_analysis_source (
        analysis_run_id, observation_id, location_id, experiment_id
    )
    SELECT run_id, observation.id, requested_location_id, requested_experiment_id
      FROM public.solution_experiment_observation AS observation
     WHERE observation.experiment_id = requested_experiment_id
       AND (observation.metric_key = requested_metric_key OR observation.adverse_event);

    INSERT INTO public.solution_experiment_analysis_run (
        id, experiment_id, metric_key, baseline_count, treatment_count,
        baseline_mean, treatment_mean, effect_estimate, standard_error,
        lower_bound, upper_bound, posterior_probability_benefit,
        adverse_event_count, decision, stopping_reason, analysis_version,
        location_id, operator_id, request_id, consent_validation_status,
        source_observation_count, source_observation_digest, protocol_digest,
        benefit_direction, minimum_sample, benefit_threshold,
        posterior_threshold, safety_event_limit, analysis_as_of
    ) VALUES (
        run_id, requested_experiment_id, requested_metric_key, baseline_n, treatment_n,
        baseline_avg, treatment_avg, effect_value, standard_error_value,
        lower_value, upper_value, posterior_value, adverse_count, decision_value,
        reason_value, 'sequential-v2-consent', requested_location_id,
        context_record.actor_id, requested_request_id, 'assessed', source_count,
        source_digest_value, protocol_digest_value, direction_value, min_sample,
        benefit_limit, posterior_limit, safety_limit, analysis_time
    );
    INSERT INTO public.solution_experiment_analysis_receipt (
        operator_id, actor_party_id, location_id, experiment_id,
        analysis_run_id, request_id, payload_digest, created_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        requested_experiment_id, run_id, requested_request_id,
        payload_digest_value, analysis_time
    );

    RETURN QUERY SELECT run_id, requested_experiment_id, requested_metric_key,
        direction_value, min_sample, baseline_n, treatment_n, baseline_avg,
        treatment_avg, effect_value, standard_error_value, lower_value, upper_value,
        posterior_value, adverse_count, benefit_limit, posterior_limit, safety_limit,
        source_count, analysis_time, decision_value, reason_value,
        'sequential-v2-consent'::TEXT, analysis_time, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_experiment_analyst;
ALTER FUNCTION kokonut_security.solution_experiment_observation_consent_is_current(
    UUID, UUID, UUID, TEXT
) OWNER TO kokonut_solution_experiment_analyst;
ALTER FUNCTION kokonut_security.analyze_location_solution_experiment(
    UUID, UUID, UUID, TEXT, BOOLEAN
) OWNER TO kokonut_solution_experiment_analyst;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_experiment_analyst;
REVOKE ALL ON FUNCTION kokonut_security.solution_experiment_observation_consent_is_current(
    UUID, UUID, UUID, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.analyze_location_solution_experiment(
    UUID, UUID, UUID, TEXT, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.analyze_location_solution_experiment(
            UUID, UUID, UUID, TEXT, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.analyze_location_solution_experiment(
            UUID, UUID, UUID, TEXT, BOOLEAN
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.solution_experiment_observation_consent_is_current(
            UUID, UUID, UUID, TEXT
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_experiment_analysis_source IS
    'Private source-observation lineage for protocol-bound analyses; live observation RLS hides the analysis when consent is withdrawn.';
COMMENT ON TABLE public.solution_experiment_analysis_receipt IS
    'Private immutable idempotency receipts for exact-location sequential experiment analysis.';
COMMENT ON FUNCTION kokonut_security.analyze_location_solution_experiment(
    UUID, UUID, UUID, TEXT, BOOLEAN
) IS
    'Persists an advisory, protocol-threshold-bound sequential analysis under exact location analyze scope. It does not complete the experiment or change solution lifecycle state.';

COMMIT;
