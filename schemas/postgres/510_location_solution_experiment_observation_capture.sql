-- Capture experiment observations under signed location scope and current participant consent.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_observer'
    ) THEN
        CREATE ROLE kokonut_solution_experiment_observer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_observer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution experiment observer role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_experiment_observer'
            OR member_role.rolname = 'kokonut_solution_experiment_observer'
    ) THEN
        RAISE EXCEPTION 'Solution experiment observer role must not have memberships';
    END IF;
END;
$$;

ALTER TABLE public.solution_experiment_observation
    ADD COLUMN IF NOT EXISTS participant_link_id UUID
        REFERENCES public.mobile_participant_link(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS consent_event_id UUID
        REFERENCES public.stakeholder_consent(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS consent_validation_status TEXT NOT NULL DEFAULT 'unassessed'
        CHECK (consent_validation_status IN ('unassessed', 'not_required', 'granted'));

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.solution_experiment_observation'::regclass
           AND conname = 'solution_experiment_observation_consent_pair'
    ) THEN
        ALTER TABLE public.solution_experiment_observation
            ADD CONSTRAINT solution_experiment_observation_consent_pair CHECK (
                (consent_validation_status = 'granted'
                    AND participant_link_id IS NOT NULL
                    AND consent_event_id IS NOT NULL)
                OR (consent_validation_status IN ('unassessed', 'not_required')
                    AND participant_link_id IS NULL
                    AND consent_event_id IS NULL)
            );
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_experiment_observation_capture_receipt (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    experiment_id UUID NOT NULL REFERENCES public.solution_experiment(id) ON DELETE RESTRICT,
    observation_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_experiment_observation(id) ON DELETE RESTRICT,
    consent_event_id UUID REFERENCES public.stakeholder_consent(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    observed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_experiment_observation_capture_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_experiment_observation_capture_receipt
    FROM kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_experiment_observer,
         kokonut_solution_experiment_reviewer;

-- Existing rows cannot be assumed to have a participant consent decision.
-- They remain unassessed and are hidden from scoped review until disposition.
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
                'REVOKE ALL ON TABLE public.solution_experiment_observation FROM %I',
                target_role
            );
            FOR target_column IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.solution_experiment_observation'::regclass
                   AND attribute.attnum > 0 AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE SELECT (%1$I), INSERT (%1$I), UPDATE (%1$I) '
                    'ON TABLE public.solution_experiment_observation FROM %2$I',
                    target_column, target_role
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_experiment_observer;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_experiment_observer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_experiment_observer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_experiment_observer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_experiment_observer;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_experiment_observer;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_observer;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_observer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_observer;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_observer;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_experiment_observer;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_experiment_observer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_experiment_observer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_experiment_observer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_experiment_observer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_experiment_observer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_experiment_observer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_experiment_observer;
GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage, status)
    ON TABLE public.solution
    TO kokonut_solution_experiment_observer;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_experiment_observer;
GRANT SELECT (
    id, solution_id, owner_party_id, protocol_version, status, started_at,
    primary_metric_keys, secondary_metric_keys, comparator_definition,
    consent_requirements
) ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_observer;
GRANT UPDATE (id) ON TABLE public.solution_experiment
    TO kokonut_solution_experiment_observer;
GRANT SELECT (id, party_id, location_id, revoked_at)
    ON TABLE public.mobile_participant_link
    TO kokonut_solution_experiment_observer;
GRANT UPDATE (id) ON TABLE public.mobile_participant_link
    TO kokonut_solution_experiment_observer;
GRANT SELECT (
    id, party_id, event_type, data_category, purpose, scope_type, scope_id,
    recipient_party_id, recipient_type, consent_version, effective_at,
    expires_at, created_at
) ON TABLE public.stakeholder_consent
    TO kokonut_solution_experiment_observer;
GRANT INSERT (
    id, experiment_id, observed_at, unit_ref, metric_key, value, arm,
    adverse_event, evidence, recorded_by_party_id, participant_link_id,
    consent_event_id, consent_validation_status
) ON TABLE public.solution_experiment_observation
    TO kokonut_solution_experiment_observer;
GRANT SELECT (
    operator_id, actor_party_id, location_id, solution_id, experiment_id,
    observation_id, consent_event_id, request_id, payload_digest, observed_at
) ON TABLE public.solution_experiment_observation_capture_receipt
    TO kokonut_solution_experiment_observer;
GRANT INSERT (
    operator_id, actor_party_id, location_id, solution_id, experiment_id,
    observation_id, consent_event_id, request_id, payload_digest, observed_at
) ON TABLE public.solution_experiment_observation_capture_receipt
    TO kokonut_solution_experiment_observer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_experiment_observer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_experiment_observer;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_experiment_observer;

-- Reviewer reads are filtered live. A later withdrawal or participant-link
-- revocation hides prior observations without deleting or rewriting evidence.
GRANT SELECT (id, party_id, revoked_at, location_id)
    ON TABLE public.mobile_participant_link
    TO kokonut_solution_experiment_reviewer;
GRANT SELECT (
    id, party_id, event_type, data_category, purpose, scope_type, scope_id,
    recipient_party_id, recipient_type, consent_version, effective_at,
    expires_at, created_at
) ON TABLE public.stakeholder_consent
    TO kokonut_solution_experiment_reviewer;

ALTER TABLE public.solution_experiment_observation ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_experiment_observation FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_experiment_observation_scoped_insert
    ON public.solution_experiment_observation;
CREATE POLICY solution_experiment_observation_scoped_insert
    ON public.solution_experiment_observation
    FOR INSERT TO kokonut_solution_experiment_observer
    WITH CHECK (
        consent_validation_status IN ('not_required', 'granted')
        AND EXISTS (
            SELECT 1
              FROM kokonut_security.current_tenant_context() AS context
              JOIN public.solution_experiment AS experiment
                ON experiment.id = solution_experiment_observation.experiment_id
              JOIN public.solution AS solution
                ON solution.id = experiment.solution_id
             WHERE context.actor_type = 'operator'
               AND context.location_id = solution.originating_scope_id
               AND solution.originating_scope_type = 'location'
               AND public.operator_scope_grant_allows(
                    context.actor_id, 'solution_lifecycle', 'collect',
                    context.location_id
               )
        )
    );

DROP POLICY IF EXISTS solution_experiment_observation_scoped_review
    ON public.solution_experiment_observation;
CREATE POLICY solution_experiment_observation_scoped_review
    ON public.solution_experiment_observation
    FOR SELECT TO kokonut_solution_experiment_reviewer
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
                    context.actor_id, 'solution_lifecycle', 'review',
                    context.location_id
               )
        )
        AND (
            (
                consent_validation_status = 'not_required'
                AND participant_link_id IS NULL
                AND consent_event_id IS NULL
                AND EXISTS (
                    SELECT 1
                      FROM public.solution_experiment AS experiment
                     WHERE experiment.id = solution_experiment_observation.experiment_id
                       AND experiment.consent_requirements->>'participant_consent_required' = 'false'
                       AND experiment.consent_requirements->>'non_personal_basis'
                           IN ('environmental_measurement',
                               'non_personal_operational_measurement',
                               'infrastructure_measurement')
                )
            )
            OR (
                consent_validation_status = 'granted'
                AND participant_link_id IS NOT NULL
                AND consent_event_id IS NOT NULL
                AND EXISTS (
                    SELECT 1
                      FROM public.solution_experiment AS experiment
                      JOIN public.solution AS solution
                        ON solution.id = experiment.solution_id
                      JOIN public.mobile_participant_link AS participant
                        ON participant.id = solution_experiment_observation.participant_link_id
                       AND participant.location_id = solution.originating_scope_id
                       AND participant.revoked_at IS NULL
                      JOIN public.party AS participant_party
                        ON participant_party.id = participant.party_id
                       AND participant_party.party_type = 'person'
                       AND participant_party.status = 'active'
                      JOIN public.stakeholder_consent AS consent
                        ON consent.id = solution_experiment_observation.consent_event_id
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
                     WHERE experiment.id = solution_experiment_observation.experiment_id
                       AND solution.originating_scope_type = 'location'
                       AND solution.originating_scope_id = (
                           SELECT context.location_id
                             FROM kokonut_security.current_tenant_context() AS context
                       )
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
            )
        )
    );

CREATE OR REPLACE FUNCTION kokonut_security.capture_location_solution_experiment_observation(
    requested_location_id UUID,
    requested_experiment_id UUID,
    requested_request_id UUID,
    requested_metric_key TEXT,
    requested_value NUMERIC,
    requested_arm TEXT,
    requested_unit_ref TEXT,
    requested_adverse_event BOOLEAN,
    requested_evidence JSONB,
    requested_participant_link_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    observation_id UUID,
    experiment_id UUID,
    metric_key TEXT,
    observed_at TIMESTAMPTZ,
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
    participant_record RECORD;
    consent_record RECORD;
    prior_receipt RECORD;
    new_observation_id UUID;
    capture_time TIMESTAMPTZ;
    consent_id UUID;
    consent_state TEXT;
    payload_digest BYTEA;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_experiment_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Experiment observation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'collect', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Experiment observation requires an active exact location collect grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Experiment observation requires explicit acknowledgement'
            USING ERRCODE = '22023';
    END IF;
    IF requested_metric_key IS NULL
       OR requested_metric_key !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$'
       OR requested_arm IS NULL
       OR requested_arm NOT IN ('baseline', 'treatment', 'comparator')
       OR requested_adverse_event IS NULL
       OR requested_evidence IS NULL
       OR pg_catalog.octet_length(requested_evidence::TEXT) > 65536
       OR pg_catalog.jsonb_typeof(requested_evidence) NOT IN ('object', 'array')
       OR (requested_value IS NULL AND NOT requested_adverse_event)
       OR (requested_value IS NOT NULL AND requested_value::TEXT IN ('NaN', 'Infinity', '-Infinity'))
       OR (requested_unit_ref IS NOT NULL AND
           requested_unit_ref !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$') THEN
        RAISE EXCEPTION 'Experiment observation payload is invalid or outside bounds'
            USING ERRCODE = '22023';
    END IF;

    capture_time := pg_catalog.clock_timestamp();
    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'experiment_id', requested_experiment_id,
                'metric_key', requested_metric_key,
                'value', requested_value,
                'arm', requested_arm,
                'unit_ref', requested_unit_ref,
                'adverse_event', requested_adverse_event,
                'evidence', requested_evidence,
                'participant_link_id', requested_participant_link_id,
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
    SELECT receipt.location_id, receipt.experiment_id, receipt.actor_party_id,
           receipt.observation_id, receipt.consent_event_id, receipt.payload_digest,
           receipt.observed_at
      INTO prior_receipt
      FROM public.solution_experiment_observation_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
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
        IF prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.experiment_id IS DISTINCT FROM requested_experiment_id
           OR actor_party_id IS NULL
           OR prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Experiment observation request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_receipt.observation_id, requested_experiment_id,
                            requested_metric_key, prior_receipt.observed_at, TRUE;
        RETURN;
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
        RAISE EXCEPTION 'Experiment observation requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    SELECT experiment.id, experiment.solution_id, experiment.status,
           experiment.started_at, experiment.primary_metric_keys,
           experiment.secondary_metric_keys, experiment.comparator_definition,
           experiment.consent_requirements, solution.current_stage,
           solution.status AS solution_status
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
        RAISE EXCEPTION 'Observation metric is not declared by the protocol'
            USING ERRCODE = '22023';
    END IF;
    IF requested_arm = 'comparator'
       AND NULLIF(pg_catalog.btrim(experiment_record.comparator_definition), '') IS NULL THEN
        RAISE EXCEPTION 'Comparator observations require a declared comparator'
            USING ERRCODE = '22023';
    END IF;

    IF experiment_record.consent_requirements->>'participant_consent_required' = 'true' THEN
        IF requested_participant_link_id IS NULL OR requested_unit_ref IS NOT NULL THEN
            RAISE EXCEPTION 'Participant observations require a location link and cannot expose a unit reference'
                USING ERRCODE = '42501';
        END IF;
        SELECT participant.party_id, participant.location_id
          INTO participant_record
          FROM public.mobile_participant_link AS participant
          JOIN public.party AS participant_party
            ON participant_party.id = participant.party_id
           AND participant_party.party_type = 'person'
           AND participant_party.status = 'active'
         WHERE participant.id = requested_participant_link_id
           AND participant.location_id = requested_location_id
           AND participant.revoked_at IS NULL
         FOR UPDATE OF participant, participant_party;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Active participant link was not found at this location'
                USING ERRCODE = '42501';
        END IF;
        SELECT consent.id, consent.event_type, consent.consent_version,
               consent.effective_at, consent.expires_at
          INTO consent_record
          FROM public.stakeholder_consent AS consent
         WHERE consent.party_id = participant_record.party_id
           AND consent.data_category = 'solution_experiment_participation'
           AND consent.purpose = experiment_record.consent_requirements->>'purpose'
           AND consent.scope_type = 'location'
           AND consent.scope_id = requested_location_id
           AND consent.recipient_party_id IS NULL
           AND consent.recipient_type = 'system'
           AND consent.effective_at <= capture_time
         ORDER BY consent.effective_at DESC, consent.created_at DESC, consent.id DESC
         LIMIT 1;
        IF NOT FOUND OR consent_record.event_type IS DISTINCT FROM 'grant'
           OR consent_record.consent_version IS DISTINCT FROM
              experiment_record.consent_requirements->>'consent_version'
           OR (consent_record.expires_at IS NOT NULL
               AND consent_record.expires_at <= capture_time) THEN
            RAISE EXCEPTION 'Current exact-location participant consent is required'
                USING ERRCODE = '42501';
        END IF;
        consent_id := consent_record.id;
        consent_state := 'granted';
    ELSIF experiment_record.consent_requirements->>'participant_consent_required' = 'false'
       AND experiment_record.consent_requirements->>'non_personal_basis'
           IN ('environmental_measurement',
               'non_personal_operational_measurement',
               'infrastructure_measurement') THEN
        IF requested_participant_link_id IS NOT NULL THEN
            RAISE EXCEPTION 'Non-personal protocol observations cannot identify participants'
                USING ERRCODE = '42501';
        END IF;
        consent_state := 'not_required';
    ELSE
        RAISE EXCEPTION 'Protocol has no recognized consent policy; a new protocol is required'
            USING ERRCODE = '55000';
    END IF;

    new_observation_id := pg_catalog.gen_random_uuid();
    INSERT INTO public.solution_experiment_observation (
        id, experiment_id, observed_at, unit_ref, metric_key, value, arm,
        adverse_event, evidence, recorded_by_party_id, participant_link_id,
        consent_event_id, consent_validation_status
    ) VALUES (
        new_observation_id, requested_experiment_id, capture_time,
        requested_unit_ref, requested_metric_key, requested_value, requested_arm,
        requested_adverse_event, requested_evidence, actor_party_id,
        requested_participant_link_id, consent_id, consent_state
    );
    INSERT INTO public.solution_experiment_observation_capture_receipt (
        operator_id, actor_party_id, location_id, solution_id, experiment_id,
        observation_id, consent_event_id, request_id, payload_digest, observed_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        experiment_record.solution_id, requested_experiment_id,
        new_observation_id, consent_id, requested_request_id,
        payload_digest, capture_time
    );
    RETURN QUERY SELECT new_observation_id, requested_experiment_id,
                        requested_metric_key, capture_time, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_experiment_observer;
ALTER FUNCTION kokonut_security.capture_location_solution_experiment_observation(
    UUID, UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, BOOLEAN, JSONB, UUID, BOOLEAN
) OWNER TO kokonut_solution_experiment_observer;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_experiment_observer;
REVOKE ALL ON FUNCTION kokonut_security.capture_location_solution_experiment_observation(
    UUID, UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, BOOLEAN, JSONB, UUID, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.capture_location_solution_experiment_observation(
            UUID, UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, BOOLEAN, JSONB, UUID, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.capture_location_solution_experiment_observation(
            UUID, UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, BOOLEAN, JSONB, UUID, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_experiment_observation_capture_receipt IS
    'Private append-only retries for location-scoped experiment observation capture.';
COMMENT ON FUNCTION kokonut_security.capture_location_solution_experiment_observation(
    UUID, UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, BOOLEAN, JSONB, UUID, BOOLEAN
) IS
    'Captures protocol-declared measurements only for an active exact-origin experiment; participant data requires a current exact-location canonical consent event and active location-scoped participant link.';

COMMIT;
