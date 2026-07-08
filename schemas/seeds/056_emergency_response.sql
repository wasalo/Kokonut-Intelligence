-- ============================================================
-- 056_emergency_response.sql — Seeds: metric, Adelphi pilot data
-- ============================================================

-- New metric definition
INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('emergency_response_time_days', 'Emergency Response Time', 'Average number of days from incident detection to resolution.', 'avg(recovery_date - detection_date) from emergency_incident where status = resolved', ARRAY['emergency_incident'], 'Use resolved emergency incidents.', 'Exclude unresolved or escalated incidents.', 'days', 'numeric', 'Operations Guild', 1, 'quarterly', TRUE, '["value >= 0"]'::jsonb, ARRAY['emergency_response', 'operational_resilience'], 'Supersede through metric_version before changing public interpretation.')
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
    deprecation_policy = EXCLUDED.deprecation_policy;

-- Adelphi pilot: drought incident (high severity, resolved in 21 days)
INSERT INTO emergency_incident (
    id, location_id, incident_type, severity, detection_date, detection_method,
    description, affected_area_pct, affected_plant_count,
    response_actions, emergency_support_provided,
    response_deadline, recovery_date, recovery_actions,
    financial_impact_usd, ecological_impact_notes, lessons_learned,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005610',
 'a0000000-0000-0000-0000-000000000001',
 'drought', 'high', '2025-09-01', 'weather_forecast',
 'Severe drought conditions lasting 6 weeks. Rainfall 60% below seasonal average. Soil moisture dropped to critical levels. Coconut palms showing frond wilting and reduced fruit set.',
 40.0, 18,
 '[
   {"action": "Emergency watering protocol activated", "responsible": "Adelphi Steward", "deadline": "2025-09-03", "status": "completed"},
   {"action": "Apply additional mulch to retain soil moisture", "responsible": "Adelphi Steward", "deadline": "2025-09-10", "status": "completed"},
   {"action": "Install temporary shade structures for juvenile palms", "responsible": "Field Team", "deadline": "2025-09-15", "status": "completed"},
   {"action": "Request emergency water truck delivery", "responsible": "Kokonut DAO", "deadline": "2025-09-05", "status": "completed"}
 ]'::jsonb,
 'Emergency watering protocol activated. 5000L water truck delivered on 2025-09-04. Additional mulch applied to all production beds. Temporary shade installed for 12 juvenile palms.',
 '2025-09-21', '2025-09-22',
 '[
   {"action": "Install permanent drip irrigation system", "responsible": "Kokonut DAO", "deadline": "2025-12-31", "status": "completed"},
   {"action": "Add soil moisture sensors to drought-prone zones", "responsible": "Field Team", "deadline": "2025-11-30", "status": "completed"},
   {"action": "Create drought response SOP for future incidents", "responsible": "Operations Manager", "deadline": "2025-10-15", "status": "completed"}
 ]'::jsonb,
 1200.00,
 'Mild leaf stress observed on 18 palms. No permanent damage. Fruit set reduced by approximately 15% for Q4 2025 harvest.',
 'Early detection via weather forecast allowed 3-day lead time. Emergency water delivery was critical. Permanent drip irrigation installed post-incident prevents recurrence. Mulching reduced soil moisture loss by estimated 40%.',
 'resolved', 'pilot_seed', 'adelphi-emergency-drought-2025',
 '{"record_type":"emergency_incident","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();
