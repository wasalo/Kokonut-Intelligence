-- Bind adoption programs and participant events to an immutable, reviewed
-- location consent policy and an active opaque participant link.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_adoption_event_manager'
    ) THEN
        CREATE ROLE kokonut_solution_adoption_event_manager
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_adoption_event_manager'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Adoption event manager role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_adoption_event_manager'
            OR member_role.rolname = 'kokonut_solution_adoption_event_manager'
    ) THEN
        RAISE EXCEPTION 'Adoption event manager role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_adoption_program_consent_policy (
    program_id UUID PRIMARY KEY
        REFERENCES public.solution_adoption_program(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    data_category TEXT NOT NULL DEFAULT 'solution_adoption_participation'
        CHECK (data_category = 'solution_adoption_participation'),
    consent_purpose TEXT NOT NULL
        CHECK (pg_catalog.length(pg_catalog.btrim(consent_purpose)) BETWEEN 1 AND 255),
    consent_version TEXT NOT NULL
        CHECK (consent_version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,29}$'),
    configured_by_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    configured_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS public.solution_adoption_program_consent_policy_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    program_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_adoption_program(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL
        CHECK (pg_catalog.octet_length(payload_digest) = 32),
    configured_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

CREATE TABLE IF NOT EXISTS public.solution_adoption_event_capture_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    program_id UUID NOT NULL REFERENCES public.solution_adoption_program(id) ON DELETE RESTRICT,
    event_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_adoption_event(id) ON DELETE RESTRICT,
    participant_link_id UUID NOT NULL
        REFERENCES public.mobile_participant_link(id) ON DELETE RESTRICT,
    consent_event_id UUID NOT NULL
        REFERENCES public.stakeholder_consent(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL
        CHECK (pg_catalog.octet_length(payload_digest) = 32),
    observed_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

ALTER TABLE public.solution_adoption_program_consent_policy
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_adoption_program_consent_policy
    FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_adoption_event_manager_policy
    ON public.solution_adoption_program_consent_policy;
CREATE POLICY solution_adoption_event_manager_policy
    ON public.solution_adoption_program_consent_policy
    TO kokonut_solution_adoption_event_manager
    USING (CURRENT_USER = 'kokonut_solution_adoption_event_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_event_manager');
DROP POLICY IF EXISTS solution_adoption_reader_policy
    ON public.solution_adoption_program_consent_policy;
CREATE POLICY solution_adoption_reader_policy
    ON public.solution_adoption_program_consent_policy
    TO kokonut_solution_reader
    USING (CURRENT_USER = 'kokonut_solution_reader')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_reader');
DROP POLICY IF EXISTS solution_adoption_program_manager_policy
    ON public.solution_adoption_program_consent_policy;
CREATE POLICY solution_adoption_program_manager_policy
    ON public.solution_adoption_program_consent_policy
    TO kokonut_solution_adoption_program_manager
    USING (CURRENT_USER = 'kokonut_solution_adoption_program_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_program_manager');

ALTER TABLE public.solution_adoption_program_consent_policy_receipt
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_adoption_program_consent_policy_receipt
    FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_adoption_event_manager_policy_receipt
    ON public.solution_adoption_program_consent_policy_receipt;
CREATE POLICY solution_adoption_event_manager_policy_receipt
    ON public.solution_adoption_program_consent_policy_receipt
    TO kokonut_solution_adoption_event_manager
    USING (CURRENT_USER = 'kokonut_solution_adoption_event_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_event_manager');

ALTER TABLE public.solution_adoption_event_capture_receipt
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_adoption_event_capture_receipt
    FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_adoption_event_manager_capture_receipt
    ON public.solution_adoption_event_capture_receipt;
CREATE POLICY solution_adoption_event_manager_capture_receipt
    ON public.solution_adoption_event_capture_receipt
    TO kokonut_solution_adoption_event_manager
    USING (CURRENT_USER = 'kokonut_solution_adoption_event_manager')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_event_manager');

REVOKE ALL ON TABLE public.solution_adoption_program_consent_policy,
    public.solution_adoption_program_consent_policy_receipt,
    public.solution_adoption_event_capture_receipt
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_adoption_event_manager, kokonut_solution_reader;
GRANT SELECT (program_id, location_id, solution_id, data_category,
              consent_purpose, consent_version, configured_by_party_id,
              configured_at)
    ON TABLE public.solution_adoption_program_consent_policy
    TO kokonut_solution_adoption_event_manager, kokonut_solution_reader;
GRANT INSERT (program_id, location_id, solution_id, data_category,
              consent_purpose, consent_version, configured_by_party_id,
              configured_at)
    ON TABLE public.solution_adoption_program_consent_policy
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, operator_id, actor_party_id, location_id, solution_id,
              program_id, request_id, payload_digest, configured_at),
      INSERT (operator_id, actor_party_id, location_id, solution_id,
              program_id, request_id, payload_digest, configured_at)
    ON TABLE public.solution_adoption_program_consent_policy_receipt
    TO kokonut_solution_adoption_event_manager;

ALTER TABLE public.solution_adoption_event
    ALTER COLUMN adopter_ref DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS participant_link_id UUID
        REFERENCES public.mobile_participant_link(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS consent_event_id UUID
        REFERENCES public.stakeholder_consent(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS consent_validation_status TEXT NOT NULL DEFAULT 'unassessed'
        CHECK (consent_validation_status IN ('unassessed', 'granted'));

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conrelid = 'public.solution_adoption_event'::regclass
           AND conname = 'solution_adoption_event_consent_link_check'
    ) THEN
        ALTER TABLE public.solution_adoption_event
            ADD CONSTRAINT solution_adoption_event_consent_link_check
            CHECK (
                (consent_validation_status = 'granted'
                 AND participant_link_id IS NOT NULL AND consent_event_id IS NOT NULL
                 AND consent_checked IS TRUE AND adopter_ref IS NULL)
                OR
                (consent_validation_status = 'unassessed'
                 AND participant_link_id IS NULL AND consent_event_id IS NULL)
            );
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_solution_adoption_event_participant
    ON public.solution_adoption_event(program_id, participant_link_id, event_type)
    WHERE participant_link_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.prevent_solution_adoption_consent_policy_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Adoption consent policy is immutable; create a revised program instead'
        USING ERRCODE = '23514';
END;
$$;
DROP TRIGGER IF EXISTS trg_solution_adoption_consent_policy_immutable
    ON public.solution_adoption_program_consent_policy;
CREATE TRIGGER trg_solution_adoption_consent_policy_immutable
    BEFORE UPDATE OR DELETE ON public.solution_adoption_program_consent_policy
    FOR EACH ROW EXECUTE FUNCTION public.prevent_solution_adoption_consent_policy_mutation();

REVOKE ALL ON TABLE public.solution_adoption_event
    FROM PUBLIC, kokonut_runtime, kokonut_directus_runtime,
         kokonut_solution_adoption_event_manager;
REVOKE SELECT (adopter_ref, consent_checked)
    ON TABLE public.solution_adoption_event FROM kokonut_solution_reader;
GRANT INSERT (program_id, cohort_id, adopter_ref, event_type, observed_at,
              fidelity_score, support_required, outcome, consent_checked,
              evidence, recorded_by_party_id, participant_link_id,
              consent_event_id, consent_validation_status)
    ON TABLE public.solution_adoption_event
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (program_id, event_type, participant_link_id,
              consent_event_id, consent_validation_status)
    ON TABLE public.solution_adoption_event TO kokonut_solution_reader;
GRANT SELECT (id, party_id, location_id, revoked_at)
    ON TABLE public.mobile_participant_link TO kokonut_solution_reader;
GRANT SELECT (id, party_id, event_type, data_category, purpose,
              scope_type, scope_id, recipient_party_id, recipient_type,
              consent_version, effective_at, expires_at, created_at)
    ON TABLE public.stakeholder_consent TO kokonut_solution_reader;
GRANT SELECT (id, party_type, status)
    ON TABLE public.party TO kokonut_solution_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_solution_adoption(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS TABLE (
    solution_id UUID,
    solution_name TEXT,
    solution_type TEXT,
    current_stage TEXT,
    solution_status TEXT,
    program_id UUID,
    program_status TEXT,
    program_created_at TIMESTAMPTZ,
    program_updated_at TIMESTAMPTZ,
    consented_adopter_reference_count BIGINT
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Solution adoption read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution adoption read requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_offset IS NULL
       OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Solution adoption page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    WITH scoped_solutions AS (
        SELECT solution.id, solution.name, solution.solution_type,
               solution.current_stage, solution.status
          FROM public.solution AS solution
         WHERE (solution.originating_scope_type = 'location'
                AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1
                  FROM public.solution_link AS location_link
                 WHERE location_link.solution_id = solution.id
                   AND location_link.entity_type = 'location'
                   AND location_link.entity_id = requested_location_id
            )
    )
    SELECT scoped.id, pg_catalog.left(scoped.name, 255)::TEXT,
           scoped.solution_type::TEXT, scoped.current_stage::TEXT,
           scoped.status::TEXT, program.id, program.status::TEXT,
           program.created_at, program.updated_at,
           CASE WHEN consented.adopter_count >= 5 THEN consented.adopter_count
                ELSE NULL END
      FROM scoped_solutions AS scoped
      JOIN public.solution_adoption_program AS program
        ON program.solution_id = scoped.id
       AND program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
      LEFT JOIN public.solution_adoption_program_consent_policy AS policy
        ON policy.program_id = program.id
       AND policy.location_id = requested_location_id
       AND policy.solution_id = program.solution_id
      CROSS JOIN LATERAL (
          SELECT count(DISTINCT event.participant_link_id) AS adopter_count
            FROM public.solution_adoption_event AS event
            JOIN public.mobile_participant_link AS participant
              ON participant.id = event.participant_link_id
             AND participant.location_id = requested_location_id
             AND participant.revoked_at IS NULL
            JOIN public.party AS participant_party
              ON participant_party.id = participant.party_id
             AND participant_party.party_type = 'person'
             AND participant_party.status = 'active'
           WHERE event.program_id = program.id
             AND event.consent_validation_status = 'granted'
             AND event.consent_event_id IS NOT NULL
             AND policy.program_id IS NOT NULL
             AND EXISTS (
                 SELECT 1
                   FROM public.stakeholder_consent AS current_consent
                  WHERE current_consent.party_id = participant.party_id
                    AND current_consent.data_category = policy.data_category
                    AND current_consent.purpose = policy.consent_purpose
                    AND current_consent.scope_type = 'location'
                    AND current_consent.scope_id = requested_location_id
                    AND current_consent.recipient_party_id IS NULL
                    AND current_consent.recipient_type = 'system'
                    AND current_consent.consent_version = policy.consent_version
                    AND current_consent.id = (
                        SELECT latest.id
                          FROM public.stakeholder_consent AS latest
                         WHERE latest.party_id = participant.party_id
                           AND latest.data_category = policy.data_category
                           AND latest.purpose = policy.consent_purpose
                           AND latest.scope_type = 'location'
                           AND latest.scope_id = requested_location_id
                           AND latest.recipient_party_id IS NULL
                           AND latest.recipient_type = 'system'
                           AND latest.consent_version = policy.consent_version
                         ORDER BY latest.effective_at DESC, latest.created_at DESC, latest.id DESC
                         LIMIT 1
                    )
                    AND current_consent.event_type = 'grant'
                    AND (current_consent.expires_at IS NULL
                         OR current_consent.expires_at > pg_catalog.now())
             )
      ) AS consented
     ORDER BY program.created_at DESC, program.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.get_location_solution_adoption_event_summary(
    requested_location_id UUID,
    requested_program_id UUID
)
RETURNS TABLE (
    program_id UUID,
    engagement_reference_count BIGINT,
    commitment_reference_count BIGINT,
    use_reference_count BIGINT,
    advocacy_reference_count BIGINT,
    paused_or_abandoned_reference_count BIGINT,
    breakdown_suppressed BOOLEAN
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    scoped_program_id UUID;
    engagement_count BIGINT;
    commitment_count BIGINT;
    use_count BIGINT;
    advocacy_count BIGINT;
    paused_or_abandoned_count BIGINT;
    suppress_breakdown BOOLEAN;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL OR requested_program_id IS NULL THEN
        RAISE EXCEPTION 'Solution adoption detail requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Solution adoption detail requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;

    SELECT program.id INTO scoped_program_id
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
     WHERE program.id = requested_program_id
       AND program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
       AND ((solution.originating_scope_type = 'location'
             AND solution.originating_scope_id = requested_location_id)
            OR EXISTS (
                SELECT 1 FROM public.solution_link AS location_link
                 WHERE location_link.solution_id = solution.id
                   AND location_link.entity_type = 'location'
                   AND location_link.entity_id = requested_location_id
            ));
    IF scoped_program_id IS NULL THEN
        RAISE EXCEPTION 'Exact-location adoption program was not found'
            USING ERRCODE = 'P0002';
    END IF;

    WITH eligible_events AS (
        SELECT event.participant_link_id,
               CASE
                   WHEN event.event_type IN ('aware', 'interested', 'eligible') THEN 'engagement'
                   WHEN event.event_type IN ('committed', 'onboarded') THEN 'commitment'
                   WHEN event.event_type IN ('first_use', 'repeat_use', 'habitual_use') THEN 'use'
                   WHEN event.event_type = 'advocating' THEN 'advocacy'
                   WHEN event.event_type IN ('paused', 'abandoned') THEN 'paused_or_abandoned'
               END AS progress_phase
          FROM public.solution_adoption_event AS event
          JOIN public.mobile_participant_link AS participant
            ON participant.id = event.participant_link_id
           AND participant.location_id = requested_location_id
           AND participant.revoked_at IS NULL
          JOIN public.party AS participant_party
            ON participant_party.id = participant.party_id
           AND participant_party.party_type = 'person'
           AND participant_party.status = 'active'
          JOIN public.solution_adoption_program_consent_policy AS policy
            ON policy.program_id = event.program_id
           AND policy.location_id = requested_location_id
         WHERE event.program_id = scoped_program_id
           AND event.consent_validation_status = 'granted'
           AND event.consent_event_id IS NOT NULL
           AND EXISTS (
               SELECT 1
                 FROM public.stakeholder_consent AS current_consent
                WHERE current_consent.party_id = participant.party_id
                  AND current_consent.data_category = policy.data_category
                  AND current_consent.purpose = policy.consent_purpose
                  AND current_consent.scope_type = 'location'
                  AND current_consent.scope_id = requested_location_id
                  AND current_consent.recipient_party_id IS NULL
                  AND current_consent.recipient_type = 'system'
                  AND current_consent.consent_version = policy.consent_version
                  AND current_consent.id = (
                      SELECT latest.id
                        FROM public.stakeholder_consent AS latest
                       WHERE latest.party_id = participant.party_id
                         AND latest.data_category = policy.data_category
                         AND latest.purpose = policy.consent_purpose
                         AND latest.scope_type = 'location'
                         AND latest.scope_id = requested_location_id
                         AND latest.recipient_party_id IS NULL
                         AND latest.recipient_type = 'system'
                         AND latest.consent_version = policy.consent_version
                       ORDER BY latest.effective_at DESC, latest.created_at DESC, latest.id DESC
                       LIMIT 1
                  )
                  AND current_consent.event_type = 'grant'
                  AND (current_consent.expires_at IS NULL
                       OR current_consent.expires_at > pg_catalog.now())
           )
    ), phase_counts AS (
        SELECT count(DISTINCT participant_link_id)
                   FILTER (WHERE progress_phase = 'engagement') AS engagement,
               count(DISTINCT participant_link_id)
                   FILTER (WHERE progress_phase = 'commitment') AS commitment,
               count(DISTINCT participant_link_id)
                   FILTER (WHERE progress_phase = 'use') AS usage,
               count(DISTINCT participant_link_id)
                   FILTER (WHERE progress_phase = 'advocacy') AS advocacy,
               count(DISTINCT participant_link_id)
                   FILTER (WHERE progress_phase = 'paused_or_abandoned') AS paused_or_abandoned
          FROM eligible_events
    )
    SELECT phase_counts.engagement, phase_counts.commitment,
           phase_counts.usage, phase_counts.advocacy,
           phase_counts.paused_or_abandoned,
           EXISTS (
               SELECT 1 FROM unnest(ARRAY[
                   phase_counts.engagement, phase_counts.commitment,
                   phase_counts.usage, phase_counts.advocacy,
                   phase_counts.paused_or_abandoned
               ]) AS phase_count WHERE phase_count BETWEEN 1 AND 4
           )
      INTO engagement_count, commitment_count, use_count,
           advocacy_count, paused_or_abandoned_count, suppress_breakdown
      FROM phase_counts;

    RETURN QUERY SELECT scoped_program_id,
        CASE WHEN suppress_breakdown THEN NULL ELSE engagement_count END,
        CASE WHEN suppress_breakdown THEN NULL ELSE commitment_count END,
        CASE WHEN suppress_breakdown THEN NULL ELSE use_count END,
        CASE WHEN suppress_breakdown THEN NULL ELSE advocacy_count END,
        CASE WHEN suppress_breakdown THEN NULL ELSE paused_or_abandoned_count END,
        suppress_breakdown;
END;
$$;

REVOKE ALL ON TABLE public.solution_adoption_program_consent_policy_receipt,
    public.solution_adoption_event_capture_receipt
    FROM kokonut_solution_adoption_event_manager;
GRANT SELECT (id, operator_id, actor_party_id, location_id, solution_id,
              program_id, request_id, payload_digest, configured_at),
      INSERT (operator_id, actor_party_id, location_id, solution_id,
              program_id, request_id, payload_digest, configured_at)
    ON TABLE public.solution_adoption_program_consent_policy_receipt
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, operator_id, actor_party_id, location_id, solution_id,
              program_id, event_id, participant_link_id, consent_event_id,
              request_id, payload_digest, observed_at),
      INSERT (operator_id, actor_party_id, location_id, solution_id,
              program_id, event_id, participant_link_id, consent_event_id,
              request_id, payload_digest, observed_at)
    ON TABLE public.solution_adoption_event_capture_receipt
    TO kokonut_solution_adoption_event_manager;

REVOKE ALL ON TABLE public.solution_adoption_program_consent_policy,
    public.solution_adoption_program_consent_policy_receipt,
    public.solution_adoption_event_capture_receipt
    FROM kokonut_runtime, kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION public.require_location_adoption_consent_policy()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF OLD.status = 'draft' AND NEW.status = 'community_review'
       AND NOT EXISTS (
           SELECT 1 FROM public.solution_adoption_program_consent_policy AS policy
            WHERE policy.program_id = NEW.id
              AND policy.location_id = NEW.target_scope_id
              AND policy.solution_id = NEW.solution_id
       ) THEN
        RAISE EXCEPTION 'Adoption program submission requires its immutable reviewed participant consent policy'
            USING ERRCODE = '23514';
    END IF;
    IF OLD.status = 'community_review' AND NEW.status = 'enablement_ready'
       AND NOT EXISTS (
           SELECT 1 FROM public.solution_adoption_program_consent_policy AS policy
            WHERE policy.program_id = NEW.id
              AND policy.location_id = NEW.target_scope_id
              AND policy.solution_id = NEW.solution_id
       ) THEN
        RAISE EXCEPTION 'Adoption program approval requires a reviewed participant consent policy'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_require_location_adoption_consent_policy
    ON public.solution_adoption_program;
DROP TRIGGER IF EXISTS trg_00_require_location_adoption_consent_policy
    ON public.solution_adoption_program;
CREATE TRIGGER trg_00_require_location_adoption_consent_policy
    BEFORE UPDATE OF status ON public.solution_adoption_program
    FOR EACH ROW EXECUTE FUNCTION public.require_location_adoption_consent_policy();

CREATE OR REPLACE FUNCTION kokonut_security.configure_location_solution_adoption_consent_policy(
    requested_location_id UUID,
    requested_program_id UUID,
    requested_request_id UUID,
    requested_consent_purpose TEXT,
    requested_consent_version TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (program_id UUID, consent_purpose TEXT, consent_version TEXT,
               configured_at TIMESTAMPTZ, replayed BOOLEAN)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    program_record RECORD;
    prior_receipt RECORD;
    digest_value BYTEA;
    configure_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Adoption consent policy requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Adoption consent policy requires an active exact location create grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_program_id IS NULL OR requested_request_id IS NULL
       OR requested_acknowledged IS DISTINCT FROM TRUE
       OR requested_consent_version IS NULL
       OR requested_consent_purpose IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_consent_purpose)) NOT BETWEEN 1 AND 255
       OR requested_consent_version !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,29}$' THEN
        RAISE EXCEPTION 'Adoption participant consent policy input is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id INTO actor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, actor;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Adoption consent policy requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    digest_value := public.digest(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'program_id', requested_program_id,
            'data_category', 'solution_adoption_participation',
            'purpose', pg_catalog.btrim(requested_consent_purpose),
            'consent_version', requested_consent_version,
            'acknowledged', requested_acknowledged
        )::TEXT, 'UTF8'), 'sha256');
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0));
    SELECT receipt.actor_party_id, receipt.location_id, receipt.solution_id,
           receipt.program_id, receipt.payload_digest, receipt.configured_at
      INTO prior_receipt
      FROM public.solution_adoption_program_consent_policy_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.program_id IS DISTINCT FROM requested_program_id
           OR prior_receipt.payload_digest IS DISTINCT FROM digest_value THEN
            RAISE EXCEPTION 'Adoption consent policy request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT policy.program_id, policy.consent_purpose,
                            policy.consent_version, prior_receipt.configured_at, TRUE
          FROM public.solution_adoption_program_consent_policy AS policy
         WHERE policy.program_id = requested_program_id;
        RETURN;
    END IF;

    SELECT program.id, program.solution_id, program.status,
           program.target_scope_type, program.target_scope_id,
           program.created_by_party_id
      INTO program_record
      FROM public.solution_adoption_program AS program
     WHERE program.id = requested_program_id
       AND program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location adoption program was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF program_record.status IS DISTINCT FROM 'draft'
       OR program_record.created_by_party_id IS DISTINCT FROM actor_party_id THEN
        RAISE EXCEPTION 'Only the draft creator may configure its participant consent policy'
            USING ERRCODE = '55000';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.solution_adoption_program_consent_policy AS policy
         WHERE policy.program_id = requested_program_id
    ) THEN
        RAISE EXCEPTION 'Adoption participant consent policy is immutable once configured'
            USING ERRCODE = '23505';
    END IF;

    configure_time := pg_catalog.clock_timestamp();
    INSERT INTO public.solution_adoption_program_consent_policy (
        program_id, location_id, solution_id, data_category,
        consent_purpose, consent_version, configured_by_party_id, configured_at
    ) VALUES (
        requested_program_id, requested_location_id, program_record.solution_id,
        'solution_adoption_participation',
        pg_catalog.btrim(requested_consent_purpose), requested_consent_version,
        actor_party_id, configure_time
    );
    INSERT INTO public.solution_adoption_program_consent_policy_receipt (
        operator_id, actor_party_id, location_id, solution_id, program_id,
        request_id, payload_digest, configured_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        program_record.solution_id, requested_program_id,
        requested_request_id, digest_value, configure_time
    );
    RETURN QUERY SELECT requested_program_id,
                        pg_catalog.btrim(requested_consent_purpose),
                        requested_consent_version, configure_time, FALSE;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_adoption_program_review_queue_with_consent(
    requested_location_id UUID, requested_limit INTEGER, requested_offset INTEGER
)
RETURNS TABLE (program_id UUID, solution_id UUID, solution_name TEXT,
               program_status TEXT, adoption_pathway TEXT,
               local_adaptation_policy TEXT, submitted_at TIMESTAMPTZ,
               consent_data_category TEXT, consent_purpose TEXT,
               consent_version TEXT)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD; reviewer_party_id UUID;
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
        RAISE EXCEPTION 'Adoption program review queue requires signed location review scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Adoption program review page bounds are invalid'
            USING ERRCODE = '22023';
    END IF;
    SELECT binding.party_id INTO reviewer_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor ON actor.id = binding.party_id
       AND actor.party_type = 'person' AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id AND binding.revoked_at IS NULL;
    IF reviewer_party_id IS NULL THEN
        RAISE EXCEPTION 'Adoption program review requires an active human identity'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT program.id, program.solution_id,
           pg_catalog.left(solution.name, 255)::TEXT,
           program.status::TEXT,
           pg_catalog.left(program.adoption_pathway, 2000)::TEXT,
           pg_catalog.left(program.local_adaptation_policy, 4000)::TEXT,
           program.submitted_at,
           policy.data_category, policy.consent_purpose, policy.consent_version
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
      JOIN public.solution_adoption_program_submission_receipt AS submission
        ON submission.id = program.current_submission_id
       AND submission.program_id = program.id
      LEFT JOIN public.solution_adoption_program_consent_policy AS policy
        ON policy.program_id = program.id
       AND policy.location_id = requested_location_id
       AND policy.solution_id = program.solution_id
     WHERE program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
       AND program.status = 'community_review'
       AND program.created_by_party_id <> reviewer_party_id
       AND program.submitted_by_party_id <> reviewer_party_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.status = 'active'
       AND solution.current_stage IN ('pilot_active', 'adoption_ready', 'adopting')
     ORDER BY program.submitted_at, program.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.location_solution_adoption_program_drafts_with_consent(
    requested_location_id UUID, requested_limit INTEGER, requested_offset INTEGER
)
RETURNS TABLE (program_id UUID, solution_id UUID, solution_name TEXT,
               program_status TEXT, adoption_pathway TEXT,
               local_adaptation_policy TEXT, created_at TIMESTAMPTZ,
               consent_data_category TEXT, consent_purpose TEXT,
               consent_version TEXT)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$
DECLARE context_record RECORD;
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
        RAISE EXCEPTION 'Adoption program draft listing requires signed location submit scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 51
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Adoption program draft page bounds are invalid' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.operator_governance_party_binding AS binding
        JOIN public.operator_identity AS operator
          ON operator.id = binding.operator_id AND operator.enabled
        JOIN public.party AS actor ON actor.id = binding.party_id
         AND actor.party_type = 'person' AND actor.status = 'active'
        WHERE binding.operator_id = context_record.actor_id AND binding.revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Adoption program draft listing requires active human identity'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT program.id, program.solution_id,
           pg_catalog.left(solution.name, 255)::TEXT,
           program.status::TEXT,
           pg_catalog.left(program.adoption_pathway, 2000)::TEXT,
           pg_catalog.left(program.local_adaptation_policy, 4000)::TEXT,
           program.created_at,
           policy.data_category, policy.consent_purpose, policy.consent_version
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
      JOIN public.operator_governance_party_binding AS binding
        ON binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
       AND binding.party_id = program.created_by_party_id
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor ON actor.id = binding.party_id
       AND actor.party_type = 'person' AND actor.status = 'active'
      LEFT JOIN public.solution_adoption_program_consent_policy AS policy
        ON policy.program_id = program.id
       AND policy.location_id = requested_location_id
       AND policy.solution_id = program.solution_id
     WHERE program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
       AND program.status = 'draft'
     ORDER BY program.created_at DESC, program.id
     LIMIT requested_limit OFFSET requested_offset;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.capture_location_solution_adoption_event(
    requested_location_id UUID,
    requested_program_id UUID,
    requested_request_id UUID,
    requested_participant_ref_hash TEXT,
    requested_event_type TEXT,
    requested_fidelity_score NUMERIC,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (event_id UUID, program_id UUID, event_type TEXT,
               observed_at TIMESTAMPTZ, replayed BOOLEAN)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    program_record RECORD;
    participant_record RECORD;
    consent_record RECORD;
    prior_receipt RECORD;
    digest_value BYTEA;
    event_time TIMESTAMPTZ;
    new_event_id UUID;
    allowed_types CONSTANT TEXT[] := ARRAY[
        'aware', 'interested', 'eligible', 'committed', 'onboarded',
        'first_use', 'repeat_use', 'habitual_use', 'advocating', 'paused', 'abandoned'
    ];
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Adoption event capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'collect', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Adoption event capture requires an active exact location collect grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_program_id IS NULL OR requested_request_id IS NULL
       OR requested_acknowledged IS DISTINCT FROM TRUE
       OR requested_participant_ref_hash IS NULL
       OR requested_participant_ref_hash !~ '^[0-9a-f]{64}$'
       OR requested_event_type IS NULL
       OR NOT (requested_event_type = ANY(allowed_types))
       OR (requested_fidelity_score IS NOT NULL AND
           (requested_fidelity_score::TEXT = 'NaN'
            OR requested_fidelity_score < 0 OR requested_fidelity_score > 100)) THEN
        RAISE EXCEPTION 'Adoption event capture input is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id INTO actor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, actor;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Adoption event capture requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    digest_value := public.digest(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'location_id', requested_location_id,
            'program_id', requested_program_id,
            'participant_ref_hash', requested_participant_ref_hash,
            'event_type', requested_event_type,
            'fidelity_score', requested_fidelity_score,
            'acknowledged', requested_acknowledged
        )::TEXT, 'UTF8'), 'sha256');
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0));
    SELECT receipt.actor_party_id, receipt.location_id, receipt.solution_id,
           receipt.program_id, receipt.event_id, receipt.payload_digest,
           receipt.observed_at
      INTO prior_receipt
      FROM public.solution_adoption_event_capture_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.program_id IS DISTINCT FROM requested_program_id
           OR prior_receipt.payload_digest IS DISTINCT FROM digest_value THEN
            RAISE EXCEPTION 'Adoption event request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_receipt.event_id, prior_receipt.program_id,
                            requested_event_type, prior_receipt.observed_at, TRUE;
        RETURN;
    END IF;

    SELECT program.id, program.solution_id, program.status,
           program.target_scope_type, program.target_scope_id,
           solution.originating_scope_type, solution.originating_scope_id,
           solution.status AS solution_status, solution.current_stage,
           policy.data_category, policy.consent_purpose, policy.consent_version
      INTO program_record
      FROM public.solution_adoption_program AS program
      JOIN public.solution AS solution ON solution.id = program.solution_id
      JOIN public.solution_adoption_program_consent_policy AS policy
        ON policy.program_id = program.id
       AND policy.location_id = program.target_scope_id
       AND policy.solution_id = program.solution_id
     WHERE program.id = requested_program_id
       AND program.target_scope_type = 'location'
       AND program.target_scope_id = requested_location_id
     FOR UPDATE OF program, solution;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Exact-location adoption program or reviewed consent policy was not found'
            USING ERRCODE = 'P0002';
    END IF;
    IF program_record.status IS DISTINCT FROM 'enablement_ready'
       OR program_record.originating_scope_type IS DISTINCT FROM 'location'
       OR program_record.originating_scope_id IS DISTINCT FROM requested_location_id
       OR program_record.solution_status IS DISTINCT FROM 'active'
       OR program_record.current_stage NOT IN ('adoption_ready', 'adopting') THEN
        RAISE EXCEPTION 'Adoption events require a reviewed, exact-location enablement-ready program and active adoption-stage solution'
            USING ERRCODE = '55000';
    END IF;

    SELECT participant.id, participant.party_id, participant.location_id,
           participant.revoked_at, party.party_type, party.status
      INTO participant_record
      FROM public.mobile_participant_link AS participant
      JOIN public.party AS party ON party.id = participant.party_id
     WHERE participant.participant_ref_hash = requested_participant_ref_hash
       AND participant.location_id = requested_location_id
       AND participant.revoked_at IS NULL
       AND party.party_type = 'person' AND party.status = 'active'
     FOR SHARE OF participant, party;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active participant reference is not assigned to this location'
            USING ERRCODE = '42501';
    END IF;

    event_time := pg_catalog.clock_timestamp();
    SELECT consent.id, consent.event_type, consent.expires_at,
           consent.effective_at, consent.consent_version
      INTO consent_record
      FROM public.stakeholder_consent AS consent
     WHERE consent.party_id = participant_record.party_id
       AND consent.data_category = program_record.data_category
       AND consent.purpose = program_record.consent_purpose
       AND consent.scope_type = 'location'
       AND consent.scope_id = requested_location_id
       AND consent.recipient_party_id IS NULL
       AND consent.recipient_type = 'system'
       AND consent.consent_version = program_record.consent_version
       AND consent.effective_at <= event_time
     ORDER BY consent.effective_at DESC, consent.created_at DESC, consent.id DESC
     LIMIT 1;
    IF NOT FOUND OR consent_record.event_type IS DISTINCT FROM 'grant'
       OR consent_record.consent_version IS DISTINCT FROM program_record.consent_version
       OR (consent_record.expires_at IS NOT NULL
           AND consent_record.expires_at <= event_time) THEN
        RAISE EXCEPTION 'Current exact-location participant consent is required'
            USING ERRCODE = '42501';
    END IF;

    new_event_id := pg_catalog.gen_random_uuid();
    INSERT INTO public.solution_adoption_event (
        id, program_id, cohort_id, adopter_ref, event_type, observed_at,
        fidelity_score, outcome, consent_checked, evidence,
        recorded_by_party_id, participant_link_id, consent_event_id,
        consent_validation_status
    ) VALUES (
        new_event_id, requested_program_id, NULL, NULL, requested_event_type,
        event_time, requested_fidelity_score, '{}'::JSONB, TRUE, '{}'::JSONB,
        actor_party_id, participant_record.id, consent_record.id, 'granted'
    );
    INSERT INTO public.solution_adoption_event_capture_receipt (
        operator_id, actor_party_id, location_id, solution_id, program_id,
        event_id, participant_link_id, consent_event_id, request_id,
        payload_digest, observed_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        program_record.solution_id, requested_program_id, new_event_id,
        participant_record.id, consent_record.id, requested_request_id,
        digest_value, event_time
    );
    RETURN QUERY SELECT new_event_id, requested_program_id,
                        requested_event_type, event_time, FALSE;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_adoption_event_manager;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_adoption_event_manager;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_adoption_event_manager;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_adoption_event_manager;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_adoption_event_manager;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_adoption_event_manager;

GRANT SELECT (id, solution_id, target_scope_type, target_scope_id, status,
              created_by_party_id)
    ON TABLE public.solution_adoption_program
    TO kokonut_solution_adoption_event_manager;
GRANT UPDATE (id) ON TABLE public.solution_adoption_program
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, originating_scope_type, originating_scope_id,
              current_stage, status)
    ON TABLE public.solution TO kokonut_solution_adoption_event_manager;
GRANT UPDATE (id) ON TABLE public.solution TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_adoption_event_manager;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_adoption_event_manager;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_adoption_event_manager;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, party_id, location_id, participant_ref_hash, revoked_at)
    ON TABLE public.mobile_participant_link
    TO kokonut_solution_adoption_event_manager;
GRANT UPDATE (id) ON TABLE public.mobile_participant_link
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, party_id, event_type, data_category, purpose,
              scope_type, scope_id, recipient_party_id, recipient_type,
              consent_version, effective_at, expires_at, created_at)
    ON TABLE public.stakeholder_consent
    TO kokonut_solution_adoption_event_manager;
GRANT UPDATE (id) ON TABLE public.stakeholder_consent
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, program_id) ON TABLE public.solution_adoption_cohort
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (program_id, location_id, solution_id, data_category,
              consent_purpose, consent_version)
    ON TABLE public.solution_adoption_program_consent_policy
    TO kokonut_solution_adoption_event_manager;
GRANT INSERT (program_id, location_id, solution_id, data_category,
              consent_purpose, consent_version, configured_by_party_id,
              configured_at)
    ON TABLE public.solution_adoption_program_consent_policy
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, operator_id, actor_party_id, location_id, solution_id,
              program_id, request_id, payload_digest, configured_at),
      INSERT (operator_id, actor_party_id, location_id, solution_id,
              program_id, request_id, payload_digest, configured_at)
    ON TABLE public.solution_adoption_program_consent_policy_receipt
    TO kokonut_solution_adoption_event_manager;
GRANT SELECT (id, operator_id, actor_party_id, location_id, solution_id,
              program_id, event_id, participant_link_id, consent_event_id,
              request_id, payload_digest, observed_at),
      INSERT (operator_id, actor_party_id, location_id, solution_id,
              program_id, event_id, participant_link_id, consent_event_id,
              request_id, payload_digest, observed_at)
    ON TABLE public.solution_adoption_event_capture_receipt
    TO kokonut_solution_adoption_event_manager;
GRANT INSERT (id, program_id, cohort_id, adopter_ref, event_type, observed_at,
              fidelity_score, support_required, outcome, consent_checked,
              evidence, recorded_by_party_id, participant_link_id,
              consent_event_id, consent_validation_status)
    ON TABLE public.solution_adoption_event
    TO kokonut_solution_adoption_event_manager;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_adoption_event_manager;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_adoption_event_manager;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_adoption_event_manager;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_adoption_event_manager;
ALTER FUNCTION kokonut_security.configure_location_solution_adoption_consent_policy(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) OWNER TO kokonut_solution_adoption_event_manager;
ALTER FUNCTION kokonut_security.capture_location_solution_adoption_event(
    UUID, UUID, UUID, TEXT, TEXT, NUMERIC, BOOLEAN
) OWNER TO kokonut_solution_adoption_event_manager;
ALTER FUNCTION kokonut_security.location_solution_adoption_program_review_queue_with_consent(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_solution_adoption_program_manager;
ALTER FUNCTION kokonut_security.location_solution_adoption_program_drafts_with_consent(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_solution_adoption_program_manager;
GRANT SELECT (program_id, location_id, solution_id, data_category,
              consent_purpose, consent_version)
    ON TABLE public.solution_adoption_program_consent_policy
    TO kokonut_solution_adoption_program_manager;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_adoption_program_manager;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_adoption_program_manager;

REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_adoption_event_manager,
         kokonut_solution_adoption_program_manager;
REVOKE ALL ON FUNCTION kokonut_security.configure_location_solution_adoption_consent_policy(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.capture_location_solution_adoption_event(
    UUID, UUID, UUID, TEXT, TEXT, NUMERIC, BOOLEAN
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_adoption_program_review_queue_with_consent(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.location_solution_adoption_program_drafts_with_consent(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.configure_location_solution_adoption_consent_policy(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.capture_location_solution_adoption_event(
            UUID, UUID, UUID, TEXT, TEXT, NUMERIC, BOOLEAN
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_solution_adoption_program_review_queue_with_consent(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_solution_adoption_program_drafts_with_consent(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.solution_adoption_program_consent_policy IS
'One immutable, exact-location participant-consent policy per adoption program. Policy purpose and version are shown to an independent program reviewer before enablement.';
COMMENT ON FUNCTION kokonut_security.capture_location_solution_adoption_event(
    UUID, UUID, UUID, TEXT, TEXT, NUMERIC, BOOLEAN
) IS
'Captures one bounded exact-location adoption event for an enablement-ready program only when a current participant link and latest exact policy consent grant exist. Stores the opaque participant link and consent event, never the raw participant reference; retries are immutable and consent-aware summaries recheck withdrawal and link revocation.';

COMMIT;
