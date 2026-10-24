-- Add independent review for bounded replication completion reports.

BEGIN;

ALTER TABLE public.solution_replication
    ADD COLUMN IF NOT EXISTS completion_reviewed_by_party_id UUID
        REFERENCES public.party(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS completion_reviewed_at TIMESTAMPTZ;

ALTER TABLE public.solution_replication
    DROP CONSTRAINT IF EXISTS solution_replication_completion_review_attribution_check;
ALTER TABLE public.solution_replication
    ADD CONSTRAINT solution_replication_completion_review_attribution_check
    CHECK ((completion_reviewed_by_party_id IS NULL) = (completion_reviewed_at IS NULL));

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_replication_completion_reviewer'
    ) THEN
        CREATE ROLE kokonut_solution_replication_completion_reviewer
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_replication_completion_reviewer'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution replication completion reviewer role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_replication_completion_reviewer'
            OR member_role.rolname = 'kokonut_solution_replication_completion_reviewer'
    ) THEN
        RAISE EXCEPTION 'Solution replication completion reviewer role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_replication_completion_review_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    replication_id UUID NOT NULL REFERENCES public.solution_replication(id) ON DELETE RESTRICT,
    completion_proposal_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_replication_completion_proposal(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    review_reason TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id),
    CHECK (review_reason IS NULL OR pg_catalog.char_length(review_reason) <= 4000),
    CHECK (decision <> 'rejected'
           OR pg_catalog.char_length(pg_catalog.btrim(COALESCE(review_reason, ''))) >= 10)
);

CREATE INDEX IF NOT EXISTS idx_solution_replication_completion_review_queue
    ON public.solution_replication_completion_proposal (location_id, created_at DESC, id DESC)
    WHERE decision_status = 'proposed';

REVOKE ALL ON TABLE public.solution_replication_completion_review_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_replication_completion_review_receipt
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader,
         kokonut_solution_replication_completion_proposer,
         kokonut_solution_replication_reviewer,
         kokonut_solution_replication_completion_reviewer;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_replication_completion_reviewer;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_replication_completion_reviewer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_replication_completion_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_replication_completion_reviewer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_replication_completion_reviewer;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_replication_completion_reviewer;

GRANT SELECT ON TABLE public.solution_replication_completion_proposal
    TO kokonut_solution_replication_completion_reviewer;
GRANT UPDATE (id, decision_status, reviewed_by_party_id, reviewed_at, review_reason)
    ON TABLE public.solution_replication_completion_proposal
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (
    id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
    status, reviewed_by_party_id, reviewed_at, started_at, started_by_party_id,
    result, evidence_maturity, evidence, completed_at,
    completion_reviewed_by_party_id, completion_reviewed_at
) ON TABLE public.solution_replication
    TO kokonut_solution_replication_completion_reviewer;
GRANT UPDATE (
    id, status, result, evidence_maturity, evidence, completed_at,
    completion_reviewed_by_party_id, completion_reviewed_at
) ON TABLE public.solution_replication
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (id, name, solution_type, current_stage, status,
              originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_replication_completion_reviewer;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (operator_id, proposer_party_id, location_id, source_experiment_id, replication_id)
    ON TABLE public.solution_replication_proposal_receipt
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (operator_id, reviewer_party_id, location_id, replication_id, decision, reviewed_at)
    ON TABLE public.solution_replication_review_receipt
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (actor_party_id, location_id, replication_id, started_at)
    ON TABLE public.solution_replication_activation_receipt
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (id, solution_id, status, owner_party_id, approved_by_party_id)
    ON TABLE public.solution_experiment
    TO kokonut_solution_replication_completion_reviewer;
GRANT UPDATE (id) ON TABLE public.solution_experiment
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (experiment_id, outcome, reviewed_by_party_id, reviewed_at)
    ON TABLE public.solution_experiment_result
    TO kokonut_solution_replication_completion_reviewer;
GRANT UPDATE (id) ON TABLE public.solution_experiment_result
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (id, entity_type, entity_id, solution_id)
    ON TABLE public.solution_link
    TO kokonut_solution_replication_completion_reviewer;
GRANT UPDATE (id) ON TABLE public.solution_link
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (id, party_type, status)
    ON TABLE public.party TO kokonut_solution_replication_completion_reviewer;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_replication_completion_reviewer;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_replication_completion_reviewer;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT (level) ON TABLE public.evidence_maturity_level
    TO kokonut_solution_replication_completion_reviewer;
GRANT SELECT, INSERT ON TABLE public.solution_replication_completion_review_receipt
    TO kokonut_solution_replication_completion_reviewer;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_replication_completion_reviewer;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_replication_completion_reviewer;

CREATE OR REPLACE FUNCTION kokonut_security.guard_solution_replication_kernel_fields()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
DECLARE
    caller_role TEXT := CURRENT_USER;
BEGIN
    IF TG_OP = 'INSERT'
       AND caller_role IN (
           'kokonut_runtime', 'kokonut_directus_runtime',
           'kokonut_solution_replication_proposer'
       )
       AND (NEW.status <> 'proposed'
            OR NEW.reviewed_by_party_id IS NOT NULL
            OR NEW.reviewed_at IS NOT NULL
            OR NEW.review_reason IS NOT NULL
            OR NEW.started_at IS NOT NULL
            OR NEW.started_by_party_id IS NOT NULL
            OR NEW.result IS NOT NULL
            OR NEW.evidence_maturity IS NOT NULL
            OR pg_catalog.jsonb_array_length(NEW.evidence) <> 0
            OR NEW.completed_at IS NOT NULL
            OR NEW.completion_reviewed_by_party_id IS NOT NULL
            OR NEW.completion_reviewed_at IS NOT NULL) THEN
        RAISE EXCEPTION 'Replication creation must begin as a proposal'
            USING ERRCODE = '42501';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF caller_role = 'kokonut_solution_replication_reviewer'
           AND OLD.status = 'proposed'
           AND NEW.status IN ('approved', 'rejected')
           AND NEW.reviewed_by_party_id IS NOT NULL
           AND NEW.reviewed_at IS NOT NULL
           AND NEW.started_at IS NOT DISTINCT FROM OLD.started_at
           AND NEW.started_by_party_id IS NOT DISTINCT FROM OLD.started_by_party_id
           AND NEW.result IS NOT DISTINCT FROM OLD.result
           AND NEW.evidence_maturity IS NOT DISTINCT FROM OLD.evidence_maturity
           AND NEW.evidence IS NOT DISTINCT FROM OLD.evidence
           AND NEW.completed_at IS NOT DISTINCT FROM OLD.completed_at
           AND NEW.completion_reviewed_by_party_id IS NOT DISTINCT FROM OLD.completion_reviewed_by_party_id
           AND NEW.completion_reviewed_at IS NOT DISTINCT FROM OLD.completion_reviewed_at THEN
            RETURN NEW;
        END IF;

        IF caller_role = 'kokonut_solution_replication_starter'
           AND OLD.status = 'approved'
           AND NEW.status = 'active'
           AND OLD.reviewed_at IS NOT NULL
           AND OLD.reviewed_by_party_id IS NOT NULL
           AND NEW.reviewed_at IS NOT DISTINCT FROM OLD.reviewed_at
           AND NEW.reviewed_by_party_id IS NOT DISTINCT FROM OLD.reviewed_by_party_id
           AND NEW.review_reason IS NOT DISTINCT FROM OLD.review_reason
           AND OLD.started_at IS NULL
           AND NEW.started_at IS NOT NULL
           AND NEW.started_by_party_id IS NOT NULL
           AND NEW.result IS NOT DISTINCT FROM OLD.result
           AND NEW.evidence_maturity IS NOT DISTINCT FROM OLD.evidence_maturity
           AND NEW.evidence IS NOT DISTINCT FROM OLD.evidence
           AND NEW.completed_at IS NOT DISTINCT FROM OLD.completed_at
           AND NEW.completion_reviewed_by_party_id IS NOT DISTINCT FROM OLD.completion_reviewed_by_party_id
           AND NEW.completion_reviewed_at IS NOT DISTINCT FROM OLD.completion_reviewed_at THEN
            RETURN NEW;
        END IF;

        IF caller_role = 'kokonut_solution_replication_completion_reviewer'
           AND OLD.status = 'active'
           AND NEW.status = 'completed'
           AND OLD.started_at IS NOT NULL
           AND OLD.started_by_party_id IS NOT NULL
           AND OLD.result IS NULL
           AND OLD.evidence_maturity IS NULL
           AND OLD.evidence = '[]'::JSONB
           AND OLD.completed_at IS NULL
           AND OLD.completion_reviewed_by_party_id IS NULL
           AND OLD.completion_reviewed_at IS NULL
           AND NEW.reviewed_by_party_id IS NOT DISTINCT FROM OLD.reviewed_by_party_id
           AND NEW.reviewed_at IS NOT DISTINCT FROM OLD.reviewed_at
           AND NEW.review_reason IS NOT DISTINCT FROM OLD.review_reason
           AND NEW.started_at IS NOT DISTINCT FROM OLD.started_at
           AND NEW.started_by_party_id IS NOT DISTINCT FROM OLD.started_by_party_id
           AND NEW.result IS NOT NULL
           AND NEW.result IN ('successful', 'failed', 'mixed', 'inconclusive')
           AND NEW.evidence_maturity IS NOT NULL
           AND NEW.evidence_maturity BETWEEN 1 AND 6
           AND NEW.evidence IS NOT NULL
           AND NEW.completed_at IS NOT NULL
           AND NEW.completion_reviewed_by_party_id IS NOT NULL
           AND NEW.completion_reviewed_at IS NOT NULL THEN
            RETURN NEW;
        END IF;

        IF NEW.status IS DISTINCT FROM OLD.status
           OR NEW.solution_id IS DISTINCT FROM OLD.solution_id
           OR NEW.source_experiment_id IS DISTINCT FROM OLD.source_experiment_id
           OR NEW.target_scope_type IS DISTINCT FROM OLD.target_scope_type
           OR NEW.target_scope_id IS DISTINCT FROM OLD.target_scope_id
           OR NEW.target_context IS DISTINCT FROM OLD.target_context
           OR NEW.context_similarity IS DISTINCT FROM OLD.context_similarity
           OR NEW.adaptation_required IS DISTINCT FROM OLD.adaptation_required
           OR NEW.replication_protocol IS DISTINCT FROM OLD.replication_protocol
           OR NEW.created_at IS DISTINCT FROM OLD.created_at
           OR NEW.reviewed_by_party_id IS DISTINCT FROM OLD.reviewed_by_party_id
           OR NEW.reviewed_at IS DISTINCT FROM OLD.reviewed_at
           OR NEW.review_reason IS DISTINCT FROM OLD.review_reason
           OR NEW.started_at IS DISTINCT FROM OLD.started_at
           OR NEW.started_by_party_id IS DISTINCT FROM OLD.started_by_party_id
           OR NEW.result IS DISTINCT FROM OLD.result
           OR NEW.evidence_maturity IS DISTINCT FROM OLD.evidence_maturity
           OR NEW.evidence IS DISTINCT FROM OLD.evidence
           OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
           OR NEW.completion_reviewed_by_party_id IS DISTINCT FROM OLD.completion_reviewed_by_party_id
           OR NEW.completion_reviewed_at IS DISTINCT FROM OLD.completion_reviewed_at THEN
            RAISE EXCEPTION 'Replication lifecycle fields require a bounded transition function'
                USING ERRCODE = '42501';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_solution_replication_kernel_fields
    ON public.solution_replication;
CREATE TRIGGER trg_solution_replication_kernel_fields
    BEFORE INSERT OR UPDATE ON public.solution_replication
    FOR EACH ROW
    EXECUTE FUNCTION kokonut_security.guard_solution_replication_kernel_fields();

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_replication_completion_review_queue(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    proposal_id UUID,
    replication_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    solution_stage TEXT,
    outcome TEXT,
    evidence_maturity INTEGER,
    created_at TIMESTAMPTZ,
    is_self_authored BOOLEAN,
    is_self_started BOOLEAN,
    is_initial_approver BOOLEAN
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
        RAISE EXCEPTION 'Completion review queue requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Completion review queue requires an active exact location grant'
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
        RAISE EXCEPTION 'Completion review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Completion review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT completion.id, replication.id,
           pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT, solution.current_stage::TEXT,
           completion.outcome, completion.evidence_maturity, completion.created_at,
           completion.proposer_party_id = reviewer_party,
           replication.started_by_party_id = reviewer_party,
           replication.reviewed_by_party_id = reviewer_party
      FROM public.solution_replication_completion_proposal AS completion
      JOIN public.solution_replication AS replication
        ON replication.id = completion.replication_id
       AND replication.status = 'active'
       AND replication.started_at IS NOT NULL
      JOIN public.solution AS solution
        ON solution.id = replication.solution_id AND solution.status = 'active'
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
     WHERE completion.location_id = requested_location_id
       AND completion.decision_status = 'proposed'
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND (
           (solution.originating_scope_type = 'location'
            AND solution.originating_scope_id = requested_location_id)
           OR EXISTS (
               SELECT 1 FROM public.solution_link AS location_link
                WHERE location_link.solution_id = solution.id
                  AND location_link.entity_type = 'location'
                  AND location_link.entity_id = requested_location_id
           )
       )
     ORDER BY completion.created_at DESC, completion.id DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_solution_replication_completion_review_detail(
    requested_location_id UUID,
    requested_replication_id UUID,
    requested_proposal_id UUID
)
RETURNS TABLE (
    proposal_id UUID,
    replication_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    solution_stage TEXT,
    replication_status TEXT,
    outcome TEXT,
    evidence_maturity INTEGER,
    outcome_summary TEXT,
    evidence JSONB,
    created_at TIMESTAMPTZ,
    is_self_authored BOOLEAN,
    is_self_started BOOLEAN,
    is_initial_approver BOOLEAN,
    source_is_current BOOLEAN,
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
       OR requested_location_id IS NULL OR requested_replication_id IS NULL
       OR requested_proposal_id IS NULL THEN
        RAISE EXCEPTION 'Completion review detail requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Completion review detail requires an active exact location grant'
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
        RAISE EXCEPTION 'Completion review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT completion.id, replication.id,
           pg_catalog.left(solution.name, 255)::TEXT,
           solution.solution_type::TEXT, solution.current_stage::TEXT,
           replication.status::TEXT, completion.outcome,
           completion.evidence_maturity, completion.outcome_summary,
           completion.evidence, completion.created_at,
           completion.proposer_party_id = reviewer_party,
           replication.started_by_party_id = reviewer_party,
           replication.reviewed_by_party_id = reviewer_party,
           experiment.status = 'validated'
               AND source_result.outcome = 'validated'
               AND source_result.reviewed_at IS NOT NULL,
           COALESCE(experiment.owner_party_id = reviewer_party, FALSE),
           COALESCE(experiment.approved_by_party_id = reviewer_party, FALSE),
           COALESCE(source_result.reviewed_by_party_id = reviewer_party, FALSE)
      FROM public.solution_replication_completion_proposal AS completion
      JOIN public.solution_replication AS replication
        ON replication.id = completion.replication_id
       AND replication.status = 'active'
       AND replication.started_at IS NOT NULL
      JOIN public.solution AS solution
        ON solution.id = replication.solution_id AND solution.status = 'active'
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
      JOIN public.solution_experiment AS experiment
        ON experiment.id = replication.source_experiment_id
      LEFT JOIN public.solution_experiment_result AS source_result
        ON source_result.experiment_id = experiment.id
     WHERE completion.location_id = requested_location_id
       AND completion.replication_id = requested_replication_id
       AND completion.id = requested_proposal_id
       AND completion.decision_status = 'proposed'
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND (
           (solution.originating_scope_type = 'location'
            AND solution.originating_scope_id = requested_location_id)
           OR EXISTS (
               SELECT 1 FROM public.solution_link AS location_link
                WHERE location_link.solution_id = solution.id
                  AND location_link.entity_type = 'location'
                  AND location_link.entity_id = requested_location_id
           )
       );
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_solution_replication_completion(
    requested_location_id UUID,
    requested_replication_id UUID,
    requested_proposal_id UUID,
    requested_request_id UUID,
    requested_decision TEXT,
    requested_review_reason TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    event_id UUID,
    proposal_id UUID,
    replication_id UUID,
    decision TEXT,
    replication_status TEXT,
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
    report_id UUID;
    completion_outcome TEXT;
    completion_maturity INTEGER;
    completion_evidence JSONB;
    source_experiment UUID;
    solution_record UUID;
    source_origin_type TEXT;
    source_origin_id UUID;
    proposer_party UUID;
    starter_party UUID;
    approval_party UUID;
    experiment_owner UUID;
    experiment_approver UUID;
    source_reviewer UUID;
    generated_event_id UUID;
    review_timestamp TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_replication_id IS NULL
       OR requested_proposal_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Completion review requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Completion review requires an active exact location review grant'
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
        RAISE EXCEPTION 'Completion review decision, reason, or acknowledgement is invalid'
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
        RAISE EXCEPTION 'Completion review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || requested_request_id::TEXT, 0)
    );
    SELECT receipt.id, receipt.location_id, receipt.replication_id,
           receipt.completion_proposal_id, receipt.reviewer_party_id,
           receipt.decision, receipt.review_reason, receipt.reviewed_at
      INTO existing_review
      FROM public.solution_replication_completion_review_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_review.location_id IS DISTINCT FROM requested_location_id
           OR existing_review.replication_id IS DISTINCT FROM requested_replication_id
           OR existing_review.completion_proposal_id IS DISTINCT FROM requested_proposal_id
           OR existing_review.reviewer_party_id IS DISTINCT FROM reviewer_party
           OR existing_review.decision IS DISTINCT FROM requested_decision
           OR existing_review.review_reason IS DISTINCT FROM requested_review_reason THEN
            RAISE EXCEPTION 'Completion review request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        event_id := existing_review.id;
        proposal_id := existing_review.completion_proposal_id;
        replication_id := existing_review.replication_id;
        decision := existing_review.decision;
        replication_status := CASE WHEN decision = 'accepted' THEN 'completed' ELSE 'active' END;
        reviewed_at := existing_review.reviewed_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT completion.id, completion.proposer_party_id, completion.outcome,
           completion.evidence_maturity, completion.evidence,
           replication.source_experiment_id, replication.solution_id,
           solution.originating_scope_type, solution.originating_scope_id,
           replication.started_by_party_id, approval.reviewer_party_id,
           experiment.owner_party_id, experiment.approved_by_party_id,
           source_result.reviewed_by_party_id
      INTO report_id, proposer_party, completion_outcome,
           completion_maturity, completion_evidence,
           source_experiment, solution_record, source_origin_type, source_origin_id,
           starter_party, approval_party, experiment_owner, experiment_approver,
           source_reviewer
      FROM public.solution_replication_completion_proposal AS completion
      JOIN public.solution_replication AS replication
        ON replication.id = completion.replication_id
       AND replication.status = 'active'
       AND replication.started_at IS NOT NULL
       AND replication.started_by_party_id IS NOT NULL
       AND replication.result IS NULL
       AND replication.evidence_maturity IS NULL
       AND replication.evidence = '[]'::JSONB
       AND replication.completed_at IS NULL
       AND replication.completion_reviewed_by_party_id IS NULL
       AND replication.completion_reviewed_at IS NULL
      JOIN public.solution AS solution
        ON solution.id = replication.solution_id AND solution.status = 'active'
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
      JOIN public.solution_experiment AS experiment
        ON experiment.id = replication.source_experiment_id
       AND experiment.status = 'validated'
      JOIN public.solution_experiment_result AS source_result
        ON source_result.experiment_id = experiment.id
       AND source_result.outcome = 'validated'
       AND source_result.reviewed_at IS NOT NULL
       AND experiment.owner_party_id IS DISTINCT FROM source_result.reviewed_by_party_id
       AND experiment.approved_by_party_id IS DISTINCT FROM source_result.reviewed_by_party_id
      JOIN public.party AS source_human
        ON source_human.id = source_result.reviewed_by_party_id
       AND source_human.party_type = 'person'
      JOIN public.party AS approval_human
        ON approval_human.id = approval.reviewer_party_id
       AND approval_human.party_type = 'person'
     WHERE completion.location_id = requested_location_id
       AND completion.replication_id = requested_replication_id
       AND completion.id = requested_proposal_id
       AND completion.decision_status = 'proposed'
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND (
           (solution.originating_scope_type = 'location'
            AND solution.originating_scope_id = requested_location_id)
           OR EXISTS (
               SELECT 1 FROM public.solution_link AS location_link
                WHERE location_link.solution_id = solution.id
                  AND location_link.entity_type = 'location'
                  AND location_link.entity_id = requested_location_id
           )
       )
     FOR UPDATE OF completion, replication, solution, experiment, source_result
     FOR SHARE OF source_human, approval_human;
    IF report_id IS NULL OR proposer_party IS NULL OR starter_party IS NULL
       OR approval_party IS NULL OR source_experiment IS NULL
       OR source_reviewer IS NULL THEN
        RAISE EXCEPTION 'Pending completion report with current approved source lineage not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF source_origin_type IS DISTINCT FROM 'location'
       OR source_origin_id IS DISTINCT FROM requested_location_id THEN
        PERFORM 1 FROM public.solution_link AS location_link
         WHERE location_link.solution_id = solution_record
           AND location_link.entity_type = 'location'
           AND location_link.entity_id = requested_location_id
         FOR SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Replication solution is not visible at the exact target location'
                USING ERRCODE = 'P0002';
        END IF;
    END IF;
    IF reviewer_party IS NOT DISTINCT FROM proposer_party
       OR reviewer_party IS NOT DISTINCT FROM starter_party
       OR reviewer_party IS NOT DISTINCT FROM approval_party
       OR reviewer_party IS NOT DISTINCT FROM experiment_owner
       OR reviewer_party IS NOT DISTINCT FROM experiment_approver
       OR reviewer_party IS NOT DISTINCT FROM source_reviewer THEN
        RAISE EXCEPTION 'Completion reviewer must be independent from report, activation, approval, and source reviewers'
            USING ERRCODE = '42501';
    END IF;

    review_timestamp := pg_catalog.clock_timestamp();
    UPDATE public.solution_replication_completion_proposal AS completion
       SET decision_status = requested_decision,
           reviewed_by_party_id = reviewer_party,
           reviewed_at = review_timestamp,
           review_reason = requested_review_reason
     WHERE completion.id = report_id;

    IF requested_decision = 'accepted' THEN
        UPDATE public.solution_replication AS replication
           SET status = 'completed',
               result = completion_outcome,
               evidence_maturity = completion_maturity,
               evidence = completion_evidence,
               completed_at = review_timestamp,
               completion_reviewed_by_party_id = reviewer_party,
               completion_reviewed_at = review_timestamp
         WHERE replication.id = requested_replication_id;
        replication_status := 'completed';
    ELSE
        replication_status := 'active';
    END IF;

    INSERT INTO public.solution_replication_completion_review_receipt (
        operator_id, reviewer_party_id, location_id, replication_id,
        completion_proposal_id, request_id, decision, review_reason, reviewed_at
    ) VALUES (
        context_record.actor_id, reviewer_party, requested_location_id,
        requested_replication_id, report_id, requested_request_id,
        requested_decision, requested_review_reason, review_timestamp
    ) RETURNING id INTO generated_event_id;

    event_id := generated_event_id;
    proposal_id := report_id;
    replication_id := requested_replication_id;
    decision := requested_decision;
    reviewed_at := review_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_replication_completion_reviewer;
ALTER FUNCTION kokonut_security.list_location_solution_replication_completion_review_queue(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_solution_replication_completion_reviewer;
ALTER FUNCTION kokonut_security.get_location_solution_replication_completion_review_detail(
    UUID, UUID, UUID
) OWNER TO kokonut_solution_replication_completion_reviewer;
ALTER FUNCTION kokonut_security.review_location_solution_replication_completion(
    UUID, UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) OWNER TO kokonut_solution_replication_completion_reviewer;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_replication_completion_reviewer;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_replication_completion_review_queue(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.get_location_solution_replication_completion_review_detail(
    UUID, UUID, UUID
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.review_location_solution_replication_completion(
    UUID, UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) FROM PUBLIC;

COMMENT ON TABLE public.solution_replication_completion_review_receipt IS
'Append-only exact-location receipt for an independent completion-report decision.';
COMMENT ON FUNCTION kokonut_security.review_location_solution_replication_completion(
    UUID, UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) IS
'Accepts or rejects one private completion report with an immutable retry receipt; acceptance atomically records the report outcome and evidence on the replication, while rejection leaves it active.';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_replication_completion_review_queue(
            UUID, INTEGER, INTEGER
        ), kokonut_security.get_location_solution_replication_completion_review_detail(UUID, UUID, UUID),
        kokonut_security.review_location_solution_replication_completion(
            UUID, UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) TO kokonut_runtime;
        REVOKE ALL ON TABLE public.solution_replication_completion_proposal,
            public.solution_replication_completion_review_receipt
            FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_replication_completion_review_queue(
            UUID, INTEGER, INTEGER
        ), kokonut_security.get_location_solution_replication_completion_review_detail(UUID, UUID, UUID),
        kokonut_security.review_location_solution_replication_completion(
            UUID, UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.solution_replication_completion_proposal,
            public.solution_replication_completion_review_receipt
            FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMIT;
