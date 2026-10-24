-- Create a draft adoption program only for a solution owned by the exact location.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_adoption_program_creator'
    ) THEN
        CREATE ROLE kokonut_solution_adoption_program_creator
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_solution_adoption_program_creator'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'Adoption program creator role has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_solution_adoption_program_creator'
            OR member_role.rolname = 'kokonut_solution_adoption_program_creator'
    ) THEN
        RAISE EXCEPTION 'Adoption program creator role must not have memberships';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.solution_adoption_program_creation_receipt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    actor_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    solution_id UUID NOT NULL REFERENCES public.solution(id) ON DELETE RESTRICT,
    program_id UUID NOT NULL UNIQUE
        REFERENCES public.solution_adoption_program(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    payload_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(payload_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (operator_id, request_id)
);

ALTER TABLE public.solution_adoption_program_creation_receipt
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_adoption_program_creation_receipt
    FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS solution_adoption_program_creator_receipt
    ON public.solution_adoption_program_creation_receipt;
CREATE POLICY solution_adoption_program_creator_receipt
    ON public.solution_adoption_program_creation_receipt
    TO kokonut_solution_adoption_program_creator
    USING (CURRENT_USER = 'kokonut_solution_adoption_program_creator')
    WITH CHECK (CURRENT_USER = 'kokonut_solution_adoption_program_creator');

REVOKE ALL ON TABLE public.solution_adoption_program_creation_receipt FROM PUBLIC;
DO $$
DECLARE target_role TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY[
        'kokonut_runtime', 'kokonut_directus_runtime',
        'kokonut_solution_adoption_program_creator'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE public.solution_adoption_program_creation_receipt FROM %I',
                target_role
            );
        END IF;
    END LOOP;
END;
$$;

-- Runtime and Directus may read adoption summaries, but writes now require the
-- signed location-scoped function below.
DO $$
DECLARE target_role TEXT; target_column TEXT;
BEGIN
    FOREACH target_role IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
            EXECUTE pg_catalog.format(
                'REVOKE INSERT, UPDATE, DELETE ON TABLE public.solution_adoption_program FROM %I',
                target_role
            );
            FOR target_column IN
                SELECT attname
                  FROM pg_catalog.pg_attribute
                 WHERE attrelid = 'public.solution_adoption_program'::regclass
                   AND attnum > 0 AND NOT attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%I), UPDATE (%I) ON TABLE public.solution_adoption_program FROM %I',
                    target_column, target_column, target_role
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

REVOKE ALL ON SCHEMA public, kokonut_security
    FROM kokonut_solution_adoption_program_creator;
REVOKE ALL ON ALL TABLES IN SCHEMA public
    FROM kokonut_solution_adoption_program_creator;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public
    FROM kokonut_solution_adoption_program_creator;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public
    FROM kokonut_solution_adoption_program_creator;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kokonut_security
    FROM kokonut_solution_adoption_program_creator;
GRANT USAGE ON SCHEMA public, kokonut_security
    TO kokonut_solution_adoption_program_creator;

GRANT SELECT (id, originating_scope_type, originating_scope_id, current_stage, status)
    ON TABLE public.solution TO kokonut_solution_adoption_program_creator;
GRANT UPDATE (id) ON TABLE public.solution
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_solution_adoption_program_creator;
GRANT UPDATE (id) ON TABLE public.operator_identity
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_solution_adoption_program_creator;
GRANT UPDATE (id) ON TABLE public.party
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_adoption_program_creator;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (id, organization_id) ON TABLE public.location
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (id, status) ON TABLE public.organization
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (location_id, organization_id, revoked_at, expires_at)
    ON TABLE public.location_organization_share
    TO kokonut_solution_adoption_program_creator;
GRANT INSERT (
    solution_id, target_scope_type, target_scope_id, target_population,
    adoption_pathway, local_adaptation_policy, status, created_by_party_id
) ON TABLE public.solution_adoption_program
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (id, solution_id, target_scope_type, target_scope_id, status, created_at)
    ON TABLE public.solution_adoption_program
    TO kokonut_solution_adoption_program_creator;
GRANT SELECT (
    operator_id, actor_party_id, location_id, solution_id, program_id,
    request_id, payload_digest, created_at
) ON TABLE public.solution_adoption_program_creation_receipt
    TO kokonut_solution_adoption_program_creator;
GRANT INSERT (
    operator_id, actor_party_id, location_id, solution_id, program_id,
    request_id, payload_digest, created_at
) ON TABLE public.solution_adoption_program_creation_receipt
    TO kokonut_solution_adoption_program_creator;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_solution_adoption_program_creator;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_solution_adoption_program_creator;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_solution_adoption_program_creator;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_solution_adoption_program(
    requested_location_id UUID,
    requested_solution_id UUID,
    requested_request_id UUID,
    requested_adoption_pathway TEXT,
    requested_local_adaptation_policy TEXT,
    requested_acknowledged BOOLEAN
)
RETURNS TABLE (
    program_id UUID,
    solution_id UUID,
    program_status TEXT,
    created_at TIMESTAMPTZ,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    solution_record RECORD;
    prior_receipt RECORD;
    payload_digest BYTEA;
    created_time TIMESTAMPTZ;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Adoption program creation requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'solution_lifecycle', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Adoption program creation requires an active exact location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_solution_id IS NULL
       OR requested_request_id IS NULL
       OR requested_adoption_pathway IS NULL
       OR pg_catalog.length(pg_catalog.btrim(requested_adoption_pathway)) NOT BETWEEN 1 AND 2000
       OR pg_catalog.octet_length(pg_catalog.convert_to(requested_adoption_pathway, 'UTF8')) > 4000
       OR requested_local_adaptation_policy IS NOT NULL
          AND (pg_catalog.length(requested_local_adaptation_policy) > 4000
               OR pg_catalog.octet_length(pg_catalog.convert_to(requested_local_adaptation_policy, 'UTF8')) > 8000)
       OR requested_acknowledged IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Adoption program draft input is invalid'
            USING ERRCODE = '22023';
    END IF;

    SELECT binding.party_id
      INTO actor_party_id
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id
       AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL
     FOR KEY SHARE OF binding, operator, actor;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Adoption program creation requires an active human identity'
            USING ERRCODE = '42501';
    END IF;

    SELECT solution.id, solution.current_stage, solution.status
      INTO solution_record
      FROM public.solution AS solution
     WHERE solution.id = requested_solution_id
       AND solution.originating_scope_type = 'location'
       AND solution.originating_scope_id = requested_location_id
       AND solution.current_stage IN ('adoption_ready', 'adopting')
       AND solution.status = 'active'
     FOR UPDATE;
    IF solution_record.id IS NULL THEN
        RAISE EXCEPTION 'Adoption program requires an active adoption-ready solution at this location'
            USING ERRCODE = '55000';
    END IF;

    payload_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_object(
                'location_id', requested_location_id,
                'solution_id', requested_solution_id,
                'adoption_pathway', pg_catalog.btrim(requested_adoption_pathway),
                'local_adaptation_policy', NULLIF(pg_catalog.btrim(requested_local_adaptation_policy), ''),
                'target_scope_type', 'location',
                'target_scope_id', requested_location_id,
                'target_population', '{}'::JSONB,
                'acknowledged', requested_acknowledged
            )::TEXT,
            'UTF8'
        ),
        'sha256'
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.actor_party_id, receipt.location_id, receipt.solution_id,
           receipt.program_id, receipt.payload_digest, receipt.created_at
      INTO prior_receipt
      FROM public.solution_adoption_program_creation_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF prior_receipt.actor_party_id IS DISTINCT FROM actor_party_id
           OR prior_receipt.location_id IS DISTINCT FROM requested_location_id
           OR prior_receipt.solution_id IS DISTINCT FROM requested_solution_id
           OR prior_receipt.payload_digest IS DISTINCT FROM payload_digest THEN
            RAISE EXCEPTION 'Adoption program request ID was reused with different input'
                USING ERRCODE = '22023';
        END IF;
        RETURN QUERY SELECT prior_receipt.program_id, prior_receipt.solution_id,
                            'draft'::TEXT, prior_receipt.created_at, TRUE;
        RETURN;
    END IF;

    INSERT INTO public.solution_adoption_program AS created_program (
        solution_id, target_scope_type, target_scope_id, target_population,
        adoption_pathway, local_adaptation_policy, status, created_by_party_id
    ) VALUES (
        requested_solution_id, 'location', requested_location_id, '{}'::JSONB,
        pg_catalog.btrim(requested_adoption_pathway),
        NULLIF(pg_catalog.btrim(requested_local_adaptation_policy), ''),
        'draft', actor_party_id
    ) RETURNING created_program.id, created_program.created_at
      INTO program_id, created_time;

    INSERT INTO public.solution_adoption_program_creation_receipt (
        operator_id, actor_party_id, location_id, solution_id, program_id,
        request_id, payload_digest, created_at
    ) VALUES (
        context_record.actor_id, actor_party_id, requested_location_id,
        requested_solution_id, program_id, requested_request_id,
        payload_digest, created_time
    );

    RETURN QUERY SELECT program_id, requested_solution_id, 'draft'::TEXT,
                        created_time, FALSE;
END;
$$;

GRANT CREATE ON SCHEMA kokonut_security
    TO kokonut_solution_adoption_program_creator;
ALTER FUNCTION kokonut_security.create_location_solution_adoption_program(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) OWNER TO kokonut_solution_adoption_program_creator;
REVOKE CREATE ON SCHEMA kokonut_security
    FROM kokonut_solution_adoption_program_creator;
REVOKE ALL ON FUNCTION kokonut_security.create_location_solution_adoption_program(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_solution_adoption_program(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_location_solution_adoption_program(
            UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_solution_adoption_program(
    UUID, UUID, UUID, TEXT, TEXT, BOOLEAN
) IS 'Creates an exact-location, human-attributed adoption program draft with immutable retry receipt; does not assess readiness, approve configuration, collect events, or launch adoption.';

COMMIT;
