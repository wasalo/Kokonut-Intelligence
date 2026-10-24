-- Bounded, redacted location-scoped resource-request category totals.

BEGIN;

GRANT SELECT (resource_type)
    ON TABLE public.operating_resource_request TO kokonut_operating_pilot_reader;

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_resource_categories(
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
    category_page JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Operating resource read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Operating resource read requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Operating resource page is outside its bounds'
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
    ), categorized_requests AS (
        SELECT CASE lower(btrim(request.resource_type))
                   WHEN 'equipment' THEN 'equipment'
                   WHEN 'machinery' THEN 'equipment'
                   WHEN 'tool' THEN 'tools'
                   WHEN 'tools' THEN 'tools'
                   WHEN 'seed' THEN 'inputs'
                   WHEN 'seeds' THEN 'inputs'
                   WHEN 'seedlings' THEN 'inputs'
                   WHEN 'planting_material' THEN 'inputs'
                   WHEN 'fertilizer' THEN 'inputs'
                   WHEN 'compost' THEN 'inputs'
                   WHEN 'soil_amendment' THEN 'inputs'
                   WHEN 'materials' THEN 'materials'
                   WHEN 'building_materials' THEN 'materials'
                   WHEN 'infrastructure' THEN 'infrastructure'
                   WHEN 'storage' THEN 'infrastructure'
                   WHEN 'fencing' THEN 'infrastructure'
                   WHEN 'water_system' THEN 'infrastructure'
                   WHEN 'transport' THEN 'transport'
                   WHEN 'logistics' THEN 'transport'
                   WHEN 'labor' THEN 'labor'
                   WHEN 'labour' THEN 'labor'
                   WHEN 'workforce' THEN 'labor'
                   WHEN 'training' THEN 'training'
                   WHEN 'capacity_building' THEN 'training'
                   WHEN 'finance' THEN 'funding'
                   WHEN 'financial_support' THEN 'funding'
                   WHEN 'funding' THEN 'funding'
                   ELSE 'other'
               END AS resource_category,
               request.requested_by_party_id
          FROM public.operating_resource_request AS request
         WHERE request.scope_type = 'adelphi'
           AND request.scope_id IN (SELECT active_scope.scope_id FROM active_scope)
           AND EXISTS (SELECT 1 FROM active_scope)
    ), category_totals AS (
        SELECT resource_category,
               count(*)::BIGINT AS request_count,
               count(DISTINCT requested_by_party_id)::BIGINT AS contributor_count
          FROM categorized_requests
         GROUP BY resource_category
    ), page_rows AS (
        SELECT *
          FROM category_totals
         ORDER BY resource_category
         OFFSET requested_offset
         LIMIT requested_limit + 1
    ), numbered_page AS (
        SELECT row_number() OVER (ORDER BY resource_category)::INTEGER AS page_sequence,
               resource_category,
               request_count,
               contributor_count
          FROM page_rows
    )
    SELECT jsonb_build_object(
        'scope_configured', EXISTS (SELECT 1 FROM active_scope),
        'limit', requested_limit,
        'offset', requested_offset,
        'items', COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'resource_category', page.resource_category,
                    'suppressed', page.contributor_count BETWEEN 1 AND 2,
                    'request_count', CASE WHEN page.contributor_count BETWEEN 1 AND 2
                        THEN NULL ELSE page.request_count END
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
      INTO category_page
      FROM numbered_page AS page;

    RETURN category_page;
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_resource_categories(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_resource_categories(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_resource_categories(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_resource_categories(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.location_operating_pilot_resource_categories(
    UUID, INTEGER, INTEGER
) IS
'Returns bounded request counts by fixed resource category for active Adelphi farms mapped to the requested location; suppresses categories with fewer than three distinct requesters and excludes request IDs, free text, urgency, lifecycle state, and identities.';

COMMIT;
