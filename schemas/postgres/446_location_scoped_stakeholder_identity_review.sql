-- Add a location-scoped Kernel path for reviewing farmer-to-party identity
-- candidates. Legacy network-wide identity views remain outside this API.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_stakeholder_identity_owner') THEN
        CREATE ROLE kokonut_stakeholder_identity_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_stakeholder_identity_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'stakeholder identity owner role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_stakeholder_identity_owner'
            OR member_role.rolname = 'kokonut_stakeholder_identity_owner'
    ) THEN
        RAISE EXCEPTION 'stakeholder identity owner role must not have memberships';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_stakeholder_identity_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_stakeholder_identity_owner;

CREATE TABLE public.party_location_identity_case (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    source_farmer_profile_id UUID NOT NULL REFERENCES public.farmer_profile(id) ON DELETE RESTRICT,
    candidate_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    proposed_party_type TEXT NOT NULL DEFAULT 'person' CHECK (proposed_party_type = 'person'),
    match_method TEXT NOT NULL CHECK (match_method IN (
        'manual', 'exact_identifier', 'verified_document', 'community_review'
    )),
    evidence_code TEXT NOT NULL CHECK (evidence_code IN (
        'verified_identifier', 'document_review', 'participant_confirmation', 'community_review'
    )),
    confidence NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    status TEXT NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    decided_at TIMESTAMPTZ,
    UNIQUE (operator_id, request_id),
    CHECK ((status = 'proposed' AND decided_at IS NULL)
        OR (status IN ('approved', 'rejected') AND decided_at IS NOT NULL))
);

CREATE UNIQUE INDEX uq_party_location_identity_pending_source
    ON public.party_location_identity_case(location_id, source_farmer_profile_id)
    WHERE status = 'proposed';
CREATE UNIQUE INDEX uq_party_location_identity_approved_source
    ON public.party_location_identity_case(source_farmer_profile_id)
    WHERE status = 'approved';
CREATE INDEX idx_party_location_identity_review_queue
    ON public.party_location_identity_case(location_id, created_at DESC, id DESC)
    WHERE status = 'proposed';

CREATE TABLE public.party_location_identity_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL UNIQUE
        REFERENCES public.party_location_identity_case(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    proposer_operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    reviewer_operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
    reason_code TEXT NOT NULL CHECK (reason_code IN (
        'match_confirmed', 'insufficient_evidence', 'conflicting_identity', 'source_not_eligible'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (reviewer_operator_id, request_id),
    CHECK (proposer_operator_id <> reviewer_operator_id)
);
CREATE INDEX idx_party_location_identity_decision_location
    ON public.party_location_identity_decision(location_id, created_at DESC, id DESC);

CREATE OR REPLACE FUNCTION public.prevent_party_location_identity_decision_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'stakeholder identity decisions are append-only';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_party_location_identity_decision_immutable
    ON public.party_location_identity_decision;
CREATE TRIGGER trg_party_location_identity_decision_immutable
    BEFORE UPDATE OR DELETE ON public.party_location_identity_decision
    FOR EACH ROW EXECUTE FUNCTION public.prevent_party_location_identity_decision_mutation();

CREATE OR REPLACE FUNCTION public.guard_party_location_identity_case_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF current_user <> 'kokonut_stakeholder_identity_owner'
       AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
             WHERE rolname = current_user AND rolsuper
       ) THEN
        RAISE EXCEPTION 'stakeholder identity cases require the audited Kernel path'
            USING ERRCODE = '42501';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'proposed' OR NEW.decided_at IS NOT NULL THEN
            RAISE EXCEPTION 'new stakeholder identity cases must be proposed'
                USING ERRCODE = '42501';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP <> 'UPDATE'
       OR OLD.status <> 'proposed'
       OR NEW.status NOT IN ('approved', 'rejected')
       OR (to_jsonb(NEW) - ARRAY['status', 'decided_at'])
          IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status', 'decided_at'])
       OR NEW.decided_at IS NULL THEN
        RAISE EXCEPTION 'stakeholder identity case transition is invalid'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_party_location_identity_case_guard
    ON public.party_location_identity_case;
CREATE TRIGGER trg_party_location_identity_case_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.party_location_identity_case
    FOR EACH ROW EXECUTE FUNCTION public.guard_party_location_identity_case_mutation();

REVOKE ALL ON TABLE public.party_location_identity_case,
    public.party_location_identity_decision FROM PUBLIC;
REVOKE ALL ON FUNCTION public.prevent_party_location_identity_decision_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.guard_party_location_identity_case_mutation() FROM PUBLIC;

GRANT SELECT ON TABLE public.party_location_identity_case,
    public.party_location_identity_decision TO kokonut_stakeholder_identity_owner;
GRANT INSERT ON TABLE public.party_location_identity_case,
    public.party_location_identity_decision TO kokonut_stakeholder_identity_owner;
GRANT UPDATE (status, decided_at) ON TABLE public.party_location_identity_case
    TO kokonut_stakeholder_identity_owner;
GRANT SELECT ON TABLE public.party, public.farmer_profile, public.farmer_consent,
    public.party_identifier,
    public.operator_identity, public.operator_scope_grant,
    public.operator_organization_membership, public.location,
    public.location_tenant_owner_verification, public.location_organization_share,
    public.organization TO kokonut_stakeholder_identity_owner;
GRANT UPDATE (id) ON TABLE public.party, public.farmer_profile,
    public.operator_identity, public.operator_scope_grant,
    public.operator_organization_membership, public.location,
    public.location_tenant_owner_verification, public.location_organization_share,
    public.organization TO kokonut_stakeholder_identity_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_stakeholder_identity_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_stakeholder_identity_owner;

CREATE OR REPLACE FUNCTION kokonut_security.propose_location_party_identity(
    requested_location_id UUID,
    requested_source_profile_id UUID,
    requested_candidate_party_id UUID,
    requested_request_id UUID,
    requested_match_method TEXT,
    requested_evidence_code TEXT,
    requested_confidence NUMERIC
)
RETURNS TABLE(case_id UUID, case_status TEXT, created_at TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    consent_record RECORD;
    profile_record RECORD;
    candidate_record RECORD;
    prior_case public.party_location_identity_case%ROWTYPE;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_source_profile_id IS NULL
       OR requested_candidate_party_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'identity proposal requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'stakeholder_identity', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'identity proposal requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_match_method IS NULL
       OR requested_match_method NOT IN ('manual', 'exact_identifier', 'verified_document', 'community_review')
       OR requested_evidence_code IS NULL
       OR requested_evidence_code NOT IN (
           'verified_identifier', 'document_review', 'participant_confirmation', 'community_review'
       )
       OR requested_confidence IS NULL
       OR requested_confidence < 0 OR requested_confidence > 1 THEN
        RAISE EXCEPTION 'identity proposal contains invalid structured evidence'
            USING ERRCODE = '22023';
    END IF;

    SELECT profile.id, profile.location_id, profile.status
      INTO profile_record
      FROM public.farmer_profile AS profile
     WHERE profile.id = requested_source_profile_id
     FOR SHARE OF profile;
    IF NOT FOUND OR profile_record.location_id IS DISTINCT FROM requested_location_id
       OR profile_record.status <> 'active' THEN
        RAISE EXCEPTION 'identity source is not eligible in this location'
            USING ERRCODE = '42501';
    END IF;

    SELECT consent.status, consent.expires_at
      INTO consent_record
      FROM public.farmer_consent AS consent
     WHERE consent.farmer_id = requested_source_profile_id::TEXT
       AND consent.location_id = requested_location_id
       AND consent.data_category = 'personal'
       AND consent.consent_scope = 'internal_use'
     ORDER BY consent.created_at DESC, consent.id DESC
     LIMIT 1;
    IF NOT FOUND OR consent_record.status <> 'granted'
       OR (consent_record.expires_at IS NOT NULL AND consent_record.expires_at <= clock_timestamp()) THEN
        RAISE EXCEPTION 'current personal internal-use consent is required'
            USING ERRCODE = '42501';
    END IF;

    SELECT party.id, party.party_type, party.status
      INTO candidate_record
      FROM public.party AS party
     WHERE party.id = requested_candidate_party_id
     FOR SHARE OF party;
    IF NOT FOUND OR candidate_record.party_type <> 'person'
       OR candidate_record.status <> 'active' THEN
        RAISE EXCEPTION 'active canonical person identity was not found'
            USING ERRCODE = '22023';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT existing.* INTO prior_case
      FROM public.party_location_identity_case AS existing
     WHERE existing.operator_id = context_record.actor_id
       AND existing.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_case.location_id IS DISTINCT FROM requested_location_id
           OR prior_case.source_farmer_profile_id IS DISTINCT FROM requested_source_profile_id
           OR prior_case.candidate_party_id IS DISTINCT FROM requested_candidate_party_id
           OR prior_case.match_method IS DISTINCT FROM requested_match_method
           OR prior_case.evidence_code IS DISTINCT FROM requested_evidence_code
           OR prior_case.confidence IS DISTINCT FROM requested_confidence THEN
            RAISE EXCEPTION 'identity request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        case_id := prior_case.id;
        case_status := prior_case.status;
        created_at := prior_case.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.party_location_identity_case AS approved_case
         WHERE approved_case.source_farmer_profile_id = requested_source_profile_id
           AND approved_case.status = 'approved'
    ) OR EXISTS (
        SELECT 1 FROM public.party_identifier AS legacy_link
         WHERE legacy_link.identifier_type = 'farmer_profile_id'
           AND legacy_link.verification_status = 'verified'
           AND (legacy_link.identifier_value = requested_source_profile_id::TEXT
                OR legacy_link.source_id = requested_source_profile_id::TEXT)
    ) THEN
        RAISE EXCEPTION 'identity source already has a canonical link outside this pending review'
            USING ERRCODE = '23505';
    END IF;

    INSERT INTO public.party_location_identity_case AS identity_case (
        location_id, source_farmer_profile_id, candidate_party_id, operator_id,
        request_id, match_method, evidence_code, confidence
    ) VALUES (
        requested_location_id, requested_source_profile_id, requested_candidate_party_id,
        context_record.actor_id, requested_request_id, requested_match_method,
        requested_evidence_code, requested_confidence
    )
    RETURNING identity_case.id, identity_case.status, identity_case.created_at
         INTO case_id, case_status, created_at;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_party_identity_cases(
    requested_location_id UUID,
    requested_limit INTEGER DEFAULT 51,
    before_created_at TIMESTAMPTZ DEFAULT NULL,
    before_case_id UUID DEFAULT NULL
)
RETURNS TABLE (
    case_id UUID,
    candidate_party_id UUID,
    candidate_name TEXT,
    source_label TEXT,
    match_method TEXT,
    evidence_code TEXT,
    confidence NUMERIC,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
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
       OR context_record.location_id IS DISTINCT FROM requested_location_id THEN
        RAISE EXCEPTION 'identity review read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'stakeholder_identity', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'identity review read requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 101
       OR (before_created_at IS NULL) <> (before_case_id IS NULL) THEN
        RAISE EXCEPTION 'identity review page arguments are invalid' USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT identity_case.id,
           CASE WHEN profile.id IS NULL
                       OR current_consent.status IS DISTINCT FROM 'granted'
                       OR (current_consent.expires_at IS NOT NULL
                           AND current_consent.expires_at <= clock_timestamp())
                       OR candidate.privacy_level = 'private'
                       OR candidate.status <> 'active'
                       OR candidate.status <> 'active'
                THEN NULL ELSE identity_case.candidate_party_id END,
           CASE WHEN profile.id IS NULL
                       OR current_consent.status IS DISTINCT FROM 'granted'
                       OR (current_consent.expires_at IS NOT NULL
                           AND current_consent.expires_at <= clock_timestamp())
                       OR candidate.privacy_level = 'private'
                THEN NULL ELSE candidate.display_name::TEXT END,
           CASE WHEN profile.id IS NULL
                       OR current_consent.status IS DISTINCT FROM 'granted'
                       OR (current_consent.expires_at IS NOT NULL
                           AND current_consent.expires_at <= clock_timestamp())
                THEN NULL
                ELSE NULLIF(pg_catalog.btrim(pg_catalog.concat_ws(' ', profile.first_name, profile.last_name)), '')
           END,
           identity_case.match_method,
           identity_case.evidence_code,
           identity_case.confidence,
           identity_case.created_at
      FROM public.party_location_identity_case AS identity_case
      LEFT JOIN public.farmer_profile AS profile
        ON profile.id = identity_case.source_farmer_profile_id
       AND profile.location_id = requested_location_id
       AND profile.status = 'active'
      JOIN public.party AS candidate ON candidate.id = identity_case.candidate_party_id
      LEFT JOIN LATERAL (
          SELECT consent.status, consent.expires_at
            FROM public.farmer_consent AS consent
           WHERE consent.farmer_id = identity_case.source_farmer_profile_id::TEXT
             AND consent.location_id = identity_case.location_id
             AND consent.data_category = 'personal'
             AND consent.consent_scope = 'internal_use'
           ORDER BY consent.created_at DESC, consent.id DESC
           LIMIT 1
      ) AS current_consent ON TRUE
     WHERE identity_case.location_id = requested_location_id
       AND identity_case.status = 'proposed'
       AND (before_created_at IS NULL OR
            (identity_case.created_at, identity_case.id) < (before_created_at, before_case_id))
     ORDER BY identity_case.created_at DESC, identity_case.id DESC
     LIMIT requested_limit;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.decide_location_party_identity(
    requested_location_id UUID,
    requested_case_id UUID,
    requested_request_id UUID,
    requested_decision TEXT,
    requested_reason_code TEXT
)
RETURNS TABLE(case_id UUID, case_status TEXT, reviewer_operator_id UUID, created_at TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    identity_case public.party_location_identity_case%ROWTYPE;
    prior_decision public.party_location_identity_decision%ROWTYPE;
    consent_record RECORD;
    decision_time TIMESTAMPTZ := clock_timestamp();
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_case_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'identity decision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'stakeholder_identity', 'review', requested_location_id
    ) THEN
        RAISE EXCEPTION 'identity decision requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision IS NULL OR requested_decision NOT IN ('approve', 'reject')
       OR requested_reason_code IS NULL
       OR requested_reason_code NOT IN (
           'match_confirmed', 'insufficient_evidence', 'conflicting_identity', 'source_not_eligible'
       ) THEN
        RAISE EXCEPTION 'identity decision is invalid' USING ERRCODE = '22023';
    END IF;

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT decision_row.* INTO prior_decision
      FROM public.party_location_identity_decision AS decision_row
     WHERE decision_row.reviewer_operator_id = context_record.actor_id
       AND decision_row.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_decision.case_id IS DISTINCT FROM requested_case_id
           OR prior_decision.location_id IS DISTINCT FROM requested_location_id
           OR prior_decision.decision IS DISTINCT FROM requested_decision
           OR prior_decision.reason_code IS DISTINCT FROM requested_reason_code THEN
            RAISE EXCEPTION 'identity decision request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        case_id := prior_decision.case_id;
        case_status := CASE prior_decision.decision
                           WHEN 'approve' THEN 'approved'
                           ELSE 'rejected'
                       END;
        reviewer_operator_id := prior_decision.reviewer_operator_id;
        created_at := prior_decision.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT pending.* INTO identity_case
      FROM public.party_location_identity_case AS pending
     WHERE pending.id = requested_case_id
       AND pending.location_id = requested_location_id
       AND pending.status = 'proposed'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'identity case was not found in this location or is already decided'
            USING ERRCODE = 'P0002';
    END IF;
    IF identity_case.operator_id = context_record.actor_id THEN
        RAISE EXCEPTION 'identity review must be performed by a different operator'
            USING ERRCODE = '42501';
    END IF;
    IF requested_decision = 'approve' THEN
        PERFORM profile.id
          FROM public.farmer_profile AS profile
         WHERE profile.id = identity_case.source_farmer_profile_id
           AND profile.location_id = requested_location_id
           AND profile.status = 'active'
         FOR SHARE OF profile;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'identity source is no longer eligible in this location'
                USING ERRCODE = '42501';
        END IF;
        PERFORM candidate.id
          FROM public.party AS candidate
         WHERE candidate.id = identity_case.candidate_party_id
           AND candidate.party_type = 'person'
           AND candidate.status = 'active'
         FOR SHARE OF candidate;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'canonical identity is no longer eligible'
                USING ERRCODE = '22023';
        END IF;
        IF EXISTS (
            SELECT 1 FROM public.party_identifier AS legacy_link
             WHERE legacy_link.identifier_type = 'farmer_profile_id'
               AND legacy_link.verification_status = 'verified'
               AND (legacy_link.identifier_value = identity_case.source_farmer_profile_id::TEXT
                    OR legacy_link.source_id = identity_case.source_farmer_profile_id::TEXT)
        ) THEN
            RAISE EXCEPTION 'identity source acquired a legacy canonical link during review'
                USING ERRCODE = '23505';
        END IF;
        SELECT consent.status, consent.expires_at
          INTO consent_record
          FROM public.farmer_consent AS consent
         WHERE consent.farmer_id = identity_case.source_farmer_profile_id::TEXT
           AND consent.location_id = requested_location_id
           AND consent.data_category = 'personal'
           AND consent.consent_scope = 'internal_use'
         ORDER BY consent.created_at DESC, consent.id DESC
         LIMIT 1;
        IF NOT FOUND OR consent_record.status <> 'granted'
           OR (consent_record.expires_at IS NOT NULL AND consent_record.expires_at <= decision_time) THEN
            RAISE EXCEPTION 'current personal internal-use consent is required for approval'
                USING ERRCODE = '42501';
        END IF;
    END IF;

    UPDATE public.party_location_identity_case AS pending
       SET status = CASE requested_decision
                        WHEN 'approve' THEN 'approved'
                        ELSE 'rejected'
                    END,
           decided_at = decision_time
     WHERE pending.id = requested_case_id
    RETURNING pending.id, pending.status INTO case_id, case_status;
    INSERT INTO public.party_location_identity_decision (
        case_id, location_id, proposer_operator_id, reviewer_operator_id,
        request_id, decision, reason_code, created_at
    ) VALUES (
        identity_case.id, requested_location_id, identity_case.operator_id,
        context_record.actor_id, requested_request_id, requested_decision,
        requested_reason_code, decision_time
    );
    reviewer_operator_id := context_record.actor_id;
    created_at := decision_time;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.propose_location_party_identity(UUID, UUID, UUID, UUID, TEXT, TEXT, NUMERIC)
    OWNER TO kokonut_stakeholder_identity_owner;
ALTER FUNCTION kokonut_security.list_location_party_identity_cases(UUID, INTEGER, TIMESTAMPTZ, UUID)
    OWNER TO kokonut_stakeholder_identity_owner;
ALTER FUNCTION kokonut_security.decide_location_party_identity(UUID, UUID, UUID, TEXT, TEXT)
    OWNER TO kokonut_stakeholder_identity_owner;

REVOKE ALL ON FUNCTION kokonut_security.propose_location_party_identity(UUID, UUID, UUID, UUID, TEXT, TEXT, NUMERIC) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_location_party_identity_cases(UUID, INTEGER, TIMESTAMPTZ, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.decide_location_party_identity(UUID, UUID, UUID, TEXT, TEXT) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.propose_location_party_identity(UUID, UUID, UUID, UUID, TEXT, TEXT, NUMERIC) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_party_identity_cases(UUID, INTEGER, TIMESTAMPTZ, UUID) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.decide_location_party_identity(UUID, UUID, UUID, TEXT, TEXT) TO kokonut_runtime;
        REVOKE ALL ON TABLE public.party_location_identity_case,
            public.party_location_identity_decision FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.party_location_identity_case,
            public.party_location_identity_decision FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.propose_location_party_identity(UUID, UUID, UUID, UUID, TEXT, TEXT, NUMERIC) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_party_identity_cases(UUID, INTEGER, TIMESTAMPTZ, UUID) FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.decide_location_party_identity(UUID, UUID, UUID, TEXT, TEXT) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON TABLE public.party_location_identity_case IS
    'Location-scoped identity proposals; source profile identifiers and structured match metadata are never exposed without current internal-use consent.';
COMMENT ON TABLE public.party_location_identity_decision IS
    'Append-only, independent OIDC operator decisions for location-scoped identity proposals.';
COMMENT ON FUNCTION kokonut_security.list_location_party_identity_cases(UUID, INTEGER, TIMESTAMPTZ, UUID) IS
    'Returns only bounded pending identity cases in the signed location, with a consent-gated name and no raw feedback, contact details, or source identifier.';

COMMIT;
