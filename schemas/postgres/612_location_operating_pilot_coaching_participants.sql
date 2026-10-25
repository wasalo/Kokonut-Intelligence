-- Expose only active, location-linked participants with current coaching consent.
-- The function is callable by the Gateway under the same exact coach grant.

BEGIN;

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_coaching_participants(
    requested_location_id UUID,
    requested_search TEXT,
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
    search_value TEXT := NULLIF(pg_catalog.btrim(requested_search), '');
    result JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Coaching participant lookup requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'coach', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Coaching participant lookup requires the exact location coaching grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000
       OR requested_search IS NOT NULL
          AND (pg_catalog.char_length(requested_search) > 80
               OR requested_search ~ '[[:cntrl:]]') THEN
        RAISE EXCEPTION 'Coaching participant page is outside its bounds'
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
        RAISE EXCEPTION 'Coaching participant lookup requires exactly one active human-party binding'
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
        SELECT DISTINCT ON (consent.party_id)
               consent.party_id, consent.event_type, consent.expires_at
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
        SELECT DISTINCT participant.id, participant.display_name
          FROM public.farmer_profile AS farmer
          JOIN public.party_identifier AS identity_link
            ON identity_link.identifier_type = 'farmer_profile_id'
           AND identity_link.identifier_value = farmer.id::TEXT
           AND identity_link.verification_status = 'verified'
          JOIN public.party AS participant
            ON participant.id = identity_link.party_id
           AND participant.party_type = 'person'
           AND participant.status = 'active'
          JOIN current_consent AS consent
            ON consent.party_id = participant.id
           AND consent.event_type = 'grant'
           AND (consent.expires_at IS NULL
                OR consent.expires_at > pg_catalog.clock_timestamp())
         WHERE farmer.location_id = requested_location_id
           AND farmer.status = 'active'
           AND NULLIF(pg_catalog.btrim(participant.display_name), '') IS NOT NULL
           AND (search_value IS NULL OR pg_catalog.strpos(
               pg_catalog.lower(participant.display_name),
               pg_catalog.lower(search_value)
           ) > 0)
    ), selected AS MATERIALIZED (
        SELECT eligible.id, eligible.display_name
          FROM eligible
         ORDER BY pg_catalog.lower(eligible.display_name), eligible.id
         LIMIT requested_limit + 1 OFFSET requested_offset
    ), page AS (
        SELECT selected.*,
               pg_catalog.row_number() OVER (
                   ORDER BY pg_catalog.lower(selected.display_name), selected.id
               ) AS page_row
          FROM selected
    )
    SELECT pg_catalog.jsonb_build_object(
               'items', coalesce(
                   pg_catalog.jsonb_agg(
                       pg_catalog.jsonb_build_object(
                           'participant_id', page.id,
                           'display_name', page.display_name
                       ) ORDER BY page.page_row
                   ) FILTER (WHERE page.page_row <= requested_limit),
                   '[]'::JSONB
               ),
               'has_more', count(*) > requested_limit,
               'next_offset', CASE WHEN count(*) > requested_limit
                                   THEN requested_offset + requested_limit
                                   ELSE NULL END
           )
      INTO result
      FROM page;

    RETURN result;
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_coaching_participants(
    UUID, TEXT, INTEGER, INTEGER
) OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_coaching_participants(
    UUID, TEXT, INTEGER, INTEGER
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_coaching_participants(
    UUID, TEXT, INTEGER, INTEGER
) TO kokonut_runtime;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_coaching_participants(
    UUID, TEXT, INTEGER, INTEGER
) FROM kokonut_directus_runtime;

COMMENT ON FUNCTION kokonut_security.location_operating_pilot_coaching_participants(
    UUID, TEXT, INTEGER, INTEGER
) IS 'Returns only active verified person participants with current exact-location operating-pilot coaching consent to an operator holding the exact coach grant; returns only participant ID and display name for bounded selection.';

COMMIT;
