-- ============================================================
-- 081_adaptive_thresholds.sql — Initial adaptive thresholds
-- ============================================================
-- Seeds initial adaptive thresholds for the feedback controller.

INSERT INTO adaptive_threshold (
    threshold_key, entity_type, entity_id, location_id,
    threshold_name, current_value, baseline_value,
    min_value, max_value, adaptation_rate,
    is_enabled
) VALUES
(
    'anomaly_sensitivity_default',
    'anomaly_sensitivity',
    NULL, NULL,
    'Anomaly Detection Sensitivity',
    '{"sensitivity": 1.0}'::jsonb,
    '{"sensitivity": 1.0}'::jsonb,
    '{"sensitivity": 0.3}'::jsonb,
    '{"sensitivity": 3.0}'::jsonb,
    0.1,
    TRUE
),
(
    'crisp_weight_carbon_yield_default',
    'crisp_weight',
    NULL, NULL,
    'CRISP Carbon Yield Weight',
    '{"weight": 0.40}'::jsonb,
    '{"weight": 0.40}'::jsonb,
    '{"weight": 0.20}'::jsonb,
    '{"weight": 0.60}'::jsonb,
    0.05,
    TRUE
),
(
    'crisp_weight_climate_default',
    'crisp_weight',
    NULL, NULL,
    'CRISP Climate Weight',
    '{"weight": 0.25}'::jsonb,
    '{"weight": 0.25}'::jsonb,
    '{"weight": 0.10}'::jsonb,
    '{"weight": 0.40}'::jsonb,
    0.05,
    TRUE
),
(
    'sampling_rate_soil_moisture_default',
    'sampling_rate',
    NULL, NULL,
    'Soil Moisture Sampling Rate',
    '{"interval_minutes": 15}'::jsonb,
    '{"interval_minutes": 15}'::jsonb,
    '{"interval_minutes": 1}'::jsonb,
    '{"interval_minutes": 60}'::jsonb,
    0.5,
    TRUE
),
(
    'score_band_warning_default',
    'score_band',
    NULL, NULL,
    'Warning Score Band',
    '{"lower": 30, "upper": 60}'::jsonb,
    '{"lower": 30, "upper": 60}'::jsonb,
    '{"lower": 10, "upper": 80}'::jsonb,
    '{"lower": 50, "upper": 70}'::jsonb,
    0.1,
    TRUE
)
ON CONFLICT (threshold_key) DO NOTHING;
