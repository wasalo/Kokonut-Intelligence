-- Record private operating-pilot coaching only for a verified, consented
-- participant at the signed location. Direct table access remains unavailable.

BEGIN;

CREATE TABLE IF NOT EXISTS public.operating_pilot_coaching_session_receipt (
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    coach_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    coachee_party_id UUID NOT NULL REFERENCES public.party(id) ON DELETE RESTRICT,
    session_id UUID NOT NULL UNIQUE
        REFERENCES public.operating_coaching_session(id) ON DELETE RESTRICT,
    consent_event_id UUID NOT NULL REFERENCES public.stakeholder_consent(id) ON DELETE RESTRICT,
    input_digest BYTEA NOT NULL CHECK (pg_catalog.octet_length(input_digest) = 32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (operator_id, request_id)
);

DO $$
DECLARE role_name TEXT;
        column_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime',
        'kokonut_operating_pilot_reader'
    ] LOOP
        EXECUTE pg_catalog.format(
            'REVOKE ALL ON TABLE public.operating_pilot_coaching_session_receipt FROM %s',
            CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
        );
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid =
                   'public.operating_pilot_coaching_session_receipt'::REGCLASS
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE ALL (%1$I) ON TABLE public.operating_pilot_coaching_session_receipt FROM %2$s',
                column_name,
                CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
            );
        END LOOP;
    END LOOP;

    FOREACH role_name IN ARRAY ARRAY[
        'PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime',
        'kokonut_operating_pilot_reader'
    ] LOOP
        EXECUTE pg_catalog.format(
            'REVOKE ALL ON TABLE public.operating_coaching_session FROM %s',
            CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
        );
        FOR column_name IN
            SELECT attribute.attname
              FROM pg_catalog.pg_attribute AS attribute
             WHERE attribute.attrelid = 'public.operating_coaching_session'::REGCLASS
               AND attribute.attnum > 0
               AND NOT attribute.attisdropped
        LOOP
            EXECUTE pg_catalog.format(
                'REVOKE ALL (%1$I) ON TABLE public.operating_coaching_session FROM %2$s',
                column_name,
                CASE WHEN role_name = 'PUBLIC' THEN 'PUBLIC' ELSE pg_catalog.quote_ident(role_name) END
            );
        END LOOP;
    END LOOP;
END;
$$;

GRANT SELECT (
    coachee_party_id, scope_type, scope_id, privacy_level,
    id, coach_party_id, session_date, focus, commitments,
    wellbeing_check, notes, status, created_at
) ON TABLE public.operating_coaching_session TO kokonut_operating_pilot_reader;
GRANT INSERT (
    id, scope_type, scope_id, coachee_party_id, coach_party_id, session_date,
    focus, commitments, wellbeing_check, notes, privacy_level, status
) ON TABLE public.operating_coaching_session TO kokonut_operating_pilot_reader;
GRANT SELECT (
    operator_id, request_id, location_id, coach_party_id, coachee_party_id,
    session_id, consent_event_id, input_digest, created_at
) ON TABLE public.operating_pilot_coaching_session_receipt
    TO kokonut_operating_pilot_reader;
GRANT INSERT (
    operator_id, request_id, location_id, coach_party_id, coachee_party_id,
    session_id, consent_event_id, input_digest
) ON TABLE public.operating_pilot_coaching_session_receipt
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, enabled) ON TABLE public.operator_identity
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, operator_id, party_id, revoked_at)
    ON TABLE public.operator_governance_party_binding
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, party_type, status, display_name) ON TABLE public.party
    TO kokonut_operating_pilot_reader;
GRANT SELECT (operator_id, location_id, resource, action, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_operating_pilot_reader;
GRANT SELECT (id, scope_type, scope_id, status)
    ON TABLE public.operating_pilot_scope TO kokonut_operating_pilot_reader;
GRANT SELECT (id, location_id, status) ON TABLE public.farm
    TO kokonut_operating_pilot_reader;
GRANT SELECT (id, location_id, status) ON TABLE public.farmer_profile
    TO kokonut_operating_pilot_reader;
GRANT SELECT (party_id, identifier_type, identifier_value, verification_status)
    ON TABLE public.party_identifier TO kokonut_operating_pilot_reader;
GRANT SELECT (
    id, party_id, event_type, data_category, purpose, scope_type, scope_id,
    recipient_party_id, recipient_type, effective_at, expires_at, created_at
) ON TABLE public.stakeholder_consent TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
    TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)
    TO kokonut_operating_pilot_reader;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_operating_pilot_reader;

CREATE INDEX IF NOT EXISTS idx_operating_pilot_coaching_receipt_location_operator
    ON public.operating_pilot_coaching_session_receipt
       (location_id, operator_id, created_at DESC, session_id);

CREATE OR REPLACE FUNCTION kokonut_security.create_location_operating_pilot_coaching_session(
    requested_location_id UUID,
    requested_coachee_party_id UUID,
    requested_request_id UUID,
    requested_session_date DATE,
    requested_focus TEXT,
    requested_commitments JSONB,
    requested_wellbeing_check TEXT,
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
    coach_party_ids UUID[] := ARRAY[]::UUID[];
    coach_party_id UUID;
    pilot_scope_id UUID;
    consent_record RECORD;
    normalized_focus TEXT := NULLIF(pg_catalog.btrim(requested_focus), '');
    normalized_wellbeing TEXT := NULLIF(pg_catalog.btrim(requested_wellbeing_check), '');
    normalized_notes TEXT := NULLIF(pg_catalog.btrim(requested_notes), '');
    normalized_commitments JSONB := coalesce(requested_commitments, '[]'::JSONB);
    input_digest BYTEA;
    existing_receipt RECORD;
    session_id UUID;
    effective_session_date DATE := coalesce(requested_session_date, CURRENT_DATE);
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL
       OR requested_coachee_party_id IS NULL
       OR requested_request_id IS NULL THEN
        RAISE EXCEPTION 'Coaching capture requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'coach', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Coaching capture requires the exact location coaching grant'
            USING ERRCODE = '42501';
    END IF;
    IF pg_catalog.jsonb_typeof(normalized_commitments) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Coaching commitments must be an array'
            USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.jsonb_array_length(normalized_commitments) > 20 THEN
        RAISE EXCEPTION 'Coaching commitments exceed their item limit'
            USING ERRCODE = '22023';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.jsonb_array_elements(normalized_commitments) AS item(value)
         WHERE pg_catalog.jsonb_typeof(item.value) IS DISTINCT FROM 'string'
            OR pg_catalog.char_length(pg_catalog.btrim(item.value #>> '{}')) NOT BETWEEN 1 AND 500
            OR (item.value #>> '{}') ~ '[[:cntrl:]]'
    ) THEN
        RAISE EXCEPTION 'Coaching commitment text is invalid'
            USING ERRCODE = '22023';
    END IF;
    IF normalized_focus IS NULL OR pg_catalog.char_length(normalized_focus) > 255
       OR requested_focus ~ '[[:cntrl:]]'
       OR requested_wellbeing_check IS NOT NULL
          AND (pg_catalog.char_length(requested_wellbeing_check) > 1000
               OR requested_wellbeing_check ~ '[[:cntrl:]]')
       OR requested_notes IS NOT NULL
          AND (pg_catalog.char_length(requested_notes) > 4000
               OR requested_notes ~ '[[:cntrl:]]')
       OR effective_session_date > CURRENT_DATE
       OR effective_session_date < CURRENT_DATE - 366 THEN
        RAISE EXCEPTION 'Coaching session input is invalid or outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    FOR binding_record IN
        SELECT binding.party_id
          FROM public.operator_governance_party_binding AS binding
          JOIN public.operator_identity AS operator
            ON operator.id = binding.operator_id AND operator.enabled
          JOIN public.party AS coach
            ON coach.id = binding.party_id
           AND coach.party_type = 'person'
           AND coach.status = 'active'
         WHERE binding.operator_id = context_record.actor_id
           AND binding.revoked_at IS NULL
         FOR SHARE OF binding, operator, coach
    LOOP
        coach_party_ids := pg_catalog.array_append(coach_party_ids, binding_record.party_id);
    END LOOP;
    IF pg_catalog.cardinality(coach_party_ids) <> 1 THEN
        RAISE EXCEPTION 'Coaching capture requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    coach_party_id := coach_party_ids[1];

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

    IF NOT EXISTS (
        SELECT 1
          FROM public.farmer_profile AS farmer
          JOIN public.party_identifier AS identity_link
            ON identity_link.identifier_type = 'farmer_profile_id'
           AND identity_link.identifier_value = farmer.id::TEXT
           AND identity_link.party_id = requested_coachee_party_id
           AND identity_link.verification_status = 'verified'
          JOIN public.party AS coachee
            ON coachee.id = identity_link.party_id
           AND coachee.party_type = 'person'
           AND coachee.status = 'active'
         WHERE farmer.location_id = requested_location_id
           AND farmer.status = 'active'
    ) THEN
        RAISE EXCEPTION 'Coachee must be a verified active participant at this location'
            USING ERRCODE = '42501';
    END IF;

    SELECT consent.id, consent.event_type, consent.expires_at, consent.effective_at
      INTO consent_record
      FROM public.stakeholder_consent AS consent
     WHERE consent.party_id = requested_coachee_party_id
       AND consent.data_category = 'coaching_session'
       AND consent.purpose = 'operating_pilot_coaching'
       AND consent.scope_type = 'location'
       AND consent.scope_id = requested_location_id
       AND consent.recipient_party_id IS NULL
       AND consent.recipient_type = 'system'
       AND consent.effective_at <= pg_catalog.clock_timestamp()
     ORDER BY consent.effective_at DESC, consent.created_at DESC, consent.id DESC
     LIMIT 1;
    IF consent_record.id IS NULL
       OR consent_record.event_type IS DISTINCT FROM 'grant'
       OR consent_record.expires_at IS NOT NULL
          AND consent_record.expires_at <= pg_catalog.clock_timestamp() THEN
        RAISE EXCEPTION 'Current participant consent for private coaching is required'
            USING ERRCODE = '42501';
    END IF;

    input_digest := public.digest(
        pg_catalog.convert_to(
            pg_catalog.jsonb_build_array(
                requested_location_id::TEXT,
                requested_coachee_party_id::TEXT,
                requested_session_date,
                normalized_focus,
                normalized_commitments,
                normalized_wellbeing,
                normalized_notes
            )::TEXT,
            'UTF8'
        ),
        'sha256'::TEXT
    );
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            context_record.actor_id::TEXT || ':' || requested_request_id::TEXT, 0
        )
    );
    SELECT receipt.session_id, receipt.input_digest, session.session_date
      INTO existing_receipt
      FROM public.operating_pilot_coaching_session_receipt AS receipt
      JOIN public.operating_coaching_session AS session
        ON session.id = receipt.session_id
     WHERE receipt.operator_id = context_record.actor_id
       AND receipt.request_id = requested_request_id;
    IF FOUND THEN
        IF existing_receipt.input_digest IS DISTINCT FROM input_digest THEN
            RAISE EXCEPTION 'Coaching request ID was reused with different input'
                USING ERRCODE = '23505';
        END IF;
        RETURN pg_catalog.jsonb_build_object(
            'session_id', existing_receipt.session_id,
            'status', 'completed',
            'privacy_level', 'private',
            'session_date', existing_receipt.session_date,
            'replayed', TRUE
        );
    END IF;

    session_id := pg_catalog.gen_random_uuid();
    INSERT INTO public.operating_coaching_session (
        id, scope_type, scope_id, coachee_party_id, coach_party_id,
        session_date, focus, commitments, wellbeing_check, notes,
        privacy_level, status
    ) VALUES (
        session_id, 'adelphi', pilot_scope_id, requested_coachee_party_id,
        coach_party_id, effective_session_date, normalized_focus,
        normalized_commitments, normalized_wellbeing, normalized_notes,
        'private', 'completed'
    );
    INSERT INTO public.operating_pilot_coaching_session_receipt (
        operator_id, request_id, location_id, coach_party_id, coachee_party_id,
        session_id, consent_event_id, input_digest
    ) VALUES (
        context_record.actor_id, requested_request_id, requested_location_id,
        coach_party_id, requested_coachee_party_id, session_id,
        consent_record.id, input_digest
    );
    RETURN pg_catalog.jsonb_build_object(
        'session_id', session_id,
        'status', 'completed',
        'privacy_level', 'private',
        'session_date', effective_session_date,
        'replayed', FALSE
    );
END;
$$;

ALTER FUNCTION kokonut_security.create_location_operating_pilot_coaching_session(
    UUID, UUID, UUID, DATE, TEXT, JSONB, TEXT, TEXT
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.create_location_operating_pilot_coaching_session(
    UUID, UUID, UUID, DATE, TEXT, JSONB, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.create_location_operating_pilot_coaching_session(
    UUID, UUID, UUID, DATE, TEXT, JSONB, TEXT, TEXT
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.create_location_operating_pilot_coaching_session(
    UUID, UUID, UUID, DATE, TEXT, JSONB, TEXT, TEXT
) FROM kokonut_directus_runtime;

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_own_coaching_sessions(
    requested_location_id UUID,
    requested_limit INTEGER,
    requested_offset INTEGER
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    context_record RECORD;
    coach_party_ids UUID[];
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Coaching history requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'coach', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Coaching history requires the exact location coaching grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Coaching history page is outside its bounds'
            USING ERRCODE = '22023';
    END IF;
    SELECT pg_catalog.array_agg(binding.party_id ORDER BY binding.party_id)
      INTO coach_party_ids
      FROM public.operator_governance_party_binding AS binding
      JOIN public.operator_identity AS operator
        ON operator.id = binding.operator_id AND operator.enabled
      JOIN public.party AS coach
        ON coach.id = binding.party_id
       AND coach.party_type = 'person'
       AND coach.status = 'active'
     WHERE binding.operator_id = context_record.actor_id
       AND binding.revoked_at IS NULL;
    IF coalesce(pg_catalog.cardinality(coach_party_ids), 0) <> 1 THEN
        RAISE EXCEPTION 'Coaching history requires exactly one active human-party binding'
            USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM public.operating_pilot_scope AS scope
          JOIN public.farm AS pilot_farm
            ON pilot_farm.id = scope.scope_id
           AND pilot_farm.location_id = requested_location_id
           AND pilot_farm.status = 'active'
         WHERE scope.scope_type = 'adelphi'
           AND scope.status = 'active'
    ) THEN
        RAISE EXCEPTION 'No active operating-pilot scope is mapped to this location'
            USING ERRCODE = 'P0002';
    END IF;

    WITH current_consent AS MATERIALIZED (
        SELECT DISTINCT ON (consent.party_id) consent.party_id, consent.event_type,
               consent.expires_at
          FROM public.stakeholder_consent AS consent
         WHERE consent.data_category = 'coaching_session'
           AND consent.purpose = 'operating_pilot_coaching'
           AND consent.scope_type = 'location'
           AND consent.scope_id = requested_location_id
           AND consent.recipient_party_id IS NULL
           AND consent.recipient_type = 'system'
           AND consent.effective_at <= pg_catalog.clock_timestamp()
         ORDER BY consent.party_id, consent.effective_at DESC,
                  consent.created_at DESC, consent.id DESC
    ), eligible AS MATERIALIZED (
        SELECT receipt.session_id, session.coachee_party_id, session.session_date,
               session.focus, session.commitments, session.wellbeing_check,
               session.notes, session.status, receipt.created_at
          FROM public.operating_pilot_coaching_session_receipt AS receipt
          JOIN public.operating_coaching_session AS session
            ON session.id = receipt.session_id
          JOIN public.party AS coachee
            ON coachee.id = receipt.coachee_party_id
           AND coachee.party_type = 'person'
           AND coachee.status = 'active'
          JOIN current_consent AS consent
            ON consent.party_id = receipt.coachee_party_id
           AND consent.event_type = 'grant'
           AND (consent.expires_at IS NULL OR consent.expires_at > pg_catalog.clock_timestamp())
         WHERE receipt.operator_id = context_record.actor_id
           AND receipt.location_id = requested_location_id
           AND receipt.coach_party_id = coach_party_ids[1]
           AND session.scope_type = 'adelphi'
           AND session.privacy_level = 'private'
           AND EXISTS (
               SELECT 1
                 FROM public.operating_pilot_scope AS scope
                 JOIN public.farm AS pilot_farm
                   ON pilot_farm.id = scope.scope_id
                  AND pilot_farm.location_id = requested_location_id
                  AND pilot_farm.status = 'active'
                WHERE scope.scope_type = 'adelphi'
                  AND scope.status = 'active'
                  AND scope.scope_id = session.scope_id
           )
    ), selected AS (
        SELECT * FROM eligible
         ORDER BY session_date DESC, session_id DESC
         LIMIT requested_limit + 1 OFFSET requested_offset
    ), page AS (
        SELECT selected.*,
               pg_catalog.row_number() OVER (ORDER BY session_date DESC, session_id DESC) AS page_row
          FROM selected
    ), page_result AS (
        SELECT coalesce(
                   pg_catalog.jsonb_agg(
                       pg_catalog.jsonb_build_object(
                           'session_id', page.session_id,
                           'coachee_name', coachee.display_name,
                           'session_date', page.session_date,
                           'focus', page.focus,
                           'commitments', page.commitments,
                           'wellbeing_check', page.wellbeing_check,
                           'notes', page.notes,
                           'status', page.status,
                           'created_at', page.created_at
                       ) ORDER BY page.page_row
                   ) FILTER (WHERE page.page_row <= requested_limit),
                   '[]'::JSONB
               ) AS items,
               count(*) > requested_limit AS has_more
          FROM page
          JOIN public.party AS coachee ON coachee.id = page.coachee_party_id
    )
    SELECT pg_catalog.jsonb_build_object(
               'items', page_result.items,
               'limit', requested_limit,
               'offset', requested_offset,
               'has_more', page_result.has_more,
               'next_offset', CASE
                   WHEN page_result.has_more THEN requested_offset + requested_limit
                   ELSE NULL
               END
           )
      INTO result
      FROM page_result;
    RETURN result;
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_own_coaching_sessions(
    UUID, INTEGER, INTEGER
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_own_coaching_sessions(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_own_coaching_sessions(
    UUID, INTEGER, INTEGER
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_own_coaching_sessions(
    UUID, INTEGER, INTEGER
) FROM kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.create_location_operating_pilot_coaching_session(
    UUID, UUID, UUID, DATE, TEXT, JSONB, TEXT, TEXT
) IS 'Creates one completed private session under signed location coaching scope for a verified active participant with current purpose-specific consent; private content is visible only through the author own-history function while that consent remains active.';
COMMENT ON FUNCTION kokonut_security.location_operating_pilot_own_coaching_sessions(
    UUID, INTEGER, INTEGER
) IS 'Returns only the authenticated coach own receipt-backed private sessions with current participant consent for the exact mapped Adelphi location.';

COMMIT;
