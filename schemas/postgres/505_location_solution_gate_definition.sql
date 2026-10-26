-- Create immutable, location-originated promotion-gate definitions in draft state.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_gate_creator'
    ) THEN
        CREATE ROLE kokonut_solution_gate_creator
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_gate_creator'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution gate creator role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_gate_creator'
            OR member_role.rolname = 'kokonut_solution_gate_creator'
    ) THEN
        RAISE EXCEPTION 'Solution gate creator role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_gate_definition_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    gate_id UUID NOT NULL UNIQUE REFERENCES public.solution_stage_gate(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_gate_definition_receipt FROM PUBLIC;
DO $$
DECLARE target_role TEXT; target_column TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.solution_stage_gate FROM %I',
                target_role
            );
            FOR target_column IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.solution_stage_gate'::regclass
                   AND attribute.attnum > 0 AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE SELECT (%1$I), INSERT (%1$I), UPDATE (%1$I) ON TABLE public.solution_stage_gate FROM %2$I',
                    target_column, target_role
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;
DO $$
DECLARE target_role TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime', 'kokonut_solution_reader',
        'kokonut_solution_gate_creator', 'kokonut_solution_gate_evaluator',
        'kokonut_solution_gate_reviewer', 'kokonut_solution_gate_approver',
        'kokonut_solution_gate_transitioner'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.solution_gate_definition_receipt FROM %I',
                target_role
            );
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_gate_creator;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_gate_creator;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_gate_creator;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_gate_creator;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_gate_creator;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_gate_creator;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_gate_creator;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_gate_creator;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_gate_creator;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_gate_creator;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_gate_creator;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_gate_creator;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_gate_creator;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_gate_creator;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_gate_creator;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_gate_creator;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_gate_creator;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_gate_creator;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_gate_creator;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_gate_creator;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_gate_creator;
GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage, status)
    ON TABLE public.solution TO kokonut_solution_gate_creator;
GRANT UPDATE (id) ON TABLE public.solution TO kokonut_solution_gate_creator;
GRANT INSERT (
    solution_id, from_stage, to_stage, required_evidence_maturity,
    required_experiment_count, minimum_evaluation_count,
    requires_human_approval, requirements, status
) ON TABLE public.solution_stage_gate TO kokonut_solution_gate_creator;
GRANT SELECT (
    id, solution_id, from_stage, to_stage, required_evidence_maturity,
    required_experiment_count, minimum_evaluation_count,
    requires_human_approval, requirements, status, approved_by_party_id,
    approved_at, created_at
) ON TABLE public.solution_stage_gate TO kokonut_solution_gate_creator;
GRANT SELECT (
    id, operator_id, actor_party_id, location_id, solution_id, gate_id,
    request_id, payload_digest, created_at
) ON TABLE public.solution_gate_definition_receipt
    TO kokonut_solution_gate_creator;
GRANT INSERT (
    operator_id, actor_party_id, location_id, solution_id, gate_id,
    request_id, payload_digest, created_at
) ON TABLE public.solution_gate_definition_receipt
    TO kokonut_solution_gate_creator;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_solution_gate(
    requested_location_id UUID,
    requested_solution_id UUID,
    requested_request_id UUID,
    requested_to_stage TEXT,
    requested_criterion TEXT,
    requested_required_evidence_maturity INTEGER,
    requested_required_experiment_count INTEGER,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    gate_id UUID,
    solution_id UUID,
    from_stage TEXT,
    to_stage TEXT,
    gate_criterion TEXT,
    required_evidence_maturity INTEGER,
    required_experiment_count INTEGER,
    minimum_evaluation_count INTEGER,
    requires_human_approval BOOLEAN,
    gate_status TEXT,
    gate_created_at TIMESTAMPTZ,
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
    gate_record RECORD;
    existing RECORD;
    expected_to_stage TEXT;
    payload_digest BYTEA;
    normalized_criterion TEXT;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_solution_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Solution gate creation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution gate creation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_to_stage IS NULL
       OR requested_to_stage NOT IN ('validated', 'funded', 'adoption_ready', 'scaled')
       OR requested_required_evidence_maturity IS NOT NULL
          AND requested_required_evidence_maturity NOT BETWEEN 1 AND 6
       OR requested_required_experiment_count IS NULL
          OR requested_required_experiment_count NOT BETWEEN 0 AND 100
       OR requested_criterion IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_criterion)) NOT BETWEEN 10 AND 2000
       OR pg_catalog.octet_length(requested_criterion) > 4000
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Location solution gate definition is invalid'
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
        RAISE EXCEPTION 'Solution gate creation requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    normalized_criterion := pg_catalog.btrim(requested_criterion);
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.location_id, receipt.solution_id, receipt.gate_id,
           receipt.actor_party_id, receipt.payload_digest
      INTO existing
      FROM public.solution_gate_definition_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.solution_id IS DISTINCT FROM requested_solution_id
           OR existing.actor_party_id IS DISTINCT FROM actor_party_id THEN
            RAISE EXCEPTION 'Solution gate request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        SELECT gate.id, gate.solution_id, gate.from_stage, gate.to_stage,
               gate.requirements ->> 'criterion' AS criterion,
               gate.required_evidence_maturity,
               gate.required_experiment_count, gate.minimum_evaluation_count,
               gate.requires_human_approval, gate.status, gate.created_at
          INTO gate_record
          FROM public.solution_stage_gate AS gate
         WHERE gate.id = existing.gate_id;
        payload_digest := public.digest(
            pg_catalog.convert_to(
                pg_catalog.jsonb_build_object(
                    'location_id', requested_location_id,
                    'solution_id', requested_solution_id,
                    'from_stage', gate_record.from_stage,
                    'to_stage', requested_to_stage,
                    'criterion', normalized_criterion,
                    'required_evidence_maturity', requested_required_evidence_maturity,
                    'required_experiment_count', requested_required_experiment_count,
                    'acknowledged', requested_acknowledged
                )::TEXT,
                'UTF8'
            ),
            'sha256'
        );
        IF gate_record.id IS NULL
           OR existing.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Solution gate request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT gate_record.id, gate_record.solution_id,
                            gate_record.from_stage::TEXT, gate_record.to_stage::TEXT,
                            gate_record.criterion::TEXT,
                            gate_record.required_evidence_maturity,
                            gate_record.required_experiment_count,
                            gate_record.minimum_evaluation_count,
                            gate_record.requires_human_approval,
                            gate_record.status::TEXT, gate_record.created_at, TRUE;
        RETURN;
    END IF;

    SELECT solution.id, solution.current_stage
      INTO solution_record
      FROM public.solution AS solution
     WHERE solution.id = requested_solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.status = 'active'
     FOR UPDATE OF solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location-origin active solution was not found'
            USING ERRCODE = 'P0002';
    END IF;

    expected_to_stage := CASE solution_record.current_stage
        WHEN 'testing' THEN 'validated'
        WHEN 'investment_ready' THEN 'funded'
        WHEN 'pilot_active' THEN 'adoption_ready'
        WHEN 'adopting' THEN 'scaled'
        ELSE NULL
    END;
    IF expected_to_stage IS DISTINCT FROM requested_to_stage THEN
        RAISE EXCEPTION 'Gate target does not match the current supported promotion'
            USING ERRCODE = '55000';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'solution_id', requested_solution_id,
                'from_stage', solution_record.current_stage,
                'to_stage', requested_to_stage,
                'criterion', normalized_criterion,
                'required_evidence_maturity', requested_required_evidence_maturity,
                'required_experiment_count', requested_required_experiment_count,
                'acknowledged', requested_acknowledged
            )::TEXT,
            'UTF8'
        ),
        'sha256'
    );
    INSERT INTO public.solution_stage_gate (
        solution_id, from_stage, to_stage, required_evidence_maturity,
        required_experiment_count, minimum_evaluation_count,
        requires_human_approval, requirements, status
    ) VALUES (
        requested_solution_id, solution_record.current_stage, requested_to_stage,
        requested_required_evidence_maturity, requested_required_experiment_count,
        1, TRUE, pg_catalog.jsonb_build_object('criterion', normalized_criterion), 'draft'
    ) RETURNING id, solution_id, from_stage, to_stage,
                requirements ->> 'criterion' AS criterion,
                required_evidence_maturity,
                required_experiment_count, minimum_evaluation_count,
                requires_human_approval, status, created_at
         INTO gate_record;

    INSERT INTO public.solution_gate_definition_receipt (
        operator_id, actor_party_id, location_id, solution_id, gate_id,
        request_id, payload_digest, created_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        requested_solution_id, gate_record.id, requested_request_id,
        payload_digest, gate_record.created_at
    );
    RETURN QUERY SELECT gate_record.id, gate_record.solution_id,
                        gate_record.from_stage::TEXT, gate_record.to_stage::TEXT,
                        gate_record.criterion::TEXT,
                        gate_record.required_evidence_maturity,
                        gate_record.required_experiment_count,
                        gate_record.minimum_evaluation_count,
                        gate_record.requires_human_approval,
                        gate_record.status::TEXT, gate_record.created_at, FALSE;
END;
$$;

-- Criteria are visible only for solutions owned by the requested location. A
-- linked solution from another origin keeps its definition private.
GRANT SELECT (requirements) ON TABLE public.solution_stage_gate
    TO kokonut_solution_reader, kokonut_solution_gate_reviewer;

DROP FUNCTION kokonut_security.list_location_solution_gates(UUID, INTEGER, INTEGER);
CREATE FUNCTION kokonut_security.list_location_solution_gates(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    solution_id UUID, solution_name TEXT, solution_type TEXT,
    current_stage TEXT, solution_status TEXT, gate_id UUID,
    from_stage TEXT, to_stage TEXT, gate_criterion TEXT,
    required_evidence_maturity INTEGER, required_experiment_count INTEGER,
    requires_human_approval BOOLEAN, gate_status TEXT,
    gate_created_at TIMESTAMPTZ, latest_evaluation_passed BOOLEAN,
    latest_evaluated_at TIMESTAMPTZ
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Solution gate read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution gate read requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Solution gate page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;
    RETURN QUERY
    WITH scoped_solutions AS (
        SELECT solution.id, solution.name, solution.solution_type,
               solution.current_stage, solution.status,
               (solution.originating_scope_type = 'location'
                AND solution.originating_scope_id = requested_location_id) AS is_origin
          FROM public.solution AS solution
         WHERE (solution.originating_scope_type = 'location'
                AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1 FROM public.solution_link AS location_link
                 WHERE location_link.solution_id = solution.id
                   AND location_link.entity_type = 'location'
                   AND location_link.entity_id = requested_location_id
            )
    )
    SELECT scoped.id, pg_catalog.left(scoped.name, 255)::TEXT,
           scoped.solution_type::TEXT, scoped.current_stage::TEXT,
           scoped.status::TEXT, gate.id, gate.from_stage::TEXT,
           gate.to_stage::TEXT,
           CASE WHEN scoped.is_origin THEN gate.requirements ->> 'criterion' END,
           gate.required_evidence_maturity, gate.required_experiment_count,
           gate.requires_human_approval, gate.status::TEXT, gate.created_at,
           latest.passed, latest.evaluated_at
      FROM scoped_solutions AS scoped
      JOIN public.solution_stage_gate AS gate ON gate.solution_id = scoped.id
      LEFT JOIN LATERAL (
          SELECT evaluation.passed, evaluation.evaluated_at
            FROM public.solution_gate_evaluation AS evaluation
           WHERE evaluation.gate_id = gate.id
           ORDER BY evaluation.evaluated_at DESC, evaluation.id DESC
           LIMIT 1
      ) AS latest ON TRUE
     ORDER BY gate.created_at DESC, gate.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

DROP FUNCTION kokonut_security.location_solution_gate_review(UUID, UUID);
CREATE FUNCTION kokonut_security.location_solution_gate_review(
    requested_location_id UUID,
    requested_gate_id UUID
)
RETURNS TABLE (
    gate_id UUID, from_stage TEXT, to_stage TEXT, gate_criterion TEXT,
    requires_human_approval BOOLEAN, gate_status TEXT,
    evaluation_passed BOOLEAN, observed JSONB, evidence JSONB,
    evaluated_at TIMESTAMPTZ
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE context_record RECORD; reviewer_party_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_gate_id IS NULL THEN
        RAISE EXCEPTION 'Solution gate review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution gate review requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id INTO reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Solution gate review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT gate.id, gate.from_stage::TEXT, gate.to_stage::TEXT,
           gate.requirements ->> 'criterion', gate.requires_human_approval,
           gate.status::TEXT, latest.passed, latest.observed,
           latest.evidence, latest.evaluated_at
      FROM public.solution_stage_gate AS gate
      JOIN public.solution AS solution ON solution.id = gate.solution_id
      LEFT JOIN LATERAL (
          SELECT evaluation.passed, evaluation.observed, evaluation.evidence,
                 evaluation.evaluated_at
            FROM public.solution_gate_evaluation AS evaluation
           WHERE evaluation.gate_id = gate.id
           ORDER BY evaluation.evaluated_at DESC, evaluation.id DESC
           LIMIT 1
      ) AS latest ON TRUE
     WHERE gate.id = requested_gate_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_gate_creator,
    kokonut_solution_reader, kokonut_solution_gate_reviewer;
ALTER FUNCTION kokonut_security.create_location_solution_gate(
    UUID, UUID, UUID, TEXT, TEXT, INTEGER, INTEGER, BOOLEAN
) OWNER TO kokonut_solution_gate_creator;
ALTER FUNCTION kokonut_security.list_location_solution_gates(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_reader;
ALTER FUNCTION kokonut_security.location_solution_gate_review(UUID, UUID)
    OWNER TO kokonut_solution_gate_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_gate_creator,
    kokonut_solution_reader, kokonut_solution_gate_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.create_location_solution_gate(
    UUID, UUID, UUID, TEXT, TEXT, INTEGER, INTEGER, BOOLEAN
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_gates(UUID, INTEGER, INTEGER)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_gate_review(UUID, UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_solution_gate(
            UUID, UUID, UUID, TEXT, TEXT, INTEGER, INTEGER, BOOLEAN
        ), kokonut_security.list_location_solution_gates(UUID, INTEGER, INTEGER),
          kokonut_security.location_solution_gate_review(UUID, UUID)
        TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_location_solution_gate(
            UUID, UUID, UUID, TEXT, TEXT, INTEGER, INTEGER, BOOLEAN
        ), kokonut_security.list_location_solution_gates(UUID, INTEGER, INTEGER),
          kokonut_security.location_solution_gate_review(UUID, UUID)
        FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_solution_gate(
    UUID, UUID, UUID, TEXT, TEXT, INTEGER, INTEGER, BOOLEAN
) IS 'Creates one exact-origin promotion gate in immutable draft state under signed solution_lifecycle:create context. The definition is fixed to the supported current-stage promotion, requires independent human approval, and never evaluates, approves, or transitions the solution.';
COMMENT ON TABLE public.solution_gate_definition_receipt IS
'Private immutable idempotency receipts for exact-location draft gate definitions.';

COMMIT;
