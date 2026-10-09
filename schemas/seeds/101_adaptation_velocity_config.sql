-- ============================================================
-- 101_adaptation_velocity_config.sql — Adaptation config seeds
-- ============================================================
-- Seeds default feedback automation config and cross-domain rules.

-- Default feedback automation config (global, location_id = NULL)
INSERT INTO feedback_automation_config (
    location_id, eval_interval_hours, max_adjustments_per_run,
    auto_apply, dry_run, enabled
) VALUES (
    NULL, 24, 5, FALSE, TRUE, TRUE
) ON CONFLICT (location_id) DO NOTHING;

-- Cross-domain insight transfer rules
INSERT INTO cross_domain_rule (
    source_domain, target_domain, source_event_pattern,
    target_action_template, confidence
) VALUES
('pest_management', 'irrigation', 'pest_outbreak_detected',
 '{"action":"adjust_irrigation","reason":"pest stress increases water demand","factor":1.2}', 0.6),
('pest_management', 'weather', 'pest_outbreak_correlated_weather',
 '{"action":"update_weather_rules","reason":"validate weather-pest correlation"}', 0.7),
('weather', 'irrigation', 'heavy_rain_predicted',
 '{"action":"skip_irrigation","reason":"rain forecast within 48h"}', 0.8),
('weather', 'planting', 'frost_warning',
 '{"action":"delay_planting","reason":"frost risk to seedlings"}', 0.9),
('irrigation', 'nutrient', 'overwatering_detected',
 '{"action":"check_leaching_risk","reason":"excess water may leach nutrients"}', 0.5),
('nutrient', 'crop_health', 'nitrogen_deficiency',
 '{"action":"increase_nitrogen_input","reason":"leaf analysis confirms deficiency"}', 0.8),
('crop_health', 'pest_management', 'disease_detected',
 '{"action":"assess_pest_pathway","reason":"disease may indicate pest-vectored pathogen"}', 0.6),
('marketplace', 'planting', 'high_price_forecast',
 '{"action":"expand_planting_area","reason":"favorable market for next harvest"}', 0.4),
('energy', 'irrigation', 'solar_surplus',
 '{"action":"run_irrigation_pumps","reason":"excess solar available for pumping"}', 0.7)
ON CONFLICT DO NOTHING;

-- ML retrain schedules
INSERT INTO ml_retrain_schedule (
    model_name, retrain_interval_days, accuracy_threshold,
    auto_retrain, enabled
) VALUES
('yield_forecast', 30, 15.0, FALSE, TRUE),
('weather_anomaly', 60, 25.0, FALSE, TRUE),
('soil_moisture_forecast', 14, 12.0, FALSE, TRUE),
('pest_outbreak_prediction', 30, 20.0, FALSE, TRUE),
('advisory_effectiveness', 30, 30.0, FALSE, TRUE)
ON CONFLICT (model_name, COALESCE(location_id, '00000000-0000-0000-0000-000000000000'::uuid))
DO NOTHING;
