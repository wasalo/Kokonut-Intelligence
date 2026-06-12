-- ============================================================
-- Pilot Farm Seed Data: MRV Claims & Verification
-- Kokonut Demo Farm — Kisumu, Kenya
-- ============================================================

-- MRV Claims
INSERT INTO mrv_claim (id, location_id, plot_id, claim_type, claim_date, claim_data, status, attestation_uid, attested_at, created_at) VALUES
('a0000000-0000-0000-0000-000000000380', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', 'soil_carbon_change', '2026-03-15', '{"baseline_tonnes_ha": 24.50, "current_tonnes_ha": 27.90, "delta_tonnes_ha": 3.40, "method": "lab_analysis", "depth_cm": 30}', 'attested', '0xac00000000000000000000000000000000000000000000000000000000000001', '2026-03-20 10:00:00+00', '2026-03-16 10:00:00+00'),
('a0000000-0000-0000-0000-000000000381', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000021', 'soil_carbon_change', '2026-03-15', '{"baseline_tonnes_ha": 21.80, "current_tonnes_ha": 24.80, "delta_tonnes_ha": 3.00, "method": "lab_analysis", "depth_cm": 30}', 'attested', '0xac00000000000000000000000000000000000000000000000000000000000002', '2026-03-20 10:00:00+00', '2026-03-16 10:00:00+00'),
('a0000000-0000-0000-0000-000000000382', 'a0000000-0000-0000-0000-000000000001', NULL, 'biodiversity_change', '2026-03-10', '{"baseline_species_count": 26, "current_species_count": 37, "delta": 11, "shannon_baseline": 0.98, "shannon_current": 1.12}', 'approved', NULL, NULL, '2026-03-11 10:00:00+00'),
('a0000000-0000-0000-0000-000000000383', 'a0000000-0000-0000-0000-000000000001', NULL, 'vegetation_change', '2026-03-15', '{"baseline_ndvi": 0.35, "current_ndvi": 0.58, "delta": 0.23, "source": "sentinel-2"}', 'submitted', NULL, NULL, '2026-03-16 10:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- Verification Reviews
INSERT INTO verification_review (id, claim_id, reviewer_id, review_date, method, result, notes, created_at) VALUES
('a0000000-0000-0000-0000-000000000390', 'a0000000-0000-0000-0000-000000000380', 'a0000000-0000-0000-0000-000000000060', '2026-03-18', 'lab_verification', 'approved', 'Lab results confirmed. Carbon gain of 3.4 t/ha is consistent with regenerative practice.', '2026-03-18 10:00:00+00'),
('a0000000-0000-0000-0000-000000000391', 'a0000000-0000-0000-0000-000000000381', 'a0000000-0000-0000-0000-000000000060', '2026-03-18', 'lab_verification', 'approved', 'Lab results confirmed. Carbon gain of 3.0 t/ha on clay soil.', '2026-03-18 10:00:00+00')
ON CONFLICT (id) DO NOTHING;
