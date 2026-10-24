-- Apply only independently accepted learning through exact location scope.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_learning_applier'
    ) THEN
        CREATE ROLE kokonut_solution_learning_applier
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_learning_applier'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution learning applier role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_learning_applier'
            OR member_role.rolname = 'kokonut_solution_learning_applier'
    ) THEN
        RAISE EXCEPTION 'Solution learning applier role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_learning_application_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    applier_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    learning_record_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_learning_record(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    applied_to_version TEXT NOT NULL
        CHECK (pg_catalog.char_length(pg_catalog.btrim(applied_to_version)) BETWEEN 1 AND 80),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_learning_application_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_learning_application_receipt
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader,
         kokonut_solution_learning_proposal_owner, kokonut_solution_learning_reviewer;

-- Application is performed only through the bounded signed-location function.
REVOKE UPDATE ON TABLE public.solution_learning_record
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;
REVOKE UPDATE (decision_status, applied_to_version, owner_party_id)
    ON TABLE public.solution_learning_record
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_learning_applier;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_learning_applier;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_learning_applier;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_learning_applier;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_learning_applier;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_learning_applier;

GRANT SELECT (
    id, solution_id, source_experiment_id, source_replication_id, lesson_type,
    finding, confidence, transferability, affected_assumptions, affected_metrics,
    recommended_action, decision_status, applied_to_version, owner_party_id,
    evidence, reviewed_by_party_id, reviewed_at
) ON TABLE public.solution_learning_record
    TO kokonut_solution_learning_applier;
GRANT UPDATE (decision_status, applied_to_version, owner_party_id)
    ON TABLE public.solution_learning_record
    TO kokonut_solution_learning_applier;
GRANT UPDATE (id) ON TABLE public.solution_learning_record
    TO kokonut_solution_learning_applier;
GRANT SELECT ON TABLE public.solution_learning_proposal_event
    TO kokonut_solution_learning_applier;
GRANT SELECT (id, operator_id, reviewer_party_id, location_id,
              learning_record_id, decision, reviewed_at)
    ON TABLE public.solution_learning_review_receipt
    TO kokonut_solution_learning_applier;
GRANT SELECT, INSERT ON TABLE public.solution_learning_application_receipt
    TO kokonut_solution_learning_applier;
GRANT SELECT (id, name, solution_type, current_stage, status,
              originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_learning_applier;
GRANT UPDATE (id) ON TABLE public.solution TO kokonut_solution_learning_applier;
GRANT SELECT (solution_id, entity_type, entity_id)
    ON TABLE public.solution_link TO kokonut_solution_learning_applier;
GRANT SELECT (
    id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
    status, reviewed_by_party_id, reviewed_at, started_at, started_by_party_id,
    completed_at, completion_reviewed_by_party_id, completion_reviewed_at
) ON TABLE public.solution_replication
    TO kokonut_solution_learning_applier;
GRANT UPDATE (id) ON TABLE public.solution_replication
    TO kokonut_solution_learning_applier;
GRANT SELECT (replication_id, location_id, source_experiment_id)
    ON TABLE public.solution_replication_proposal_receipt
    TO kokonut_solution_learning_applier;
GRANT SELECT (replication_id, location_id, decision, reviewer_party_id, reviewed_at)
    ON TABLE public.solution_replication_review_receipt
    TO kokonut_solution_learning_applier;
GRANT SELECT (replication_id, location_id, actor_party_id, started_at)
    ON TABLE public.solution_replication_activation_receipt
    TO kokonut_solution_learning_applier;
GRANT SELECT (id, replication_id, location_id, decision_status,
              reviewed_by_party_id, reviewed_at)
    ON TABLE public.solution_replication_completion_proposal
    TO kokonut_solution_learning_applier;
GRANT SELECT (completion_proposal_id, location_id, decision,
              reviewer_party_id, reviewed_at)
    ON TABLE public.solution_replication_completion_review_receipt
    TO kokonut_solution_learning_applier;
GRANT SELECT (id, status, owner_party_id, approved_by_party_id)
    ON TABLE public.solution_experiment
    TO kokonut_solution_learning_applier;
GRANT UPDATE (id) ON TABLE public.solution_experiment
    TO kokonut_solution_learning_applier;
GRANT SELECT (experiment_id, outcome, reviewed_by_party_id, reviewed_at)
    ON TABLE public.solution_experiment_result
    TO kokonut_solution_learning_applier;
GRANT UPDATE (id) ON TABLE public.solution_experiment_result
    TO kokonut_solution_learning_applier;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_learning_applier;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_learning_applier;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_learning_applier;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_learning_applier;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_learning_applier;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_learning_applier;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_learning_applier;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_learning_applier;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_learning_applier;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_learning_applier;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_learning_applier;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_learning_applier;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_learning_applier;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_learning_applier;

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

    IF caller_role = 'kokonut_solution_learning_applier'
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

    RAISE EXCEPTION 'Learning decisions require independent review or scoped application'
        USING ERRCODE = '42501';
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_learning_applications(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    learning_record_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    lesson_type TEXT,
    finding TEXT,
    recommended_action TEXT,
    confidence TEXT,
    transferability TEXT,
    affected_assumptions JSONB,
    affected_metrics JSONB,
    evidence JSONB,
    reviewed_at TIMESTAMPTZ,
    is_reviewed_by_current_actor BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    applier_party UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Learning application list requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'apply', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning application list requires an active exact location apply grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit < 1 OR requested_limit > 51
       OR requested_offset IS NULL OR requested_offset < 0 OR requested_offset > 10000 THEN
        RAISE EXCEPTION 'Learning application pagination is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id INTO applier_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS human
        ON human.id = binding.party_id
       AND human.party_type = 'person' AND human.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF applier_party IS NULL THEN
        RAISE EXCEPTION 'Learning application requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT learning.id, solution.name, solution.solution_type,
           learning.lesson_type, learning.finding, learning.recommended_action,
           learning.confidence, learning.transferability,
           learning.affected_assumptions, learning.affected_metrics,
           learning.evidence, learning.reviewed_at,
           learning.reviewed_by_party_id = applier_party
      FROM public.solution_learning_record AS learning
      JOIN public.solution_learning_review_receipt AS review
        ON review.learning_record_id = learning.id
       AND review.location_id = requested_location_id
       AND review.decision = 'accepted'
       AND review.reviewer_party_id = learning.reviewed_by_party_id
       AND review.reviewed_at = learning.reviewed_at
      JOIN public.solution_learning_proposal_event AS proposal
        ON proposal.learning_record_id = learning.id
       AND proposal.location_id = requested_location_id
      JOIN public.solution_replication AS replication
        ON replication.id = proposal.replication_id
       AND replication.id = learning.source_replication_id
       AND replication.status = 'completed'
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND replication.completed_at IS NOT NULL
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
      JOIN public.solution AS solution
        ON solution.id = learning.solution_id
       AND solution.id = replication.solution_id
       AND solution.status = 'active'
       AND ((solution.originating_scope_type = 'location'
             AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1 FROM public.solution_link AS location_link
                 WHERE location_link.solution_id = solution.id
                   AND location_link.entity_type = 'location'
                   AND location_link.entity_id = requested_location_id
            ))
     WHERE learning.decision_status = 'accepted'
       AND learning.reviewed_by_party_id IS NOT NULL
       AND learning.reviewed_at IS NOT NULL
       AND learning.applied_to_version IS NULL
       AND NOT EXISTS (
           SELECT 1 FROM public.solution_learning_application_receipt AS application
            WHERE application.learning_record_id = learning.id
       )
     ORDER BY learning.reviewed_at DESC, learning.id DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.apply_location_solution_learning(
    requested_location_id UUID,
    requested_learning_record_id UUID,
    requested_request_id UUID,
    requested_applied_to_version TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    application_id UUID,
    learning_record_id UUID,
    decision_status TEXT,
    applied_to_version TEXT,
    applied_by_party_id UUID,
    applied_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    applier_party UUID;
    existing_application RECORD;
    source_lineage RECORD;
    generated_application_id UUID;
    applied_timestamp TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_learning_record_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Learning application requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'apply', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Learning application requires an active exact location apply grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE
       OR requested_applied_to_version IS NULL
       OR pg_catalog.btrim(requested_applied_to_version) = ''
       OR pg_catalog.char_length(pg_catalog.btrim(requested_applied_to_version)) > 80 THEN
        RAISE EXCEPTION 'Learning application input or acknowledgement is invalid'
            USING ERRCODE = '22023';
    END IF;
    requested_applied_to_version := pg_catalog.btrim(requested_applied_to_version);

    SELECT binding.party_id INTO applier_party
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS human
        ON human.id = binding.party_id
       AND human.party_type = 'person' AND human.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, operator, human;
    IF applier_party IS NULL THEN
        RAISE EXCEPTION 'Learning application requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || requested_request_id::TEXT, 0)
    );
    SELECT receipt.id, receipt.location_id, receipt.learning_record_id,
           receipt.applier_party_id, receipt.applied_to_version, receipt.applied_at
      INTO existing_application
      FROM public.solution_learning_application_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_application.location_id IS DISTINCT FROM requested_location_id
           OR existing_application.learning_record_id IS DISTINCT FROM requested_learning_record_id
           OR existing_application.applier_party_id IS DISTINCT FROM applier_party
           OR existing_application.applied_to_version IS DISTINCT FROM requested_applied_to_version THEN
            RAISE EXCEPTION 'Learning application request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        application_id := existing_application.id;
        learning_record_id := existing_application.learning_record_id;
        decision_status := 'applied';
        applied_to_version := existing_application.applied_to_version;
        applied_by_party_id := existing_application.applier_party_id;
        applied_at := existing_application.applied_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT learning.id AS learning_id,
           learning.reviewed_by_party_id,
           proposal.proposer_party_id,
           replication.started_by_party_id,
           replication.reviewed_by_party_id AS initial_approver_party_id,
           replication.completion_reviewed_by_party_id,
           experiment.owner_party_id AS experiment_owner_party_id,
           experiment.approved_by_party_id AS experiment_approver_party_id,
           source_result.reviewed_by_party_id AS source_result_reviewer_party_id
      INTO source_lineage
      FROM public.solution_learning_record AS learning
      JOIN public.solution_learning_review_receipt AS review
        ON review.learning_record_id = learning.id
       AND review.location_id = requested_location_id
       AND review.decision = 'accepted'
       AND review.reviewer_party_id = learning.reviewed_by_party_id
       AND review.reviewed_at = learning.reviewed_at
      JOIN public.solution_learning_proposal_event AS proposal
        ON proposal.learning_record_id = learning.id
       AND proposal.location_id = requested_location_id
      JOIN public.solution_replication AS replication
        ON replication.id = proposal.replication_id
       AND replication.id = learning.source_replication_id
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
      JOIN public.solution AS solution
        ON solution.id = learning.solution_id
       AND solution.id = replication.solution_id
       AND solution.status = 'active'
       AND ((solution.originating_scope_type = 'location'
             AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1 FROM public.solution_link AS location_link
                 WHERE location_link.solution_id = solution.id
                   AND location_link.entity_type = 'location'
                   AND location_link.entity_id = requested_location_id
            ))
     WHERE learning.id = requested_learning_record_id
       AND learning.decision_status = 'accepted'
       AND learning.reviewed_at IS NOT NULL
       AND learning.applied_to_version IS NULL
       AND replication.status = 'completed'
       AND replication.completed_at IS NOT NULL
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
     FOR UPDATE OF learning, replication, solution, experiment, source_result;
    IF source_lineage.learning_id IS NULL THEN
        RAISE EXCEPTION 'Accepted learning with current source lineage not found for this location'
            USING ERRCODE = 'P0002';
    END IF;
    IF applier_party IS NOT DISTINCT FROM source_lineage.reviewed_by_party_id THEN
        RAISE EXCEPTION 'Learning application must be performed by a human distinct from its reviewer'
            USING ERRCODE = '42501';
    END IF;

    applied_timestamp := pg_catalog.clock_timestamp();
    UPDATE public.solution_learning_record AS learning
       SET decision_status = 'applied',
           applied_to_version = requested_applied_to_version,
           owner_party_id = applier_party
     WHERE learning.id = requested_learning_record_id;

    INSERT INTO public.solution_learning_application_receipt (
        operator_id, applier_party_id, location_id, learning_record_id,
        request_id, applied_to_version, applied_at
    ) VALUES (
        context_record.actor_id, applier_party, requested_location_id,
        requested_learning_record_id, requested_request_id,
        requested_applied_to_version, applied_timestamp
    ) RETURNING id INTO generated_application_id;

    application_id := generated_application_id;
    learning_record_id := requested_learning_record_id;
    decision_status := 'applied';
    applied_to_version := requested_applied_to_version;
    applied_by_party_id := applier_party;
    applied_at := applied_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_learning_applier;
ALTER FUNCTION kokonut_security.list_location_solution_learning_applications(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_solution_learning_applier;
ALTER FUNCTION kokonut_security.apply_location_solution_learning(
    UUID, UUID, UUID, TEXT, BOOLEAN
) OWNER TO kokonut_solution_learning_applier;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_learning_applier;
REVOKE ALL ON FUNCTION kokonut_security.list_location_solution_learning_applications(
    UUID, INTEGER, INTEGER
) FROM PUBLIC, kokonut_directus_runtime;
REVOKE ALL ON FUNCTION kokonut_security.apply_location_solution_learning(
    UUID, UUID, UUID, TEXT, BOOLEAN
) FROM PUBLIC, kokonut_directus_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.list_location_solution_learning_applications(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.apply_location_solution_learning(
    UUID, UUID, UUID, TEXT, BOOLEAN
) TO kokonut_runtime;

COMMENT ON FUNCTION kokonut_security.list_location_solution_learning_applications(
    UUID, INTEGER, INTEGER
) IS 'Lists accepted, unapplied learning only for the exact signed location and an active solution_lifecycle:apply grant, with current source lineage and bounded private lesson fields.';
COMMENT ON FUNCTION kokonut_security.apply_location_solution_learning(
    UUID, UUID, UUID, TEXT, BOOLEAN
) IS 'Applies one independently accepted learning record for its exact signed location through an active human with solution_lifecycle:apply, using current lineage, reviewer separation, and an immutable retry receipt.';

COMMIT;
