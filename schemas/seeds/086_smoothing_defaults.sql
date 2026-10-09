-- ============================================================
-- 086_smoothing_defaults.sql — Default smoothing configurations
-- ============================================================

INSERT INTO smoothing_config (metric_key, location_id, smoothing_type, window_size, alpha, is_enabled) VALUES
('soil_carbon_delta', NULL, 'exponential', 7, 0.3, TRUE),
('water_resilience', NULL, 'exponential', 7, 0.3, TRUE),
('biodiversity_delta', NULL, 'exponential', 14, 0.3, TRUE),
('value_flowed', NULL, 'exponential', 7, 0.3, TRUE),
('crop_revenue', NULL, 'exponential', 7, 0.3, TRUE),
('operating_margin_pct', NULL, 'exponential', 7, 0.3, TRUE),
('soil_moisture', NULL, 'moving_average', 5, 0.3, TRUE),
('air_temperature', NULL, 'moving_average', 5, 0.3, TRUE),
('humidity', NULL, 'moving_average', 5, 0.3, TRUE)
ON CONFLICT (metric_key, location_id, smoothing_type) DO NOTHING;
