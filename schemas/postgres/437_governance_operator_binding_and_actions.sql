-- Explicitly bind OIDC operators to human governance parties, then expose only
-- tenant-scoped tension intake/submission through bounded Gateway functions.

BEGIN;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_governance_binding_owner',
        'kokonut_governance_identity_admin',
        'kokonut_governance_action_owner'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                'NOCREATEROLE NOREPLICATION NOBYPASSRLS',
                role_name
            );
        ELSIF EXISTS (
            SELECT 1 FROM pg_roles
             WHERE rolname = role_name
               AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                    OR rolreplication OR rolbypassrls OR rolinherit)
        ) THEN
            RAISE EXCEPTION 'governance role % has unsafe attributes', role_name;
        END IF;

        IF role_name <> 'kokonut_governance_identity_admin' AND EXISTS (
            SELECT 1
              FROM pg_auth_members AS membership
              JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
              JOIN pg_roles AS member_role ON member_role.oid = membership.member
             WHERE granted_role.rolname = role_name OR member_role.rolname = role_name
        ) THEN
            RAISE EXCEPTION 'governance owner/admin role % must not have role memberships', role_name;
        END IF;
    END LOOP;
END;
$$;

CREATE SCHEMA IF NOT EXISTS kokonut_security;
REVOKE CREATE ON SCHEMA kokonut_security FROM PUBLIC;
GRANT USAGE ON SCHEMA public, kokonut_security TO
    kokonut_governance_binding_owner,
    kokonut_governance_identity_admin,
    kokonut_governance_action_owner;
GRANT CREATE ON SCHEMA kokonut_security TO
    kokonut_governance_binding_owner,
    kokonut_governance_action_owner;

CREATE TABLE public.operator_governance_party_binding (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    bound_by TEXT NOT NULL CHECK (NULLIF(BTRIM(bound_by), '') IS NOT NULL AND CHAR_LENGTH(bound_by) <= 200),
    binding_reason TEXT NOT NULL CHECK (NULLIF(BTRIM(binding_reason), '') IS NOT NULL AND CHAR_LENGTH(binding_reason) <= 2000),
    provisioned_by_db_user TEXT NOT NULL DEFAULT SESSION_USER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    revoked_at TIMESTAMPTZ,
    revoked_by TEXT,
    revocation_reason TEXT,
    CHECK ((revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL)
        OR (revoked_at IS NOT NULL AND NULLIF(BTRIM(revoked_by), '') IS NOT NULL
            AND NULLIF(BTRIM(revocation_reason), '') IS NOT NULL))
);

CREATE UNIQUE INDEX uq_operator_governance_binding_active_operator
    ON public.operator_governance_party_binding(operator_id)
    WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX uq_operator_governance_binding_active_party
    ON public.operator_governance_party_binding(party_id)
    WHERE revoked_at IS NULL;
CREATE INDEX idx_operator_governance_binding_history
    ON public.operator_governance_party_binding(operator_id, created_at DESC);

REVOKE ALL ON TABLE public.operator_governance_party_binding FROM PUBLIC;
GRANT SELECT ON TABLE public.operator_governance_party_binding,
    public.operator_identity, public.party TO kokonut_governance_binding_owner;
GRANT UPDATE (id) ON TABLE public.operator_identity, public.party
    TO kokonut_governance_binding_owner;
GRANT INSERT ON TABLE public.operator_governance_party_binding
    TO kokonut_governance_binding_owner;
GRANT UPDATE (revoked_at, revoked_by, revocation_reason)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_governance_binding_owner;
GRANT SELECT ON TABLE public.operator_governance_party_binding
    TO kokonut_governance_action_owner;

CREATE OR REPLACE FUNCTION kokonut_security.bind_operator_governance_party(
    requested_operator_id UUID,
    requested_party_id UUID,
    requested_bound_by TEXT,
    requested_reason TEXT
)
RETURNS TABLE (
    binding_id UUID,
    operator_id UUID,
    party_id UUID,
    bound_by TEXT,
    binding_reason TEXT,
    provisioned_by_db_user TEXT,
    created_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    existing public.operator_governance_party_binding%ROWTYPE;
BEGIN
    IF NOT pg_catalog.pg_has_role(SESSION_USER, 'kokonut_governance_identity_admin', 'MEMBER')
       OR requested_operator_id IS NULL
       OR requested_party_id IS NULL
       OR requested_bound_by IS NULL
       OR NULLIF(BTRIM(requested_bound_by), '') IS NULL
       OR CHAR_LENGTH(requested_bound_by) > 200
       OR requested_reason IS NULL
       OR NULLIF(BTRIM(requested_reason), '') IS NULL
       OR CHAR_LENGTH(requested_reason) > 2000 THEN
        RAISE EXCEPTION 'governance identity binding is not authorized or has invalid arguments'
            USING ERRCODE = '42501';
    END IF;

    PERFORM identity.id
      FROM public.operator_identity AS identity
     WHERE identity.id = requested_operator_id AND identity.enabled = TRUE
     FOR SHARE OF identity;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'enabled operator identity was not found' USING ERRCODE = '22023';
    END IF;

    PERFORM human.id
      FROM public.party AS human
     WHERE human.id = requested_party_id
       AND human.party_type = 'person'
       AND human.status = 'active'
     FOR SHARE OF human;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'an active person party was not found' USING ERRCODE = '22023';
    END IF;

    SELECT binding.* INTO existing
      FROM public.operator_governance_party_binding AS binding
     WHERE binding.operator_id = requested_operator_id
       AND binding.revoked_at IS NULL
     FOR UPDATE OF binding;
    IF FOUND THEN
        IF existing.party_id IS DISTINCT FROM requested_party_id THEN
            RAISE EXCEPTION 'operator already has an active party binding; revoke it first'
                USING ERRCODE = '23505';
        END IF;
        binding_id := existing.id;
        operator_id := existing.operator_id;
        party_id := existing.party_id;
        bound_by := existing.bound_by;
        binding_reason := existing.binding_reason;
        provisioned_by_db_user := existing.provisioned_by_db_user;
        created_at := existing.created_at;
        revoked_at := existing.revoked_at;
        RETURN NEXT;
        RETURN;
    END IF;

    INSERT INTO public.operator_governance_party_binding AS binding (
        operator_id, party_id, bound_by, binding_reason
    ) VALUES (
        requested_operator_id, requested_party_id,
        BTRIM(requested_bound_by), BTRIM(requested_reason)
    )
    RETURNING binding.id, binding.operator_id, binding.party_id, binding.bound_by,
              binding.binding_reason, binding.provisioned_by_db_user,
              binding.created_at, binding.revoked_at
         INTO binding_id, operator_id, party_id, bound_by, binding_reason,
              provisioned_by_db_user, created_at, revoked_at;
    RETURN NEXT;
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'operator or person party already has an active binding; revoke it first'
        USING ERRCODE = '23505';
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.revoke_operator_governance_party_binding(
    requested_binding_id UUID,
    requested_revoked_by TEXT,
    requested_reason TEXT
)
RETURNS TABLE (
    binding_id UUID,
    operator_id UUID,
    party_id UUID,
    revoked_at TIMESTAMPTZ,
    revoked_by TEXT,
    revocation_reason TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF NOT pg_catalog.pg_has_role(SESSION_USER, 'kokonut_governance_identity_admin', 'MEMBER')
       OR requested_binding_id IS NULL
       OR requested_revoked_by IS NULL
       OR NULLIF(BTRIM(requested_revoked_by), '') IS NULL
       OR CHAR_LENGTH(requested_revoked_by) > 200
       OR requested_reason IS NULL
       OR NULLIF(BTRIM(requested_reason), '') IS NULL
       OR CHAR_LENGTH(requested_reason) > 2000 THEN
        RAISE EXCEPTION 'governance identity binding revocation is not authorized or has invalid arguments'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    UPDATE public.operator_governance_party_binding AS binding
       SET revoked_at = clock_timestamp(),
           revoked_by = BTRIM(requested_revoked_by),
           revocation_reason = BTRIM(requested_reason)
     WHERE binding.id = requested_binding_id
       AND binding.revoked_at IS NULL
    RETURNING binding.id, binding.operator_id, binding.party_id, binding.revoked_at,
              binding.revoked_by, binding.revocation_reason;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'active governance identity binding was not found'
            USING ERRCODE = '22023';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_operator_governance_party_bindings(
    requested_operator_id UUID DEFAULT NULL
)
RETURNS TABLE (
    binding_id UUID,
    operator_id UUID,
    issuer TEXT,
    subject TEXT,
    operator_display_name TEXT,
    party_id UUID,
    party_display_name TEXT,
    bound_by TEXT,
    binding_reason TEXT,
    provisioned_by_db_user TEXT,
    created_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by TEXT,
    revocation_reason TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF NOT pg_catalog.pg_has_role(SESSION_USER, 'kokonut_governance_identity_admin', 'MEMBER') THEN
        RAISE EXCEPTION 'governance identity binding listing is not authorized'
            USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT binding.id, binding.operator_id, identity.issuer, identity.subject,
           identity.display_name, binding.party_id, human.display_name,
           binding.bound_by, binding.binding_reason, binding.provisioned_by_db_user,
           binding.created_at, binding.revoked_at, binding.revoked_by,
           binding.revocation_reason
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS identity ON identity.id = binding.operator_id
      JOIN public.party AS human ON human.id = binding.party_id
     WHERE requested_operator_id IS NULL OR binding.operator_id = requested_operator_id
     ORDER BY binding.created_at, binding.id;
END;
$$;

ALTER FUNCTION kokonut_security.bind_operator_governance_party(UUID, UUID, TEXT, TEXT)
    OWNER TO kokonut_governance_binding_owner;
ALTER FUNCTION kokonut_security.revoke_operator_governance_party_binding(UUID, TEXT, TEXT)
    OWNER TO kokonut_governance_binding_owner;
ALTER FUNCTION kokonut_security.list_operator_governance_party_bindings(UUID)
    OWNER TO kokonut_governance_binding_owner;
REVOKE ALL ON FUNCTION kokonut_security.bind_operator_governance_party(UUID, UUID, TEXT, TEXT)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.revoke_operator_governance_party_binding(UUID, TEXT, TEXT)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.list_operator_governance_party_bindings(UUID)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.bind_operator_governance_party(UUID, UUID, TEXT, TEXT)
    TO kokonut_governance_identity_admin;
GRANT EXECUTE ON FUNCTION kokonut_security.revoke_operator_governance_party_binding(UUID, TEXT, TEXT)
    TO kokonut_governance_identity_admin;
GRANT EXECUTE ON FUNCTION kokonut_security.list_operator_governance_party_bindings(UUID)
    TO kokonut_governance_identity_admin;

GRANT SELECT ON TABLE
    public.operator_identity,
    public.operator_governance_party_binding,
    public.party,
    public.party,
    public.operator_scope_grant,
    public.operator_organization_membership,
    public.location_organization_share,
    public.location_tenant_owner_verification,
    public.organization,
    public.location
TO kokonut_governance_action_owner;
GRANT UPDATE (id) ON TABLE
    public.operator_governance_party_binding,
    public.party TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_governance_action_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_governance_action_owner;
GRANT SELECT ON TABLE public.governance_tension, public.governance_tension_event
    TO kokonut_governance_action_owner;
GRANT INSERT (
    tension_key, title, description, tension_type, severity, urgency,
    scope_type, scope_id, reported_by_party_id, status
) ON TABLE public.governance_tension TO kokonut_governance_action_owner;
GRANT UPDATE (status, updated_at) ON TABLE public.governance_tension
    TO kokonut_governance_action_owner;
GRANT INSERT ON TABLE public.governance_tension_event
    TO kokonut_governance_action_owner;

CREATE OR REPLACE FUNCTION kokonut_security.report_governance_tension(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_title TEXT,
    requested_description TEXT,
    requested_tension_type TEXT,
    requested_severity SMALLINT,
    requested_urgency SMALLINT
)
RETURNS TABLE (
    tension_id UUID,
    tension_key TEXT,
    title TEXT,
    description TEXT,
    tension_type TEXT,
    severity SMALLINT,
    urgency SMALLINT,
    status TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    reporter_party_id UUID;
    selected_tension RECORD;
    generated_key TEXT;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'governance tension report requires a signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_tension', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'governance tension creation requires an active tenant grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_title IS NULL OR NULLIF(BTRIM(requested_title), '') IS NULL
       OR CHAR_LENGTH(requested_title) > 255
       OR requested_description IS NULL OR NULLIF(BTRIM(requested_description), '') IS NULL
       OR CHAR_LENGTH(requested_description) > 10000
       OR requested_tension_type IS NULL
       OR requested_tension_type NOT IN (
           'unmet_interest', 'unclear_accountability', 'authority_gap',
           'authority_conflict', 'commitment_risk', 'representation_gap',
           'consent_gap', 'evidence_gap', 'harm_risk', 'policy_gap',
           'cross_circle_dependency', 'role_overload'
       )
       OR requested_severity IS NULL OR requested_severity NOT BETWEEN 1 AND 5
       OR requested_urgency IS NULL OR requested_urgency NOT BETWEEN 1 AND 5 THEN
        RAISE EXCEPTION 'governance tension report has invalid content'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id INTO reporter_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.party AS human
        ON human.id = binding.party_id
       AND human.party_type = 'person'
       AND human.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, human;
    IF reporter_party_id IS NULL THEN
        RAISE EXCEPTION 'operator has no active governance person binding'
            USING ERRCODE = '42501';
    END IF;

    generated_key := 'gateway:' || context_record.actor_id::TEXT || ':' || requested_request_id::TEXT;
    SELECT tension.id, tension.tension_key, tension.title, tension.description,
           tension.tension_type, tension.severity, tension.urgency,
           tension.status, tension.created_at, tension.scope_type, tension.scope_id,
           tension.reported_by_party_id
      INTO selected_tension
      FROM public.governance_tension AS tension
     WHERE tension.tension_key = generated_key
     FOR UPDATE OF tension;
    IF FOUND THEN
        IF selected_tension.scope_type IS DISTINCT FROM 'location'
           OR selected_tension.scope_id IS DISTINCT FROM requested_location_id
           OR selected_tension.reported_by_party_id IS DISTINCT FROM reporter_party_id
           OR selected_tension.title IS DISTINCT FROM BTRIM(requested_title)
           OR selected_tension.description IS DISTINCT FROM BTRIM(requested_description)
           OR selected_tension.tension_type IS DISTINCT FROM requested_tension_type
           OR selected_tension.severity IS DISTINCT FROM requested_severity
           OR selected_tension.urgency IS DISTINCT FROM requested_urgency THEN
            RAISE EXCEPTION 'governance tension request id was reused with different content'
                USING ERRCODE = '22023';
        END IF;
        tension_id := selected_tension.id;
        tension_key := selected_tension.tension_key;
        title := selected_tension.title;
        description := selected_tension.description;
        tension_type := selected_tension.tension_type;
        severity := selected_tension.severity;
        urgency := selected_tension.urgency;
        status := selected_tension.status;
        created_at := selected_tension.created_at;
        RETURN NEXT;
        RETURN;
    END IF;

    INSERT INTO public.governance_tension AS tension (
        tension_key, title, description, tension_type, severity, urgency,
        scope_type, scope_id, reported_by_party_id, status
    ) VALUES (
        generated_key, BTRIM(requested_title), BTRIM(requested_description),
        requested_tension_type, requested_severity, requested_urgency,
        'location', requested_location_id, reporter_party_id, 'draft'
    )
    ON CONFLICT ON CONSTRAINT governance_tension_tension_key_key DO NOTHING
    RETURNING tension.id, tension.tension_key, tension.title, tension.description,
              tension.tension_type, tension.severity, tension.urgency,
              tension.status, tension.created_at
         INTO selected_tension;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'governance tension request is concurrently being created; retry'
            USING ERRCODE = '40001';
    END IF;
    INSERT INTO public.governance_tension_event (
        tension_id, actor_party_id, to_status, action, note
    ) VALUES (
        selected_tension.id, reporter_party_id, 'draft', 'reported',
        'Reported through authenticated Gateway'
    );

    tension_id := selected_tension.id;
    tension_key := selected_tension.tension_key;
    title := selected_tension.title;
    description := selected_tension.description;
    tension_type := selected_tension.tension_type;
    severity := selected_tension.severity;
    urgency := selected_tension.urgency;
    status := selected_tension.status;
    created_at := selected_tension.created_at;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.submit_governance_tension(
    requested_location_id UUID,
    requested_tension_id UUID
)
RETURNS TABLE (
    tension_id UUID,
    tension_key TEXT,
    title TEXT,
    description TEXT,
    tension_type TEXT,
    severity SMALLINT,
    urgency SMALLINT,
    status TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    reporter_party_id UUID;
    selected_tension RECORD;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_tension_id IS NULL THEN
        RAISE EXCEPTION 'governance tension submission requires a signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'governance_tension', 'submit', requested_location_id
    ) THEN
        RAISE EXCEPTION 'governance tension submission requires an active tenant grant'
            USING ERRCODE = '42501';
    END IF;
    SELECT binding.party_id INTO reporter_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.party AS human
        ON human.id = binding.party_id
       AND human.party_type = 'person'
       AND human.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR SHARE OF binding, human;
    IF reporter_party_id IS NULL THEN
        RAISE EXCEPTION 'operator has no active governance person binding'
            USING ERRCODE = '42501';
    END IF;

    SELECT tension.id, tension.tension_key, tension.title, tension.description,
           tension.tension_type, tension.severity, tension.urgency, tension.status,
           tension.created_at, tension.scope_type, tension.scope_id,
           tension.reported_by_party_id
      INTO selected_tension
      FROM public.governance_tension AS tension
     WHERE tension.id = requested_tension_id
     FOR UPDATE OF tension;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'governance tension was not found for this location and reporter'
            USING ERRCODE = '42501';
    END IF;
    IF selected_tension.scope_type IS DISTINCT FROM 'location'
       OR selected_tension.scope_id IS DISTINCT FROM requested_location_id
       OR selected_tension.reported_by_party_id IS DISTINCT FROM reporter_party_id THEN
        RAISE EXCEPTION 'governance tension was not found for this location and reporter'
            USING ERRCODE = '42501';
    END IF;

    IF selected_tension.status = 'draft' THEN
        UPDATE public.governance_tension AS tension
           SET status = 'submitted', updated_at = clock_timestamp()
         WHERE tension.id = requested_tension_id;
        selected_tension.status := 'submitted';
        INSERT INTO public.governance_tension_event (
            tension_id, actor_party_id, from_status, to_status, action, note
        ) VALUES (
            requested_tension_id, reporter_party_id, 'draft', 'submitted',
            'submitted', 'Submitted through authenticated Gateway'
        );
    ELSIF selected_tension.status IS DISTINCT FROM 'submitted' THEN
        RAISE EXCEPTION 'governance tension can only be submitted from draft'
            USING ERRCODE = '55000';
    END IF;

    tension_id := selected_tension.id;
    tension_key := selected_tension.tension_key;
    title := selected_tension.title;
    description := selected_tension.description;
    tension_type := selected_tension.tension_type;
    severity := selected_tension.severity;
    urgency := selected_tension.urgency;
    status := selected_tension.status;
    created_at := selected_tension.created_at;
    RETURN NEXT;
END;
$$;

ALTER FUNCTION kokonut_security.report_governance_tension(UUID, UUID, TEXT, TEXT, TEXT, SMALLINT, SMALLINT)
    OWNER TO kokonut_governance_action_owner;
ALTER FUNCTION kokonut_security.submit_governance_tension(UUID, UUID)
    OWNER TO kokonut_governance_action_owner;
REVOKE ALL ON FUNCTION kokonut_security.report_governance_tension(UUID, UUID, TEXT, TEXT, TEXT, SMALLINT, SMALLINT)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.submit_governance_tension(UUID, UUID)
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.report_governance_tension(UUID, UUID, TEXT, TEXT, TEXT, SMALLINT, SMALLINT)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.submit_governance_tension(UUID, UUID)
            TO kokonut_runtime;
        REVOKE ALL ON TABLE public.operator_governance_party_binding FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON TABLE public.operator_governance_party_binding FROM kokonut_directus_runtime;
    END IF;
END;
$$;

REVOKE CREATE ON SCHEMA kokonut_security FROM
    kokonut_governance_binding_owner, kokonut_governance_action_owner;

COMMENT ON TABLE public.operator_governance_party_binding IS
    'Explicit, one-to-one and revocable administrator mapping between an OIDC operator and an active human governance party. Never inferred from email or display name.';
COMMENT ON FUNCTION kokonut_security.report_governance_tension(UUID, UUID, TEXT, TEXT, TEXT, SMALLINT, SMALLINT) IS
    'Creates or idempotently replays an attributed location-scoped tension draft under a signed operator tenant context; does not submit, verify, or publish it.';
COMMENT ON FUNCTION kokonut_security.submit_governance_tension(UUID, UUID) IS
    'Submits only the authenticated operator’s own location-scoped tension draft and appends the matching event atomically; never verifies or publishes.';

COMMIT;
