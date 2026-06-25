-- ============================================================
-- Pilot Farm Seed Data: Extended Partners & Sales
-- Kokonut Adelphi — Sabana Grande de Boya, Dominican Republic
-- ============================================================

-- Additional buyer partners
INSERT INTO partner (id, name, slug, partner_type, contact_email, status, metadata) VALUES
('a0000000-0000-0000-0000-000000000053', 'Adelphi Fresh Buyers', 'adelphi-fresh-buyers', 'buyer', 'buyers@example.kokonut.network', 'active', '{"buyer_type": "processor", "specialty": "lettuce and tropical produce", "payment_terms": "net_30"}'),
('a0000000-0000-0000-0000-000000000054', 'DirectFarm Dominican Republic', 'directfarm-dominican-republic', 'buyer', 'direct@example.kokonut.network', 'active', '{"buyer_type": "direct", "specialty": "regenerative produce", "payment_terms": "net_14"}')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    partner_type = EXCLUDED.partner_type,
    contact_email = EXCLUDED.contact_email,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Additional sales events with different buyers
INSERT INTO sales_event (id, location_id, crop_cycle_id, buyer, buyer_type, partner_id, sale_date, quantity, unit, price_per_unit, total_amount, return_amount, discount_amount, net_amount, payment_status, payment_date, status) VALUES
('a0000000-0000-0000-0000-000000000400', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000040', 'Adelphi Fresh Buyers', 'processor', 'a0000000-0000-0000-0000-000000000053', '2026-01-20', 8.00, 'tonnes', 210.00, 1680.00, 0.00, 0.00, 1680.00, 'paid', '2026-02-19', 'published'),
('a0000000-0000-0000-0000-000000000401', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000041', 'DirectFarm Dominican Republic', 'direct', 'a0000000-0000-0000-0000-000000000054', '2026-02-20', 5.00, 'tonnes', 980.00, 4900.00, 0.00, 50.00, 4850.00, 'paid', '2026-03-06', 'published'),
('a0000000-0000-0000-0000-000000000402', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000042', 'Adelphi Fresh Buyers', 'processor', 'a0000000-0000-0000-0000-000000000053', '2026-03-10', 3.50, 'tonnes', 260.00, 910.00, 0.00, 0.00, 910.00, 'paid', '2026-04-09', 'published')
ON CONFLICT (id) DO UPDATE SET
    buyer = EXCLUDED.buyer,
    buyer_type = EXCLUDED.buyer_type,
    partner_id = EXCLUDED.partner_id,
    quantity = EXCLUDED.quantity,
    unit = EXCLUDED.unit,
    price_per_unit = EXCLUDED.price_per_unit,
    total_amount = EXCLUDED.total_amount,
    net_amount = EXCLUDED.net_amount,
    payment_status = EXCLUDED.payment_status,
    payment_date = EXCLUDED.payment_date,
    status = EXCLUDED.status;
