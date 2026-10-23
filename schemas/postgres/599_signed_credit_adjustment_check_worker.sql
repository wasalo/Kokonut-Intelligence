-- Bound the scheduled read-only carbon credit adjustment check to one signed
-- location. The worker receives no direct application-table access.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_credit_adjustment_check_owner'
    ) THEN
        CREATE ROLE kokonut_credit_adjustment_check_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_credit_adjustment_check_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'credit-adjustment function owner has unsafe attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS membership
          JOIN pg_catalog.pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_credit_adjustment_check_owner'
            OR member_role.rolname = 'kokonut_credit_adjustment_check_owner'
    ) THEN
        RAISE EXCEPTION 'credit-adjustment function owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA kokonut_security, public
    TO kokonut_credit_adjustment_check_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_credit_adjustment_check_owner;
GRANT SELECT (
    credit_code, location_id, current_sequestration_tonnes, status
) ON public.carbon_credit TO kokonut_credit_adjustment_check_owner;
GRANT SELECT (location_id, reporting_year, total_sequestration_tonnes_co2e)
    ON public.climate_impact_summary TO kokonut_credit_adjustment_check_owner;
GRANT SELECT (location_id, status, co2e_estimate_tonnes)
    ON public.tree_inventory TO kokonut_credit_adjustment_check_owner;
GRANT SELECT (id, location_id, plot_id, measurement_date, carbon_tonnes_per_ha)
    ON public.soil_carbon_measurement TO kokonut_credit_adjustment_check_owner;

CREATE OR REPLACE FUNCTION kokonut_security.credit_adjustment_snapshot_for_location(
    requested_location_id UUID
)
RETURNS TABLE (
    credit_code TEXT,
    current_sequestration_tonnes NUMERIC,
    recomputed_sequestration_tonnes NUMERIC
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    signed_location_id UUID;
BEGIN
    SELECT scope.location_id
      INTO signed_location_id
      FROM kokonut_security.current_worker_scope(
          'carbon_credit_adjustment', 'read'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed carbon-credit adjustment scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM signed_location_id THEN
        RAISE EXCEPTION 'credit-adjustment location differs from signed worker scope'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    WITH latest_summary AS (
        SELECT summary.total_sequestration_tonnes_co2e
          FROM public.climate_impact_summary AS summary
         WHERE summary.location_id = signed_location_id
         ORDER BY summary.reporting_year DESC
         LIMIT 1
    ),
    tree_total AS (
        SELECT COALESCE(SUM(tree.co2e_estimate_tonnes), 0)::NUMERIC AS value
          FROM public.tree_inventory AS tree
         WHERE tree.location_id = signed_location_id
           AND tree.status IN ('verified', 'published')
    ),
    soil_ranked AS (
        SELECT soil.plot_id,
               soil.carbon_tonnes_per_ha,
               pg_catalog.row_number() OVER (
                   PARTITION BY soil.plot_id
                   ORDER BY soil.measurement_date, soil.id
               ) AS first_measurement,
               pg_catalog.row_number() OVER (
                   PARTITION BY soil.plot_id
                   ORDER BY soil.measurement_date DESC, soil.id DESC
               ) AS last_measurement,
               pg_catalog.count(*) OVER (PARTITION BY soil.plot_id) AS measurement_count
          FROM public.soil_carbon_measurement AS soil
         WHERE soil.location_id = signed_location_id
    ),
    per_plot AS (
        SELECT plot_id,
               MAX(carbon_tonnes_per_ha) FILTER (WHERE first_measurement = 1) AS baseline,
               MAX(carbon_tonnes_per_ha) FILTER (WHERE last_measurement = 1) AS latest,
               MAX(measurement_count) AS measurement_count
          FROM soil_ranked
         GROUP BY plot_id
    ),
    soil_total AS (
        SELECT COALESCE(SUM(
                   CASE WHEN measurement_count >= 2
                        THEN (latest - baseline) * 3.67
                        ELSE 0
                   END
               ), 0)::NUMERIC AS value
          FROM per_plot
    ),
    recomputed AS (
        SELECT CASE
                   WHEN EXISTS (SELECT 1 FROM latest_summary)
                   THEN COALESCE(
                       (SELECT summary.total_sequestration_tonnes_co2e
                          FROM latest_summary AS summary),
                       0
                   )
                   ELSE tree_total.value + soil_total.value
               END::NUMERIC AS value
          FROM tree_total CROSS JOIN soil_total
    )
    SELECT credit.credit_code::TEXT,
           credit.current_sequestration_tonnes,
           recomputed.value
      FROM public.carbon_credit AS credit
      CROSS JOIN recomputed
     WHERE credit.location_id = signed_location_id
       AND credit.status IN ('verified', 'published')
     ORDER BY credit.credit_code;
END;
$$;

ALTER FUNCTION kokonut_security.credit_adjustment_snapshot_for_location(UUID)
    OWNER TO kokonut_credit_adjustment_check_owner;
REVOKE ALL ON FUNCTION kokonut_security.credit_adjustment_snapshot_for_location(UUID)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.credit_adjustment_snapshot_for_location(UUID)
    TO kokonut_worker_execution;

COMMENT ON FUNCTION kokonut_security.credit_adjustment_snapshot_for_location(UUID) IS
    'Returns only verified/published credit adjustment inputs for the exact location in the signed carbon_credit_adjustment/read worker context. The worker has no direct application-table access and cannot mutate credit or review state.';

COMMIT;
