-- Revise only the caller's own unsubmitted capacity draft.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_capacity_draft_revision_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL,
    original_profile_id UUID NOT NULL
        REFERENCES public.operating_capacity_profile(id) ON DELETE RESTRICT,
    replacement_profile_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_capacity_profile(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (operator_id, request_id),
    CHECK (original_profile_id <> replacement_profile_id)
);
REVOKE ALL ON TABLE public.operating_capacity_draft_revision_receipt FROM PUBLIC;

GRANT SELECT (id, scope_type, scope_id, party_id, source, status,
              period_start, period_end)
    ON TABLE public.operating_capacity_profile
    TO kokonut_operating_pilot_reader;
GRANT UPDATE (status)
    ON TABLE public.operating_capacity_profile
    TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, request_id, location_id, original_profile_id,
              replacement_profile_id, input_digest)
    ON TABLE public.operating_capacity_draft_revision_receipt
    TO kokonut_operating_pilot_reader;
GRANT INSERT (operator_id, request_id, location_id, original_profile_id,
              replacement_profile_id, input_digest)
    ON TABLE public.operating_capacity_draft_revision_receipt
    TO kokonut_operating_pilot_reader;

-- Remove any stale reader update grants before granting only status mutation
-- for the function below. The runtime and Directus roles remain non-writers.
REVOKE UPDATE ON TABLE public.operating_capacity_profile
    FROM kokonut_operating_pilot_reader;
DO $$
DECLARE column_name TEXT;
        role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_operating_pilot_reader', 'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = 'public.operating_capacity_profile'::REGCLASS
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.operating_capacity_profile FROM %2$I',
                    column_name, role_name
                );
            END LOOP;
        END IF;
    END LOOP;
    GRANT UPDATE (status)
        ON TABLE public.operating_capacity_profile
        TO kokonut_operating_pilot_reader;

    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.operating_capacity_draft_revision_receipt FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.revise_location_operating_pilot_capacity_draft(
    requested_location_id UUID,
    requested_profile_id UUID,
    requested_request_id UUID,
    requested_period_start DATE,
    requested_period_end DATE,
    requested_available_hours NUMERIC,
    requested_committed_hours NUMERIC,
    requested_protected_hours NUMERIC,
    requested_notes TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    binding_record RECORD;
    active_party_ids UUID[] := ARRAY[]::UUID[];
    actor_party_id UUID;
    pilot_scope_id UUID;
    old_profile RECORD;
    existing_receipt RECORD;
    existing_status TEXT;
    input_digest BYTEA;
    replacement_profile_id UUID;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_profile_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Capacity revision requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'edit_own', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Capacity revision requires an active exact location edit-own grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_period_start IS NULL
       OR requested_period_end IS NULL
       OR requested_period_end < requested_period_start
       OR requested_period_end > requested_period_start + 366
       OR requested_available_hours IS NULL
       OR requested_available_hours < 0
       OR requested_available_hours > 100000
       OR pg_catalog.scale(requested_available_hours) > 2
       OR requested_committed_hours IS NULL
       OR requested_committed_hours < 0
       OR requested_committed_hours > 100000
       OR pg_catalog.scale(requested_committed_hours) > 2
       OR requested_protected_hours IS NULL
       OR requested_protected_hours < 0
       OR requested_protected_hours > 100000
       OR pg_catalog.scale(requested_protected_hours) > 2
       OR requested_committed_hours + requested_protected_hours > requested_available_hours
       OR requested_notes IS NOT NULL AND pg_catalog.char_length(requested_notes) > 2000 THEN
        RAISE EXCEPTION 'Capacity revision input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    FOR binding_record IN
        SELECT binding.party_id
          FROM public.operator_governance_party_binding AS binding
          JOIN public.operator_identity AS operator
            ON operator.id = binding.operator_id AND operator.enabled
          JOIN public.party AS actor
            ON actor.id = binding.party_id
           AND actor.party_type = 'person'
           AND actor.status = 'active'
         WHERE binding.operator_id = context_record.actor_id
           AND binding.revoked_at IS NULL
         FOR SHARE OF binding, operator, actor
    LOOP
        active_party_ids := pg_catalog.array_append(active_party_ids, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(active_party_ids) <> 1 THEN
        RAISE EXCEPTION 'Capacity revision requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    actor_party_id := active_party_ids[1];

    SELECT scope.scope_id
      INTO pilot_scope_id
      FROM public.operating_pilot_scope AS scope
      JOIN public.farm AS pilot_farm
        ON pilot_farm.id = scope.scope_id
       AND pilot_farm.location_id = requested_location_id
       AND pilot_farm.status = 'active'
     WHERE scope.scope_type = 'adelphi'
       AND scope.status = 'active'
     FOR KEY SHARE OF scope, pilot_farm;
    IF pilot_scope_id IS NULL THEN
        RAISE EXCEPTION 'No active operating-pilot scope is mapped to this location'
            USING ERRCODE = 'P0002';
    END IF;

    input_digest := pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.jsonb_build_object(
            'profile_id', requested_profile_id,
            'period_start', requested_period_start,
            'period_end', requested_period_end,
            'available_hours', requested_available_hours,
            'committed_hours', requested_committed_hours,
            'protected_hours', requested_protected_hours,
            'notes', NULLIF(pg_catalog.btrim(requested_notes), '')
        )::TEXT,
        'UTF8'
    ));

    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );

    SELECT receipt.location_id, receipt.original_profile_id,
           receipt.replacement_profile_id, receipt.input_digest
      INTO existing_receipt
      FROM public.operating_capacity_draft_revision_receipt AS receipt
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.location_id IS DISTINCT FROM requested_location_id
           OR existing_receipt.original_profile_id IS DISTINCT FROM requested_profile_id
           OR existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Capacity revision request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        SELECT profile.status
          INTO existing_status
          FROM public.operating_capacity_profile AS profile
         WHERE profile.id = existing_receipt.replacement_profile_id;
        IF existing_status IS NULL THEN
            RAISE EXCEPTION 'Capacity revision receipt lost its replacement profile';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'profile_id', existing_receipt.replacement_profile_id,
            'replaced_profile_id', existing_receipt.original_profile_id,
            'status', existing_status,
            'replayed', TRUE
        );
    END IF;

    SELECT profile.id, profile.scope_id, profile.period_start, profile.period_end,
           profile.available_hours, profile.committed_hours, profile.protected_hours,
           profile.notes
      INTO old_profile
      FROM public.operating_capacity_profile AS profile
     WHERE profile.id = requested_profile_id
       AND profile.scope_type = 'adelphi'
       AND profile.scope_id = pilot_scope_id
       AND profile.party_id = actor_party_id
       AND profile.source = 'self_reported'
       AND profile.status = 'draft'
     FOR UPDATE OF profile;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Capacity draft is unavailable or no longer editable'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM public.operating_capacity_profile AS profile
         WHERE profile.scope_type = 'adelphi'
           AND profile.scope_id = pilot_scope_id
           AND profile.party_id = actor_party_id
           AND profile.period_start = requested_period_start
           AND profile.period_end = requested_period_end
           AND profile.status <> 'superseded'
           AND profile.id <> old_profile.id
    ) THEN
        RAISE EXCEPTION 'A capacity profile already exists for this person and period'
            USING ERRCODE = '23505';
    END IF;

    UPDATE public.operating_capacity_profile
       SET status = 'superseded'
     WHERE id = old_profile.id AND status = 'draft';

    INSERT INTO public.operating_capacity_profile (
        scope_type, scope_id, party_id, period_start, period_end,
        available_hours, committed_hours, protected_hours, notes, source, status
    ) VALUES (
        'adelphi', pilot_scope_id, actor_party_id, requested_period_start,
        requested_period_end, requested_available_hours, requested_committed_hours,
        requested_protected_hours, NULLIF(pg_catalog.btrim(requested_notes), ''),
        'self_reported', 'draft'
    ) RETURNING id INTO replacement_profile_id;

    INSERT INTO public.operating_capacity_draft_revision_receipt (
        operator_id, request_id, location_id, original_profile_id,
        replacement_profile_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        old_profile.id, replacement_profile_id, input_digest
    );

    RETURN pg_catalog.jsonb_build_object(
        'profile_id', replacement_profile_id,
        'replaced_profile_id', old_profile.id,
        'status', 'draft',
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.revise_location_operating_pilot_capacity_draft(
    UUID, UUID, UUID, DATE, DATE, NUMERIC, NUMERIC, NUMERIC, TEXT
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.revise_location_operating_pilot_capacity_draft(
    UUID, UUID, UUID, DATE, DATE, NUMERIC, NUMERIC, NUMERIC, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.revise_location_operating_pilot_capacity_draft(
    UUID, UUID, UUID, DATE, DATE, NUMERIC, NUMERIC, NUMERIC, TEXT
) TO kokonut_runtime;

DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['kokonut_runtime', 'kokonut_directus_runtime'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.operating_capacity_draft_revision_receipt FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END;
$$;

COMMENT ON FUNCTION kokonut_security.revise_location_operating_pilot_capacity_draft(
    UUID, UUID, UUID, DATE, DATE, NUMERIC, NUMERIC, NUMERIC, TEXT
) IS
'Preserves the prior version as superseded and creates a replacement draft only for the authenticated operator own self-reported capacity record at the exact granted location; it cannot submit or review capacity.';
COMMENT ON TABLE public.operating_capacity_draft_revision_receipt IS
'Private idempotency and revision-link receipt for operator edits to own capacity drafts; excludes capacity values and notes.';

COMMIT;
