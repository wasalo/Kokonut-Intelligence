-- Derive location-scoped identity trust evidence only from independently
-- approved Kernel identity decisions. Legacy global trust tables stay private.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_stakeholder_trust_reader') THEN
        CREATE ROLE kokonut_stakeholder_trust_reader
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_stakeholder_trust_reader'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'stakeholder trust reader role has unsafe attributes';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_stakeholder_trust_reader'
            OR member_role.rolname = 'kokonut_stakeholder_trust_reader'
    ) THEN
        RAISE EXCEPTION 'stakeholder trust reader role must not have memberships';
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_stakeholder_trust_reader;
GRANT SELECT ON TABLE public.party_location_identity_case,
    public.party_location_identity_decision, public.party, public.farmer_profile,
    public.farmer_consent, public.operator_scope_grant
    TO kokonut_stakeholder_trust_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_stakeholder_trust_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_stakeholder_trust_reader;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_party_identity_trust_evidence(
    requested_location_id UUID,
    requested_party_id UUID,
    requested_limit INTEGER DEFAULT 51,
    before_reviewed_at TIMESTAMPTZ DEFAULT NULL,
    before_evidence_id UUID DEFAULT NULL
)
RETURNS TABLE (
    evidence_id UUID,
    dimension TEXT,
    direction TEXT,
    evidence_code TEXT,
    match_method TEXT,
    confidence NUMERIC,
    reviewed_at TIMESTAMPTZ
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
       OR requested_party_id IS NULL THEN
        RAISE EXCEPTION 'trust evidence read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'stakeholder_trust', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'trust evidence read requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit NOT BETWEEN 1 AND 101
       OR (before_reviewed_at IS NULL) <> (before_evidence_id IS NULL) THEN
        RAISE EXCEPTION 'trust evidence page arguments are invalid'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT identity_case.id,
           'identity'::TEXT,
           'supporting'::TEXT,
           identity_case.evidence_code,
           identity_case.match_method,
           identity_case.confidence,
           decision.created_at
      FROM public.party_location_identity_case AS identity_case
      JOIN public.party_location_identity_decision AS decision
        ON decision.case_id = identity_case.id
       AND decision.location_id = requested_location_id
       AND decision.decision = 'approve'
      JOIN public.party AS candidate
        ON candidate.id = identity_case.candidate_party_id
       AND candidate.status = 'active'
       AND candidate.privacy_level <> 'private'
      JOIN public.farmer_profile AS source_profile
        ON source_profile.id = identity_case.source_farmer_profile_id
       AND source_profile.location_id = requested_location_id
       AND source_profile.status = 'active'
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
       AND identity_case.candidate_party_id = requested_party_id
       AND identity_case.status = 'approved'
       AND current_consent.status = 'granted'
       AND (current_consent.expires_at IS NULL
            OR current_consent.expires_at > statement_timestamp())
       AND (before_reviewed_at IS NULL
            OR (decision.created_at, identity_case.id) < (before_reviewed_at, before_evidence_id))
     ORDER BY decision.created_at DESC, identity_case.id DESC
     LIMIT requested_limit;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security TO kokonut_stakeholder_trust_reader;
ALTER FUNCTION kokonut_security.list_location_party_identity_trust_evidence(
    UUID, UUID, INTEGER, TIMESTAMPTZ, UUID
) OWNER TO kokonut_stakeholder_trust_reader;
REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_stakeholder_trust_reader;
REVOKE ALL ON FUNCTION kokonut_security.list_location_party_identity_trust_evidence(
    UUID, UUID, INTEGER, TIMESTAMPTZ, UUID
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_party_identity_trust_evidence(
            UUID, UUID, INTEGER, TIMESTAMPTZ, UUID
        ) TO kokonut_runtime;
        REVOKE ALL ON TABLE public.party_location_identity_case,
            public.party_location_identity_decision FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.party_location_identity_case,
            public.party_location_identity_decision FROM kokonut_directus_runtime;
        REVOKE ALL ON FUNCTION kokonut_security.list_location_party_identity_trust_evidence(
            UUID, UUID, INTEGER, TIMESTAMPTZ, UUID
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.list_location_party_identity_trust_evidence(
    UUID, UUID, INTEGER, TIMESTAMPTZ, UUID
) IS
    'Returns only bounded, independently approved location identity evidence while the source consent is current; exposes no profile identifiers, names, feedback, free text, or global trust score.';

COMMIT;
