-- ============================================================
-- Pilot Farm Seed Data: Capital Sources & Value Flows
-- Kokonut Demo Farm — Kisumu, Kenya
-- ============================================================

-- Capital Sources
INSERT INTO capital_source (id, name, source_type, description, amount, currency, terms, start_date, end_date, status) VALUES
('a0000000-0000-0000-0000-000000000320', 'Kokonut DAO Grant', 'dao', 'Initial seed funding from Kokonut DAO treasury', 15000.00, 'USD', 'Non-dilutive grant, 10% public goods allocation', '2025-09-01', '2026-08-31', 'active'),
('a0000000-0000-0000-0000-000000000321', 'Farm Revenue Reinvestment', 'revenue', 'Reinvested crop sales revenue', 8000.00, 'USD', 'Self-funded from operations', '2025-10-01', NULL, 'active'),
('a0000000-0000-0000-0000-000000000322', 'Green Bonds DAO Lending', 'partner', 'Green bond proceeds for irrigation infrastructure', 5000.00, 'USD', '3-year term, 5% APR, collateralized by equipment', '2025-11-15', '2028-11-15', 'active'),
('a0000000-0000-0000-0000-000000000323', 'Regen Network Impact Sponsorship', 'sponsorship', 'Impact verification sponsorship for ecological outcomes', 2500.00, 'USD', 'Performance-based, tied to verified ecological gains', '2025-12-01', '2026-11-30', 'active')
ON CONFLICT (id) DO NOTHING;

-- Value Flow Events
INSERT INTO value_flow_event (id, location_id, flow_date, flow_type, from_entity, to_entity, amount, currency, description, verified, verified_at, source_system) VALUES
('a0000000-0000-0000-0000-000000000330', 'a0000000-0000-0000-0000-000000000001', '2025-12-20', 'revenue', 'Nairobi Markets Ltd', 'Kokonut Farm', 5288.80, 'USD', 'Maize cycle 1 sales revenue', TRUE, '2025-12-21 10:00:00+00', 'sales_event'),
('a0000000-0000-0000-0000-000000000331', 'a0000000-0000-0000-0000-000000000001', '2026-01-15', 'revenue', 'Nairobi Markets Ltd', 'Kokonut Farm', 1360.00, 'USD', 'Cassava cycle 1 sales revenue', TRUE, '2026-01-16 10:00:00+00', 'sales_event'),
('a0000000-0000-0000-0000-000000000332', 'a0000000-0000-0000-0000-000000000001', '2026-02-10', 'revenue', 'Nairobi Markets Ltd', 'Kokonut Farm', 4800.00, 'USD', 'Beans cycle 1 sales revenue', TRUE, '2026-02-11 10:00:00+00', 'sales_event'),
('a0000000-0000-0000-0000-000000000333', 'a0000000-0000-0000-0000-000000000001', '2026-03-05', 'revenue', 'Nairobi Markets Ltd', 'Kokonut Farm', 3750.00, 'USD', 'Sweet potato cycle 1 sales revenue', TRUE, '2026-03-06 10:00:00+00', 'sales_event'),
('a0000000-0000-0000-0000-000000000334', 'a0000000-0000-0000-0000-000000000001', '2025-10-05', 'cost', 'Kokonut Farm', 'AgroSupplies Kenya', 480.00, 'USD', 'Seeds and fertilizer purchase', TRUE, '2025-10-06 10:00:00+00', 'expense_event'),
('a0000000-0000-0000-0000-000000000335', 'a0000000-0000-0000-0000-000000000001', '2025-11-01', 'cost', 'Kokonut Farm', 'Various', 600.00, 'USD', 'Labor costs for planting season', TRUE, '2025-11-02 10:00:00+00', 'expense_event'),
('a0000000-0000-0000-0000-000000000336', 'a0000000-0000-0000-0000-000000000001', '2025-12-01', 'cost', 'Kokonut Farm', 'Kisumu Transport Co', 350.00, 'USD', 'Transport and logistics costs', TRUE, '2025-12-02 10:00:00+00', 'expense_event'),
('a0000000-0000-0000-0000-000000000337', 'a0000000-0000-0000-0000-000000000001', '2025-12-31', 'public_goods', 'Kokonut Farm', 'Community Water Project', 1500.00, 'USD', '10% of Q4 revenue allocated to community water infrastructure', TRUE, '2026-01-02 10:00:00+00', 'treasury_event'),
('a0000000-0000-0000-0000-000000000338', 'a0000000-0000-0000-0000-000000000001', '2026-01-10', 'reinvestment', 'Kokonut Farm', 'Farm Operations', 2000.00, 'USD', 'Reinvestment in irrigation infrastructure', TRUE, '2026-01-11 10:00:00+00', 'treasury_event'),
('a0000000-0000-0000-0000-000000000339', 'a0000000-0000-0000-0000-000000000001', '2025-10-01', 'revenue', 'Kokonut DAO', 'Kokonut Farm', 15000.00, 'USD', 'Initial DAO grant for farm establishment', TRUE, '2025-10-02 10:00:00+00', 'treasury_event'),
('a0000000-0000-0000-0000-00000000033a', 'a0000000-0000-0000-0000-000000000001', '2025-12-15', 'revenue', 'Regen Network', 'Kokonut Farm', 2500.00, 'USD', 'Impact verification sponsorship payment', TRUE, '2025-12-16 10:00:00+00', 'digital_lego_usage')
ON CONFLICT (id) DO NOTHING;

-- Cash Flow Snapshots
INSERT INTO cash_flow_snapshot (id, location_id, period_start, period_end, total_revenue, capital_inflows, grants_received, total_inflows, total_operating_expenses, total_capex, loan_repayments, public_goods_allocation, total_outflows, net_cash_flow, running_balance, calculation_version, inputs) VALUES
('a0000000-0000-0000-0000-000000000340', 'a0000000-0000-0000-0000-000000000001', '2025-10-01', '2025-12-31', 15198.80, 15000.00, 15000.00, 30198.80, 4800.00, 2000.00, 0.00, 1500.00, 8300.00, 21898.80, 21898.80, '1.0', '{"period": "Q4 2025"}'),
('a0000000-0000-0000-0000-000000000341', 'a0000000-0000-0000-0000-000000000001', '2026-01-01', '2026-03-31', 8550.00, 0.00, 0.00, 8550.00, 3200.00, 500.00, 0.00, 855.00, 4555.00, 3995.00, 25893.80, '1.0', '{"period": "Q1 2026"}')
ON CONFLICT (id) DO NOTHING;
