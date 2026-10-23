-- Create a private, self-reported competency assessment draft through the signed Gateway.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_pilot_competency_draft (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL,
    scope_id UUID NOT NULL,
    party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    competency_key VARCHAR(120) NOT NULL,
    current_level NUMERIC(4,2) NOT NULL CHECK (current_level BETWEEN 0 AND 5),
    target_level NUMERIC(4,2) NOT NULL CHECK (target_level BETWEEN current_level AND 5),
    evidence_note TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'superseded', 'submitted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (evidence_note IS NULL OR char_length(evidence_note) <= 2000)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_operating_pilot_competency_open_draft
    ON public.operating_pilot_competency_draft(operator_id, location_id, competency_key)
    WHERE status = 'draft';

CREATE TABLE IF NOT EXISTS public.operating_pilot_competency_draft_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    draft_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_pilot_competency_draft(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);
REVOKE ALL ON TABLE public.operating_pilot_competency_draft,
    public.operating_pilot_competency_draft_receipt FROM PUBLIC;

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
GRANT SELECT (id, operator_id, location_id, competency_key, status)
    ON TABLE public.operating_pilot_competency_draft
    TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, location_id, resource, action, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_operating_pilot_reader;
GRANT INSERT (operator_id, location_id, scope_id, party_id, competency_key,
              current_level, target_level, evidence_note)
    ON TABLE public.operating_pilot_competency_draft TO kokonut_operating_pilot_reader;
GRANT UPDATE (id) ON TABLE public.operator_governance_party_binding,
    public.operator_identity, public.party, public.operating_pilot_scope, public.farm
    TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, request_id, location_id, draft_id, input_digest),
      INSERT (operator_id, request_id, location_id, draft_id, input_digest)
    ON TABLE public.operating_pilot_competency_draft_receipt
    TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_operating_pilot_reader;

CREATE OR REPLACE FUNCTION kokonut_security.create_location_operating_pilot_competency_draft(
    requested_location_id UUID,
    requested_request_id UUID,
    requested_competency_key TEXT,
    requested_current_level NUMERIC,
    requested_target_level NUMERIC,
    requested_evidence_note TEXT
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
    normalized_key TEXT;
    normalized_note TEXT;
    input_digest BYTEA;
    existing_receipt public.operating_pilot_competency_draft_receipt%ROWTYPE;
    existing_status TEXT;
    competency_draft_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Competency draft requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'create', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Competency draft requires an active exact location create grant'
            USING ERRCODE = '42501';
    END IF;

    normalized_key := pg_catalog.lower(pg_catalog.btrim(requested_competency_key));
    normalized_note := NULLIF(pg_catalog.btrim(requested_evidence_note), '');
    IF requested_competency_key IS NULL
       OR normalized_key IS NULL
       OR normalized_key !~ '^[a-z][a-z0-9_.-]{0,119}$'
       OR requested_current_level IS NULL
       OR requested_current_level NOT BETWEEN 0 AND 5
       OR pg_catalog.scale(requested_current_level) > 2
       OR requested_target_level IS NULL
       OR requested_target_level NOT BETWEEN requested_current_level AND 5
       OR pg_catalog.scale(requested_target_level) > 2
       OR requested_evidence_note IS NOT NULL
          AND pg_catalog.char_length(requested_evidence_note) > 2000 THEN
        RAISE EXCEPTION 'Competency draft input is invalid or outside its bounds'
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
        RAISE EXCEPTION 'Competency draft requires an active human party binding'
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
        RAISE EXCEPTION 'Competency draft requires one unambiguous active human party binding'
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
            'competency_key', normalized_key,
            'current_level', requested_current_level,
            'target_level', requested_target_level,
            'evidence_note', normalized_note
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
      FROM public.operating_pilot_competency_draft_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Competency draft request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT draft.status INTO existing_status
          FROM public.operating_pilot_competency_draft AS draft
         WHERE draft.id = existing_receipt.draft_id;
        IF existing_status IS NULL THEN
            RAISE EXCEPTION 'Competency draft receipt lost its draft';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'draft_id', existing_receipt.draft_id,
            'status', existing_status,
            'replayed', TRUE
        );
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.operating_pilot_competency_draft AS draft
         WHERE draft.operator_id = context_record.actor_id
           AND draft.location_id = requested_location_id
           AND draft.competency_key = normalized_key
           AND draft.status = 'draft'
    ) THEN
        RAISE EXCEPTION 'An open competency draft already exists for this competency'
            USING ERRCODE = '23505';
    END IF;

    INSERT INTO public.operating_pilot_competency_draft (
        operator_id, location_id, scope_id, party_id, competency_key,
        current_level, target_level, evidence_note
    ) VALUES (
        context_record.actor_id, requested_location_id, pilot_scope_id, actor_party_id,
        normalized_key, requested_current_level, requested_target_level, normalized_note
    ) RETURNING id INTO competency_draft_id;

    INSERT INTO public.operating_pilot_competency_draft_receipt (
        operator_id, request_id, location_id, draft_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        competency_draft_id, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'draft_id', competency_draft_id,
        'status', 'draft',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_operating_pilot_competency_draft(
    UUID, UUID, TEXT, NUMERIC, NUMERIC, TEXT
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.create_location_operating_pilot_competency_draft(
    UUID, UUID, TEXT, NUMERIC, NUMERIC, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.create_location_operating_pilot_competency_draft(
    UUID, UUID, TEXT, NUMERIC, NUMERIC, TEXT
) TO kokonut_runtime;

REVOKE ALL ON TABLE public.operating_pilot_competency_draft,
    public.operating_pilot_competency_draft_receipt FROM kokonut_runtime, kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.create_location_operating_pilot_competency_draft(
    UUID, UUID, TEXT, NUMERIC, NUMERIC, TEXT
) IS 'Creates an exact-location self-reported competency draft; does not update canonical competency profiles or verify evidence.';

COMMIT;
