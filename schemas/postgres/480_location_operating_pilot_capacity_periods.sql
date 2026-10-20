-- Bounded, redacted location-scoped capacity periods.

BEGIN;

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_capacity_periods(
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
    capacity_page JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Operating capacity read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Operating capacity read requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Operating capacity page is outside its bounds'
            USING ERRCODE = '22023';
    END IF;

    WITH active_scope AS (
        SELECT scope.scope_id
          FROM public.operating_pilot_scope AS scope
          JOIN public.farm AS pilot_farm
            ON pilot_farm.id = scope.scope_id
           AND pilot_farm.location_id = requested_location_id
           AND pilot_farm.status = 'active'
         WHERE scope.scope_type = 'adelphi'
           AND scope.status = 'active'
    ), period_totals AS (
        SELECT profile.period_start,
               profile.period_end,
               count(DISTINCT profile.party_id)::BIGINT AS participant_count,
               sum(profile.available_hours) AS available_hours,
               sum(profile.committed_hours) AS committed_hours,
               sum(profile.protected_hours) AS protected_hours
          FROM public.operating_capacity_profile AS profile
         WHERE profile.scope_type = 'adelphi'
           AND profile.scope_id IN (SELECT active_scope.scope_id FROM active_scope)
           AND profile.status IN ('submitted', 'approved')
           AND EXISTS (SELECT 1 FROM active_scope)
         GROUP BY profile.period_start, profile.period_end
    ), page_rows AS (
        SELECT *
          FROM period_totals
         ORDER BY period_start, period_end
         OFFSET requested_offset
         LIMIT requested_limit + 1
    ), numbered_page AS (
        SELECT row_number() OVER (ORDER BY period_start, period_end)::INTEGER AS page_sequence,
               period_start,
               period_end,
               participant_count,
               available_hours,
               committed_hours,
               protected_hours
          FROM page_rows
    )
    SELECT jsonb_build_object(
        'scope_configured', EXISTS (SELECT 1 FROM active_scope),
        'limit', requested_limit,
        'offset', requested_offset,
        'items', COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'period_start', page.period_start,
                    'period_end', page.period_end,
                    'suppressed', page.participant_count BETWEEN 1 AND 2,
                    'available_hours', CASE WHEN page.participant_count BETWEEN 1 AND 2
                        THEN NULL ELSE page.available_hours END,
                    'committed_hours', CASE WHEN page.participant_count BETWEEN 1 AND 2
                        THEN NULL ELSE page.committed_hours END,
                    'protected_hours', CASE WHEN page.participant_count BETWEEN 1 AND 2
                        THEN NULL ELSE page.protected_hours END
                ) ORDER BY page.page_sequence
            ) FILTER (WHERE page.page_sequence <= requested_limit),
            '[]'::JSONB
        ),
        'has_more', COALESCE(bool_or(page.page_sequence > requested_limit), FALSE),
        'next_offset', CASE
            WHEN COALESCE(bool_or(page.page_sequence > requested_limit), FALSE)
                THEN requested_offset + requested_limit
            ELSE NULL
        END
    )
      INTO capacity_page
      FROM numbered_page AS page;

    RETURN capacity_page;
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_capacity_periods(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_capacity_periods(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_capacity_periods(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_capacity_periods(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.location_operating_pilot_capacity_periods(
    UUID, INTEGER, INTEGER
) IS
'Returns bounded per-period capacity totals from submitted or approved Adelphi profiles for an active farm mapped to the requested location; hides hours when fewer than three distinct people contributed and excludes identities, notes, draft profiles, and internal scope.';

COMMIT;
