-- Create private, self-attributed resource-request drafts through the signed Gateway.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_resource_request_draft (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL,
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type = 'adelphi'),
    scope_id UUID NOT NULL,
    requested_by_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    resource_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    urgency VARCHAR(20) NOT NULL CHECK (urgency IN ('low', 'medium', 'high', 'critical')),
    requested_by DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'superseded', 'submitted')),
    submitted_request_id UUID REFERENCES public.operating_resource_request(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK ((status = 'submitted') = (submitted_request_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_operating_resource_request_draft_owner
    ON public.operating_resource_request_draft(operator_id, location_id, status, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS public.operating_resource_request_draft_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    draft_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_resource_request_draft(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
REVOKE ALL ON TABLE public.operating_resource_request_draft,
    public.operating_resource_request_draft_receipt FROM PUBLIC;

GRANT SELECT (id, operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding TO kokonut_operating_pilot_reader;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, party_type, status) ON TABLE public.party
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, scope_type, scope_id, status) ON TABLE public.operating_pilot_scope
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, location_id, status) ON TABLE public.farm
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id) ON TABLE public.operating_resource_request_draft
    TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, location_id, resource, action, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_operating_pilot_reader;
GRANT INSERT (operator_id, location_id, scope_type, scope_id, requested_by_party_id,
              resource_type, description, urgency, requested_by)
    ON TABLE public.operating_resource_request_draft TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, request_id, location_id, draft_id, input_digest),
      INSERT (operator_id, request_id, location_id, draft_id, input_digest)
    ON TABLE public.operating_resource_request_draft_receipt TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_operating_pilot_reader;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_operating_pilot_resource_draft(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_resource_type TEXT,
    requested_description TEXT,
    requested_urgency TEXT,
    requested_by DATE
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    actor_party_id UUID;
    active_binding_count INTEGER;
    pilot_scope_id UUID;
    input_digest BYTEA;
    existing_receipt public.operating_resource_request_draft_receipt%ROWTYPE;
    resource_draft_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Resource draft requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Resource draft requires an active exact location create grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_resource_type IS NULL
       OR requested_resource_type !~ '^[A-Za-z0-9][A-Za-z0-9 _./-]{0,49}$'
       OR requested_description IS NULL
       OR pg_catalog.char_length(pg_catalog.btrim(requested_description)) NOT BETWEEN 1 AND 2000
       OR requested_urgency IS NULL
       OR requested_urgency NOT IN ('low', 'medium', 'high', 'critical')
       OR requested_by IS NULL THEN
        RAISE EXCEPTION 'Resource draft input is invalid or outside its bounds'
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
     ORDER BY binding.id
     LIMIT 1
     FOR KEY SHARE OF binding, operator, actor;
    IF actor_party_id IS NULL THEN
        RAISE EXCEPTION 'Resource draft requires an active human party binding'
            USING ERRCODE = '42501';
    END IF;
    SELECT count(*)::INTEGER INTO active_binding_count
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS actor
        ON actor.id = binding.party_id
       AND actor.party_type = 'person'
       AND actor.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF active_binding_count <> 1 THEN
        RAISE EXCEPTION 'Resource draft requires one unambiguous active human party binding'
            USING ERRCODE = '42501';
    END IF;

    SELECT scope.scope_id
      INTO pilot_scope_id
      FROM public.operating_pilot_scope AS scope
      JOIN public.farm AS pilot_farm
        ON pilot_farm.id = scope.scope_id
       AND pilot_farm.location_id = requested_location_id
       AND pilot_farm.status = 'active'
     WHERE scope.scope_type = 'adelphi'
       AND scope.status = 'active'
     ORDER BY scope.id
     LIMIT 1
     FOR KEY SHARE OF scope, pilot_farm;
    IF pilot_scope_id IS NULL THEN
        RAISE EXCEPTION 'No active operating-pilot scope is mapped to this location'
            USING ERRCODE = 'P0002';
    END IF;

    input_digest := pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'resource_type', pg_catalog.btrim(requested_resource_type),
            'description', pg_catalog.btrim(requested_description),
            'urgency', requested_urgency,
            'requested_by', requested_by
        )::TEXT,
        'UTF8'
    ));
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT receipt.operator_id, receipt.request_id, receipt.location_id,
           receipt.draft_id, receipt.input_digest
      INTO existing_receipt
      FROM public.operating_resource_request_draft_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Resource draft request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'draft_id', existing_receipt.draft_id,
            'status', 'draft',
            'replayed', TRUE
        );
    END IF;

    INSERT INTO public.operating_resource_request_draft (
        operator_id, location_id, scope_type, scope_id, requested_by_party_id,
        resource_type, description, urgency, requested_by
    ) VALUES (
        context_record.actor_id, requested_location_id, 'adelphi', pilot_scope_id,
        actor_party_id, pg_catalog.btrim(requested_resource_type),
        pg_catalog.btrim(requested_description), requested_urgency, requested_by
    ) RETURNING id INTO resource_draft_id;

    INSERT INTO public.operating_resource_request_draft_receipt (
        operator_id, request_id, location_id, draft_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        resource_draft_id, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'draft_id', resource_draft_id,
        'status', 'draft',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_operating_pilot_resource_draft(
    UUID, UUID, TEXT, TEXT, TEXT, DATE
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.create_location_operating_pilot_resource_draft(
    UUID, UUID, TEXT, TEXT, TEXT, DATE
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.create_location_operating_pilot_resource_draft(
            UUID, UUID, TEXT, TEXT, TEXT, DATE
        ) TO kokonut_runtime;
        REVOKE ALL ON TABLE public.operating_resource_request_draft,
            public.operating_resource_request_draft_receipt FROM kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.create_location_operating_pilot_resource_draft(
            UUID, UUID, TEXT, TEXT, TEXT, DATE
        ) FROM kokonut_directus_runtime;
        REVOKE ALL ON TABLE public.operating_resource_request_draft,
            public.operating_resource_request_draft_receipt FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.create_location_operating_pilot_resource_draft(
    UUID, UUID, TEXT, TEXT, TEXT, DATE
) IS
'Creates an exact-location private resource-request draft for the authenticated operator party; it does not create a legacy submitted request or perform a lifecycle action.';
COMMENT ON TABLE public.operating_resource_request_draft IS
'Private Kernel drafts kept separate from submitted legacy resource requests until explicit submission.';
COMMENT ON TABLE public.operating_resource_request_draft_receipt IS
'Private idempotency receipts for authenticated resource-request draft creation.';

COMMIT;
