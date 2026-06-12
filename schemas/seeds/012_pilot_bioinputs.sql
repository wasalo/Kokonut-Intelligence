-- ============================================================
-- Pilot Farm Seed Data: Bioinput Production
-- Kokonut Demo Farm — Kisumu, Kenya
-- ============================================================

-- Additional bioinput expense events (category = 'Bioinputs & Compost')
INSERT INTO expense_event (id, location_id, crop_cycle_id, expense_date, description, amount, currency, category, vendor, allocation_method, status) VALUES
('a0000000-0000-0000-0000-000000000410', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000040', '2025-10-15', 'Compost tea and liquid biofertilizer for soil preparation', 80.00, 'USD', 'Bioinputs & Compost', 'AgroSupplies Kenya', 'direct', 'approved'),
('a0000000-0000-0000-0000-000000000411', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000040', '2025-11-10', 'Neem extract biopesticide for fall armyworm control', 60.00, 'USD', 'Bioinputs & Compost', 'AgroSupplies Kenya', 'direct', 'approved'),
('a0000000-0000-0000-0000-000000000412', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000040', '2025-12-05', 'Biopesticide for fall armyworm — follow-up application', 45.00, 'USD', 'Bioinputs & Compost', 'AgroSupplies Kenya', 'direct', 'approved')
ON CONFLICT (id) DO NOTHING;

-- Biofactory infrastructure asset
INSERT INTO infrastructure_asset (id, location_id, name, asset_type, description, capacity, capacity_unit, condition_status, status) VALUES
('a0000000-0000-0000-0000-000000000420', 'a0000000-0000-0000-0000-000000000001', 'On-Farm Biofactory', 'biofactory', 'Small-scale bioinput production facility for compost tea, liquid biofertilizer, and neem extract', 500, 'litres/month', 'good', 'active')
ON CONFLICT (id) DO NOTHING;
