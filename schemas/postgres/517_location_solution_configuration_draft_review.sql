-- Add immutable location configuration drafts and independent approval.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_configuration_manager'
    ) THEN
        CREATE ROLE kokonut_solution_configuration_manager
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_configuration_manager'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Solution configuration manager role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_configuration_manager'
            OR member_role.rolname = 'kokonut_solution_configuration_manager'
    ) THEN
        RAISE EXCEPTION 'Solution configuration manager role must not have memberships';
    END IF;
END;
$$;

ALTER TABLE public.solution_configuration
    ADD COLUMN IF NOT EXISTS proposed_by_operator_id UUID
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS proposed_by_party_id UUID
        REFERENCES public.party(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS proposed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS submitted_by_operator_id UUID
        REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS submitted_by_party_id UUID
        REFERENCES public.party(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS current_approval_review_id UUID;

CREATE TABLE IF NOT EXISTS public.solution_configuration_legacy_approval_archive (
    configuration_id UUID PRIMARY KEY
        REFERENCES public.solution_configuration(id) ON DELETE RESTRICT,
    prior_approval_status TEXT NOT NULL,
    prior_approved_by_party_id UUID,
    prior_approved_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

CREATE TABLE IF NOT EXISTS public.solution_configuration_draft_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    proposer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    configuration_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_configuration(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL CHECK (version > 0),
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    proposed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS public.solution_configuration_submission_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    submitter_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    configuration_id UUID NOT NULL
        REFERENCES public.solution_configuration(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    submitted_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id),
    UNIQUE (configuration_id)
);

CREATE TABLE IF NOT EXISTS public.solution_configuration_review_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reviewer_operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    proposer_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    configuration_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_configuration(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    review_note TEXT NOT NULL CHECK (pg_catalog.length(review_note) BETWEEN 1 AND 2000),
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    reviewed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (reviewer_operator_id, request_id),
    CHECK (reviewer_party_id <> proposer_party_id)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.solution_configuration'::regclass
           AND conname = 'solution_configuration_current_review_fk'
    ) THEN
        ALTER TABLE public.solution_configuration
            ADD CONSTRAINT solution_configuration_current_review_fk
            FOREIGN KEY (current_approval_review_id)
            REFERENCES public.solution_configuration_review_receipt(id)
            ON DELETE RESTRICT;
    END IF;
END;
$$;

-- Preserve the old approval facts, but do not let an approval made through the
-- retired shared-role writer satisfy a future adoption-stage transition.
INSERT INTO public.solution_configuration_legacy_approval_archive (
    configuration_id, prior_approval_status, prior_approved_by_party_id,
    prior_approved_at
)
SELECT configuration.id, configuration.approval_status,
       configuration.approved_by_party_id, configuration.approved_at
  FROM public.solution_configuration AS configuration
 WHERE configuration.approval_status = 'approved'
ON CONFLICT (configuration_id) DO NOTHING;

UPDATE public.solution_configuration
   SET approval_status = 'draft',
       approved_by_party_id = NULL,
       approved_at = NULL,
       current_approval_review_id = NULL
 WHERE approval_status = 'approved';

CREATE INDEX IF NOT EXISTS idx_solution_configuration_location_drafts
    ON public.solution_configuration(scope_id, proposed_at DESC, id DESC)
    WHERE scope_type = 'location' AND approval_status = 'draft'
      AND proposed_by_operator_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_solution_configuration_location_review
    ON public.solution_configuration(scope_id, submitted_at DESC, id DESC)
    WHERE scope_type = 'location' AND approval_status = 'submitted'
      AND proposed_by_party_id IS NOT NULL;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE
    ON TABLE public.solution_configuration
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime;
REVOKE ALL ON TABLE public.solution_configuration_legacy_approval_archive,
    public.solution_configuration_draft_receipt,
    public.solution_configuration_submission_receipt,
    public.solution_configuration_review_receipt
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime,
    kokonut_solution_configuration_manager;

ALTER TABLE public.solution_configuration_draft_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_configuration_draft_receipt FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_configuration_manager_draft_receipt
    ON public.solution_configuration_draft_receipt;
CREATE POLICY solution_configuration_manager_draft_receipt
    ON public.solution_configuration_draft_receipt
    TO kokonut_solution_configuration_manager
    USING (CURRENT_USER = 'kokonut_solution_configuration_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_configuration_manager');

ALTER TABLE public.solution_configuration_submission_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_configuration_submission_receipt FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_configuration_manager_submission_receipt
    ON public.solution_configuration_submission_receipt;
CREATE POLICY solution_configuration_manager_submission_receipt
    ON public.solution_configuration_submission_receipt
    TO kokonut_solution_configuration_manager
    USING (CURRENT_USER = 'kokonut_solution_configuration_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_configuration_manager');

ALTER TABLE public.solution_configuration_review_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_configuration_review_receipt FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_configuration_manager_review_receipt
    ON public.solution_configuration_review_receipt;
CREATE POLICY solution_configuration_manager_review_receipt
    ON public.solution_configuration_review_receipt
    TO kokonut_solution_configuration_manager
    USING (CURRENT_USER = 'kokonut_solution_configuration_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_configuration_manager');

ALTER TABLE public.solution_configuration_legacy_approval_archive ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_configuration_legacy_approval_archive FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_configuration_manager_legacy_archive
    ON public.solution_configuration_legacy_approval_archive;
CREATE POLICY solution_configuration_manager_legacy_archive
    ON public.solution_configuration_legacy_approval_archive
    TO kokonut_solution_configuration_manager
    USING (CURRENT_USER = 'kokonut_solution_configuration_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_configuration_manager');

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_configuration_manager;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_configuration_manager;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_configuration_manager;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_configuration_manager;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_configuration_manager;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_configuration_manager;

GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage, status)
    ON TABLE public.solution TO kokonut_solution_configuration_manager;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_configuration_manager;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_configuration_manager;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_configuration_manager;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_configuration_manager;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_configuration_manager;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_configuration_manager;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_configuration_manager;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_configuration_manager;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_configuration_manager;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_configuration_manager;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_configuration_manager;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_configuration_manager;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_configuration_manager;

GRANT SELECT (id, solution_id, scope_type, scope_id, version,
              invariant_components, configurable_components, prohibited_components,
              local_assumptions, adaptation_owner_party_id, comparability_class,
              evidence_impact, approval_status, approved_by_party_id, approved_at,
              proposed_by_operator_id, proposed_by_party_id, proposed_at,
              submitted_by_operator_id, submitted_by_party_id, submitted_at,
              current_approval_review_id)
    ON TABLE public.solution_configuration
    TO kokonut_solution_configuration_manager;
GRANT INSERT (solution_id, scope_type, scope_id, version,
              invariant_components, configurable_components, prohibited_components,
              local_assumptions, adaptation_owner_party_id, comparability_class,
              evidence_impact, approval_status, proposed_by_operator_id,
              proposed_by_party_id, proposed_at)
    ON TABLE public.solution_configuration
    TO kokonut_solution_configuration_manager;
GRANT UPDATE (approval_status, approved_by_party_id, approved_at,
              current_approval_review_id, submitted_by_operator_id,
              submitted_by_party_id, submitted_at)
    ON TABLE public.solution_configuration
    TO kokonut_solution_configuration_manager;

GRANT SELECT (operator_id, proposer_party_id, location_id, solution_id,
              configuration_id, version, request_id, payload_digest, proposed_at)
    ON TABLE public.solution_configuration_draft_receipt
    TO kokonut_solution_configuration_manager;
GRANT INSERT (operator_id, proposer_party_id, location_id, solution_id,
              configuration_id, version, request_id, payload_digest, proposed_at)
    ON TABLE public.solution_configuration_draft_receipt
    TO kokonut_solution_configuration_manager;
GRANT SELECT (operator_id, submitter_party_id, location_id, configuration_id,
              request_id, payload_digest, submitted_at)
    ON TABLE public.solution_configuration_submission_receipt
    TO kokonut_solution_configuration_manager;
GRANT INSERT (operator_id, submitter_party_id, location_id, configuration_id,
              request_id, payload_digest, submitted_at)
    ON TABLE public.solution_configuration_submission_receipt
    TO kokonut_solution_configuration_manager;
GRANT SELECT (id, reviewer_operator_id, reviewer_party_id, proposer_party_id,
              location_id, solution_id, configuration_id, decision, review_note,
              request_id, payload_digest, reviewed_at)
    ON TABLE public.solution_configuration_review_receipt
    TO kokonut_solution_configuration_manager;
GRANT INSERT (reviewer_operator_id, reviewer_party_id, proposer_party_id,
              location_id, solution_id, configuration_id, decision, review_note,
              request_id, payload_digest, reviewed_at)
    ON TABLE public.solution_configuration_review_receipt
    TO kokonut_solution_configuration_manager;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_configuration_manager;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_configuration_manager;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_configuration_manager;

CREATE OR REPLACE FUNCTION public.enforce_solution_configuration_independent_review()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF NEW.approval_status = 'approved' THEN
        IF NEW.current_approval_review_id IS NULL
           OR NEW.scope_type <> 'location'
           OR NEW.proposed_by_party_id IS NULL
           OR NEW.approved_by_party_id IS NULL
           OR NEW.approved_by_party_id = NEW.proposed_by_party_id
           OR NOT EXISTS (
               SELECT 1
                 FROM public.solution_configuration_review_receipt AS receipt
                WHERE receipt.id = NEW.current_approval_review_id
                  AND receipt.configuration_id = NEW.id
                  AND receipt.location_id = NEW.scope_id
                  AND receipt.solution_id = NEW.solution_id
                  AND receipt.decision = 'approved'
                  AND receipt.reviewer_party_id = NEW.approved_by_party_id
                  AND receipt.proposer_party_id = NEW.proposed_by_party_id
           ) THEN
            RAISE EXCEPTION 'Configuration cannot be approved without an independent review of this exact draft'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_solution_configuration_independent_review
    ON public.solution_configuration;
CREATE TRIGGER trg_solution_configuration_independent_review
    BEFORE INSERT OR UPDATE OF approval_status, approved_by_party_id,
        proposed_by_party_id, current_approval_review_id
    ON public.solution_configuration
    FOR EACH ROW EXECUTE FUNCTION public.enforce_solution_configuration_independent_review();

CREATE OR REPLACE FUNCTION kokonut_security.create_location_solution_configuration_draft(
    requested_location_id UUID,
    requested_solution_id UUID,
    requested_request_id UUID,
    requested_invariant_components JSONB,
    requested_configurable_components JSONB,
    requested_prohibited_components JSONB,
    requested_local_assumptions JSONB,
    requested_comparability_class TEXT,
    requested_evidence_impact TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    configuration_id UUID,
    solution_id UUID,
    version INTEGER,
    approval_status TEXT,
    proposed_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    proposer_party_id UUID;
    solution_record RECORD;
    prior_receipt RECORD;
    configuration_key UUID;
    next_version INTEGER;
    proposed_time TIMESTAMPTZ;
    payload_digest BYTEA;
    component_key TEXT;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Configuration draft requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Configuration draft requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_solution_id IS NULL OR requested_request_id IS NULL
       OR requested_invariant_components IS NULL
       OR pg_catalog.jsonb_typeof(requested_invariant_components) IS DISTINCT FROM 'object'
       OR requested_configurable_components IS NULL
       OR pg_catalog.jsonb_typeof(requested_configurable_components) IS DISTINCT FROM 'object'
       OR requested_prohibited_components IS NULL
       OR pg_catalog.jsonb_typeof(requested_prohibited_components) IS DISTINCT FROM 'object'
       OR requested_local_assumptions IS NULL
       OR pg_catalog.jsonb_typeof(requested_local_assumptions) IS DISTINCT FROM 'object'
       OR pg_catalog.octet_length(pg_catalog.convert_to(
           pg_catalog.jsonb_build_array(requested_invariant_components,
               requested_configurable_components, requested_prohibited_components,
               requested_local_assumptions)::TEXT, 'UTF8')) > 65536
       OR requested_comparability_class IS NULL
       OR requested_comparability_class NOT IN (
           'comparable', 'partially_comparable', 'not_comparable'
       )
       OR requested_evidence_impact IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_evidence_impact)) NOT BETWEEN 1 AND 4000
       OR pg_catalog.octet_length(pg_catalog.convert_to(requested_evidence_impact, 'UTF8')) > 8000
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Configuration draft input is invalid'
            USING ERRCODE = '22023';
    END IF;
    FOR component_key IN SELECT pg_catalog.jsonb_object_keys(requested_invariant_components)
    LOOP
        IF requested_configurable_components ? component_key
           OR requested_prohibited_components ? component_key THEN
            RAISE EXCEPTION 'A component cannot be both invariant and configurable or prohibited'
                USING ERRCODE = '22023';
        END IF;
    END LOOP;
    FOR component_key IN SELECT pg_catalog.jsonb_object_keys(requested_configurable_components)
    LOOP
        IF requested_prohibited_components ? component_key THEN
            RAISE EXCEPTION 'A component cannot be both configurable and prohibited'
                USING ERRCODE = '22023';
        END IF;
    END LOOP;

    SELECT binding.party_id
      INTO proposer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS proposer
        ON proposer.id = binding.party_id
       AND proposer.party_type = 'person'
       AND proposer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, proposer;
    IF proposer_party_id IS NULL THEN
        RAISE EXCEPTION 'Configuration draft requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'solution_id', requested_solution_id,
            'invariant_components', requested_invariant_components,
            'configurable_components', requested_configurable_components,
            'prohibited_components', requested_prohibited_components,
            'local_assumptions', requested_local_assumptions,
            'comparability_class', requested_comparability_class,
            'evidence_impact', pg_catalog.btrim(requested_evidence_impact),
            'acknowledged', requested_acknowledged
        )::TEXT, 'UTF8'), 'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.proposer_party_id, receipt.location_id, receipt.solution_id,
           receipt.configuration_id, receipt.version, receipt.payload_digest,
           receipt.proposed_at
      INTO prior_receipt
      FROM public.solution_configuration_draft_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.proposer_party_id IS DISTINCT FROM proposer_party_id
           OR prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.solution_id IS DISTINCT FROM requested_solution_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Configuration draft request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY
        SELECT prior_receipt.configuration_id, prior_receipt.solution_id,
               prior_receipt.version, configuration.approval_status::TEXT,
               prior_receipt.proposed_at, TRUE
          FROM public.solution_configuration AS configuration
         WHERE configuration.id = prior_receipt.configuration_id;
        RETURN;
    END IF;

    SELECT solution.id INTO solution_record
      FROM public.solution AS solution
     WHERE solution.id = requested_solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.current_stage IN ('pilot_active', 'adoption_ready')
       AND solution.status = 'active'
     FOR UPDATE;
    IF solution_record.id IS NULL THEN
        RAISE EXCEPTION 'Active location-origin solution was not found'
            USING ERRCODE = 'P0002';
    END IF;

    SELECT COALESCE(pg_catalog.max(configuration.version), 0) + 1
      INTO next_version
      FROM public.solution_configuration AS configuration
     WHERE configuration.solution_id = requested_solution_id
       AND configuration.scope_type = 'location'
       AND configuration.scope_id = requested_location_id;
    proposed_time := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_configuration (
        solution_id, scope_type, scope_id, version,
        invariant_components, configurable_components, prohibited_components,
        local_assumptions, adaptation_owner_party_id, comparability_class,
        evidence_impact, approval_status, proposed_by_operator_id,
        proposed_by_party_id, proposed_at
    ) VALUES (
        requested_solution_id, 'location', requested_location_id, next_version,
        requested_invariant_components, requested_configurable_components,
        requested_prohibited_components, requested_local_assumptions,
        proposer_party_id, requested_comparability_class,
        pg_catalog.btrim(requested_evidence_impact), 'draft',
        context_record.actor_id, proposer_party_id, proposed_time
    ) RETURNING id INTO configuration_key;
    INSERT INTO public.solution_configuration_draft_receipt (
        operator_id, proposer_party_id, location_id, solution_id,
        configuration_id, version, request_id, payload_digest, proposed_at
    ) VALUES (
        context_record.actor_id, proposer_party_id, requested_location_id,
        requested_solution_id, configuration_key, next_version,
        requested_request_id, payload_digest, proposed_time
    );
    RETURN QUERY SELECT configuration_key, requested_solution_id,
                        next_version, 'draft'::TEXT, proposed_time, FALSE;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_configuration_drafts(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    configuration_id UUID,
    solution_id UUID,
    version INTEGER,
    comparability_class TEXT,
    evidence_impact TEXT,
    proposed_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    proposer_party_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR NOT public.operator_scope_grant_allows(
           context_record.actor_id, 'solution_lifecycle', 'submit', requested_location_id
       ) THEN
        RAISE EXCEPTION 'Configuration draft list requires signed exact-location submit scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 26
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Configuration draft page is invalid' USING ERRCODE = '22023';
    END IF;
    SELECT binding.party_id INTO proposer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS proposer
        ON proposer.id = binding.party_id AND proposer.party_type = 'person'
       AND proposer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF proposer_party_id IS NULL THEN
        RAISE EXCEPTION 'Configuration draft list requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT configuration.id, configuration.solution_id, configuration.version,
           configuration.comparability_class::TEXT, configuration.evidence_impact,
           configuration.proposed_at
      FROM public.solution_configuration AS configuration
     WHERE configuration.scope_type = 'location'
       AND configuration.scope_id = requested_location_id
       AND configuration.proposed_by_operator_id = context_record.actor_id
       AND configuration.proposed_by_party_id = proposer_party_id
       AND configuration.approval_status = 'draft'
     ORDER BY configuration.proposed_at DESC, configuration.id DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.submit_location_solution_configuration(
    requested_location_id UUID,
    requested_configuration_id UUID,
    requested_request_id UUID,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    configuration_id UUID,
    solution_id UUID,
    version INTEGER,
    approval_status TEXT,
    submitted_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
#variable_conflict use_column
DECLARE
    context_record RECORD;
    submitter_party_id UUID;
    configuration RECORD;
    solution_record RECORD;
    prior_receipt RECORD;
    submission_time TIMESTAMPTZ;
    payload_digest BYTEA;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Configuration submission requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'submit', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Configuration submission requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_configuration_id IS NULL OR requested_request_id IS NULL
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Configuration submission input is invalid' USING ERRCODE = '22023';
    END IF;
    SELECT binding.party_id INTO submitter_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS submitter
        ON submitter.id = binding.party_id AND submitter.party_type = 'person'
       AND submitter.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, submitter;
    IF submitter_party_id IS NULL THEN
        RAISE EXCEPTION 'Configuration submission requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'configuration_id', requested_configuration_id,
            'acknowledged', requested_acknowledged
        )::TEXT, 'UTF8'), 'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.submitter_party_id, receipt.location_id,
           receipt.configuration_id, receipt.payload_digest, receipt.submitted_at
      INTO prior_receipt
      FROM public.solution_configuration_submission_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.submitter_party_id IS DISTINCT FROM submitter_party_id
           OR prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.configuration_id IS DISTINCT FROM requested_configuration_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Configuration submission request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY
        SELECT prior_receipt.configuration_id, configuration.solution_id,
               configuration.version, 'submitted'::TEXT,
               prior_receipt.submitted_at, TRUE
          FROM public.solution_configuration AS configuration
         WHERE configuration.id = prior_receipt.configuration_id;
        RETURN;
    END IF;

    SELECT config.id, config.solution_id, config.version,
           config.proposed_by_operator_id, config.proposed_by_party_id
      INTO configuration
      FROM public.solution_configuration AS config
     WHERE config.id = requested_configuration_id
       AND config.scope_type = 'location'
       AND config.scope_id = requested_location_id
       AND config.proposed_by_operator_id = context_record.actor_id
       AND config.proposed_by_party_id = submitter_party_id
       AND config.approval_status = 'draft'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location configuration draft is missing or no longer eligible'
            USING ERRCODE = '55000';
    END IF;
    SELECT solution.id INTO solution_record
      FROM public.solution AS solution
     WHERE solution.id = configuration.solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.current_stage IN ('pilot_active', 'adoption_ready')
       AND solution.status = 'active'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Configuration solution is no longer active at this location'
            USING ERRCODE = '55000';
    END IF;
    submission_time := pg_catalog.clock_timestamp();
    UPDATE public.solution_configuration AS current_configuration
       SET approval_status = 'submitted',
           submitted_by_operator_id = context_record.actor_id,
           submitted_by_party_id = submitter_party_id,
           submitted_at = submission_time
     WHERE current_configuration.id = configuration.id;
    INSERT INTO public.solution_configuration_submission_receipt (
        operator_id, submitter_party_id, location_id, configuration_id,
        request_id, payload_digest, submitted_at
    ) VALUES (
        context_record.actor_id, submitter_party_id, requested_location_id,
        configuration.id, requested_request_id, payload_digest, submission_time
    );
    RETURN QUERY SELECT configuration.id, configuration.solution_id,
                        configuration.version, 'submitted'::TEXT,
                        submission_time, FALSE;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_configuration_review_queue(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    configuration_id UUID,
    solution_id UUID,
    version INTEGER,
    invariant_components JSONB,
    configurable_components JSONB,
    prohibited_components JSONB,
    local_assumptions JSONB,
    comparability_class TEXT,
    evidence_impact TEXT,
    submitted_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    reviewer_party_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR NOT public.operator_scope_grant_allows(
           context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
       ) THEN
        RAISE EXCEPTION 'Configuration review queue requires signed exact-location review scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 26
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Configuration review page is invalid' USING ERRCODE = '22023';
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
        RAISE EXCEPTION 'Configuration review queue requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT configuration.id, configuration.solution_id, configuration.version,
           configuration.invariant_components, configuration.configurable_components,
           configuration.prohibited_components, configuration.local_assumptions,
           configuration.comparability_class::TEXT, configuration.evidence_impact,
           configuration.submitted_at
      FROM public.solution_configuration AS configuration
     WHERE configuration.scope_type = 'location'
       AND configuration.scope_id = requested_location_id
       AND configuration.approval_status = 'submitted'
       AND configuration.proposed_by_party_id <> reviewer_party_id
       AND NOT EXISTS (
           SELECT 1 FROM public.solution_configuration_review_receipt AS receipt
            WHERE receipt.configuration_id = configuration.id
       )
     ORDER BY configuration.submitted_at DESC, configuration.id DESC
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.review_location_solution_configuration(
    requested_location_id UUID,
    requested_configuration_id UUID,
    requested_request_id UUID,
    requested_decision TEXT,
    requested_review_note TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    configuration_id UUID,
    solution_id UUID,
    decision TEXT,
    approval_status TEXT,
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
    reviewer_party_id UUID;
    configuration RECORD;
    solution_record RECORD;
    prior_receipt RECORD;
    review_time TIMESTAMPTZ;
    payload_digest BYTEA;
    configuration_record_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Configuration review requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Configuration review requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_configuration_id IS NULL OR requested_request_id IS NULL
       OR requested_decision IS NULL
       OR requested_decision NOT IN ('approved', 'rejected')
       OR requested_review_note IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_review_note)) NOT BETWEEN 1 AND 2000
       OR pg_catalog.octet_length(pg_catalog.convert_to(requested_review_note, 'UTF8')) > 4000
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Configuration review input is invalid' USING ERRCODE = '22023';
    END IF;
    SELECT binding.party_id INTO reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS reviewer
        ON reviewer.id = binding.party_id AND reviewer.party_type = 'person'
       AND reviewer.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, reviewer;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Configuration review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    payload_digest := public.digest(
        pg_catalog.convert_to(pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'configuration_id', requested_configuration_id,
            'decision', requested_decision,
            'review_note', pg_catalog.btrim(requested_review_note),
            'acknowledged', requested_acknowledged
        )::TEXT, 'UTF8'), 'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.reviewer_party_id, receipt.proposer_party_id,
           receipt.location_id, receipt.solution_id, receipt.configuration_id,
           receipt.decision, receipt.review_note, receipt.payload_digest,
           receipt.reviewed_at
      INTO prior_receipt
      FROM public.solution_configuration_review_receipt AS receipt
     WHERE receipt.reviewer_operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.reviewer_party_id IS DISTINCT FROM reviewer_party_id
           OR prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.configuration_id IS DISTINCT FROM requested_configuration_id
           OR prior_receipt.decision IS DISTINCT FROM requested_decision
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Configuration review request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_receipt.configuration_id,
                            prior_receipt.solution_id, prior_receipt.decision,
                            prior_receipt.decision, prior_receipt.reviewed_at, TRUE;
        RETURN;
    END IF;

    SELECT config.id, config.solution_id, config.proposed_by_party_id
      INTO configuration
      FROM public.solution_configuration AS config
     WHERE config.id = requested_configuration_id
       AND config.scope_type = 'location'
       AND config.scope_id = requested_location_id
       AND config.approval_status = 'submitted'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Location configuration is missing or no longer submitted'
            USING ERRCODE = '55000';
    END IF;
    IF configuration.proposed_by_party_id IS NULL
       OR configuration.proposed_by_party_id = reviewer_party_id THEN
        RAISE EXCEPTION 'Configuration must be reviewed by a different active human'
            USING ERRCODE = '42501';
    END IF;
    SELECT solution.id INTO solution_record
      FROM public.solution AS solution
     WHERE solution.id = configuration.solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.current_stage IN ('pilot_active', 'adoption_ready')
       AND solution.status = 'active'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Configuration solution is no longer active at this location'
            USING ERRCODE = '55000';
    END IF;

    review_time := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_configuration_review_receipt (
        reviewer_operator_id, reviewer_party_id, proposer_party_id,
        location_id, solution_id, configuration_id, decision, review_note,
        request_id, payload_digest, reviewed_at
    ) VALUES (
        context_record.actor_id, reviewer_party_id,
        configuration.proposed_by_party_id, requested_location_id,
        configuration.solution_id, configuration.id, requested_decision,
        pg_catalog.btrim(requested_review_note), requested_request_id,
        payload_digest, review_time
    ) RETURNING id INTO configuration_record_id;
    UPDATE public.solution_configuration AS current_configuration
       SET approval_status = requested_decision,
           approved_by_party_id = CASE WHEN requested_decision = 'approved'
                                       THEN reviewer_party_id ELSE NULL END,
           approved_at = CASE WHEN requested_decision = 'approved'
                              THEN review_time ELSE NULL END,
           current_approval_review_id = configuration_record_id
     WHERE current_configuration.id = configuration.id;
    RETURN QUERY SELECT configuration.id, configuration.solution_id,
                        requested_decision, requested_decision,
                        review_time, FALSE;
END;
$$;

ALTER FUNCTION kokonut_security.create_location_solution_configuration_draft(
    UUID, UUID, UUID, JSONB, JSONB, JSONB, JSONB, TEXT, TEXT, BOOLEAN
) OWNER TO kokonut_solution_configuration_manager;
ALTER FUNCTION kokonut_security.location_solution_configuration_drafts(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_solution_configuration_manager;
ALTER FUNCTION kokonut_security.submit_location_solution_configuration(
    UUID, UUID, UUID, BOOLEAN
) OWNER TO kokonut_solution_configuration_manager;
ALTER FUNCTION kokonut_security.location_solution_configuration_review_queue(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_solution_configuration_manager;
ALTER FUNCTION kokonut_security.review_location_solution_configuration(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) OWNER TO kokonut_solution_configuration_manager;

REVOKE ALL ON FUNCTION kokonut_security.create_location_solution_configuration_draft(
    UUID, UUID, UUID, JSONB, JSONB, JSONB, JSONB, TEXT, TEXT, BOOLEAN
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_configuration_drafts(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_configuration(
    UUID, UUID, UUID, BOOLEAN
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_configuration_review_queue(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.review_location_solution_configuration(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_solution_configuration_draft(
            UUID, UUID, UUID, JSONB, JSONB, JSONB, JSONB, TEXT, TEXT, BOOLEAN
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_solution_configuration_drafts(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.submit_location_solution_configuration(
            UUID, UUID, UUID, BOOLEAN
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_solution_configuration_review_queue(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.review_location_solution_configuration(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_location_solution_configuration_draft(
            UUID, UUID, UUID, JSONB, JSONB, JSONB, JSONB, TEXT, TEXT, BOOLEAN
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.location_solution_configuration_drafts(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.submit_location_solution_configuration(
            UUID, UUID, UUID, BOOLEAN
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.location_solution_configuration_review_queue(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.review_location_solution_configuration(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_configuration_legacy_approval_archive IS
    'Preserves status and attribution from pre-Kernel configuration approvals that lacked an immutable independent-review receipt.';
COMMENT ON TABLE public.solution_configuration_draft_receipt IS
    'Private immutable idempotency receipt for exact-location configuration drafts.';
COMMENT ON TABLE public.solution_configuration_submission_receipt IS
    'Private immutable idempotency receipt for creator-submitted location configuration drafts.';
COMMENT ON TABLE public.solution_configuration_review_receipt IS
    'Private immutable approval or rejection by a different active human at the exact location.';
COMMENT ON FUNCTION public.enforce_solution_configuration_independent_review() IS
    'Prevents approved configuration status without an independent receipt for the exact current configuration.';

COMMIT;
