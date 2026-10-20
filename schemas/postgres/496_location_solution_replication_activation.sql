-- Start only independently approved replication proposals at their exact location.

BEGIN;

ALTER TABLE public.solution_replication
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS started_by_party_id UUID REFERENCES public.party(id) ON DELETE RESTRICT;

ALTER TABLE public.solution_replication
    DROP CONSTRAINT IF EXISTS solution_replication_started_attribution_check;
ALTER TABLE public.solution_replication
    ADD CONSTRAINT solution_replication_started_attribution_check
    CHECK ((started_at IS NULL) = (started_by_party_id IS NULL));

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_replication_starter'
    ) THEN
        CREATE ROLE kokonut_solution_replication_starter
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_replication_starter'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution replication starter role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_replication_starter'
            OR member_role.rolname = 'kokonut_solution_replication_starter'
    ) THEN
        RAISE EXCEPTION 'Solution replication starter role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_replication_activation_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    replication_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_replication(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (operator_id, request_id)
);

REVOKE ALL ON TABLE public.solution_replication_activation_receipt FROM PUBLIC;
REVOKE ALL ON TABLE public.solution_replication_activation_receipt
    FROM kokonut_runtime, kokonut_directus_runtime, kokonut_solution_reader,
         kokonut_solution_replication_proposer, kokonut_solution_replication_reviewer;
REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_replication_starter;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_replication_starter;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_replication_starter;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_replication_starter;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_replication_starter;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_replication_starter;

GRANT SELECT (
    id, solution_id, source_experiment_id, target_scope_type, target_scope_id,
    status, reviewed_by_party_id, reviewed_at, started_at, started_by_party_id,
    result, evidence_maturity, evidence, completed_at
) ON TABLE public.solution_replication TO kokonut_solution_replication_starter;
GRANT UPDATE (id, status, started_at, started_by_party_id)
    ON TABLE public.solution_replication TO kokonut_solution_replication_starter;
GRANT SELECT (id, status, originating_scope_type, originating_scope_id)
    ON TABLE public.solution TO kokonut_solution_replication_starter;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_replication_starter;
GRANT SELECT (source_experiment_id, proposer_party_id,
              location_id, replication_id)
    ON TABLE public.solution_replication_proposal_receipt
    TO kokonut_solution_replication_starter;
GRANT SELECT (operator_id, reviewer_party_id, location_id, replication_id,
              decision, reviewed_at)
    ON TABLE public.solution_replication_review_receipt
    TO kokonut_solution_replication_starter;
GRANT SELECT (id, solution_id, status, owner_party_id, approved_by_party_id)
    ON TABLE public.solution_experiment TO kokonut_solution_replication_starter;
GRANT UPDATE (id) ON TABLE public.solution_experiment
    TO kokonut_solution_replication_starter;
GRANT SELECT (experiment_id, outcome, reviewed_by_party_id, reviewed_at)
    ON TABLE public.solution_experiment_result
    TO kokonut_solution_replication_starter;
GRANT UPDATE (id) ON TABLE public.solution_experiment_result
    TO kokonut_solution_replication_starter;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_replication_starter;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_replication_starter;
GRANT SELECT (id, solution_id, entity_type, entity_id)
    ON TABLE public.solution_link TO kokonut_solution_replication_starter;
GRANT UPDATE (id) ON TABLE public.solution_link
    TO kokonut_solution_replication_starter;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_replication_starter;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_replication_starter;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_replication_starter;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_replication_starter;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_replication_starter;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_replication_starter;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_replication_starter;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_replication_starter;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_replication_starter;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_replication_starter;
GRANT SELECT, INSERT ON TABLE public.solution_replication_activation_receipt
    TO kokonut_solution_replication_starter;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_replication_starter;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_replication_starter;

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
            OR NEW.completed_at IS NOT NULL) THEN
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
           AND NEW.completed_at IS NOT DISTINCT FROM OLD.completed_at THEN
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
           AND NEW.completed_at IS NOT DISTINCT FROM OLD.completed_at THEN
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
           OR NEW.completed_at IS DISTINCT FROM OLD.completed_at THEN
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

CREATE OR REPLACE FUNCTION kokonut_security.activate_location_solution_replication(
    requested_location_id UUID,
    requested_replication_id UUID,
    requested_request_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    event_id UUID,
    replication_id UUID,
    replication_status TEXT,
    started_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    starter_party_id UUID;
    existing_receipt RECORD;
    selected_solution_id UUID;
    source_origin_type TEXT;
    source_origin_id UUID;
    proposer_party_id UUID;
    approval_party_id UUID;
    generated_receipt_id UUID;
    activation_timestamp TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_replication_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Replication activation requires signed operator location context and identifiers'
            USING ERRCODE = '42501';
    END IF;
    IF requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Replication activation acknowledgement is required'
            USING ERRCODE = '22023';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'transition', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Replication activation requires an active exact location transition grant'
            USING ERRCODE = '42501';
    END IF;

    SELECT binding.party_id
      INTO starter_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS starter
        ON starter.id = binding.party_id
       AND starter.party_type = 'person'
       AND starter.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, operator, starter;
    IF starter_party_id IS NULL THEN
        RAISE EXCEPTION 'Replication activation requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(context_record.actor_id::TEXT || requested_request_id::TEXT, 0)
    );
    SELECT receipt.id, receipt.location_id, receipt.replication_id,
           receipt.actor_party_id, receipt.started_at
      INTO existing_receipt
      FROM public.solution_replication_activation_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.replication_id IS DISTINCT FROM requested_replication_id
           OR existing_receipt.actor_party_id IS DISTINCT FROM starter_party_id THEN
            RAISE EXCEPTION 'Replication activation request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        event_id := existing_receipt.id;
        replication_id := existing_receipt.replication_id;
        replication_status := 'active';
        started_at := existing_receipt.started_at;
        replayed := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT replication.solution_id,
           solution.originating_scope_type,
           solution.originating_scope_id,
           proposal.proposer_party_id,
           approval.reviewer_party_id
      INTO selected_solution_id,
           source_origin_type,
           source_origin_id,
           proposer_party_id,
           approval_party_id
      FROM public.solution_replication AS replication
      JOIN public.solution AS solution
        ON solution.id = replication.solution_id
       AND solution.status = 'active'
      JOIN public.solution_replication_proposal_receipt AS proposal
        ON proposal.replication_id = replication.id
       AND proposal.location_id = requested_location_id
      JOIN public.solution_replication_review_receipt AS approval
        ON approval.replication_id = replication.id
       AND approval.location_id = requested_location_id
       AND approval.decision = 'approved'
       AND approval.reviewer_party_id = replication.reviewed_by_party_id
       AND approval.reviewed_at = replication.reviewed_at
      JOIN public.solution_experiment AS experiment
        ON experiment.id = proposal.source_experiment_id
       AND experiment.status = 'validated'
      JOIN public.solution_experiment_result AS source_result
        ON source_result.experiment_id = experiment.id
       AND source_result.outcome = 'validated'
       AND source_result.reviewed_at IS NOT NULL
      JOIN public.party AS source_reviewer
        ON source_reviewer.id = source_result.reviewed_by_party_id
       AND source_reviewer.party_type = 'person'
       AND source_reviewer.status = 'active'
     WHERE replication.id = requested_replication_id
       AND replication.status = 'approved'
       AND replication.target_scope_type = 'location'
       AND replication.target_scope_id = requested_location_id
       AND replication.started_at IS NULL
       AND replication.started_by_party_id IS NULL
       AND experiment.owner_party_id IS DISTINCT FROM source_result.reviewed_by_party_id
       AND experiment.approved_by_party_id IS DISTINCT FROM source_result.reviewed_by_party_id
     FOR UPDATE OF replication, solution, experiment, source_result
     FOR SHARE OF source_reviewer;
    IF selected_solution_id IS NULL OR proposer_party_id IS NULL
       OR approval_party_id IS NULL THEN
        RAISE EXCEPTION 'Independently approved replication was not found for this location'
            USING ERRCODE = 'P0002';
    END IF;
    IF source_origin_type IS DISTINCT FROM 'location'
       OR source_origin_id IS DISTINCT FROM requested_location_id THEN
        PERFORM 1
          FROM public.solution_link AS location_link
         WHERE location_link.solution_id = selected_solution_id
           AND location_link.entity_type = 'location'
           AND location_link.entity_id = requested_location_id
         FOR SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Replication solution is no longer visible at the exact target location'
                USING ERRCODE = 'P0002';
        END IF;
    END IF;

    activation_timestamp := pg_catalog.clock_timestamp();
    UPDATE public.solution_replication
       SET status = 'active',
           started_at = activation_timestamp,
           started_by_party_id = starter_party_id
     WHERE id = requested_replication_id;

    INSERT INTO public.solution_replication_activation_receipt (
        operator_id, actor_party_id, location_id, replication_id, request_id, started_at
    ) VALUES (
        context_record.actor_id, starter_party_id, requested_location_id,
        requested_replication_id, requested_request_id, activation_timestamp
    ) RETURNING id INTO generated_receipt_id;

    event_id := generated_receipt_id;
    replication_id := requested_replication_id;
    replication_status := 'active';
    started_at := activation_timestamp;
    replayed := FALSE;
    RETURN NEXT;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_solution_replication_starter;
ALTER FUNCTION kokonut_security.activate_location_solution_replication(UUID, UUID, UUID, BOOLEAN)
    OWNER TO kokonut_solution_replication_starter;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_solution_replication_starter;
REVOKE ALL ON FUNCTION kokonut_security.activate_location_solution_replication(UUID, UUID, UUID, BOOLEAN)
    FROM PUBLIC;

COMMENT ON TABLE public.solution_replication_activation_receipt IS
'Append-only receipt for explicitly starting an independently approved location replication.';
COMMENT ON FUNCTION kokonut_security.activate_location_solution_replication(UUID, UUID, UUID, BOOLEAN) IS
'Starts only an independently approved replication targeting the exact signed location, after rechecking the active source experiment, reviewed result, human identity, exact transition grant, and solution visibility; writes the activation and immutable idempotency receipt atomically and does not complete replication or change solution stage.';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.activate_location_solution_replication(UUID, UUID, UUID, BOOLEAN)
            TO kokonut_runtime;
        REVOKE ALL ON TABLE public.solution_replication_activation_receipt FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.activate_location_solution_replication(UUID, UUID, UUID, BOOLEAN)
            FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.solution_replication_activation_receipt FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMIT;
