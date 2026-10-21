-- Bounded, redacted location-scoped work-claim category totals.

BEGIN;

GRANT SELECT (work_type)
    ON TABLE public.work_item TO kokonut_operating_pilot_reader;

CREATE OR REPLACE FUNCTION kokonut_security.location_operating_pilot_work_claims(
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
    claims_page JSONB;
BEGIN
    SELECT context.actor_id, context.location_id, context.actor_type
      INTO context_record
      FROM kokonut_security.current_tenant_context() AS context;
    IF context_record.actor_type IS DISTINCT FROM 'operator'
       OR context_record.actor_id IS NULL
       OR context_record.location_id IS DISTINCT FROM requested_location_id
       OR requested_location_id IS NULL THEN
        RAISE EXCEPTION 'Operating work-claim read requires signed operator location context'
            USING ERRCODE = '42501';
    END IF;
    IF NOT public.operator_scope_grant_allows(
        context_record.actor_id, 'operating_pilot', 'read', requested_location_id
    ) THEN
        RAISE EXCEPTION 'Operating work-claim read requires an active location grant'
            USING ERRCODE = '42501';
    END IF;
    IF requested_limit IS NULL OR requested_limit NOT BETWEEN 1 AND 50
       OR requested_offset IS NULL OR requested_offset NOT BETWEEN 0 AND 10000 THEN
        RAISE EXCEPTION 'Operating work-claim page is outside its bounds'
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
    ), claim_totals AS (
        SELECT CASE lower(btrim(item.work_type))
                   WHEN 'general' THEN 'general'
                   WHEN 'planting' THEN 'planting'
                   WHEN 'harvest' THEN 'harvest'
                   WHEN 'harvesting' THEN 'harvest'
                   WHEN 'irrigation' THEN 'irrigation'
                   WHEN 'monitoring' THEN 'monitoring'
                   WHEN 'maintenance' THEN 'maintenance'
                   WHEN 'tree-care' THEN 'tree-care'
                   WHEN 'agroforestry' THEN 'agroforestry'
                   WHEN 'soil-health' THEN 'soil-health'
                   WHEN 'water-management' THEN 'water-management'
                   ELSE 'other'
               END AS work_type,
               count(*)::BIGINT AS claim_count,
               count(DISTINCT claim.claimant_party_id)::BIGINT AS contributor_count
          FROM public.work_item AS item
          JOIN public.work_item_claim AS claim ON claim.work_item_id = item.id
         WHERE item.location_id = requested_location_id
           AND EXISTS (SELECT 1 FROM active_scope)
         GROUP BY 1
    ), page_rows AS (
        SELECT *
          FROM claim_totals
         ORDER BY work_type
         OFFSET requested_offset
         LIMIT requested_limit + 1
    ), numbered_page AS (
        SELECT row_number() OVER (ORDER BY work_type)::INTEGER AS page_sequence,
               work_type,
               claim_count,
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
                    'work_type', page.work_type,
                    'suppressed', page.contributor_count BETWEEN 1 AND 2,
                    'claim_count', CASE WHEN page.contributor_count BETWEEN 1 AND 2
                        THEN NULL ELSE page.claim_count END
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
      INTO claims_page
      FROM numbered_page AS page;

    RETURN claims_page;
END;
$$;

ALTER FUNCTION kokonut_security.location_operating_pilot_work_claims(UUID, INTEGER, INTEGER)
    OWNER TO kokonut_operating_pilot_reader;
REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_work_claims(
    UUID, INTEGER, INTEGER
) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT USAGE ON SCHEMA kokonut_security TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.location_operating_pilot_work_claims(
            UUID, INTEGER, INTEGER
        ) TO kokonut_runtime;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_directus_runtime') THEN
        REVOKE ALL ON FUNCTION kokonut_security.location_operating_pilot_work_claims(
            UUID, INTEGER, INTEGER
        ) FROM kokonut_directus_runtime;
    END IF;
END;
$$;

COMMENT ON FUNCTION kokonut_security.location_operating_pilot_work_claims(
    UUID, INTEGER, INTEGER
) IS
'Returns bounded claim totals by fixed safe work-type bucket for an active Adelphi farm mapped to the requested location. Hides counts below three distinct claimants and never returns claim/item identifiers, participant identity, claim lifecycle, evidence, narratives, or reasons.';

COMMIT;
