-- Minimal application contract for the signed NOI worker acceptance.
CREATE TABLE public.crop_cycle (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES public.location(id),
    status TEXT NOT NULL,
    planting_date DATE,
    expected_harvest_date DATE,
    actual_harvest_date DATE,
    gross_revenue NUMERIC(15,2) NOT NULL,
    returns_discounts NUMERIC(15,2) NOT NULL,
    net_revenue NUMERIC(15,2) NOT NULL,
    direct_crop_costs NUMERIC(15,2) NOT NULL,
    allocated_shared_costs NUMERIC(15,2) NOT NULL,
    total_costs NUMERIC(15,2) NOT NULL,
    noi NUMERIC(15,2) NOT NULL,
    operating_margin_pct NUMERIC(8,4) NOT NULL,
    loss_rate_pct NUMERIC(8,4) NOT NULL
);

CREATE TABLE public.noi_snapshot (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    crop_cycle_id UUID NOT NULL REFERENCES public.crop_cycle(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    gross_revenue NUMERIC(15,2),
    returns_and_discounts NUMERIC(15,2),
    net_revenue NUMERIC(15,2),
    direct_crop_costs NUMERIC(15,2),
    allocated_shared_costs NUMERIC(15,2),
    total_costs NUMERIC(15,2),
    noi NUMERIC(15,2),
    operating_margin_pct NUMERIC(8,4),
    loss_rate_pct NUMERIC(8,4),
    calculation_version VARCHAR(20),
    calculated_at TIMESTAMPTZ DEFAULT statement_timestamp(),
    inputs JSONB,
    created_by UUID
);
CREATE UNIQUE INDEX uq_noi_snapshot_crop_cycle_id
    ON public.noi_snapshot(crop_cycle_id);

CREATE VIEW public.v_crop_cycle_noi AS
SELECT
    id AS crop_cycle_id,
    location_id,
    planting_date AS period_start,
    COALESCE(actual_harvest_date, expected_harvest_date) AS period_end,
    gross_revenue,
    returns_discounts,
    net_revenue,
    direct_crop_costs,
    allocated_shared_costs,
    total_costs,
    noi,
    operating_margin_pct,
    loss_rate_pct
FROM public.crop_cycle;

INSERT INTO public.crop_cycle (
    id, location_id, status, planting_date, expected_harvest_date,
    gross_revenue, returns_discounts, net_revenue, direct_crop_costs,
    allocated_shared_costs, total_costs, noi, operating_margin_pct, loss_rate_pct
) VALUES
    ('a0000000-0000-0000-0000-000000000101', 'a0000000-0000-0000-0000-000000000001',
     'active', DATE '2026-01-01', DATE '2026-12-31', 100, 5, 95, 30, 10, 40, 55, 57.9, 0),
    ('a0000000-0000-0000-0000-000000000102', 'a0000000-0000-0000-0000-000000000002',
     'active', DATE '2026-01-01', DATE '2026-12-31', 200, 5, 195, 40, 10, 50, 145, 74.3, 0),
    ('a0000000-0000-0000-0000-000000000103', 'a0000000-0000-0000-0000-000000000001',
     'active', DATE '2026-02-01', DATE '2026-12-31', 300, 5, 295, 60, 10, 70, 225, 76.3, 0);

-- A stale snapshot points a location-A crop cycle at location B. A worker for
-- location A may not repair or overwrite that cross-location row implicitly.
INSERT INTO public.noi_snapshot (
    crop_cycle_id, location_id, period_start, period_end, noi, inputs
) VALUES (
    'a0000000-0000-0000-0000-000000000103',
    'a0000000-0000-0000-0000-000000000002',
    DATE '2026-02-01', DATE '2026-12-31', 777, '{"fixture":"stale-owner"}'::jsonb
);
