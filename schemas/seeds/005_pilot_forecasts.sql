-- ============================================================
-- Pilot Farm Seed Data: Forecast Scenarios & Outputs
-- Kokonut Demo Farm — Kisumu, Kenya
-- ============================================================

-- Forecast Scenarios (columns: id, name, description, scenario_type, location_id, assumptions, price_assumptions, yield_assumptions, cost_assumptions, growth_assumptions, version, parent_scenario_id, status)
INSERT INTO forecast_scenario (id, name, description, scenario_type, location_id, assumptions, price_assumptions, yield_assumptions, cost_assumptions, growth_assumptions, version, status) VALUES
('a0000000-0000-0000-0000-000000000080', 'Baseline Forecast 2026', 'Base case scenario using historical averages and current market prices', 'baseline', 'a0000000-0000-0000-0000-000000000001',
 '{"period":"2026-04-01 to 2027-03-31","inflation_rate":0.05,"exchange_rate_usd_kes":155,"discount_rate":0.12}',
 '{"maize_per_tonne_usd":280,"cassava_per_tonne_usd":180,"beans_per_tonne_usd":650,"sweet_potato_per_tonne_usd":220}',
 '{"maize_yield_tonne_ha":2.8,"cassava_yield_tonne_ha":7.5,"beans_yield_tonne_ha":1.1,"sweet_potato_yield_tonne_ha":5.5}',
 '{"fertilizer_usd_per_ha":120,"seeds_usd_per_ha":80,"labor_usd_per_ha":200,"irrigation_usd_per_ha":60}',
 '{"area_growth_pct":0.10,"yield_improvement_pct":0.05,"price_appreciation_pct":0.08}',
 1, 'published'),
('a0000000-0000-0000-0000-000000000081', 'Optimistic Forecast 2026', 'Best case with premium prices, high yields, and expanded area', 'optimistic', 'a0000000-0000-0000-0000-000000000001',
 '{"period":"2026-04-01 to 2027-03-31","inflation_rate":0.04,"exchange_rate_usd_kes":150,"discount_rate":0.10}',
 '{"maize_per_tonne_usd":320,"cassava_per_tonne_usd":210,"beans_per_tonne_usd":750,"sweet_potato_per_tonne_usd":260}',
 '{"maize_yield_tonne_ha":3.2,"cassava_yield_tonne_ha":8.5,"beans_yield_tonne_ha":1.3,"sweet_potato_yield_tonne_ha":6.2}',
 '{"fertilizer_usd_per_ha":100,"seeds_usd_per_ha":70,"labor_usd_per_ha":180,"irrigation_usd_per_ha":50}',
 '{"area_growth_pct":0.20,"yield_improvement_pct":0.12,"price_appreciation_pct":0.15}',
 1, 'draft'),
('a0000000-0000-0000-0000-000000000082', 'Conservative Forecast 2026', 'Downside scenario with lower yields, drought risk, and flat prices', 'conservative', 'a0000000-0000-0000-0000-000000000001',
 '{"period":"2026-04-01 to 2027-03-31","inflation_rate":0.07,"exchange_rate_usd_kes":160,"discount_rate":0.15,"drought_probability":0.25}',
 '{"maize_per_tonne_usd":250,"cassava_per_tonne_usd":160,"beans_per_tonne_usd":580,"sweet_potato_per_tonne_usd":190}',
 '{"maize_yield_tonne_ha":2.2,"cassava_yield_tonne_ha":6.5,"beans_yield_tonne_ha":0.9,"sweet_potato_yield_tonne_ha":4.5}',
 '{"fertilizer_usd_per_ha":140,"seeds_usd_per_ha":90,"labor_usd_per_ha":220,"irrigation_usd_per_ha":70}',
 '{"area_growth_pct":0.05,"yield_improvement_pct":0.02,"price_appreciation_pct":0.03}',
 1, 'draft')
ON CONFLICT (id) DO NOTHING;

-- Forecast Outputs (columns: id, scenario_id, location_id, crop_cycle_id, metric_name, period_start, period_end, value, unit, confidence_low, confidence_high, confidence_level, calculation_version, calculated_at, inputs)
-- Baseline scenario outputs
INSERT INTO forecast_output (id, scenario_id, location_id, metric_name, period_start, period_end, value, unit, confidence_low, confidence_high, confidence_level, calculation_version, calculated_at, inputs) VALUES
-- Revenue forecasts
('a0000000-0000-0000-0000-000000000200', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000001', 'projected_revenue_usd', '2026-04-01', '2027-03-31', 18200.00, 'usd', 15500.00, 21000.00, 0.80, 'v1.0', NOW(), '{"maize_area":4.4,"cassava_area":3.3,"beans_area":2.2,"sweet_potato_area":2.2}'),
('a0000000-0000-0000-0000-000000000201', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000001', 'projected_noi_usd', '2026-04-01', '2027-03-31', 5800.00, 'usd', 3500.00, 8200.00, 0.80, 'v1.0', NOW(), '{"revenue":18200,"total_costs":12400}'),
('a0000000-0000-0000-0000-000000000202', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000001', 'operating_margin_pct', '2026-04-01', '2027-03-31', 31.87, 'pct', 22.50, 39.00, 0.80, 'v1.0', NOW(), '{"noi":5800,"revenue":18200}'),
('a0000000-0000-0000-0000-000000000203', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000001', 'total_yield_tonnes', '2026-04-01', '2027-03-31', 48.50, 'tonnes', 40.00, 56.00, 0.80, 'v1.0', NOW(), '{"maize":12.32,"cassava":24.75,"beans":2.42,"sweet_potato":12.10}'),
('a0000000-0000-0000-0000-000000000204', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000001', 'projected_cash_flow_usd', '2026-04-01', '2027-03-31', 4200.00, 'usd', 2000.00, 6500.00, 0.75, 'v1.0', NOW(), '{"noi":5800,"capex":1600}'),
('a0000000-0000-0000-0000-000000000205', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000001', 'public_goods_allocation_usd', '2026-04-01', '2027-03-31', 1820.00, 'usd', 1550.00, 2100.00, 0.80, 'v1.0', NOW(), '{"revenue":18200,"allocation_pct":0.10}'),
('a0000000-0000-0000-0000-000000000206', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000001', 'ecological_score_forecast', '2026-04-01', '2027-03-31', 78.00, 'score', 70.00, 85.00, 0.75, 'v1.0', NOW(), '{"current_ndvi":0.62,"soil_organic_matter":3.3,"water_efficiency":0.85}'),
('a0000000-0000-0000-0000-000000000207', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000001', 'risk_adjusted_noi_usd', '2026-04-01', '2027-03-31', 4930.00, 'usd', 3000.00, 7000.00, 0.80, 'v1.0', NOW(), '{"noi":5800,"risk_factor":0.85}'),

-- Optimistic scenario outputs
('a0000000-0000-0000-0000-000000000210', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000001', 'projected_revenue_usd', '2026-04-01', '2027-03-31', 24500.00, 'usd', 21000.00, 28000.00, 0.80, 'v1.0', NOW(), '{"maize_area":4.8,"cassava_area":3.6,"beans_area":2.4,"sweet_potato_area":2.4}'),
('a0000000-0000-0000-0000-000000000211', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000001', 'projected_noi_usd', '2026-04-01', '2027-03-31', 9200.00, 'usd', 7000.00, 11500.00, 0.80, 'v1.0', NOW(), '{"revenue":24500,"total_costs":15300}'),
('a0000000-0000-0000-0000-000000000212', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000001', 'operating_margin_pct', '2026-04-01', '2027-03-31', 37.55, 'pct', 30.00, 44.00, 0.80, 'v1.0', NOW(), '{"noi":9200,"revenue":24500}'),
('a0000000-0000-0000-0000-000000000213', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000001', 'total_yield_tonnes', '2026-04-01', '2027-03-31', 58.50, 'tonnes', 50.00, 66.00, 0.80, 'v1.0', NOW(), '{"maize":15.36,"cassava":30.60,"beans":3.12,"sweet_potato":14.88}'),
('a0000000-0000-0000-0000-000000000214', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000001', 'projected_cash_flow_usd', '2026-04-01', '2027-03-31', 7000.00, 'usd', 5000.00, 9000.00, 0.75, 'v1.0', NOW(), '{"noi":9200,"capex":2200}'),
('a0000000-0000-0000-0000-000000000215', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000001', 'public_goods_allocation_usd', '2026-04-01', '2027-03-31', 2450.00, 'usd', 2100.00, 2800.00, 0.80, 'v1.0', NOW(), '{"revenue":24500,"allocation_pct":0.10}'),
('a0000000-0000-0000-0000-000000000216', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000001', 'ecological_score_forecast', '2026-04-01', '2027-03-31', 85.00, 'score', 78.00, 90.00, 0.75, 'v1.0', NOW(), '{"current_ndvi":0.62,"soil_organic_matter":3.5,"water_efficiency":0.90}'),
('a0000000-0000-0000-0000-000000000217', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000001', 'risk_adjusted_noi_usd', '2026-04-01', '2027-03-31', 7820.00, 'usd', 6000.00, 9800.00, 0.80, 'v1.0', NOW(), '{"noi":9200,"risk_factor":0.85}'),

-- Conservative scenario outputs
('a0000000-0000-0000-0000-000000000220', 'a0000000-0000-0000-0000-000000000082', 'a0000000-0000-0000-0000-000000000001', 'projected_revenue_usd', '2026-04-01', '2027-03-31', 13800.00, 'usd', 11000.00, 16500.00, 0.80, 'v1.0', NOW(), '{"maize_area":4.2,"cassava_area":3.15,"beans_area":2.1,"sweet_potato_area":2.1}'),
('a0000000-0000-0000-0000-000000000221', 'a0000000-0000-0000-0000-000000000082', 'a0000000-0000-0000-0000-000000000001', 'projected_noi_usd', '2026-04-01', '2027-03-31', 2800.00, 'usd', 1000.00, 4500.00, 0.80, 'v1.0', NOW(), '{"revenue":13800,"total_costs":11000}'),
('a0000000-0000-0000-0000-000000000222', 'a0000000-0000-0000-0000-000000000082', 'a0000000-0000-0000-0000-000000000001', 'operating_margin_pct', '2026-04-01', '2027-03-31', 20.29, 'pct', 9.00, 27.00, 0.80, 'v1.0', NOW(), '{"noi":2800,"revenue":13800}'),
('a0000000-0000-0000-0000-000000000223', 'a0000000-0000-0000-0000-000000000082', 'a0000000-0000-0000-0000-000000000001', 'total_yield_tonnes', '2026-04-01', '2027-03-31', 37.00, 'tonnes', 28.00, 44.00, 0.80, 'v1.0', NOW(), '{"maize":9.24,"cassava":20.48,"beans":1.89,"sweet_potato":9.45}'),
('a0000000-0000-0000-0000-000000000224', 'a0000000-0000-0000-0000-000000000082', 'a0000000-0000-0000-0000-000000000001', 'projected_cash_flow_usd', '2026-04-01', '2027-03-31', 1800.00, 'usd', 200.00, 3500.00, 0.75, 'v1.0', NOW(), '{"noi":2800,"capex":1000}'),
('a0000000-0000-0000-0000-000000000225', 'a0000000-0000-0000-0000-000000000082', 'a0000000-0000-0000-0000-000000000001', 'public_goods_allocation_usd', '2026-04-01', '2027-03-31', 1380.00, 'usd', 1100.00, 1650.00, 0.80, 'v1.0', NOW(), '{"revenue":13800,"allocation_pct":0.10}'),
('a0000000-0000-0000-0000-000000000226', 'a0000000-0000-0000-0000-000000000082', 'a0000000-0000-0000-0000-000000000001', 'ecological_score_forecast', '2026-04-01', '2027-03-31', 65.00, 'score', 55.00, 72.00, 0.75, 'v1.0', NOW(), '{"current_ndvi":0.62,"soil_organic_matter":3.1,"water_efficiency":0.75,"drought_impact":-0.15}'),
('a0000000-0000-0000-0000-000000000227', 'a0000000-0000-0000-0000-000000000082', 'a0000000-0000-0000-0000-000000000001', 'risk_adjusted_noi_usd', '2026-04-01', '2027-03-31', 2100.00, 'usd', 750.00, 3400.00, 0.80, 'v1.0', NOW(), '{"noi":2800,"risk_factor":0.75}')
ON CONFLICT (id) DO NOTHING;

-- NOI Snapshots (columns: id, crop_cycle_id, location_id, period_start, period_end, gross_revenue, returns_and_discounts, net_revenue, direct_crop_costs, allocated_shared_costs, total_costs, noi, operating_margin_pct, loss_rate_pct, calculation_version, calculated_at, inputs)
INSERT INTO noi_snapshot (id, crop_cycle_id, location_id, period_start, period_end, gross_revenue, returns_and_discounts, net_revenue, direct_crop_costs, allocated_shared_costs, total_costs, noi, operating_margin_pct, loss_rate_pct, calculation_version, calculated_at, inputs) VALUES
('a0000000-0000-0000-0000-000000000300', 'a0000000-0000-0000-0000-000000000040', 'a0000000-0000-0000-0000-000000000001', '2025-10-01', '2025-12-31', 9788.80, 200.00, 9588.80, 4200.00, 1800.00, 6000.00, 3588.80, 37.43, 5.00, 'v1.0', NOW(), '{"harvest_qty":34.96,"price_per_tonne":280,"loss_amount":1.75}'),
('a0000000-0000-0000-0000-000000000301', 'a0000000-0000-0000-0000-000000000041', 'a0000000-0000-0000-0000-000000000001', '2026-01-01', '2026-03-31', 8870.40, 150.00, 8720.40, 3800.00, 1600.00, 5400.00, 3320.40, 38.09, 5.00, 'v1.0', NOW(), '{"harvest_qty":31.68,"price_per_tonne":280,"loss_amount":1.58}'),
('a0000000-0000-0000-0000-000000000302', 'a0000000-0000-0000-0000-000000000042', 'a0000000-0000-0000-0000-000000000001', '2025-10-01', '2026-03-31', 3848.40, 100.00, 3748.40, 1800.00, 800.00, 2600.00, 1148.40, 30.64, 3.00, 'v1.0', NOW(), '{"harvest_qty":21.38,"price_per_tonne":180,"loss_amount":0.64}'),
('a0000000-0000-0000-0000-000000000303', 'a0000000-0000-0000-0000-000000000043', 'a0000000-0000-0000-0000-000000000001', '2025-10-10', '2025-12-08', 2210.00, 0.00, 2210.00, 120.00, 282.35, 402.35, 1807.65, 81.79, 12.00, 'v1.0', NOW(), '{"harvest_qty":2.21,"price_per_tonne":900,"loss_amount":0.30}'),
('a0000000-0000-0000-0000-000000000304', 'a0000000-0000-0000-0000-000000000044', 'a0000000-0000-0000-0000-000000000001', '2025-11-01', '2026-02-28', 2538.00, 0.00, 2538.00, 80.00, 282.35, 362.35, 2175.65, 85.73, 7.80, 'v1.0', NOW(), '{"harvest_qty":9.40,"price_per_tonne":270,"loss_amount":0.80}'),
('a0000000-0000-0000-0000-000000000305', 'a0000000-0000-0000-0000-000000000045', 'a0000000-0000-0000-0000-000000000001', '2026-01-10', '2026-03-08', 1881.00, 0.00, 1881.00, 95.00, 282.35, 377.35, 1503.65, 79.94, 0.00, 'v1.0', NOW(), '{"harvest_qty":1.98,"price_per_tonne":950,"loss_amount":0}')
ON CONFLICT (id) DO NOTHING;
