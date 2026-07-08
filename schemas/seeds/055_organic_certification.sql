-- ============================================================
-- 055_organic_certification.sql — Seeds: metrics, reports, Adelphi pilot data
-- ============================================================

-- New metric definitions
INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('organic_readiness_score', 'Organic Readiness Score', 'Composite organic certification readiness score (0-100) across 8 dimensions: soil health, input compliance, pest management, biodiversity, buffer zones, records, training, and harvest segregation.', 'weighted_avg(transition_progress_pct, soil_health_score, input_compliance_pct, pest_management_score, biodiversity_score, buffer_zone_score, record_completeness_pct, training_completion_pct, harvest_segregation_score)', ARRAY['organic_readiness_assessment', 'organic_input_audit', 'buffer_zone', 'harvest_handling_record', 'soil_sample', 'species_observation', 'pest_observation', 'biocontrol_release'], 'Use latest organic_readiness_assessment per location.', 'Exclude assessments older than 12 months.', 'score', 'numeric', 'Organic Certification Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['organic_certification', 'readiness', 'compliance'], 'Supersede through metric_version before changing public interpretation.'),
('organic_input_compliance_pct', 'Organic Input Compliance Percentage', 'Percentage of farm inputs that are organic-certified or on-farm produced during the assessment period.', 'count(organic_certified = TRUE inputs) / count(total inputs) * 100', ARRAY['organic_input_audit'], 'Use organic_input_audit records from the last 12 months.', 'Exclude records without valid input_category.', 'percentage', 'numeric', 'Organic Certification Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100"]'::jsonb, ARRAY['organic_certification', 'input_compliance'], 'Supersede through metric_version before changing public interpretation.')
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

-- Adelphi pilot: organic certification record (IFOAM, preparing)
INSERT INTO organic_certification_record (
    id, location_id, standard, certification_type, certification_body,
    application_date, inspection_date, certification_date, expiration_date,
    certificate_number, certificate_url, status, scope, scope_areas,
    annual_fee_usd, notes, evidence_urls, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005510',
 'a0000000-0000-0000-0000-000000000001',
 'IFOAM', 'initial', 'Caribbean Organic Certification Body',
 '2026-03-15', NULL, NULL, NULL,
 NULL, NULL, 'preparing', 'partial', '["production_zone", "nursery_zone"]'::jsonb,
 500.00,
 'Preparing initial IFOAM certification for production and nursery zones. Biofactory zone pending organic input verification.',
 '["https://docs.example.com/adelphi-organic-plan.pdf"]'::jsonb,
 'published', 'pilot_seed', 'adelphi-organic-cert-ifoam',
 '{"record_type":"organic_certification_record","privacy":"public_summary","record_type":"organic_certification"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- Adelphi pilot: organic transition plan (year 2 of 3, IFOAM)
INSERT INTO organic_transition_plan (
    id, location_id, plot_id, standard, transition_start_date,
    expected_certification_date, current_year, total_years_required,
    status, prohibited_substance_free_date, buffer_zone_established_date,
    record_keeping_ready_date, training_completed_date,
    organic_management_plan_date, readiness_score, barriers, notes,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005520',
 'a0000000-0000-0000-0000-000000000001',
 NULL, 'IFOAM', '2024-09-01',
 '2027-09-01', 2, 3,
 'active', '2024-09-01', '2024-10-15',
 '2024-11-01', '2025-03-01',
 '2025-06-01', 72.5,
 '["nearby_conventional_plot_north", "incomplete_biodiversity_records_q4_2025"]'::jsonb,
 'Year 2 of 3. Soil health improving. Buffer zones established. Training completed. Biodiversity records need completion.',
 'pilot_seed', 'adelphi-transition-ifoam',
 '{"record_type":"organic_transition_plan","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    current_year = EXCLUDED.current_year,
    readiness_score = EXCLUDED.readiness_score,
    updated_at = NOW();

-- Adelphi pilot: buffer zones (hedgerow 4m, uncultivated strip 5m)
INSERT INTO buffer_zone (
    id, location_id, plot_id, buffer_name, buffer_type,
    width_m, length_m, area_m2, adjacent_use,
    establishment_date, condition_status, last_inspection_date,
    photos_urls, notes, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005530',
 'a0000000-0000-0000-0000-000000000001',
 NULL, 'North Hedgerow Buffer', 'hedgerow',
 4.0, 120.0, 480.0, 'conventional_farm',
 '2024-10-15', 'adequate', '2026-01-10',
 '["https://docs.example.com/adelphi-buffer-north.jpg"]'::jsonb,
 'North boundary buffer separating organic production from adjacent conventional plot. Mixed native hedgerow.',
 'pilot_seed', 'adelphi-buffer-north',
 '{"record_type":"buffer_zone","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005531',
 'a0000000-0000-0000-0000-000000000001',
 NULL, 'East Uncultivated Strip', 'uncultivated_strip',
 5.0, 80.0, 400.0, 'road',
 '2024-10-20', 'adequate', '2026-01-10',
 '["https://docs.example.com/adelphi-buffer-east.jpg"]'::jsonb,
 'East boundary buffer along access road. 5m uncultivated strip with native groundcover.',
 'pilot_seed', 'adelphi-buffer-east',
 '{"record_type":"buffer_zone","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    condition_status = EXCLUDED.condition_status,
    updated_at = NOW();

-- Adelphi pilot: organic input audit (compost, biochar, neem — all organic-certified)
INSERT INTO organic_input_audit (
    id, location_id, plot_id, crop_cycle_id, application_date,
    input_category, input_name, input_source, organic_certified,
    supplier_name, supplier_organic_cert_url,
    quantity, unit, application_method, target_pest_or_nutrient,
    pre_harvest_interval_days, reentry_interval_hours,
    is_prohibited, prohibition_standard, notes,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005540',
 'a0000000-0000-0000-0000-000000000001',
 NULL, NULL, '2025-11-01',
 'soil_amendment', 'Adelphi Compost (on-farm)', 'on_farm', TRUE,
 NULL, NULL,
 500.0, 'kg', 'surface_broadcast', 'soil_organic_matter',
 0, 0,
 FALSE, NULL,
 'On-farm compost from poultry litter and green waste. Applied to production zone beds.',
 'pilot_seed', 'adelphi-input-compost',
 '{"record_type":"organic_input_audit","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005541',
 'a0000000-0000-0000-0000-000000000001',
 NULL, NULL, '2025-11-15',
 'soil_amendment', 'Adelphi Biochar (on-farm)', 'on_farm', TRUE,
 NULL, NULL,
 200.0, 'kg', 'incorporation', 'soil_carbon_retention',
 0, 0,
 FALSE, NULL,
 'On-farm biochar from coconut shell pyrolysis. Incorporated into nursery beds.',
 'pilot_seed', 'adelphi-input-biochar',
 '{"record_type":"organic_input_audit","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005542',
 'a0000000-0000-0000-0000-000000000001',
 NULL, NULL, '2026-01-10',
 'pesticide', 'Neem Oil Extract (organic)', 'purchased', TRUE,
 'Caribbean Organic Inputs Ltd', 'https://docs.example.com/supplier-organic-cert.pdf',
 15.0, 'L', 'foliar_spray', 'aphids_whiteflies',
 3, 4,
 FALSE, NULL,
 'Organic-certified neem oil for aphid and whitefly management. Applied per IFOAM approved list.',
 'pilot_seed', 'adelphi-input-neem',
 '{"record_type":"organic_input_audit","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    quantity = EXCLUDED.quantity,
    updated_at = NOW();

-- Adelphi pilot: harvest handling records (organic segregated)
INSERT INTO harvest_handling_record (
    id, location_id, harvest_event_id, handling_date, handling_type,
    organic_segregated, equipment_cleaned, contamination_risk,
    temperature_controlled, storage_conditions, transport_conditions,
    organic_lot_number, buyer_requirements_met, notes,
    source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005550',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000052',
 '2025-12-01', 'cleaning',
 TRUE, TRUE, 'low',
 FALSE, 'Dedicated organic drying rack in shaded area',
 'Organic produce transported in dedicated clean containers',
 'ADE-P-2025-001', TRUE,
 'Coconut harvest cleaned and graded. Organic segregation maintained throughout.',
 'pilot_seed', 'adelphi-harvest-cleaning',
 '{"record_type":"harvest_handling_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005551',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000052',
 '2025-12-02', 'storage',
 TRUE, TRUE, 'low',
 TRUE, 'Temperature-controlled organic storage unit (18-22°C)',
 'N/A — stored on-farm',
 'ADE-P-2025-001', TRUE,
 'Coconut produce stored in dedicated organic storage. Temperature logged and within range.',
 'pilot_seed', 'adelphi-harvest-storage',
 '{"record_type":"harvest_handling_record","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    handling_type = EXCLUDED.handling_type,
    updated_at = NOW();

-- Adelphi pilot: compliance checklist (14/18 items pass)
INSERT INTO organic_compliance_checklist (
    id, location_id, certification_record_id, inspection_date,
    inspector_name, inspector_organization, inspection_type,
    checklist_items, findings, non_conformances,
    corrective_actions_required, follow_up_date, overall_result,
    notes, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005560',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000005510',
 '2026-02-20',
 'Maria Santos', 'Caribbean Organic Certification Body', 'initial',
 '[
   {"step": "1. Site Assessment", "requirement": "No prohibited substances for 36 months", "status": "pass", "evidence": "Soil test clean, no prohibited substance records"},
   {"step": "2. Soil Management", "requirement": "Organic soil amendments and crop rotation", "status": "pass", "evidence": "Compost, biochar, green manure documented"},
   {"step": "3. Seed & Planting Stock", "requirement": "Organic or untreated seeds", "status": "pass", "evidence": "On-farm saved seed, no GMO"},
   {"step": "4. Crop Protection", "requirement": "Approved natural pest control", "status": "pass", "evidence": "Neem oil, biocontrol releases documented"},
   {"step": "5. Fertilization", "requirement": "Organic fertilizers only", "status": "pass", "evidence": "On-farm compost, biochar, vermicompost"},
   {"step": "6. Buffer Zones", "requirement": "Adequate buffers from conventional", "status": "conditional", "evidence": "North buffer adequate (4m), east buffer adequate (5m), south buffer needs verification"},
   {"step": "7. Wildlife & Biodiversity", "requirement": "Protect habitats, encourage pollinators", "status": "pass", "evidence": "29 species documented, hedgerows, pollinator strips"},
   {"step": "8. Harvest & Handling", "requirement": "Separate storage, dedicated equipment", "status": "pass", "evidence": "Organic segregation documented, dedicated storage"},
   {"step": "9. Record Keeping", "requirement": "Complete records for 5 years", "status": "conditional", "evidence": "Soil and input records complete. Biodiversity records missing Q4 2025."},
   {"step": "10. Organic Management Plan", "requirement": "Written OSP submitted", "status": "pass", "evidence": "OSP submitted 2025-06-01"},
   {"step": "11. Input Traceability", "requirement": "All inputs traceable to source", "status": "pass", "evidence": "Organic input audit log maintained"},
   {"step": "12. Contamination Prevention", "requirement": "No commingling with conventional", "status": "pass", "evidence": "Organic segregation in harvest and storage"},
   {"step": "13. Water Quality", "requirement": "Clean water source, no contamination risk", "status": "pass", "evidence": "Water analysis results within organic limits"},
   {"step": "14. Pest Monitoring", "requirement": "Regular pest monitoring and IPM", "status": "pass", "evidence": "Pest observation log, biocontrol effectiveness tracked"},
   {"step": "15. Training Records", "requirement": "Staff trained in organic practices", "status": "pass", "evidence": "4 training sessions documented"},
   {"step": "16. Equipment Cleaning", "requirement": "Dedicated or cleaned equipment", "status": "pass", "evidence": "Equipment cleaning log maintained"},
   {"step": "17. Transport Protocols", "requirement": "Organic produce transported separately", "status": "conditional", "evidence": "Dedicated containers used, transport log needs more detail"},
   {"step": "18. Complaint System", "requirement": "System for handling organic complaints", "status": "pass", "evidence": "Complaint process documented in OSP"}
  ]'::jsonb,
 'Farm is well-prepared for organic certification. Strong soil health, input traceability, and pest management. Minor gaps in transport documentation and Q4 biodiversity records.',
 '["South buffer zone width needs verification (target: 3m minimum)", "Biodiversity records missing Q4 2025", "Transport log needs more detailed entries"]'::jsonb,
 '[
   {"action": "Verify south buffer zone width and document in GIS", "deadline": "2026-04-01", "priority": "medium"},
   {"action": "Complete Q4 2025 biodiversity survey and enter records", "deadline": "2026-03-15", "priority": "high"},
   {"action": "Update transport log with detailed entries for each shipment", "deadline": "2026-04-01", "priority": "low"}
  ]'::jsonb,
 '2026-04-15', 'conditional',
 'Pre-certification inspection. Farm meets most IFOAM requirements. 3 corrective actions required before certification can proceed.',
 'pilot_seed', 'adelphi-checklist-ifoam-01',
 '{"record_type":"organic_compliance_checklist","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    overall_result = EXCLUDED.overall_result,
    updated_at = NOW();

-- Adelphi pilot: organic readiness assessment (score 72.5/100)
INSERT INTO organic_readiness_assessment (
    id, location_id, assessment_date, standard,
    overall_score, transition_progress_pct, soil_health_score,
    input_compliance_pct, pest_management_score, biodiversity_score,
    buffer_zone_score, record_completeness_pct, training_completion_pct,
    harvest_segregation_score, barriers, recommendations, assessor,
    notes, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005570',
 'a0000000-0000-0000-0000-000000000001',
 '2026-02-20', 'IFOAM',
 72.5, 66.7, 82.0,
 100.0, 88.0, 75.0,
 85.0, 78.0, 90.0,
 95.0,
 '["nearby_conventional_plot_north", "incomplete_biodiversity_records_q4_2025", "south_buffer_width_unverified"]'::jsonb,
 '["Complete Q4 2025 biodiversity survey", "Verify south buffer zone width in GIS", "Update transport log detail"]'::jsonb,
 'Maria Santos (Caribbean Organic Certification Body)',
 'Year 2 of 3 transition. Strong input compliance and harvest segregation. Soil health and biodiversity need improvement. Buffer zones mostly adequate.',
 'pilot_seed', 'adelphi-readiness-ifoam-01',
 '{"record_type":"organic_readiness_assessment","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    overall_score = EXCLUDED.overall_score,
    updated_at = NOW();

-- Adelphi pilot: EAS compliance attestation (Celo)
INSERT INTO attestation_record (
    id, location_id, attestation_type, schema_uid, attester_address,
    subject_type, subject_id, chain, tx_hash,
    attestation_data, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005580',
 'a0000000-0000-0000-0000-000000000001',
 'organic', '01e4...',
 '0x1234567890abcdef1234567890abcdef12345678',
 'location', 'a0000000-0000-0000-0000-000000000001',
 'celo', '0xabcdef...',
 '{"framework": "IFOAM", "requirement": "transition_year_2", "compliant": true, "evidenceHash": "ipfs://Qm...", "notes": "Year 2 of 3 transition. On track for 2027 certification."}'::jsonb,
 'published', 'pilot_seed', 'adelphi-eas-compliance-organic',
 '{"record_type":"attestation_record","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    attestation_data = EXCLUDED.attestation_data,
    updated_at = NOW();
