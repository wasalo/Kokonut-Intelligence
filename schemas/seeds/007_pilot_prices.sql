-- ============================================================
-- Pilot Farm Seed Data: Price Observations
-- Kokonut Adelphi — Sabana Grande de Boya, Dominican Republic
-- ============================================================

INSERT INTO price_observation (id, crop_id, market_name, price_date, price_per_unit, unit, currency, source) VALUES
-- Lettuce prices (4 market dates)
('a0000000-0000-0000-0000-000000000300', 'a0000000-0000-0000-0000-000000000030', 'Sabana Grande Market', '2025-10-15', 350.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-000000000301', 'a0000000-0000-0000-0000-000000000030', 'Sabana Grande Market', '2025-12-15', 370.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-000000000302', 'a0000000-0000-0000-0000-000000000030', 'Sabana Grande Market', '2026-02-15', 380.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-000000000303', 'a0000000-0000-0000-0000-000000000030', 'Santo Domingo Wholesale', '2026-03-01', 390.00, 'tonnes', 'USD', 'market_observation'),
-- Passion fruit prices
('a0000000-0000-0000-0000-000000000304', 'a0000000-0000-0000-0000-000000000031', 'Sabana Grande Market', '2025-10-15', 180.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-000000000305', 'a0000000-0000-0000-0000-000000000031', 'Sabana Grande Market', '2025-12-15', 190.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-000000000306', 'a0000000-0000-0000-0000-000000000031', 'Sabana Grande Market', '2026-02-15', 200.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-000000000307', 'a0000000-0000-0000-0000-000000000031', 'Santo Domingo Wholesale', '2026-03-01', 210.00, 'tonnes', 'USD', 'market_observation'),
-- Coconut prices
('a0000000-0000-0000-0000-000000000308', 'a0000000-0000-0000-0000-000000000032', 'Sabana Grande Market', '2025-10-15', 850.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-000000000309', 'a0000000-0000-0000-0000-000000000032', 'Sabana Grande Market', '2025-12-15', 900.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-00000000030a', 'a0000000-0000-0000-0000-000000000032', 'Sabana Grande Market', '2026-02-15', 920.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-00000000030b', 'a0000000-0000-0000-0000-000000000032', 'Santo Domingo Wholesale', '2026-03-01', 950.00, 'tonnes', 'USD', 'market_observation'),
-- Indian yam prices
('a0000000-0000-0000-0000-00000000030c', 'a0000000-0000-0000-0000-000000000033', 'Sabana Grande Market', '2025-10-15', 220.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-00000000030d', 'a0000000-0000-0000-0000-000000000033', 'Sabana Grande Market', '2025-12-15', 230.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-00000000030e', 'a0000000-0000-0000-0000-000000000033', 'Sabana Grande Market', '2026-02-15', 240.00, 'tonnes', 'USD', 'market_observation'),
('a0000000-0000-0000-0000-00000000030f', 'a0000000-0000-0000-0000-000000000033', 'Santo Domingo Wholesale', '2026-03-01', 250.00, 'tonnes', 'USD', 'market_observation')
ON CONFLICT (id) DO UPDATE SET
    crop_id = EXCLUDED.crop_id,
    market_name = EXCLUDED.market_name,
    price_date = EXCLUDED.price_date,
    price_per_unit = EXCLUDED.price_per_unit,
    unit = EXCLUDED.unit,
    currency = EXCLUDED.currency,
    source = EXCLUDED.source;
