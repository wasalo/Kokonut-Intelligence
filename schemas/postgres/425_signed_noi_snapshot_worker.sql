-- Expose NOI snapshot reconciliation only as a signed, location-bound worker
-- operation. The worker login receives no direct application-table privileges.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_noi_snapshot_owner'
    ) THEN
        CREATE ROLE kokonut_noi_snapshot_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_noi_snapshot_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'kokonut_noi_snapshot_owner has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_noi_snapshot_owner'
            OR member_role.rolname = 'kokonut_noi_snapshot_owner'
    ) THEN
        RAISE EXCEPTION 'NOI snapshot function owner must not have role memberships';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_noi_snapshot_owner;
GRANT CREATE ON SCHEMA kokonut_security TO kokonut_noi_snapshot_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_noi_snapshot_owner;
GRANT SELECT (id, location_id, status) ON public.crop_cycle
    TO kokonut_noi_snapshot_owner;
GRANT SELECT ON public.v_crop_cycle_noi TO kokonut_noi_snapshot_owner;
GRANT SELECT (crop_cycle_id, location_id) ON public.noi_snapshot
    TO kokonut_noi_snapshot_owner;
GRANT INSERT (
    id, crop_cycle_id, location_id, period_start, period_end,
    gross_revenue, returns_and_discounts, net_revenue,
    direct_crop_costs, allocated_shared_costs, total_costs,
    noi, operating_margin_pct, loss_rate_pct,
    calculation_version, calculated_at, inputs
) ON public.noi_snapshot TO kokonut_noi_snapshot_owner;
GRANT UPDATE (
    location_id, period_start, period_end,
    gross_revenue, returns_and_discounts, net_revenue,
    direct_crop_costs, allocated_shared_costs, total_costs,
    noi, operating_margin_pct, loss_rate_pct,
    calculation_version, calculated_at, inputs
) ON public.noi_snapshot TO kokonut_noi_snapshot_owner;

CREATE OR REPLACE FUNCTION kokonut_security.reconcile_noi_snapshot_for_location(
    requested_location_id UUID
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    inserted_cycle_ids UUID[];
    inserted_rows INTEGER;
    updated_rows INTEGER;
    affected_rows INTEGER;
BEGIN
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope(
          'noi_snapshot', 'reconcile'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed NOI snapshot worker scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS NULL
       OR requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'NOI snapshot location differs from the signed worker scope'
            USING ERRCODE = '42501';
    END IF;

    WITH inserted AS (
        INSERT INTO public.noi_snapshot (
            id, crop_cycle_id, location_id, period_start, period_end,
            gross_revenue, returns_and_discounts, net_revenue,
            direct_crop_costs, allocated_shared_costs, total_costs,
            noi, operating_margin_pct, loss_rate_pct,
            calculation_version, calculated_at, inputs
        )
        SELECT
            pg_catalog.gen_random_uuid(), source.crop_cycle_id, source.location_id,
            COALESCE(source.period_start, CURRENT_DATE),
            COALESCE(source.period_end, source.period_start, CURRENT_DATE),
            source.gross_revenue, source.returns_discounts, source.net_revenue,
            source.direct_crop_costs, source.allocated_shared_costs,
            source.total_costs, source.noi, source.operating_margin_pct,
            source.loss_rate_pct, '1.0', statement_timestamp(),
            jsonb_build_object(
                'source_view', 'v_crop_cycle_noi',
                'formula_version', '1.0'
            )
        FROM public.v_crop_cycle_noi AS source
        JOIN public.crop_cycle AS cycle
          ON cycle.id = source.crop_cycle_id
         AND cycle.location_id = worker_scope.location_id
        WHERE source.location_id = worker_scope.location_id
          AND cycle.status IN (
              'active', 'flowering', 'harvesting', 'harvested', 'completed'
          )
        ON CONFLICT (crop_cycle_id) DO NOTHING
        RETURNING crop_cycle_id
    )
    SELECT count(*)::INTEGER,
           COALESCE(array_agg(crop_cycle_id), ARRAY[]::UUID[])
      INTO inserted_rows, inserted_cycle_ids
      FROM inserted;

    UPDATE public.noi_snapshot AS existing_snapshot
       SET location_id = source.location_id,
           period_start = COALESCE(source.period_start, CURRENT_DATE),
           period_end = COALESCE(source.period_end, source.period_start, CURRENT_DATE),
           gross_revenue = source.gross_revenue,
           returns_and_discounts = source.returns_discounts,
           net_revenue = source.net_revenue,
           direct_crop_costs = source.direct_crop_costs,
           allocated_shared_costs = source.allocated_shared_costs,
           total_costs = source.total_costs,
           noi = source.noi,
           operating_margin_pct = source.operating_margin_pct,
           loss_rate_pct = source.loss_rate_pct,
           calculation_version = '1.0',
           calculated_at = statement_timestamp(),
           inputs = jsonb_build_object(
               'source_view', 'v_crop_cycle_noi',
               'formula_version', '1.0'
           )
      FROM public.v_crop_cycle_noi AS source
      JOIN public.crop_cycle AS cycle
        ON cycle.id = source.crop_cycle_id
       AND cycle.location_id = worker_scope.location_id
     WHERE existing_snapshot.crop_cycle_id = source.crop_cycle_id
       AND existing_snapshot.location_id = worker_scope.location_id
       AND source.location_id = worker_scope.location_id
       AND cycle.status IN (
           'active', 'flowering', 'harvesting', 'harvested', 'completed'
       )
       AND NOT (existing_snapshot.crop_cycle_id = ANY(inserted_cycle_ids));

    GET DIAGNOSTICS updated_rows = ROW_COUNT;
    affected_rows := inserted_rows + updated_rows;
    RETURN affected_rows;
END;
$$;

ALTER FUNCTION kokonut_security.reconcile_noi_snapshot_for_location(UUID)
    OWNER TO kokonut_noi_snapshot_owner;
REVOKE ALL ON FUNCTION kokonut_security.reconcile_noi_snapshot_for_location(UUID)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.reconcile_noi_snapshot_for_location(UUID)
    TO kokonut_worker_execution;

COMMENT ON FUNCTION kokonut_security.reconcile_noi_snapshot_for_location(UUID) IS
    'Upserts NOI snapshots only for the active location in a signed noi_snapshot/reconcile worker transaction; worker logins receive no table privileges.';

COMMIT;
