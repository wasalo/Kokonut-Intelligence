-- ============================================================
-- 085_trend_monitor_defaults.sql — Default trend monitoring configs
-- ============================================================

INSERT INTO trend_monitor_config (metric_key, min_data_points, time_unit, trend_window_days, smoothing_window, smoothing_alpha, seasonal_period, forecast_horizon, description) VALUES
('soil_carbon_delta', 10, 'day', 365, 7, 0.3, NULL, 90, 'Soil carbon change tracking'),
('water_resilience', 10, 'day', 365, 7, 0.3, 365, 60, 'Water resilience monitoring'),
('biodiversity_delta', 10, 'day', 365, 14, 0.3, NULL, 90, 'Biodiversity change tracking'),
('value_flowed', 5, 'day', 180, 7, 0.3, 12, 30, 'Value flow monitoring'),
('crop_revenue', 5, 'day', 365, 7, 0.3, 12, 30, 'Revenue trend tracking'),
('operating_margin_pct', 5, 'day', 180, 7, 0.3, NULL, 30, 'Operating margin tracking'),
('attestation_coverage', 10, 'day', 365, 14, 0.3, NULL, 90, 'Attestation coverage tracking'),
('wallet_retention', 10, 'day', 365, 14, 0.3, NULL, 90, 'Wallet retention tracking')
ON CONFLICT (metric_key) DO NOTHING;
