-- ============================================================
-- 063_statement_of_work.sql — Seeds: Adelphi pilot data
-- ============================================================

-- Adelphi SOW: Syntropic Farm Establishment
INSERT INTO statement_of_work (
    id, location_id, sow_name, sow_version, effective_date, expiration_date,
    client_name, contractor_name, total_contract_value, currency, payment_terms,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000630',
 'a0000000-0000-0000-0000-000000000001',
 'Adelphi Syntropic Farm Establishment SOW', '1.0',
 '2025-01-01', '2027-12-31',
 'Kokonut DAO', 'Adelphi Farm Operations Team',
 45000.00, 'USD',
 '30% upon signing, 40% at midpoint review, 30% upon completion and certification. Net 30 days from invoice.',
 'active', 'pilot_seed', 'adelphi-sow-001',
 '{"record_type":"statement_of_work","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- Deliverables
INSERT INTO sow_deliverable (
    id, sow_id, deliverable_name, description, acceptance_criteria,
    due_date, delivered_at, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000640',
 'a0000000-0000-0000-0000-000000000630',
 'Soil Assessment & Baseline Report',
 'Complete soil analysis across all plots with pH, NPK, organic matter, carbon measurement, and baseline biodiversity survey.',
 'Lab-verified soil results for all 3 plots. Species count >= 15. Carbon baseline established. Report formatted as JSON with evidence links.',
 '2025-03-31', '2025-03-15', 'accepted',
 'pilot_seed', 'adelphi-sow-del-001',
 '{"record_type":"sow_deliverable","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000641',
 'a0000000-0000-0000-0000-000000000630',
 'Syntropic Planting Plan & Implementation',
 'Design and implement syntropic planting across production zone and agroforestry corridor with multi-strata species selection.',
 'Planting plan approved by DAO. 45 coconut palms + companion species planted. Survival rate >= 85% at 6 months.',
 '2025-06-30', '2025-06-20', 'accepted',
 'pilot_seed', 'adelphi-sow-del-002',
 '{"record_type":"sow_deliverable","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000642',
 'a0000000-0000-0000-0000-000000000630',
 'Quarterly Impact Report & Certification Preparation',
 'Generate quarterly impact reports with ecological metrics, financial performance, and organic certification readiness assessment.',
 'Report generated via report_generator. All 17 governed metrics populated. Organic readiness score >= 70/100.',
 '2025-09-30', NULL, 'pending',
 'pilot_seed', 'adelphi-sow-del-003',
 '{"record_type":"sow_deliverable","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    delivered_at = EXCLUDED.delivered_at,
    updated_at = NOW();

-- Payment schedule
INSERT INTO sow_payment_schedule (
    id, sow_id, milestone_name, amount, due_date, payment_status,
    invoice_number, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000650',
 'a0000000-0000-0000-0000-000000000630',
 '30% Upon Signing', 13500.00, '2025-01-15', 'paid',
 'INV-2025-001', 'pilot_seed', 'adelphi-sow-pay-001',
 '{"record_type":"sow_payment_schedule","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000651',
 'a0000000-0000-0000-0000-000000000630',
 '40% Midpoint Review', 18000.00, '2025-07-01', 'paid',
 'INV-2025-002', 'pilot_seed', 'adelphi-sow-pay-002',
 '{"record_type":"sow_payment_schedule","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000652',
 'a0000000-0000-0000-0000-000000000630',
 '30% Upon Completion & Certification', 13500.00, '2025-12-31', 'pending',
 NULL, 'pilot_seed', 'adelphi-sow-pay-003',
 '{"record_type":"sow_payment_schedule","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    payment_status = EXCLUDED.payment_status,
    invoice_number = EXCLUDED.invoice_number,
    updated_at = NOW();

-- Change request
INSERT INTO sow_change_request (
    id, sow_id, change_name, description, impact_on_timeline, impact_on_budget,
    requested_by, status, decided_at, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000660',
 'a0000000-0000-0000-0000-000000000630',
 'Scope Extension: Add Biofactory Zone',
 'Extend SOW to include biofactory zone establishment with compost production capacity and bio-input manufacturing.',
 '2 additional months for biofactory setup and commissioning.',
 5000.00,
 'Adelphi Farm Lead', 'approved', '2025-04-15',
 'pilot_seed', 'adelphi-sow-cr-001',
 '{"record_type":"sow_change_request","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    decided_at = EXCLUDED.decided_at,
    updated_at = NOW();
