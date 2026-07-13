-- ============================================================
-- 102_improvement_metrics_config.sql — Meta-learning & improvement seeds
-- ============================================================
-- Seeds meta-learning strategies and default tracked improvement metrics.

-- Meta-learning strategies
INSERT INTO meta_learning_strategy (
    strategy_name, strategy_type, domain, context_conditions,
    effectiveness_score, enabled
) VALUES
('Raise threshold on false positives', 'threshold_tuning', NULL,
 '{"trigger":"false_positive_rate_high","condition":"fp_rate > 0.3"}', 0.0, TRUE),
('Lower threshold on false negatives', 'threshold_tuning', NULL,
 '{"trigger":"false_negative_rate_high","condition":"fn_rate > 0.3"}', 0.0, TRUE),
('Retrain model on accuracy drop', 'model_retraining', NULL,
 '{"trigger":"accuracy_degradation","condition":"mape_increase > 5.0"}', 0.0, TRUE),
('Increase sampling frequency on anomaly', 'sampling_adjustment', NULL,
 '{"trigger":"anomaly_detected","condition":"severity >= high"}', 0.0, TRUE),
('Decrease sampling on stable metrics', 'sampling_adjustment', NULL,
 '{"trigger":"stable_period","condition":"variance < threshold for 7 days"}', 0.0, TRUE),
('Switch to alternative approach on failure streak', 'approach_switch', NULL,
 '{"trigger":"consecutive_failures","condition":"count >= 3"}', 0.0, TRUE),
('Transfer insight cross-domain on pattern match', 'cross_domain_transfer', NULL,
 '{"trigger":"pattern_detected","condition":"correlation > 0.7"}', 0.0, TRUE),
('Escalate to human on system degradation', 'escalation', NULL,
 '{"trigger":"system_degradation","condition":"velocity_status == stalled"}', 0.0, TRUE)
ON CONFLICT DO NOTHING;
