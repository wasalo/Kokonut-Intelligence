-- ============================================================
-- 078_carbon_credits.sql — Seed data
-- ============================================================

-- Adelphi pilot: 1 carbon credit for 2026 vintage
INSERT INTO carbon_credit (
    location_id, credit_code, vintage_year,
    methodology, methodology_version,
    initial_sequestration_tonnes, current_sequestration_tonnes,
    adjustment_margin_pct, buffer_pool_pct, issuable_tonnes,
    price_per_tonne_usd,
    evidence_maturity, external_verifier, methodology_ref,
    status, source_system
) VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'KKNT-2026-ADELPHI-0001',
    2026,
    'IPCC 2006 Tier 2',
    '2024 update',
    50.0000,
    50.0000,
    10.00,
    20.00,
    40.0000,
    25.00,
    6,
    'Kokonut Intelligence Internal Verification',
    'IPCC 2006 Guidelines for National Greenhouse Gas Inventories, Vol 4',
    'verified',
    'carbon_credit_service'
) ON CONFLICT (credit_code) DO UPDATE SET
    methodology = EXCLUDED.methodology,
    initial_sequestration_tonnes = EXCLUDED.initial_sequestration_tonnes,
    current_sequestration_tonnes = EXCLUDED.current_sequestration_tonnes,
    issuable_tonnes = EXCLUDED.issuable_tonnes,
    status = EXCLUDED.status,
    updated_at = NOW();
