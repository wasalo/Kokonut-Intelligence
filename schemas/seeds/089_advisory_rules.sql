DO $$
BEGIN
    -- ============================================================
    -- Advisory Rules (8 default rules)
    -- ============================================================

    -- 1. Soil Moisture Low
    INSERT INTO advisory_rule (
        id, location_id, name, description, rule_type,
        metric_source, threshold_value, threshold_operator,
        severity, recommendation_template, action_category,
        notification_channels
    ) VALUES (
        '00000000-0000-0000-0000-000000000089',
        NULL,
        'Soil Moisture Low',
        'Alert when soil moisture drops below 30% of field capacity',
        'threshold',
        'soil_moisture',
        30,
        '<',
        'warning',
        'Soil moisture is critically low. Consider irrigation within 24 hours. Current reading: {current_value}%. Recommended: {recommended_action}.',
        'irrigation',
        '["sms", "dashboard"]'
    ) ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        threshold_value = EXCLUDED.threshold_value,
        recommendation_template = EXCLUDED.recommendation_template,
        updated_at = NOW();

    -- 2. Soil Moisture Critical
    INSERT INTO advisory_rule (
        id, location_id, name, description, rule_type,
        metric_source, threshold_value, threshold_operator,
        severity, recommendation_template, action_category,
        notification_channels
    ) VALUES (
        '00000000-0000-0000-0000-000000000090',
        NULL,
        'Soil Moisture Critical',
        'Alert when soil moisture drops below 15% of field capacity',
        'threshold',
        'soil_moisture',
        15,
        '<',
        'critical',
        'URGENT: Soil moisture critically low at {current_value}%. Immediate irrigation required. Potential crop stress imminent.',
        'irrigation',
        '["sms", "dashboard", "email"]'
    ) ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        threshold_value = EXCLUDED.threshold_value,
        recommendation_template = EXCLUDED.recommendation_template,
        updated_at = NOW();

    -- 3. Heat Stress
    INSERT INTO advisory_rule (
        id, location_id, name, description, rule_type,
        metric_source, threshold_value, threshold_operator,
        severity, recommendation_template, action_category,
        notification_channels
    ) VALUES (
        '00000000-0000-0000-0000-000000000091',
        NULL,
        'Heat Stress',
        'Alert when temperature exceeds 35°C',
        'threshold',
        'air_temperature',
        35,
        '>',
        'warning',
        'Temperature at {current_value}°C exceeds heat stress threshold. Consider shade structures or misting. Monitor crop condition.',
        'heat_management',
        '["sms", "dashboard"]'
    ) ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        threshold_value = EXCLUDED.threshold_value,
        recommendation_template = EXCLUDED.recommendation_template,
        updated_at = NOW();

    -- 4. Nitrogen Deficiency
    INSERT INTO advisory_rule (
        id, location_id, name, description, rule_type,
        metric_source, threshold_value, threshold_operator,
        severity, recommendation_template, action_category,
        notification_channels
    ) VALUES (
        '00000000-0000-0000-0000-000000000092',
        NULL,
        'Nitrogen Deficiency',
        'Alert when NDVI indicates nitrogen stress (NDVI < 0.4)',
        'threshold',
        'ndvi',
        0.4,
        '<',
        'warning',
        'NDVI at {current_value} suggests nitrogen deficiency. Consider foliar application or soil amendment. Field zone: {zone_id}.',
        'fertilization',
        '["dashboard"]'
    ) ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        threshold_value = EXCLUDED.threshold_value,
        recommendation_template = EXCLUDED.recommendation_template,
        updated_at = NOW();

    -- 5. Pest Alert
    INSERT INTO advisory_rule (
        id, location_id, name, description, rule_type,
        metric_source, threshold_value, threshold_operator,
        severity, recommendation_template, action_category,
        notification_channels
    ) VALUES (
        '00000000-0000-0000-0000-000000000093',
        NULL,
        'Pest Alert',
        'Alert when pest probability exceeds 0.7',
        'threshold',
        'pest_probability',
        0.7,
        '>',
        'critical',
        'Pest probability at {current_value}. Immediate scouting recommended. Check adjacent fields. Consider organic pest control measures.',
        'pest_management',
        '["sms", "dashboard", "email"]'
    ) ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        threshold_value = EXCLUDED.threshold_value,
        recommendation_template = EXCLUDED.recommendation_template,
        updated_at = NOW();

    -- 6. Harvest Readiness
    INSERT INTO advisory_rule (
        id, location_id, name, description, rule_type,
        metric_source, threshold_value, threshold_operator,
        severity, recommendation_template, action_category,
        notification_channels
    ) VALUES (
        '00000000-0000-0000-0000-000000000094',
        NULL,
        'Harvest Readiness',
        'Alert when crop maturity score reaches 0.9',
        'threshold',
        'crop_maturity_score',
        0.9,
        '>',
        'info',
        'Crop at {current_value}% maturity. Harvest window opening within 3-5 days. Prepare equipment and labor.',
        'harvest',
        '["dashboard"]'
    ) ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        threshold_value = EXCLUDED.threshold_value,
        recommendation_template = EXCLUDED.recommendation_template,
        updated_at = NOW();

    -- 7. Frost Warning
    INSERT INTO advisory_rule (
        id, location_id, name, description, rule_type,
        metric_source, threshold_value, threshold_operator,
        severity, recommendation_template, action_category,
        notification_channels
    ) VALUES (
        '00000000-0000-0000-0000-000000000095',
        NULL,
        'Frost Warning',
        'Alert when temperature drops below 2°C',
        'threshold',
        'air_temperature',
        2,
        '<',
        'critical',
        'FROST WARNING: Temperature at {current_value}°C. Protect vulnerable crops. Consider row covers or irrigation.',
        'frost_protection',
        '["sms", "dashboard", "email"]'
    ) ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        threshold_value = EXCLUDED.threshold_value,
        recommendation_template = EXCLUDED.recommendation_template,
        updated_at = NOW();

    -- 8. Spray Window
    INSERT INTO advisory_rule (
        id, location_id, name, description, rule_type,
        metric_source, threshold_value, threshold_operator,
        severity, recommendation_template, action_category,
        notification_channels
    ) VALUES (
        '00000000-0000-0000-0000-000000000096',
        NULL,
        'Spray Window Open',
        'Alert when wind speed < 15 km/h and humidity 40-80% for 4+ hours',
        'composite',
        'wind_speed',
        15,
        '<',
        'info',
        'Optimal spray window detected: {current_value} km/h wind. Duration: {window_hours}h. Temp: {temp}°C, Humidity: {humidity}%. Consider application.',
        'spray_application',
        '["sms", "dashboard"]'
    ) ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        threshold_value = EXCLUDED.threshold_value,
        recommendation_template = EXCLUDED.recommendation_template,
        updated_at = NOW();

END $$;
