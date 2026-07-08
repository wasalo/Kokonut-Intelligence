-- ============================================================
-- 069_demand_analysis.sql — Seeds: metrics, pilot data, config
-- ============================================================

-- ============================================================================
-- METRICS
-- ============================================================================

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables,
    inclusion_rules, exclusion_rules, unit, data_type, owner, version,
    update_frequency, active, validation_tests, report_usage, deprecation_policy
) VALUES
('demand_coverage_pct', 'Demand Coverage %',
 'Percentage of projected production with confirmed buyer demand.',
 'confirmed_demand_tonnes / projected_production_tonnes * 100',
 ARRAY['production_market_match', 'demand_forecast', 'forecast_output'],
 'Only verified/published match records', 'Exclude exploratory buyer signals',
 'percentage', 'numeric', 'Demand Analytics Guild', 1, 'weekly', TRUE,
 '["0 <= value <= 100"]'::jsonb, ARRAY['demand_analysis', 'demand_sizing'],
 'Supersede through metric_version before changing public interpretation.'),
('buyer_pipeline_value', 'Buyer Pipeline Value',
 'Total value of active buyer demand signals (firm + probable).',
 'SUM(price_offered * quantity_requested) WHERE commitment_level IN (''firm'', ''probable'') AND status != ''rejected''',
 ARRAY['buyer_demand_signal'],
 'Only firm and probable signals', 'Exclude exploratory and possible signals',
 'currency', 'numeric', 'Demand Analytics Guild', 1, 'weekly', TRUE,
 '["value >= 0"]'::jsonb, ARRAY['demand_analysis'],
 'Supersede through metric_version before changing public interpretation.'),
('market_penetration_pct', 'Market Penetration %',
 'Serviceable Obtainable Market achieved as percentage of total SOM.',
 'achieved_revenue / som_value * 100',
 ARRAY['market_size_estimate', 'sales_event'],
 'Only verified market size estimates', 'None',
 'percentage', 'numeric', 'Demand Analytics Guild', 1, 'monthly', TRUE,
 '["0 <= value <= 100"]'::jsonb, ARRAY['demand_sizing'],
 'Supersede through metric_version before changing public interpretation.'),
('demand_supply_gap_tonnes', 'Demand-Supply Gap (tonnes)',
 'Net gap between total demand and projected production (negative = surplus).',
 'total_demand_tonnes - projected_production_tonnes',
 ARRAY['production_market_match'],
 'Only verified match records', 'None',
 'tonnes', 'numeric', 'Demand Analytics Guild', 1, 'weekly', TRUE,
 '[]'::jsonb, ARRAY['demand_analysis'],
 'Supersede through metric_version before changing public interpretation.'),
('buyer_retention_rate', 'Buyer Retention Rate',
 'Percentage of buyers from prior period who placed orders in current period.',
 'COUNT(buyers_active_both_periods) / COUNT(buyers_active_prior_period) * 100',
 ARRAY['sales_event', 'partner'],
 'Only verified/published sales', 'Exclude one-time buyers',
 'percentage', 'numeric', 'Demand Analytics Guild', 1, 'monthly', TRUE,
 '["0 <= value <= 100"]'::jsonb, ARRAY['demand_analysis'],
 'Supersede through metric_version before changing public interpretation.'),
('demand_seasonality_index', 'Demand Seasonality Index',
 'Peak-to-trough ratio of monthly demand (higher = more seasonal).',
 'max_monthly_avg / min_monthly_avg',
 ARRAY['demand_trend'],
 'Only verified trend analysis with 12+ months data', 'None',
 'ratio', 'numeric', 'Demand Analytics Guild', 1, 'quarterly', TRUE,
 '["value >= 1"]'::jsonb, ARRAY['demand_analysis'],
 'Supersede through metric_version before changing public interpretation.'),
('buyer_diversification_score', 'Buyer Diversification Score',
 'Herfindahl-Hirschman Index inverse for buyer concentration (0-100, higher = more diversified).',
 '(1 - SUM(share_i^2)) * 100',
 ARRAY['sales_event', 'partner'],
 'Only verified/published sales', 'None',
 'score', 'numeric', 'Demand Analytics Guild', 1, 'monthly', TRUE,
 '["0 <= value <= 100"]'::jsonb, ARRAY['demand_analysis'],
 'Supersede through metric_version before changing public interpretation.')
ON CONFLICT (metric_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    formula = EXCLUDED.formula,
    source_tables = EXCLUDED.source_tables,
    inclusion_rules = EXCLUDED.inclusion_rules,
    exclusion_rules = EXCLUDED.exclusion_rules,
    unit = EXCLUDED.unit,
    data_type = EXCLUDED.data_type,
    owner = EXCLUDED.owner,
    update_frequency = EXCLUDED.update_frequency,
    active = EXCLUDED.active,
    validation_tests = EXCLUDED.validation_tests,
    report_usage = EXCLUDED.report_usage,
    deprecation_policy = EXCLUDED.deprecation_policy,
    updated_at = NOW();

-- ============================================================================
-- PILOT DATA: Buyer Demand Signals
-- ============================================================================

INSERT INTO buyer_demand_signal (
    id, location_id, partner_id, crop_id, buyer_name, buyer_type,
    signal_type, signal_date, expected_delivery_start, expected_delivery_end,
    quantity_requested, unit, price_offered, currency,
    recurring, recurrence_pattern, commitment_level, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000700',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000053',
 NULL,
 'Adelphi Fresh Buyers', 'processor',
 'recurring_order', '2026-03-01', '2026-04-01', '2026-06-30',
 10.00, 'tonnes', 220.00, 'USD',
 TRUE, 'monthly', 'firm', 'published',
 'pilot_seed', 'adelphi-demand-001',
 '{"record_type":"buyer_demand_signal","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000701',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000054',
 NULL,
 'DirectFarm Dominican Republic', 'direct',
 'written_order', '2026-03-15', '2026-04-15', '2026-05-15',
 5.00, 'tonnes', 950.00, 'USD',
 FALSE, NULL, 'firm', 'published',
 'pilot_seed', 'adelphi-demand-002',
 '{"record_type":"buyer_demand_signal","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000702',
 'a0000000-0000-0000-0000-000000000001',
 NULL,
 NULL,
 'Santo Domingo Market Cooperative', 'market',
 'forecast_request', '2026-04-01', '2026-07-01', '2026-09-30',
 15.00, 'tonnes', 180.00, 'USD',
 TRUE, 'seasonal', 'probable', 'published',
 'pilot_seed', 'adelphi-demand-003',
 '{"record_type":"buyer_demand_signal","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000703',
 'a0000000-0000-0000-0000-000000000001',
 NULL,
 NULL,
 'Caribbean Greens Restaurant Group', 'restaurant',
 'verbal_intent', '2026-04-10', '2026-05-01', '2026-08-31',
 2.00, 'tonnes', 1200.00, 'USD',
 TRUE, 'weekly', 'possible', 'submitted',
 'pilot_seed', 'adelphi-demand-004',
 '{"record_type":"buyer_demand_signal","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    buyer_name = EXCLUDED.buyer_name,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- PILOT DATA: Market Size Estimates
-- ============================================================================

INSERT INTO market_size_estimate (
    id, location_id, crop_id, market_name, market_scope,
    tam_value, tam_unit, tam_source,
    sam_value, sam_unit, sam_source,
    som_value, som_unit, som_source,
    market_penetration_pct, market_share_pct,
    annual_growth_rate_pct, estimation_method,
    confidence_level, assessment_date, period_start, period_end, status,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000710',
 'a0000000-0000-0000-0000-000000000001',
 NULL,
 'Lettuce Market - Greater Santo Domingo', 'regional',
 500000.00, 'usd', 'MINAGRD regional production statistics; INEPI market survey 2025',
 125000.00, 'usd', 'Accessible buyers within 60km radius, organic/regenerative premium channels',
 25000.00, 'usd', 'Current Adelphi revenue + committed pipeline',
 5.00, 20.00,
 8.00, 'bottom_up',
 'medium', '2026-04-01', '2026-01-01', '2026-12-31', 'published',
 'pilot_seed', 'adelphi-market-001',
 '{"record_type":"market_size_estimate","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000000711',
 'a0000000-0000-0000-0000-000000000001',
 NULL,
 'Leafy Greens Market - DR National', 'national',
 2000000.00, 'usd', 'DGDA national leafy greens market report 2025',
 400000.00, 'usd', 'Organic and premium segments accessible from Sabana Grande',
 45000.00, 'usd', 'Adelphi actual + projected from buyer pipeline',
 2.25, 11.25,
 6.00, 'hybrid',
 'low', '2026-04-01', '2026-01-01', '2026-12-31', 'published',
 'pilot_seed', 'adelphi-market-002',
 '{"record_type":"market_size_estimate","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    tam_value = EXCLUDED.tam_value,
    sam_value = EXCLUDED.sam_value,
    som_value = EXCLUDED.som_value,
    market_penetration_pct = EXCLUDED.market_penetration_pct,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- REVENUE MULTIPLIER CONFIG
-- ============================================================================

INSERT INTO revenue_multiplier_config (config_key, config_value, description) VALUES
('demand_forecast_horizon_months', '12', 'Default forecast horizon in months'),
('demand_confidence_threshold', '0.80', 'Minimum confidence level for demand forecasts'),
('market_sizing_refresh_months', '6', 'How often to refresh market size estimates'),
('buyer_churn_threshold_days', '90', 'Days without order before marking buyer as churned'),
('buyer_at_risk_threshold_days', '45', 'Days without order before flagging buyer as at_risk'),
('demand_signal_weight', '0.3', 'Weight of buyer signals vs historical in demand forecast')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    description = EXCLUDED.description,
    updated_at = NOW();
