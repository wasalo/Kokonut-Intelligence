-- ============================================================
-- Pilot Farm Seed Data: Extended Partners & Sales
-- Kokonut Demo Farm — Kisumu, Kenya
-- ============================================================

-- Additional buyer partners
INSERT INTO partner (id, name, slug, partner_type, contact_email, status, metadata) VALUES
('a0000000-0000-0000-0000-000000000053', 'Kisumu Fresh Processors', 'kisumu-fresh-processors', 'buyer', 'amina@kisumufresh.co.ke', 'active', '{"buyer_type": "processor", "specialty": "cassava processing", "payment_terms": "net_30"}'),
('a0000000-0000-0000-0000-000000000054', 'DirectFarm Kenya', 'directfarm-kenya', 'buyer', 'peter@directfarm.co.ke', 'active', '{"buyer_type": "direct", "specialty": "organic produce", "payment_terms": "net_14"}')
ON CONFLICT (id) DO NOTHING;

-- Additional sales events with different buyers
INSERT INTO sales_event (id, location_id, crop_cycle_id, buyer, buyer_type, partner_id, sale_date, quantity, unit, price_per_unit, total_amount, return_amount, discount_amount, net_amount, payment_status, payment_date, status) VALUES
('a0000000-0000-0000-0000-000000000400', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000040', 'Kisumu Fresh Processors', 'processor', 'a0000000-0000-0000-0000-000000000053', '2026-01-20', 8.00, 'tonnes', 210.00, 1680.00, 0.00, 0.00, 1680.00, 'paid', '2026-02-19', 'published'),
('a0000000-0000-0000-0000-000000000401', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000041', 'DirectFarm Kenya', 'direct', 'a0000000-0000-0000-0000-000000000054', '2026-02-20', 5.00, 'tonnes', 980.00, 4900.00, 0.00, 50.00, 4850.00, 'paid', '2026-03-06', 'published'),
('a0000000-0000-0000-0000-000000000402', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000042', 'Kisumu Fresh Processors', 'processor', 'a0000000-0000-0000-0000-000000000053', '2026-03-10', 3.50, 'tonnes', 260.00, 910.00, 0.00, 0.00, 910.00, 'paid', '2026-04-09', 'published')
ON CONFLICT (id) DO NOTHING;
