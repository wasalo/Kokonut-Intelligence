-- Add an independent, exact-location review path for Kernel learning proposals.

BEGIN;

ALTER TABLE public.solution_learning_record
    ADD COLUMN IF NOT EXISTS reviewed_by_party_id UUID
        REFERENCES public.party(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS review_reason TEXT;

ALTER TABLE public.solution_learning_record
    DROP CONSTRAINT IF EXISTS solution_learning_record_review_attribution_check;
ALTER TABLE public.solution_learning_record
    ADD CONSTRAINT solution_learning_record_review_attribution_check
    CHECK ((reviewed_by_party_id IS NULL) = (reviewed_at IS NULL));
ALTER TABLE public.solution_learning_record
    DROP CONSTRAINT IF EXISTS solution_learning_record_review_reason_bound_check;
ALTER TABLE public.solution_learning_record
    ADD CONSTRAINT solution_learning_record_review_reason_bound_check
    CHECK (review_reason IS NULL OR pg_catalog.char_length(review_reason) <= 4000);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_learning_reviewer'
    ) THEN
        CREATE ROLE kokonut_solution_learning_reviewer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_learning_reviewer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution learning reviewer role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_learning_reviewer'
            OR member_role.rolname = 'kokonut_solution_learning_reviewer'
    ) THEN
        RAISE EXCEPTION 'Solution learning reviewer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_learning_review_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    learning_record_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_learning_record(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    review_reason TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id),
    CHECK (review_reason IS NULL OR pg_catalog.char_length(review_reason) <= 4000),
    CHECK (decision <> 'rejected'
           OR pg_catalog.char_length(pg_catalog.btrim(COALESCE(review_reason, ''))) >= 10)
);

CREATE INDEX IF NOT EXISTS idx_solution_learning_review_queue
    ON public.solution_learning_proposal_event (location_id, created_at DESC, id DESC);

REVOKE ALL ON TABLE public.solution_learning_review_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_learning_review_receipt
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader,
         kokonut_solution_learning_proposal_owner;
REVOKE DELETE, TRUNCATE ON TABLE public.solution_learning_record
    FROM kokonut_runtime, kokonut_directus_runtime;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT SELECT (
            id, decision_status, applied_to_version, owner_party_id,
            reviewed_by_party_id, reviewed_at
        ) ON TABLE public.solution_learning_record TO kokonut_runtime;
        GRANT UPDATE (decision_status, applied_to_version, owner_party_id)
            ON TABLE public.solution_learning_record TO kokonut_runtime;
    END IF;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_learning_reviewer;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_learning_reviewer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_learning_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_learning_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_learning_reviewer;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_learning_reviewer;

GRANT SELECT ON TABLE public.solution_learning_proposal_event
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (
    id, solution_id, source_experiment_id, source_replication_id, lesson_type,
    finding, confidence, transferability, affected_assumptions, affected_metrics,
    recommended_action, decision_status, applied_to_version, owner_party_id,
    evidence, created_at, reviewed_by_party_id, reviewed_at, review_reason
) ON TABLE public.solution_learning_record
    TO kokonut_solution_learning_reviewer;
GRANT UPDATE (id, decision_status, reviewed_by_party_id, reviewed_at, review_reason)
    ON TABLE public.solution_learning_record
    TO kokonut_solution_learning_reviewer;
GRANT SELECT, INSERT ON TABLE public.solution_learning_review_receipt
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (id, name, solution_type, current_stage, status,
              originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_learning_reviewer;
GRANT UPDATE (id) ON TABLE public.solution TO kokonut_solution_learning_reviewer;
GRANT SELECT (solution_id, entity_type, entity_id)
    ON TABLE public.solution_link TO kokonut_solution_learning_reviewer;
GRANT SELECT (
    id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
    status, reviewed_by_party_id, reviewed_at, started_at, started_by_party_id,
    completed_at, completion_reviewed_by_party_id, completion_reviewed_at
) ON TABLE public.solution_replication
    TO kokonut_solution_learning_reviewer;
GRANT UPDATE (id) ON TABLE public.solution_replication
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (replication_id, location_id, source_experiment_id)
    ON TABLE public.solution_replication_proposal_receipt
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (replication_id, location_id, decision, reviewer_party_id, reviewed_at)
    ON TABLE public.solution_replication_review_receipt
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (replication_id, location_id, actor_party_id, started_at)
    ON TABLE public.solution_replication_activation_receipt
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (id, replication_id, location_id, decision_status,
              reviewed_by_party_id, reviewed_at)
    ON TABLE public.solution_replication_completion_proposal
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (completion_proposal_id, location_id, decision,
              reviewer_party_id, reviewed_at)
    ON TABLE public.solution_replication_completion_review_receipt
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (id, status, owner_party_id, approved_by_party_id)
    ON TABLE public.solution_experiment
    TO kokonut_solution_learning_reviewer;
GRANT UPDATE (id) ON TABLE public.solution_experiment
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (experiment_id, outcome, reviewed_by_party_id, reviewed_at)
    ON TABLE public.solution_experiment_result
    TO kokonut_solution_learning_reviewer;
GRANT UPDATE (id) ON TABLE public.solution_experiment_result
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_learning_reviewer;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_learning_reviewer;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_learning_reviewer;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_learning_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_learning_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_learning_reviewer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_learning_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.guard_solution_learning_review_fields()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
DECLARE
    caller_role TEXT := CURRENT_USER;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.decision_status IS DISTINCT FROM 'proposed'
           OR NEW.reviewed_by_party_id IS NOT NULL
           OR NEW.reviewed_at IS NOT NULL
           OR NEW.review_reason IS NOT NULL
           OR NEW.applied_to_version IS NOT NULL THEN
            RAISE EXCEPTION 'Learning records must begin as unreviewed proposals'
                USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;

    IF caller_role = 'kokonut_solution_learning_reviewer'
       AND OLD.decision_status = 'proposed'
       AND NEW.decision_status IN ('accepted', 'rejected')
       AND NEW.reviewed_by_party_id IS NOT NULL
       AND NEW.reviewed_at IS NOT NULL
       AND (NEW.decision_status <> 'rejected'
            OR pg_catalog.char_length(pg_catalog.btrim(COALESCE(NEW.review_reason, ''))) >= 10)
       AND (pg_catalog.to_jsonb(NEW) - ARRAY[
                'decision_status', 'reviewed_by_party_id', 'reviewed_at', 'review_reason'
            ]) = (pg_catalog.to_jsonb(OLD) - ARRAY[
                'decision_status', 'reviewed_by_party_id', 'reviewed_at', 'review_reason'
            ]) THEN
        RETURN NEW;
    END IF;

    IF caller_role = 'kokonut_runtime'
       AND OLD.decision_status = 'accepted'
       AND NEW.decision_status = 'applied'
       AND OLD.reviewed_by_party_id IS NOT NULL
       AND OLD.reviewed_at IS NOT NULL
       AND NEW.reviewed_by_party_id IS NOT DISTINCT FROM OLD.reviewed_by_party_id
       AND NEW.reviewed_at IS NOT DISTINCT FROM OLD.reviewed_at
       AND NEW.review_reason IS NOT DISTINCT FROM OLD.review_reason
       AND NEW.applied_to_version IS NOT NULL
       AND pg_catalog.btrim(NEW.applied_to_version) <> ''
       AND pg_catalog.char_length(NEW.applied_to_version) <= 80
       AND NEW.owner_party_id IS NOT NULL
       AND (pg_catalog.to_jsonb(NEW) - ARRAY[
                'decision_status', 'applied_to_version', 'owner_party_id'
            ]) = (pg_catalog.to_jsonb(OLD) - ARRAY[
                'decision_status', 'applied_to_version', 'owner_party_id'
            ]) THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Learning decisions require independent review or accepted-only application'
        USING ERRCODE = '42501';
END;
$$;
REVOKE ALL ON FUNCTION kokonut_security.guard_solution_learning_review_fields()
    FROM PUBLIC;
DROP TRIGGER IF EXISTS trg_solution_learning_review_fields
    ON public.solution_learning_record;
CREATE TRIGGER trg_solution_learning_review_fields
    BEFORE INSERT OR UPDATE ON public.solution_learning_record
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.guard_solution_learning_review_fields();

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_learning_review_queue(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    learning_record_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    solution_stage TEXT,
    lesson_type TEXT,
    confidence TEXT,
    transferability TEXT,
    created_at TIMESTAMPTZ,
    is_self_authored BOOLEAN,
    is_self_starter BOOLEAN,
    is_initial_approver BOOLEAN,
    is_completion_reviewer BOOLEAN,
    is_source_owner BOOLEAN,
    is_source_approver BOOLEAN,
    is_source_result_reviewer BOOLEAN
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
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Learning review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning review queue requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id INTO reviewer_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id
       AND reviewer.party_type = 'person' AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF reviewer_party IS NULL THEN
        RAISE EXCEPTION 'Learning review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Learning review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT learning.id, pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT, solution.current_stage::TEXT,
           learning.lesson_type::TEXT, learning.confidence::TEXT,
           learning.transferability::TEXT, learning.created_at,
           proposal.proposer_party_id = reviewer_party,
           replication.started_by_party_id = reviewer_party,
           replication.reviewed_by_party_id = reviewer_party,
           replication.completion_reviewed_by_party_id = reviewer_party,
           experiment.owner_party_id = reviewer_party,
           experiment.approved_by_party_id = reviewer_party,
           source_result.reviewed_by_party_id = reviewer_party
      FROM public.solution_learning_record AS learning
      JOIN public.solution_learning_proposal_event AS proposal
        ON proposal.learning_record_id = learning.id
       AND proposal.location_id = requested_location_id
      JOIN public.solution_replication AS replication
        ON replication.id = proposal.replication_id
      JOIN public.solution AS solution
        ON solution.id = learning.solution_id
       AND solution.id = replication.solution_id
       AND solution.status = 'active'
      JOIN public.solution_replication_proposal_receipt AS origin
        ON origin.replication_id = replication.id
       AND origin.location_id = requested_location_id
       AND origin.source_experiment_id = replication.source_experiment_id
      JOIN public.solution_replication_review_receipt AS approval
        ON approval.replication_id = replication.id
       AND approval.location_id = requested_location_id
       AND approval.decision = 'approved'
       AND approval.reviewer_party_id = replication.reviewed_by_party_id
       AND approval.reviewed_at = replication.reviewed_at
      JOIN public.solution_replication_activation_receipt AS activation
        ON activation.replication_id = replication.id
       AND activation.location_id = requested_location_id
       AND activation.actor_party_id = replication.started_by_party_id
       AND activation.started_at = replication.started_at
      JOIN public.solution_replication_completion_proposal AS completion
        ON completion.replication_id = replication.id
       AND completion.location_id = requested_location_id
       AND completion.decision_status = 'accepted'
       AND completion.reviewed_by_party_id = replication.completion_reviewed_by_party_id
       AND completion.reviewed_at = replication.completion_reviewed_at
      JOIN public.solution_replication_completion_review_receipt AS completion_review
        ON completion_review.completion_proposal_id = completion.id
       AND completion_review.location_id = requested_location_id
       AND completion_review.decision = 'accepted'
       AND completion_review.reviewer_party_id = replication.completion_reviewed_by_party_id
       AND completion_review.reviewed_at = replication.completion_reviewed_at
      JOIN public.solution_experiment AS experiment
        ON experiment.id = replication.source_experiment_id
       AND experiment.status = 'validated'
      JOIN public.solution_experiment_result AS source_result
        ON source_result.experiment_id = experiment.id
       AND source_result.outcome = 'validated'
       AND source_result.reviewed_at IS NOT NULL
      JOIN public.party AS approver
        ON approver.id = approval.reviewer_party_id
       AND approver.party_type = 'person' AND approver.status = 'active'
      JOIN public.party AS completion_human
        ON completion_human.id = completion_review.reviewer_party_id
       AND completion_human.party_type = 'person' AND completion_human.status = 'active'
      JOIN public.party AS source_reviewer
        ON source_reviewer.id = source_result.reviewed_by_party_id
       AND source_reviewer.party_type = 'person' AND source_reviewer.status = 'active'
     WHERE learning.source_replication_id = replication.id
       AND learning.decision_status = 'proposed'
       AND learning.reviewed_by_party_id IS NULL
       AND learning.reviewed_at IS NULL
       AND replication.status = 'completed'
       AND replication.completed_at IS NOT NULL
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND ((solution.originating_scope_type = 'location'
             AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1 FROM public.solution_link AS location_link
                 WHERE location_link.solution_id = solution.id
                   AND location_link.entity_type = 'location'
                   AND location_link.entity_id = requested_location_id
            ))
     ORDER BY learning.created_at DESC, learning.id DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_solution_learning_review_detail(
    requested_location_id UUID,
    requested_learning_record_id UUID
)
RETURNS TABLE (
    learning_record_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    solution_stage TEXT,
    lesson_type TEXT,
    finding TEXT,
    confidence TEXT,
    transferability TEXT,
    affected_assumptions JSONB,
    affected_metrics JSONB,
    recommended_action TEXT,
    evidence JSONB,
    created_at TIMESTAMPTZ,
    source_is_current BOOLEAN,
    is_self_authored BOOLEAN,
    is_self_starter BOOLEAN,
    is_initial_approver BOOLEAN,
    is_completion_reviewer BOOLEAN,
    is_source_owner BOOLEAN,
    is_source_approver BOOLEAN,
    is_source_result_reviewer BOOLEAN
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
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_learning_record_id IS NULL THEN
        RAISE EXCEPTION 'Learning review detail requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning review detail requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id INTO reviewer_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS person
        ON person.id = binding.party_id
       AND person.party_type = 'person' AND person.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF reviewer_party IS NULL THEN
        RAISE EXCEPTION 'Learning review detail requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT learning.id, pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT, solution.current_stage::TEXT,
           learning.lesson_type::TEXT, learning.finding::TEXT,
           learning.confidence::TEXT, learning.transferability::TEXT,
           learning.affected_assumptions, learning.affected_metrics,
           learning.recommended_action::TEXT, learning.evidence,
           learning.created_at, TRUE,
           proposal.proposer_party_id = reviewer_party,
           replication.started_by_party_id = reviewer_party,
           replication.reviewed_by_party_id = reviewer_party,
           replication.completion_reviewed_by_party_id = reviewer_party,
           experiment.owner_party_id = reviewer_party,
           experiment.approved_by_party_id = reviewer_party,
           source_result.reviewed_by_party_id = reviewer_party
      FROM public.solution_learning_record AS learning
      JOIN public.solution_learning_proposal_event AS proposal
        ON proposal.learning_record_id = learning.id
       AND proposal.location_id = requested_location_id
      JOIN public.solution_replication AS replication
        ON replication.id = proposal.replication_id
      JOIN public.solution AS solution
        ON solution.id = learning.solution_id
       AND solution.id = replication.solution_id
       AND solution.status = 'active'
      JOIN public.solution_replication_proposal_receipt AS origin
        ON origin.replication_id = replication.id
       AND origin.location_id = requested_location_id
       AND origin.source_experiment_id = replication.source_experiment_id
      JOIN public.solution_replication_review_receipt AS approval
        ON approval.replication_id = replication.id
       AND approval.location_id = requested_location_id
       AND approval.decision = 'approved'
       AND approval.reviewer_party_id = replication.reviewed_by_party_id
       AND approval.reviewed_at = replication.reviewed_at
      JOIN public.solution_replication_activation_receipt AS activation
        ON activation.replication_id = replication.id
       AND activation.location_id = requested_location_id
       AND activation.actor_party_id = replication.started_by_party_id
       AND activation.started_at = replication.started_at
      JOIN public.solution_replication_completion_proposal AS completion
        ON completion.replication_id = replication.id
       AND completion.location_id = requested_location_id
       AND completion.decision_status = 'accepted'
       AND completion.reviewed_by_party_id = replication.completion_reviewed_by_party_id
       AND completion.reviewed_at = replication.completion_reviewed_at
      JOIN public.solution_replication_completion_review_receipt AS completion_review
        ON completion_review.completion_proposal_id = completion.id
       AND completion_review.location_id = requested_location_id
       AND completion_review.decision = 'accepted'
       AND completion_review.reviewer_party_id = replication.completion_reviewed_by_party_id
       AND completion_review.reviewed_at = replication.completion_reviewed_at
      JOIN public.solution_experiment AS experiment
        ON experiment.id = replication.source_experiment_id
       AND experiment.status = 'validated'
      JOIN public.solution_experiment_result AS source_result
        ON source_result.experiment_id = experiment.id
       AND source_result.outcome = 'validated'
       AND source_result.reviewed_at IS NOT NULL
      JOIN public.party AS approver
        ON approver.id = approval.reviewer_party_id
       AND approver.party_type = 'person' AND approver.status = 'active'
      JOIN public.party AS completion_human
        ON completion_human.id = completion_review.reviewer_party_id
       AND completion_human.party_type = 'person' AND completion_human.status = 'active'
      JOIN public.party AS source_reviewer
        ON source_reviewer.id = source_result.reviewed_by_party_id
       AND source_reviewer.party_type = 'person' AND source_reviewer.status = 'active'
     WHERE learning.id = requested_learning_record_id
       AND learning.source_replication_id = replication.id
       AND learning.decision_status = 'proposed'
       AND learning.reviewed_by_party_id IS NULL
       AND learning.reviewed_at IS NULL
       AND replication.status = 'completed'
       AND replication.completed_at IS NOT NULL
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND ((solution.originating_scope_type = 'location'
             AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1 FROM public.solution_link AS location_link
                 WHERE location_link.solution_id = solution.id
                   AND location_link.entity_type = 'location'
                   AND location_link.entity_id = requested_location_id
            ));
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_solution_learning(
    requested_location_id UUID,
    requested_learning_record_id UUID,
    requested_request_id UUID,
    requested_decision TEXT,
    requested_review_reason TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    event_id UUID,
    learning_record_id UUID,
    decision TEXT,
    reviewed_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    reviewer_party UUID;
    existing_review RECORD;
    source_lineage RECORD;
    generated_event_id UUID;
    review_timestamp TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_learning_record_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Learning review requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning review requires an active exact location review grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision IS NULL
       OR requested_decision NOT IN ('accepted', 'rejected')
       OR requested_acknowledged IS DISTINCT FROM TRUE
       OR (requested_review_reason IS NOT NULL
           AND (pg_catalog.btrim(requested_review_reason) = ''
                OR pg_catalog.char_length(requested_review_reason) > 4000))
       OR (requested_decision = 'rejected'
           AND (requested_review_reason IS NULL
                OR pg_catalog.char_length(pg_catalog.btrim(requested_review_reason)) < 10)) THEN
        RAISE EXCEPTION 'Learning review decision, reason, or acknowledgement is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id INTO reviewer_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id
       AND reviewer.party_type = 'person' AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, operator, reviewer;
    IF reviewer_party IS NULL THEN
        RAISE EXCEPTION 'Learning review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || requested_request_id::TEXT, 0)
    );
    SELECT receipt.id, receipt.location_id, receipt.learning_record_id,
           receipt.reviewer_party_id, receipt.decision, receipt.review_reason,
           receipt.reviewed_at
      INTO existing_review
      FROM public.solution_learning_review_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_review.location_id IS DISTINCT FROM requested_location_id
           OR existing_review.learning_record_id IS DISTINCT FROM requested_learning_record_id
           OR existing_review.reviewer_party_id IS DISTINCT FROM reviewer_party
           OR existing_review.decision IS DISTINCT FROM requested_decision
           OR existing_review.review_reason IS DISTINCT FROM requested_review_reason THEN
            RAISE EXCEPTION 'Learning review request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        event_id := existing_review.id;
        learning_record_id := existing_review.learning_record_id;
        decision := existing_review.decision;
        reviewed_at := existing_review.reviewed_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT learning.id AS learning_id,
           proposal.proposer_party_id,
           replication.id AS replication_id,
           replication.started_by_party_id,
           replication.reviewed_by_party_id AS initial_approver_party_id,
           replication.completion_reviewed_by_party_id,
           experiment.id AS experiment_id,
           experiment.owner_party_id,
           experiment.approved_by_party_id,
           source_result.reviewed_by_party_id AS source_result_reviewer_party_id
      INTO source_lineage
      FROM public.solution_learning_record AS learning
      JOIN public.solution_learning_proposal_event AS proposal
        ON proposal.learning_record_id = learning.id
       AND proposal.location_id = requested_location_id
      JOIN public.solution_replication AS replication
        ON replication.id = proposal.replication_id
      JOIN public.solution AS solution
        ON solution.id = learning.solution_id
       AND solution.id = replication.solution_id
       AND solution.status = 'active'
      JOIN public.solution_replication_proposal_receipt AS origin
        ON origin.replication_id = replication.id
       AND origin.location_id = requested_location_id
       AND origin.source_experiment_id = replication.source_experiment_id
      JOIN public.solution_replication_review_receipt AS approval
        ON approval.replication_id = replication.id
       AND approval.location_id = requested_location_id
       AND approval.decision = 'approved'
       AND approval.reviewer_party_id = replication.reviewed_by_party_id
       AND approval.reviewed_at = replication.reviewed_at
      JOIN public.solution_replication_activation_receipt AS activation
        ON activation.replication_id = replication.id
       AND activation.location_id = requested_location_id
       AND activation.actor_party_id = replication.started_by_party_id
       AND activation.started_at = replication.started_at
      JOIN public.solution_replication_completion_proposal AS completion
        ON completion.replication_id = replication.id
       AND completion.location_id = requested_location_id
       AND completion.decision_status = 'accepted'
       AND completion.reviewed_by_party_id = replication.completion_reviewed_by_party_id
       AND completion.reviewed_at = replication.completion_reviewed_at
      JOIN public.solution_replication_completion_review_receipt AS completion_review
        ON completion_review.completion_proposal_id = completion.id
       AND completion_review.location_id = requested_location_id
       AND completion_review.decision = 'accepted'
       AND completion_review.reviewer_party_id = replication.completion_reviewed_by_party_id
       AND completion_review.reviewed_at = replication.completion_reviewed_at
      JOIN public.solution_experiment AS experiment
        ON experiment.id = replication.source_experiment_id
       AND experiment.status = 'validated'
      JOIN public.solution_experiment_result AS source_result
        ON source_result.experiment_id = experiment.id
       AND source_result.outcome = 'validated'
       AND source_result.reviewed_at IS NOT NULL
      JOIN public.party AS approver
        ON approver.id = approval.reviewer_party_id
       AND approver.party_type = 'person' AND approver.status = 'active'
      JOIN public.party AS completion_human
        ON completion_human.id = completion_review.reviewer_party_id
       AND completion_human.party_type = 'person' AND completion_human.status = 'active'
      JOIN public.party AS source_reviewer
        ON source_reviewer.id = source_result.reviewed_by_party_id
       AND source_reviewer.party_type = 'person' AND source_reviewer.status = 'active'
     WHERE learning.id = requested_learning_record_id
       AND learning.source_replication_id = replication.id
       AND learning.decision_status = 'proposed'
       AND learning.reviewed_by_party_id IS NULL
       AND learning.reviewed_at IS NULL
       AND replication.status = 'completed'
       AND replication.completed_at IS NOT NULL
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND ((solution.originating_scope_type = 'location'
             AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1 FROM public.solution_link AS location_link
                 WHERE location_link.solution_id = solution.id
                   AND location_link.entity_type = 'location'
                   AND location_link.entity_id = requested_location_id
            ))
     FOR UPDATE OF learning, replication, solution, experiment, source_result;
    IF source_lineage.learning_id IS NULL THEN
        RAISE EXCEPTION 'Pending learning proposal with current reviewed source lineage not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF reviewer_party IS NOT DISTINCT FROM source_lineage.proposer_party_id
       OR reviewer_party IS NOT DISTINCT FROM source_lineage.started_by_party_id
       OR reviewer_party IS NOT DISTINCT FROM source_lineage.initial_approver_party_id
       OR reviewer_party IS NOT DISTINCT FROM source_lineage.completion_reviewed_by_party_id
       OR reviewer_party IS NOT DISTINCT FROM source_lineage.owner_party_id
       OR reviewer_party IS NOT DISTINCT FROM source_lineage.approved_by_party_id
       OR reviewer_party IS NOT DISTINCT FROM source_lineage.source_result_reviewer_party_id THEN
        RAISE EXCEPTION 'Learning reviewer must be independent from proposer and source decision makers'
            USING ERRCODE = '42501';
    END IF;

    review_timestamp := pg_catalog.clock_timestamp();
    UPDATE public.solution_learning_record AS learning
       SET decision_status = requested_decision,
           reviewed_by_party_id = reviewer_party,
           reviewed_at = review_timestamp,
           review_reason = requested_review_reason
     WHERE learning.id = requested_learning_record_id;

    INSERT INTO public.solution_learning_review_receipt (
        operator_id, reviewer_party_id, location_id, learning_record_id,
        request_id, decision, review_reason, reviewed_at
    ) VALUES (
        context_record.actor_id, reviewer_party, requested_location_id,
        requested_learning_record_id, requested_request_id,
        requested_decision, requested_review_reason, review_timestamp
    ) RETURNING id INTO generated_event_id;

    event_id := generated_event_id;
    learning_record_id := requested_learning_record_id;
    decision := requested_decision;
    reviewed_at := review_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_learning_reviewer;
ALTER FUNCTION kokonut_security.list_location_solution_learning_review_queue(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_solution_learning_reviewer;
ALTER FUNCTION kokonut_security.get_location_solution_learning_review_detail(
    UUID, UUID
) OWNER TO kokonut_solution_learning_reviewer;
ALTER FUNCTION kokonut_security.review_location_solution_learning(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) OWNER TO kokonut_solution_learning_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_learning_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_learning_review_queue(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_learning_review_detail(
    UUID, UUID
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.review_location_solution_learning(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) FROM PUBLIC;

COMMENT ON TABLE public.solution_learning_review_receipt IS
'Append-only exact-location receipt for an independent learning proposal decision.';
COMMENT ON FUNCTION kokonut_security.review_location_solution_learning(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) IS
'Accepts or rejects a learning proposal only after revalidating its exact-location completed replication, accepted completion receipt, validated source experiment, and distinct human decision makers; does not apply the lesson or advance solution stage.';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_learning_review_queue(
            UUID, INTEGER, INTEGER
        ), kokonut_security.get_location_solution_learning_review_detail(UUID, UUID),
        kokonut_security.review_location_solution_learning(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) TO kokonut_runtime;
        REVOKE ALL ON TABLE public.solution_learning_review_receipt
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_learning_review_queue(
            UUID, INTEGER, INTEGER
        ), kokonut_security.get_location_solution_learning_review_detail(UUID, UUID),
        kokonut_security.review_location_solution_learning(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.solution_learning_review_receipt
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMIT;
