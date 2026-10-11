-- Reviewed PostgreSQL reporting surface for the optional Metabase consumer.
-- The metric publication policy intentionally starts empty: values remain
-- private to this source until a human explicitly publishes a metric key.

CREATE SCHEMA IF NOT EXISTS kokonut_reporting;
REVOKE ALL ON SCHEMA kokonut_reporting FROM PUBLIC;

CREATE TABLE IF NOT EXISTS kokonut_reporting.metric_publication_policy (
    metric_id UUID PRIMARY KEY
        REFERENCES public.metric_definition(id) ON DELETE RESTRICT,
    status lifecycle_status NOT NULL DEFAULT 'draft',
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_metric_publication_review CHECK (
        status NOT IN ('verified', 'published')
        OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
    )
);

COMMENT ON TABLE kokonut_reporting.metric_publication_policy IS
    'Human-reviewed public reporting allowlist for metric definitions. Only published rows are exposed; empty by default.';

CREATE OR REPLACE VIEW kokonut_reporting.v_farm_summary
WITH (security_barrier = true)
AS
WITH eligible_locations AS (
    SELECT l.id, l.name, l.country, l.region, l.status
    FROM public.location AS l
    WHERE l.status = 'active'
      AND EXISTS (
          SELECT 1
          FROM public.farm_registry_record AS fr
          WHERE fr.location_id = l.id
            AND fr.status IN ('verified', 'published')
      )
), eligible_farms AS (
    SELECT f.id, f.location_id, f.total_area, f.area_unit
    FROM public.farm AS f
    JOIN eligible_locations AS l ON l.id = f.location_id
    WHERE f.status = 'active'
      AND EXISTS (
          SELECT 1
          FROM public.farm_registry_record AS fr
          WHERE fr.location_id = f.location_id
            AND fr.status IN ('verified', 'published')
            AND (fr.farm_id IS NULL OR fr.farm_id = f.id)
      )
), farm_totals AS (
    SELECT
        f.location_id,
        COUNT(*)::BIGINT AS farm_count,
        SUM(
            CASE LOWER(BTRIM(COALESCE(f.area_unit, '')))
                WHEN 'hectare' THEN f.total_area
                WHEN 'hectares' THEN f.total_area
                WHEN 'ha' THEN f.total_area
                WHEN 'square_meter' THEN f.total_area / 10000.0
                WHEN 'square_meters' THEN f.total_area / 10000.0
                WHEN 'm2' THEN f.total_area / 10000.0
                WHEN 'sqm' THEN f.total_area / 10000.0
                WHEN 'acre' THEN f.total_area * 0.40468564224
                WHEN 'acres' THEN f.total_area * 0.40468564224
                ELSE NULL
            END
        ) AS total_area_ha,
        BOOL_AND(
            f.total_area IS NOT NULL
            AND LOWER(BTRIM(COALESCE(f.area_unit, ''))) IN (
                'hectare', 'hectares', 'ha', 'square_meter', 'square_meters',
                'm2', 'sqm', 'acre', 'acres'
            )
        ) AS area_data_complete
    FROM eligible_farms AS f
    GROUP BY f.location_id
), plot_totals AS (
    SELECT f.location_id, COUNT(p.id)::BIGINT AS plot_count
    FROM eligible_farms AS f
    LEFT JOIN public.plot AS p
        ON p.farm_id = f.id
       AND p.status = 'active'
    GROUP BY f.location_id
)
SELECT
    l.id AS location_id,
    l.name AS location_name,
    l.country,
    l.region,
    COALESCE(ft.farm_count, 0)::BIGINT AS farm_count,
    COALESCE(pt.plot_count, 0)::BIGINT AS plot_count,
    CASE
        WHEN COALESCE(ft.area_data_complete, TRUE)
            THEN ROUND(COALESCE(ft.total_area_ha, 0)::NUMERIC, 2)
        ELSE NULL
    END AS total_area_ha,
    COALESCE(ft.area_data_complete, TRUE) AS area_data_complete,
    l.status
FROM eligible_locations AS l
LEFT JOIN farm_totals AS ft ON ft.location_id = l.id
LEFT JOIN plot_totals AS pt ON pt.location_id = l.id;

COMMENT ON VIEW kokonut_reporting.v_farm_summary IS
    'Active public-eligible farms and active plots per eligible location. Farm rows are included only when location-wide or farm-specific registry approval exists. Area is NULL if any included farm has missing or unsupported units.';

CREATE OR REPLACE VIEW kokonut_reporting.v_verified_metric_values
WITH (security_barrier = true)
AS
SELECT
    mv.location_id,
    l.name AS location_name,
    md.metric_key,
    md.display_name,
    COALESCE(mv.unit, md.unit) AS unit,
    mv.value,
    mv.period_start,
    mv.period_end,
    mv.computation_method,
    mv.computed_at,
    mv.verified_at
FROM public.metric_value AS mv
JOIN public.metric_definition AS md ON md.id = mv.metric_id
JOIN public.location AS l ON l.id = mv.location_id
JOIN kokonut_reporting.metric_publication_policy AS policy
    ON policy.metric_id = md.id
   AND policy.status = 'published'
WHERE md.active = TRUE
  AND mv.verified = TRUE
  AND l.status = 'active'
  AND EXISTS (
      SELECT 1
      FROM public.farm_registry_record AS fr
      WHERE fr.location_id = l.id
        AND fr.status IN ('verified', 'published')
  );

COMMENT ON VIEW kokonut_reporting.v_verified_metric_values IS
    'All verified values for explicitly published metric definitions at eligible active locations. Periods and methods are preserved; no latest-row selection is applied.';

CREATE OR REPLACE VIEW kokonut_reporting.v_attestation_summary
WITH (security_barrier = true)
AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    ar.claim_type,
    ar.chain,
    COUNT(*)::BIGINT AS total_attestations,
    COUNT(*) FILTER (WHERE ar.status = 'published')::BIGINT AS published_count,
    MIN(ar.attested_at) AS first_attestation,
    MAX(ar.attested_at) AS latest_attestation
FROM public.attestation_record AS ar
JOIN public.location AS l
    ON ar.subject_type = 'location'
   AND ar.subject_id = l.id
WHERE ar.status IN ('verified', 'published')
  AND ar.chain = 'celo'
  AND l.status = 'active'
  AND EXISTS (
      SELECT 1
      FROM public.farm_registry_record AS fr
      WHERE fr.location_id = l.id
        AND fr.status IN ('verified', 'published')
  )
GROUP BY l.id, l.name, ar.claim_type, ar.chain;

COMMENT ON VIEW kokonut_reporting.v_attestation_summary IS
    'Aggregate Celo attestation counts for active locations with verified or published registry records. Does not expose payloads or imply all-chain coverage.';

-- Source-role provisioning is separate and grants SELECT on the three views by
-- name. The private allowlist table and all canonical relations remain denied.
REVOKE ALL ON ALL TABLES IN SCHEMA kokonut_reporting FROM PUBLIC;
