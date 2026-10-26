-- Minimal source tables for migration 599 signed read-only acceptance.
CREATE TABLE public.carbon_credit (
    credit_code TEXT NOT NULL,
    location_id UUID NOT NULL,
    current_sequestration_tonnes NUMERIC NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE public.climate_impact_summary (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL,
    reporting_year INTEGER NOT NULL,
    total_sequestration_tonnes_co2e NUMERIC
);
CREATE TABLE public.tree_inventory (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL,
    status TEXT NOT NULL,
    co2e_estimate_tonnes NUMERIC
);
CREATE TABLE public.soil_carbon_measurement (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL,
    plot_id UUID NOT NULL,
    measurement_date DATE NOT NULL,
    carbon_tonnes_per_ha NUMERIC NOT NULL
);
CREATE TABLE public.credit_adjustment (id UUID PRIMARY KEY);
CREATE TABLE public.credit_retirement (id UUID PRIMARY KEY);

INSERT INTO public.carbon_credit
    (credit_code, location_id, current_sequestration_tonnes, status)
VALUES
    ('KKNT-A-STALE', 'a0000000-0000-0000-0000-000000000001', 100, 'verified'),
    ('KKNT-A-CURRENT', 'a0000000-0000-0000-0000-000000000001', 1100, 'published'),
    ('KKNT-A-DRAFT', 'a0000000-0000-0000-0000-000000000001', 5, 'draft'),
    ('KKNT-B-FALLBACK', 'a0000000-0000-0000-0000-000000000002', 100, 'verified');

INSERT INTO public.climate_impact_summary
    (id, location_id, reporting_year, total_sequestration_tonnes_co2e)
VALUES
    ('a0000000-0000-0000-0000-000000000821', 'a0000000-0000-0000-0000-000000000001', 2025, 900),
    ('a0000000-0000-0000-0000-000000000822', 'a0000000-0000-0000-0000-000000000001', 2026, 1100);

INSERT INTO public.tree_inventory (id, location_id, status, co2e_estimate_tonnes)
VALUES
    ('a0000000-0000-0000-0000-000000000831', 'a0000000-0000-0000-0000-000000000002', 'verified', 200),
    ('a0000000-0000-0000-0000-000000000832', 'a0000000-0000-0000-0000-000000000002', 'draft', 999);

INSERT INTO public.soil_carbon_measurement
    (id, location_id, plot_id, measurement_date, carbon_tonnes_per_ha)
VALUES
    ('a0000000-0000-0000-0000-000000000841', 'a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000851', DATE '2024-01-01', 10),
    ('a0000000-0000-0000-0000-000000000842', 'a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000851', DATE '2025-01-01', 12);
