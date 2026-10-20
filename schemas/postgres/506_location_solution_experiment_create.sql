-- Create immutable experiment protocol drafts under signed exact-location scope.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_creator'
    ) THEN
        CREATE ROLE kokonut_solution_experiment_creator
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_experiment_creator'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution experiment creator role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_experiment_creator'
            OR member_role.rolname = 'kokonut_solution_experiment_creator'
    ) THEN
        RAISE EXCEPTION 'Solution experiment creator role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_experiment_creation_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    experiment_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_experiment(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_experiment_creation_receipt FROM PUBLIC;
DO $$
DECLARE target_role TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime',
        'kokonut_solution_experiment_creator'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.solution_experiment_creation_receipt FROM %I',
                target_role
            );
        END IF;
    END LOOP;
END;
$$;

-- Keep the legacy lifecycle fields writable for the existing submission,
-- approval, start, completion, and reviewed-result paths. Protocol definitions
-- themselves can only be inserted by the bounded function below.
DO $$
DECLARE
    target_role TEXT;
    target_column TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE INSERT, UPDATE, DELETE ON TABLE public.solution_experiment FROM %I',
                target_role
            );
            FOR target_column IN
                SELECT attname
                  FROM pg_catalog.pg_attribute
                 WHERE attrelid = 'public.solution_experiment'::regclass
                   AND attnum > 0 AND NOT attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%I), UPDATE (%I) ON TABLE public.solution_experiment FROM %I',
                    target_column, target_column, target_role
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT UPDATE (
            status, approved_by_party_id, approved_at, started_at, completed_at, updated_at
        ) ON TABLE public.solution_experiment TO kokonut_runtime;
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_experiment_creator;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_experiment_creator;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_experiment_creator;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_experiment_creator;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_experiment_creator;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_experiment_creator;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_creator;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_experiment_creator;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_creator;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_experiment_creator;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_experiment_creator;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_experiment_creator;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_experiment_creator;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_experiment_creator;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_experiment_creator;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_experiment_creator;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_experiment_creator;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_experiment_creator;
GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage, status)
    ON TABLE public.solution TO kokonut_solution_experiment_creator;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_experiment_creator;
GRANT INSERT (
    solution_id, hypothesis, null_hypothesis, protocol_version,
    baseline_definition, treatment_definition, comparator_definition,
    unit_of_analysis, sample_plan, primary_metric_keys, secondary_metric_keys,
    minimum_detectable_effect, confidence_target, duration_days, stopping_rules,
    rollback_plan, safety_boundaries, consent_requirements, owner_party_id, status
) ON TABLE public.solution_experiment TO kokonut_solution_experiment_creator;
GRANT SELECT (id, solution_id, protocol_version, status, created_at)
    ON TABLE public.solution_experiment TO kokonut_solution_experiment_creator;
GRANT SELECT (
    id, operator_id, actor_party_id, location_id, solution_id, experiment_id,
    request_id, payload_digest, created_at
) ON TABLE public.solution_experiment_creation_receipt
    TO kokonut_solution_experiment_creator;
GRANT INSERT (
    operator_id, actor_party_id, location_id, solution_id, experiment_id,
    request_id, payload_digest, created_at
) ON TABLE public.solution_experiment_creation_receipt
    TO kokonut_solution_experiment_creator;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_experiment_creator;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_experiment_creator;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_experiment_creator;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_solution_experiment(
    requested_location_id UUID,
    requested_solution_id UUID,
    requested_request_id UUID,
    requested_protocol JSONB,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    experiment_id UUID,
    solution_id UUID,
    protocol_version TEXT,
    experiment_status TEXT,
    experiment_created_at TIMESTAMPTZ,
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
    solution_record RECORD;
    experiment_record RECORD;
    prior_receipt RECORD;
    payload_digest BYTEA;
    protocol_keys TEXT[] := ARRAY[
        'hypothesis', 'null_hypothesis', 'baseline_definition',
        'treatment_definition', 'comparator_definition', 'unit_of_analysis',
        'sample_plan', 'primary_metric_keys', 'secondary_metric_keys',
        'minimum_detectable_effect', 'confidence_target', 'duration_days',
        'stopping_rules', 'rollback_plan', 'safety_boundaries',
        'consent_requirements'
    ];
    json_key TEXT;
    metrics JSONB;
    metric_key TEXT;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_solution_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Experiment creation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Experiment creation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE
       OR requested_protocol IS NULL
       OR pg_catalog.jsonb_typeof(requested_protocol) IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length(requested_protocol::TEXT) > 65536 THEN
        RAISE EXCEPTION 'Experiment protocol draft input is invalid'
            USING ERRCODE = '22023';
    END IF;
    FOR json_key IN SELECT pg_catalog.jsonb_object_keys(requested_protocol)
    LOOP
        IF NOT json_key = ANY (protocol_keys) THEN
            RAISE EXCEPTION 'Experiment protocol contains an unsupported field'
                USING ERRCODE = '22023';
        END IF;
    END LOOP;
    IF requested_protocol->>'hypothesis' IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_protocol->>'hypothesis')) NOT BETWEEN 1 AND 4000
       OR requested_protocol->>'baseline_definition' IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_protocol->>'baseline_definition')) NOT BETWEEN 1 AND 4000
       OR requested_protocol->>'treatment_definition' IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_protocol->>'treatment_definition')) NOT BETWEEN 1 AND 4000
       OR requested_protocol->>'unit_of_analysis' IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_protocol->>'unit_of_analysis')) NOT BETWEEN 1 AND 255
       OR requested_protocol->>'rollback_plan' IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_protocol->>'rollback_plan')) NOT BETWEEN 1 AND 4000 THEN
        RAISE EXCEPTION 'Experiment protocol draft text is invalid'
            USING ERRCODE = '22023';
    END IF;
    FOREACH json_key IN ARRAY ARRAY['null_hypothesis', 'comparator_definition'] LOOP
        IF requested_protocol ? json_key
           AND (pg_catalog.jsonb_typeof(requested_protocol->json_key) IS DISTINCT FROM 'string'
                OR pg_catalog.length(requested_protocol->>json_key) > 4000) THEN
            RAISE EXCEPTION 'Experiment protocol optional text is invalid'
                USING ERRCODE = '22023';
        END IF;
    END LOOP;
    FOREACH json_key IN ARRAY ARRAY[
        'sample_plan', 'stopping_rules', 'safety_boundaries', 'consent_requirements'
    ] LOOP
        IF requested_protocol ? json_key
           AND (pg_catalog.jsonb_typeof(requested_protocol->json_key) IS DISTINCT FROM 'object'
                OR pg_catalog.octet_length((requested_protocol->json_key)::TEXT) > 8192) THEN
            RAISE EXCEPTION 'Experiment protocol object is invalid'
                USING ERRCODE = '22023';
        END IF;
    END LOOP;
    FOREACH json_key IN ARRAY ARRAY['primary_metric_keys', 'secondary_metric_keys'] LOOP
        metrics := COALESCE(requested_protocol->json_key, '[]'::JSONB);
        IF pg_catalog.jsonb_typeof(metrics) IS DISTINCT FROM 'array'
           OR pg_catalog.jsonb_array_length(metrics) > 50
           OR pg_catalog.octet_length(metrics::TEXT) > 8192 THEN
            RAISE EXCEPTION 'Experiment metric-key list is invalid'
                USING ERRCODE = '22023';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.jsonb_array_elements(metrics) AS item(value)
             WHERE pg_catalog.jsonb_typeof(item.value) IS DISTINCT FROM 'string'
        ) THEN
            RAISE EXCEPTION 'Experiment metric-key list is invalid'
                USING ERRCODE = '22023';
        END IF;
        FOR metric_key IN
            SELECT item.value #>> '{}'
              FROM pg_catalog.jsonb_array_elements(metrics) AS item(value)
        LOOP
            IF pg_catalog.length(metric_key) NOT BETWEEN 1 AND 120
               OR metric_key !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$' THEN
                RAISE EXCEPTION 'Experiment metric-key list is invalid'
                    USING ERRCODE = '22023';
            END IF;
        END LOOP;
        IF (SELECT pg_catalog.count(*) FROM pg_catalog.jsonb_array_elements(metrics))
           <> (SELECT pg_catalog.count(DISTINCT value)
                 FROM pg_catalog.jsonb_array_elements_text(metrics) AS item(value)) THEN
            RAISE EXCEPTION 'Experiment metric keys must be unique'
                USING ERRCODE = '22023';
        END IF;
    END LOOP;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.jsonb_array_elements_text(
                   COALESCE(requested_protocol->'primary_metric_keys', '[]'::JSONB)
               ) AS primary_item(value)
          JOIN pg_catalog.jsonb_array_elements_text(
                   COALESCE(requested_protocol->'secondary_metric_keys', '[]'::JSONB)
               ) AS secondary_item(value) USING (value)
    ) THEN
        RAISE EXCEPTION 'Primary and secondary experiment metrics must be distinct'
            USING ERRCODE = '22023';
    END IF;
    IF requested_protocol ? 'minimum_detectable_effect'
       AND (pg_catalog.jsonb_typeof(requested_protocol->'minimum_detectable_effect') IS DISTINCT FROM 'number'
            OR pg_catalog.abs((requested_protocol->>'minimum_detectable_effect')::NUMERIC) > 1000000000000) THEN
        RAISE EXCEPTION 'Experiment effect threshold is invalid'
            USING ERRCODE = '22023';
    END IF;
    IF requested_protocol ? 'confidence_target'
       AND (pg_catalog.jsonb_typeof(requested_protocol->'confidence_target') IS DISTINCT FROM 'number'
            OR (requested_protocol->>'confidence_target')::NUMERIC NOT BETWEEN 0.5 AND 1) THEN
        RAISE EXCEPTION 'Experiment confidence target is invalid'
            USING ERRCODE = '22023';
    END IF;
    IF requested_protocol ? 'duration_days'
       AND (pg_catalog.jsonb_typeof(requested_protocol->'duration_days') IS DISTINCT FROM 'number'
            OR (requested_protocol->>'duration_days')::NUMERIC NOT BETWEEN 1 AND 3650
            OR (requested_protocol->>'duration_days')::NUMERIC
               <> pg_catalog.trunc((requested_protocol->>'duration_days')::NUMERIC)) THEN
        RAISE EXCEPTION 'Experiment duration is invalid'
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
        RAISE EXCEPTION 'Experiment creation requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'solution_id', requested_solution_id,
                'protocol', requested_protocol,
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
           receipt.experiment_id, receipt.payload_digest
      INTO prior_receipt
      FROM public.solution_experiment_creation_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.solution_id IS DISTINCT FROM requested_solution_id
           OR prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Experiment request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        SELECT experiment.id, experiment.solution_id, experiment.protocol_version,
               experiment.status, experiment.created_at
          INTO experiment_record
          FROM public.solution_experiment AS experiment
         WHERE experiment.id = prior_receipt.experiment_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Experiment creation receipt is incomplete'
                USING ERRCODE = '55000';
        END IF;
        RETURN QUERY SELECT experiment_record.id, experiment_record.solution_id,
                            experiment_record.protocol_version::TEXT,
                            experiment_record.status::TEXT,
                            experiment_record.created_at, TRUE;
        RETURN;
    END IF;

    SELECT solution.id, solution.current_stage, solution.status
      INTO solution_record
      FROM public.solution AS solution
     WHERE solution.id = requested_solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
     FOR UPDATE OF solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location-origin solution was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF solution_record.status IS DISTINCT FROM 'active'
       OR solution_record.current_stage NOT IN ('experiment_ready', 'testing') THEN
        RAISE EXCEPTION 'Solution must be active and experiment-ready to draft a protocol'
            USING ERRCODE = '55000';
    END IF;

    INSERT INTO public.solution_experiment AS created_experiment (
        solution_id, hypothesis, null_hypothesis, protocol_version,
        baseline_definition, treatment_definition, comparator_definition,
        unit_of_analysis, sample_plan, primary_metric_keys, secondary_metric_keys,
        minimum_detectable_effect, confidence_target, duration_days, stopping_rules,
        rollback_plan, safety_boundaries, consent_requirements, owner_party_id, status
    ) VALUES (
        requested_solution_id,
        pg_catalog.btrim(requested_protocol->>'hypothesis'),
        NULLIF(requested_protocol->>'null_hypothesis', ''),
        'v1',
        pg_catalog.btrim(requested_protocol->>'baseline_definition'),
        pg_catalog.btrim(requested_protocol->>'treatment_definition'),
        NULLIF(requested_protocol->>'comparator_definition', ''),
        pg_catalog.btrim(requested_protocol->>'unit_of_analysis'),
        COALESCE(requested_protocol->'sample_plan', '{}'::JSONB),
        COALESCE(requested_protocol->'primary_metric_keys', '[]'::JSONB),
        COALESCE(requested_protocol->'secondary_metric_keys', '[]'::JSONB),
        (requested_protocol->>'minimum_detectable_effect')::NUMERIC,
        (requested_protocol->>'confidence_target')::NUMERIC,
        (requested_protocol->>'duration_days')::INTEGER,
        COALESCE(requested_protocol->'stopping_rules', '{}'::JSONB),
        pg_catalog.btrim(requested_protocol->>'rollback_plan'),
        COALESCE(requested_protocol->'safety_boundaries', '{}'::JSONB),
        COALESCE(requested_protocol->'consent_requirements', '{}'::JSONB),
        actor_party_id, 'draft'
    ) RETURNING created_experiment.id, created_experiment.solution_id,
                created_experiment.protocol_version, created_experiment.status,
                created_experiment.created_at
         INTO experiment_record;

    INSERT INTO public.solution_experiment_creation_receipt (
        operator_id, actor_party_id, location_id, solution_id, experiment_id,
        request_id, payload_digest, created_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        requested_solution_id, experiment_record.id, requested_request_id,
        payload_digest, experiment_record.created_at
    );
    RETURN QUERY SELECT experiment_record.id, experiment_record.solution_id,
                        experiment_record.protocol_version::TEXT,
                        experiment_record.status::TEXT,
                        experiment_record.created_at, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_experiment_creator;
ALTER FUNCTION kokonut_security.create_location_solution_experiment(
    UUID, UUID, UUID, JSONB, BOOLEAN
) OWNER TO kokonut_solution_experiment_creator;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_experiment_creator;
REVOKE ALL ON FUNCTION kokonut_security.create_location_solution_experiment(
    UUID, UUID, UUID, JSONB, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_solution_experiment(
            UUID, UUID, UUID, JSONB, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_location_solution_experiment(
            UUID, UUID, UUID, JSONB, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_solution_experiment(
    UUID, UUID, UUID, JSONB, BOOLEAN
) IS 'Creates an immutable draft experiment protocol under signed exact-location solution_lifecycle:create context. Only exact-origin active experiment-ready solutions are eligible; submit, approve, observe, execute, and review remain separate actions.';

COMMIT;
