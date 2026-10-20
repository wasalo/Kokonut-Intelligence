-- Add signed location-scoped assessment and independent review for solution scale gates.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_scale_gate_owner'
    ) THEN
        CREATE ROLE kokonut_solution_scale_gate_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_scale_gate_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution scale-gate owner role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_scale_gate_owner'
            OR member_role.rolname = 'kokonut_solution_scale_gate_owner'
    ) THEN
        RAISE EXCEPTION 'Solution scale-gate owner role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_scale_gate_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    gate_id UUID NOT NULL REFERENCES public.solution_scale_gate(id) ON DELETE RESTRICT,
    evaluator_operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    evaluator_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    passed BOOLEAN NOT NULL,
    measured_value TEXT NOT NULL
        CHECK (pg_catalog.char_length(pg_catalog.btrim(measured_value)) BETWEEN 1 AND 1000),
    measured_numeric NUMERIC,
    sample_size INTEGER NOT NULL CHECK (sample_size > 0),
    evidence_refs JSONB NOT NULL CHECK (pg_catalog.jsonb_typeof(evidence_refs) = 'array'),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    review_decision TEXT CHECK (review_decision IN ('accepted', 'rejected')),
    review_reason TEXT CHECK (review_reason IS NULL OR pg_catalog.char_length(review_reason) <= 4000),
    reviewer_operator_id UUID REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID REFERENCES public.party(id) ON DELETE RESTRICT,
    review_request_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    reviewed_at TIMESTAMPTZ,
    UNIQUE (evaluator_operator_id, request_id),
    UNIQUE (reviewer_operator_id, review_request_id),
    CHECK (
        (status = 'pending' AND review_decision IS NULL AND review_reason IS NULL
         AND reviewer_operator_id IS NULL AND reviewer_party_id IS NULL
         AND review_request_id IS NULL AND reviewed_at IS NULL)
        OR
        (status = 'approved' AND review_decision = 'accepted'
         AND reviewer_operator_id IS NOT NULL AND reviewer_party_id IS NOT NULL
         AND review_request_id IS NOT NULL AND reviewed_at IS NOT NULL)
        OR
        (status = 'rejected' AND review_decision = 'rejected'
         AND pg_catalog.char_length(pg_catalog.btrim(COALESCE(review_reason, ''))) >= 10
         AND reviewer_operator_id IS NOT NULL AND reviewer_party_id IS NOT NULL
         AND review_request_id IS NOT NULL AND reviewed_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_solution_scale_gate_one_pending_assessment
    ON public.solution_scale_gate_assessment (gate_id)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_solution_scale_gate_assessment_review_queue
    ON public.solution_scale_gate_assessment (location_id, created_at DESC, id DESC)
    WHERE status = 'pending';

REVOKE ALL ON TABLE public.solution_scale_gate_assessment FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_scale_gate_assessment
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader;

-- The legacy scale helper has no authenticated tenant context. Remove direct runtime
-- writes to the gate itself; all new evaluation changes pass through bounded functions.
REVOKE ALL ON TABLE public.solution_scale_gate
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_scale_gate_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_scale_gate_owner;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_scale_gate_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_scale_gate_owner;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_scale_gate_owner;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_scale_gate_owner;

GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_scale_gate_owner;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_scale_gate_owner;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_scale_gate_owner;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_scale_gate_owner;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_scale_gate_owner;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_scale_gate_owner;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_scale_gate_owner;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_scale_gate_owner;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_scale_gate_owner;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_scale_gate_owner;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_scale_gate_owner;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_scale_gate_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_scale_gate_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_scale_gate_owner;

GRANT SELECT (
    id, name, solution_type, current_stage, status,
    originating_scope_type, originating_scope_id
) ON TABLE public.solution TO kokonut_solution_scale_gate_owner;
GRANT SELECT (solution_id, entity_type, entity_id)
    ON TABLE public.solution_link TO kokonut_solution_scale_gate_owner;
GRANT SELECT (
    id, solution_id, scope_type, scope_id, gate_type, requirement,
    measured_value, threshold, evidence_refs, status, approved_by_party_id,
    approved_at, metric_key, comparison_operator, threshold_numeric, unit,
    minimum_sample
) ON TABLE public.solution_scale_gate TO kokonut_solution_scale_gate_owner;
GRANT UPDATE (status, measured_value, evidence_refs, approved_by_party_id, approved_at)
    ON TABLE public.solution_scale_gate TO kokonut_solution_scale_gate_owner;
GRANT UPDATE (id) ON TABLE public.solution_scale_gate
    TO kokonut_solution_scale_gate_owner;
GRANT SELECT, INSERT, UPDATE ON TABLE public.solution_scale_gate_assessment
    TO kokonut_solution_scale_gate_owner;

CREATE OR REPLACE FUNCTION kokonut_security.guard_solution_scale_gate_assessment()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Scale-gate assessments are append-only'
            USING ERRCODE = '42501';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status IS DISTINCT FROM 'pending'
           OR NEW.review_decision IS NOT NULL
           OR NEW.reviewer_operator_id IS NOT NULL
           OR NEW.reviewer_party_id IS NOT NULL
           OR NEW.review_request_id IS NOT NULL
           OR NEW.reviewed_at IS NOT NULL THEN
            RAISE EXCEPTION 'Scale-gate assessments must begin pending independent review'
                USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;
    IF CURRENT_USER <> 'kokonut_solution_scale_gate_owner'
       OR OLD.status <> 'pending'
       OR NEW.status NOT IN ('approved', 'rejected')
       OR (NEW.id, NEW.location_id, NEW.solution_id, NEW.gate_id,
           NEW.evaluator_operator_id, NEW.evaluator_party_id, NEW.request_id,
           NEW.passed, NEW.measured_value, NEW.measured_numeric, NEW.sample_size,
           NEW.evidence_refs, NEW.created_at)
          IS DISTINCT FROM
          (OLD.id, OLD.location_id, OLD.solution_id, OLD.gate_id,
           OLD.evaluator_operator_id, OLD.evaluator_party_id, OLD.request_id,
           OLD.passed, OLD.measured_value, OLD.measured_numeric, OLD.sample_size,
           OLD.evidence_refs, OLD.created_at)
       OR NEW.review_decision NOT IN ('accepted', 'rejected')
       OR NEW.reviewer_operator_id IS NULL
       OR NEW.reviewer_party_id IS NULL
       OR NEW.review_request_id IS NULL
       OR NEW.reviewed_at IS NULL THEN
        RAISE EXCEPTION 'Scale-gate assessment review must be a single attributed decision'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS solution_scale_gate_assessment_append_only
    ON public.solution_scale_gate_assessment;
CREATE TRIGGER solution_scale_gate_assessment_append_only
    BEFORE INSERT OR UPDATE OR DELETE ON public.solution_scale_gate_assessment
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.guard_solution_scale_gate_assessment();

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_scale_gate_assessment_targets(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    solution_id UUID,
    solution_name TEXT,
    scale_gate_id UUID,
    gate_type TEXT,
    requirement TEXT,
    threshold TEXT,
    metric_key TEXT,
    comparison_operator TEXT,
    threshold_numeric NUMERIC,
    unit TEXT,
    minimum_sample INTEGER,
    gate_status TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Scale-gate assessment targets require signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Scale-gate assessment targets require an active exact location create grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id INTO actor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS human
        ON human.id = binding.party_id
       AND human.party_type = 'person' AND human.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Scale-gate assessment requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Scale-gate assessment page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT solution.id, pg_catalog.left(solution.name, 255)::TEXT,
           gate.id, gate.gate_type::TEXT,
           pg_catalog.left(gate.requirement, 2000)::TEXT,
           pg_catalog.left(gate.threshold, 1000)::TEXT,
           gate.metric_key::TEXT, gate.comparison_operator::TEXT,
           gate.threshold_numeric, gate.unit::TEXT, gate.minimum_sample,
           gate.status::TEXT
      FROM public.solution_scale_gate AS gate
      JOIN public.solution AS solution ON solution.id = gate.solution_id
     WHERE gate.scope_type = 'location'
       AND gate.scope_id = requested_location_id
       AND gate.status IN ('pending', 'failed')
       AND ((solution.originating_scope_type = 'location'
             AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1 FROM public.solution_link AS link
                 WHERE link.solution_id = solution.id
                   AND link.entity_type = 'location'
                   AND link.entity_id = requested_location_id
            ))
     ORDER BY gate.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_solution_scale_gate_assessment(
    requested_location_id UUID,
    requested_gate_id UUID,
    requested_request_id UUID,
    requested_measured_value TEXT,
    requested_sample_size INTEGER,
    requested_reported_pass BOOLEAN,
    requested_evidence_refs JSONB
)
RETURNS TABLE (
    assessment_id UUID,
    gate_id UUID,
    assessment_status TEXT,
    passed BOOLEAN,
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
    evaluator_party UUID;
    gate_record RECORD;
    prior_assessment RECORD;
    numeric_value NUMERIC;
    derived_pass BOOLEAN;
    saved_at TIMESTAMPTZ;
    saved_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_gate_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Scale-gate assessment requires signed operator location context and request identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Scale-gate assessment requires an active exact location create grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id INTO evaluator_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS human
        ON human.id = binding.party_id
       AND human.party_type = 'person' AND human.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF evaluator_party IS NULL THEN
        RAISE EXCEPTION 'Scale-gate assessment requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    IF requested_measured_value IS NULL
       OR pg_catalog.char_length(pg_catalog.btrim(requested_measured_value)) NOT BETWEEN 1 AND 1000
       OR requested_sample_size IS NULL
       OR requested_sample_size NOT BETWEEN 1 AND 10000000
       OR requested_evidence_refs IS NULL
       OR pg_catalog.jsonb_typeof(requested_evidence_refs) IS DISTINCT FROM 'array'
       OR requested_evidence_refs = '[]'::jsonb
       OR pg_catalog.jsonb_array_length(requested_evidence_refs) > 100
       OR pg_catalog.octet_length(requested_evidence_refs::TEXT) > 65536 THEN
        RAISE EXCEPTION 'Scale-gate assessment input is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT assessment.id, assessment.location_id, assessment.gate_id,
           assessment.evaluator_party_id, assessment.passed,
           assessment.measured_value, assessment.measured_numeric,
           assessment.sample_size,
           assessment.evidence_refs, assessment.status, assessment.created_at
      INTO prior_assessment
      FROM public.solution_scale_gate_assessment AS assessment
     WHERE assessment.evaluator_operator_id = context_record.actor_id
       AND assessment.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_assessment.location_id IS DISTINCT FROM requested_location_id
           OR prior_assessment.gate_id IS DISTINCT FROM requested_gate_id
           OR prior_assessment.evaluator_party_id IS DISTINCT FROM evaluator_party
           OR prior_assessment.measured_value IS DISTINCT FROM requested_measured_value
           OR prior_assessment.sample_size IS DISTINCT FROM requested_sample_size
           OR prior_assessment.evidence_refs IS DISTINCT FROM requested_evidence_refs
           OR (prior_assessment.measured_numeric IS NULL
               AND requested_reported_pass IS DISTINCT FROM prior_assessment.passed)
           OR (prior_assessment.measured_numeric IS NOT NULL
               AND requested_reported_pass IS NOT NULL) THEN
            RAISE EXCEPTION 'Scale-gate assessment request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        assessment_id := prior_assessment.id;
        gate_id := prior_assessment.gate_id;
        assessment_status := prior_assessment.status;
        passed := prior_assessment.passed;
        created_at := prior_assessment.created_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT gate.id, gate.solution_id, gate.scope_type, gate.scope_id, gate.status,
           gate.metric_key, gate.comparison_operator, gate.threshold_numeric,
           gate.minimum_sample, gate.unit
      INTO gate_record
      FROM public.solution_scale_gate AS gate
      JOIN public.solution AS solution ON solution.id = gate.solution_id
     WHERE gate.id = requested_gate_id
       AND gate.scope_type = 'location'
       AND gate.scope_id = requested_location_id
       AND ((solution.originating_scope_type = 'location'
             AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1 FROM public.solution_link AS link
                 WHERE link.solution_id = solution.id
                   AND link.entity_type = 'location'
                   AND link.entity_id = requested_location_id
            ))
     FOR UPDATE OF gate;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Scale gate not found for this location'
            USING ERRCODE = 'P0002';
    END IF;
    IF gate_record.status NOT IN ('pending', 'failed') THEN
        RAISE EXCEPTION 'Scale gate is not open for a new assessment'
            USING ERRCODE = '55000';
    END IF;
    IF (gate_record.comparison_operator IS NULL)
       <> (gate_record.threshold_numeric IS NULL) THEN
        RAISE EXCEPTION 'Scale gate numeric comparison contract is incomplete'
            USING ERRCODE = '22023';
    END IF;
    IF gate_record.comparison_operator IS NOT NULL THEN
        IF requested_reported_pass IS NOT NULL
           OR gate_record.metric_key IS NULL OR gate_record.unit IS NULL
           OR (gate_record.minimum_sample IS NOT NULL
               AND requested_sample_size < gate_record.minimum_sample)
           OR requested_measured_value !~ '^-?[0-9]{1,24}(\.[0-9]{1,12})?$' THEN
            RAISE EXCEPTION 'Typed scale-gate measurement is invalid or below minimum sample'
                USING ERRCODE = '22023';
        END IF;
        BEGIN
            numeric_value := requested_measured_value::NUMERIC;
        EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN
            RAISE EXCEPTION 'Typed scale-gate measurement is invalid'
                USING ERRCODE = '22023';
        END;
        derived_pass := CASE gate_record.comparison_operator
            WHEN 'lt' THEN numeric_value < gate_record.threshold_numeric
            WHEN 'lte' THEN numeric_value <= gate_record.threshold_numeric
            WHEN 'eq' THEN numeric_value = gate_record.threshold_numeric
            WHEN 'gte' THEN numeric_value >= gate_record.threshold_numeric
            WHEN 'gt' THEN numeric_value > gate_record.threshold_numeric
            ELSE NULL
        END;
        IF derived_pass IS NULL THEN
            RAISE EXCEPTION 'Scale gate comparison operator is unsupported'
                USING ERRCODE = '22023';
        END IF;
    ELSE
        IF requested_reported_pass IS NULL THEN
            RAISE EXCEPTION 'Untyped scale-gate assessment requires a proposed result'
                USING ERRCODE = '22023';
        END IF;
        derived_pass := requested_reported_pass;
    END IF;

    INSERT INTO public.solution_scale_gate_assessment (
        location_id, solution_id, gate_id, evaluator_operator_id,
        evaluator_party_id, request_id, passed, measured_value,
        measured_numeric, sample_size, evidence_refs
    ) VALUES (
        requested_location_id, gate_record.solution_id, gate_record.id,
        context_record.actor_id, evaluator_party, requested_request_id,
        derived_pass, requested_measured_value, numeric_value,
        requested_sample_size, requested_evidence_refs
    ) RETURNING id, created_at INTO saved_id, saved_at;

    assessment_id := saved_id;
    gate_id := gate_record.id;
    assessment_status := 'pending';
    passed := derived_pass;
    created_at := saved_at;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_scale_gate_review_queue(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    assessment_id UUID,
    gate_id UUID,
    solution_name TEXT,
    gate_type TEXT,
    passed BOOLEAN,
    measured_value TEXT,
    sample_size INTEGER,
    evaluator_conflict BOOLEAN,
    submitted_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    reviewer_party UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Scale-gate review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Scale-gate review queue requires an active exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id INTO reviewer_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS human
        ON human.id = binding.party_id
       AND human.party_type = 'person' AND human.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF reviewer_party IS NULL THEN
        RAISE EXCEPTION 'Scale-gate review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Scale-gate review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT assessment.id, assessment.gate_id,
           pg_catalog.left(solution.name, 255)::TEXT,
           gate.gate_type::TEXT, assessment.passed,
           assessment.measured_value, assessment.sample_size,
           assessment.evaluator_party_id = reviewer_party,
           assessment.created_at
      FROM public.solution_scale_gate_assessment AS assessment
      JOIN public.solution_scale_gate AS gate ON gate.id = assessment.gate_id
      JOIN public.solution AS solution ON solution.id = assessment.solution_id
     WHERE assessment.location_id = requested_location_id
       AND assessment.status = 'pending'
     ORDER BY assessment.created_at, assessment.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_solution_scale_gate_review_detail(
    requested_location_id UUID,
    requested_assessment_id UUID
)
RETURNS TABLE (
    assessment_id UUID,
    gate_id UUID,
    solution_name TEXT,
    gate_type TEXT,
    requirement TEXT,
    threshold TEXT,
    metric_key TEXT,
    comparison_operator TEXT,
    threshold_numeric NUMERIC,
    unit TEXT,
    passed BOOLEAN,
    measured_value TEXT,
    measured_numeric NUMERIC,
    sample_size INTEGER,
    evidence_refs JSONB,
    evaluator_conflict BOOLEAN,
    submitted_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    reviewer_party UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_assessment_id IS NULL THEN
        RAISE EXCEPTION 'Scale-gate review detail requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Scale-gate review detail requires an active exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id INTO reviewer_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS human
        ON human.id = binding.party_id
       AND human.party_type = 'person' AND human.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF reviewer_party IS NULL THEN
        RAISE EXCEPTION 'Scale-gate review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT assessment.id, assessment.gate_id,
           pg_catalog.left(solution.name, 255)::TEXT,
           gate.gate_type::TEXT, pg_catalog.left(gate.requirement, 2000)::TEXT,
           pg_catalog.left(gate.threshold, 1000)::TEXT, gate.metric_key::TEXT,
           gate.comparison_operator::TEXT, gate.threshold_numeric,
           gate.unit::TEXT, assessment.passed, assessment.measured_value,
           assessment.measured_numeric, assessment.sample_size,
           assessment.evidence_refs,
           assessment.evaluator_party_id = reviewer_party,
           assessment.created_at
      FROM public.solution_scale_gate_assessment AS assessment
      JOIN public.solution_scale_gate AS gate ON gate.id = assessment.gate_id
      JOIN public.solution AS solution ON solution.id = assessment.solution_id
     WHERE assessment.location_id = requested_location_id
       AND assessment.id = requested_assessment_id
       AND assessment.status = 'pending';
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_solution_scale_gate_assessment(
    requested_location_id UUID,
    requested_assessment_id UUID,
    requested_request_id UUID,
    requested_decision TEXT,
    requested_reason TEXT
)
RETURNS TABLE (
    assessment_id UUID,
    gate_id UUID,
    assessment_status TEXT,
    gate_status TEXT,
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
    reviewer_party UUID;
    existing RECORD;
    assessment RECORD;
    gate_status_value TEXT;
    review_timestamp TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_assessment_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Scale-gate review requires signed operator location context and request identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Scale-gate review requires an active exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision NOT IN ('accepted', 'rejected')
       OR pg_catalog.char_length(COALESCE(requested_reason, '')) > 4000
       OR (requested_decision = 'rejected'
           AND pg_catalog.char_length(pg_catalog.btrim(COALESCE(requested_reason, ''))) < 10) THEN
        RAISE EXCEPTION 'Scale-gate review decision or reason is invalid'
            USING ERRCODE = '22023';
    END IF;
    requested_reason := NULLIF(pg_catalog.btrim(requested_reason), '');
    SELECT binding.party_id INTO reviewer_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS human
        ON human.id = binding.party_id
       AND human.party_type = 'person' AND human.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, operator, human;
    IF reviewer_party IS NULL THEN
        RAISE EXCEPTION 'Scale-gate review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    SELECT candidate.id, candidate.location_id, candidate.gate_id,
           candidate.reviewer_party_id, candidate.review_decision,
           candidate.review_reason, candidate.status, candidate.reviewed_at
      INTO existing
      FROM public.solution_scale_gate_assessment AS candidate
     WHERE candidate.reviewer_operator_id = context_record.actor_id
       AND candidate.review_request_id = requested_request_id;
    IF FOUND THEN
        IF existing.location_id IS DISTINCT FROM requested_location_id
           OR existing.id IS DISTINCT FROM requested_assessment_id
           OR existing.reviewer_party_id IS DISTINCT FROM reviewer_party
           OR existing.review_decision IS DISTINCT FROM requested_decision
           OR existing.review_reason IS DISTINCT FROM requested_reason THEN
            RAISE EXCEPTION 'Scale-gate review request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        SELECT gate.status::TEXT INTO gate_status_value
          FROM public.solution_scale_gate AS gate
         WHERE gate.id = existing.gate_id;
        assessment_id := existing.id;
        gate_id := existing.gate_id;
        assessment_status := existing.status;
        gate_status := gate_status_value;
        reviewed_at := existing.reviewed_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT candidate.id, candidate.location_id, candidate.solution_id,
           candidate.gate_id, candidate.evaluator_party_id, candidate.passed,
           candidate.measured_value, candidate.evidence_refs, candidate.status
      INTO assessment
      FROM public.solution_scale_gate_assessment AS candidate
     WHERE candidate.id = requested_assessment_id
       AND candidate.location_id = requested_location_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Pending scale-gate assessment not found for this location'
            USING ERRCODE = 'P0002';
    END IF;

    SELECT gate.status::TEXT INTO gate_status_value
      FROM public.solution_scale_gate AS gate
      JOIN public.solution AS solution ON solution.id = assessment.solution_id
     WHERE gate.id = assessment.gate_id
       AND gate.solution_id = assessment.solution_id
       AND gate.scope_type = 'location'
       AND gate.scope_id = requested_location_id
       AND ((solution.originating_scope_type = 'location'
             AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1 FROM public.solution_link AS link
                 WHERE link.solution_id = solution.id
                   AND link.entity_type = 'location'
                   AND link.entity_id = requested_location_id
            ))
     FOR UPDATE OF gate;
    IF NOT FOUND OR gate_status_value NOT IN ('pending', 'failed') THEN
        RAISE EXCEPTION 'Scale gate is no longer eligible for assessment review'
            USING ERRCODE = '55000';
    END IF;

    SELECT candidate.id, candidate.location_id, candidate.solution_id,
           candidate.gate_id, candidate.evaluator_party_id, candidate.passed,
           candidate.measured_value, candidate.evidence_refs, candidate.status
      INTO assessment
      FROM public.solution_scale_gate_assessment AS candidate
     WHERE candidate.id = requested_assessment_id
       AND candidate.location_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND OR assessment.status <> 'pending' THEN
        RAISE EXCEPTION 'Pending scale-gate assessment not found for this location'
            USING ERRCODE = 'P0002';
    END IF;
    IF assessment.evaluator_party_id = reviewer_party THEN
        RAISE EXCEPTION 'Scale-gate evaluator cannot review their own assessment'
            USING ERRCODE = '42501';
    END IF;
    review_timestamp := clock_timestamp();
    UPDATE public.solution_scale_gate_assessment AS candidate
       SET status = CASE requested_decision WHEN 'accepted' THEN 'approved' ELSE 'rejected' END,
           review_decision = requested_decision,
           review_reason = NULLIF(pg_catalog.btrim(requested_reason), ''),
           reviewer_operator_id = context_record.actor_id,
           reviewer_party_id = reviewer_party,
           review_request_id = requested_request_id,
           reviewed_at = review_timestamp
     WHERE candidate.id = assessment.id;

    IF requested_decision = 'accepted' THEN
        gate_status_value := CASE assessment.passed WHEN TRUE THEN 'passed' ELSE 'failed' END;
        UPDATE public.solution_scale_gate AS gate
           SET status = gate_status_value,
               measured_value = assessment.measured_value,
               evidence_refs = assessment.evidence_refs,
               approved_by_party_id = reviewer_party,
               approved_at = review_timestamp
         WHERE gate.id = assessment.gate_id;
    END IF;

    assessment_id := assessment.id;
    gate_id := assessment.gate_id;
    assessment_status := CASE requested_decision WHEN 'accepted' THEN 'approved' ELSE 'rejected' END;
    gate_status := gate_status_value;
    reviewed_at := review_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_scale_gate_owner;
ALTER FUNCTION kokonut_security.guard_solution_scale_gate_assessment()
    OWNER TO kokonut_solution_scale_gate_owner;
ALTER FUNCTION kokonut_security.list_location_solution_scale_gate_assessment_targets(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_scale_gate_owner;
ALTER FUNCTION kokonut_security.submit_location_solution_scale_gate_assessment(UUID, UUID, UUID, TEXT, INTEGER, BOOLEAN, JSONB)
    OWNER TO kokonut_solution_scale_gate_owner;
ALTER FUNCTION kokonut_security.list_location_solution_scale_gate_review_queue(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_solution_scale_gate_owner;
ALTER FUNCTION kokonut_security.get_location_solution_scale_gate_review_detail(UUID, UUID)
    OWNER TO kokonut_solution_scale_gate_owner;
ALTER FUNCTION kokonut_security.review_location_solution_scale_gate_assessment(UUID, UUID, UUID, TEXT, TEXT)
    OWNER TO kokonut_solution_scale_gate_owner;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_scale_gate_owner;

REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_scale_gate_assessment_targets(UUID, INTEGER, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_scale_gate_assessment(UUID, UUID, UUID, TEXT, INTEGER, BOOLEAN, JSONB) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_scale_gate_review_queue(UUID, INTEGER, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_scale_gate_review_detail(UUID, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.review_location_solution_scale_gate_assessment(UUID, UUID, UUID, TEXT, TEXT) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_scale_gate_assessment_targets(UUID, INTEGER, INTEGER),
            kokonut_security.submit_location_solution_scale_gate_assessment(UUID, UUID, UUID, TEXT, INTEGER, BOOLEAN, JSONB),
            kokonut_security.list_location_solution_scale_gate_review_queue(UUID, INTEGER, INTEGER),
            kokonut_security.get_location_solution_scale_gate_review_detail(UUID, UUID),
            kokonut_security.review_location_solution_scale_gate_assessment(UUID, UUID, UUID, TEXT, TEXT)
            TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_scale_gate_assessment_targets(UUID, INTEGER, INTEGER),
            kokonut_security.submit_location_solution_scale_gate_assessment(UUID, UUID, UUID, TEXT, INTEGER, BOOLEAN, JSONB),
            kokonut_security.list_location_solution_scale_gate_review_queue(UUID, INTEGER, INTEGER),
            kokonut_security.get_location_solution_scale_gate_review_detail(UUID, UUID),
            kokonut_security.review_location_solution_scale_gate_assessment(UUID, UUID, UUID, TEXT, TEXT)
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_scale_gate_assessment IS
'Append-only location-scoped claimed/measured scale-gate assessments with independent human review. Only accepted reviews update the current gate status; rejection preserves prior gate state.';
COMMENT ON FUNCTION kokonut_security.submit_location_solution_scale_gate_assessment(UUID, UUID, UUID, TEXT, INTEGER, BOOLEAN, JSONB) IS
'Submits an exact-location scale-gate assessment under signed solution_lifecycle:create scope and active human attribution. Typed results are derived from the configured numeric comparator; an independent reviewer must accept before the gate changes.';
COMMENT ON FUNCTION kokonut_security.review_location_solution_scale_gate_assessment(UUID, UUID, UUID, TEXT, TEXT) IS
'Accepts or rejects one pending exact-location scale-gate assessment under signed solution_lifecycle:review scope. The evaluator cannot review their own submission. Acceptance alone updates the gate status and human approval; lifecycle stage never changes.';

COMMIT;
