-- ============================================================
-- 048_economic_social_enhancement.sql — Seeds: metrics, Adelphi pilot data
-- ============================================================

-- New metric definitions
INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('training_improvement_pct', 'Training Improvement %', 'Average improvement in best practices adoption scores after training.', 'avg(post_score - pre_score) / avg(pre_score) * 100 from training_session where pre_score > 0', ARRAY['training_session'], 'Use published training sessions with both pre and post scores.', 'Exclude sessions without pre/post score pairs.', 'percentage', 'numeric', 'Wellbeing Guild', 1, 'quarterly', TRUE, '["value >= -100", "value <= 500"]'::jsonb, ARRAY['training_impact', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('revenue_per_acre_usd', 'Revenue per Acre (USD)', 'Gross revenue per acre of cultivated area.', 'sum(revenue_event.amount_usd) / sum(cycle.area_planted) where area_unit = hectares', ARRAY['revenue_event', 'crop_cycle'], 'Use verified revenue events with area_planted data.', 'Exclude revenue events without area linkage.', 'usd_per_acre', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["value >= 0"]'::jsonb, ARRAY['economic_performance', 'green_paper'], 'Supersede through metric_version before changing public interpretation.')
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

-- Adelphi pilot: training sessions
INSERT INTO training_session (
    id, location_id, participant_name, participant_role,
    session_date, session_topic, session_type, duration_hours,
    pre_score, post_score, improvement_pct, trainer,
    notes, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004810',
 'a0000000-0000-0000-0000-000000000001',
 'Maria Santos', 'field_worker',
 '2025-10-15', 'Organic pest management', 'pest_management', 4.0,
 45.0, 78.0, 73.33, 'Kokonut Collective',
 'Training on neem-based biopesticide preparation and application. Maria showed significant improvement in pest identification and treatment selection.',
 'published', 'pilot_seed', 'adelphi-training-maria-pest',
 '{"record_type":"training_session","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004811',
 'a0000000-0000-0000-0000-000000000001',
 'Carlos Rivera', 'field_worker',
 '2025-10-15', 'Organic pest management', 'pest_management', 4.0,
 52.0, 81.0, 55.77, 'Kokonut Collective',
 'Carlos demonstrated strong understanding of predator-prey dynamics and biocontrol agent selection.',
 'published', 'pilot_seed', 'adelphi-training-carlos-pest',
 '{"record_type":"training_session","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004812',
 'a0000000-0000-0000-0000-000000000001',
 'Ana Gutierrez', 'field_worker',
 '2025-11-20', 'Soil health and biochar application', 'soil_management', 3.0,
 40.0, 72.0, 80.00, 'Kokonut Collective',
 'Ana learned biochar application rates, depth, and incorporation techniques for syntropic beds.',
 'published', 'pilot_seed', 'adelphi-training-ana-soil',
 '{"record_type":"training_session","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004813',
 'a0000000-0000-0000-0000-000000000001',
 'Luis Hernandez', 'manager',
 '2025-12-10', 'Financial record-keeping', 'financial_management', 6.0,
 60.0, 88.0, 46.67, 'Kokonut Collective',
 'Luis completed financial record-keeping training covering expense tracking, revenue allocation, and NOI calculation.',
 'published', 'pilot_seed', 'adelphi-training-luis-finance',
 '{"record_type":"training_session","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    participant_name = EXCLUDED.participant_name,
    pre_score = EXCLUDED.pre_score,
    post_score = EXCLUDED.post_score,
    improvement_pct = EXCLUDED.improvement_pct,
    updated_at = NOW();

-- Adelphi pilot: revenue stream contributions
INSERT INTO revenue_stream_contribution (
    id, location_id, crop_cycle_id,
    period_start, period_end,
    stream_name, stream_category,
    gross_revenue, direct_costs, allocated_costs, net_contribution, contribution_pct,
    notes, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000004820',
 'a0000000-0000-0000-0000-000000000001',
 NULL,
 '2025-10-01', '2025-12-31',
 'Fresh produce sales', 'fresh_produce',
 2850.00, 680.00, 320.00, 1850.00, 64.91,
 'Primary revenue stream from lettuce, passion fruit, and coconut sales at local markets.',
 'published', 'pilot_seed', 'adelphi-revstream-fresh-q4',
 '{"record_type":"revenue_stream_contribution","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004821',
 'a0000000-0000-0000-0000-000000000001',
 NULL,
 '2025-10-01', '2025-12-31',
 'Bio-input sales', 'bio_input_sales',
 420.00, 85.00, 40.00, 295.00, 10.33,
 'Vermicompost and compost tea sales to neighboring farms.',
 'published', 'pilot_seed', 'adelphi-revstream-bioinput-q4',
 '{"record_type":"revenue_stream_contribution","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004822',
 'a0000000-0000-0000-0000-000000000001',
 NULL,
 '2025-10-01', '2025-12-31',
 'Nursery seedlings', 'nursery_sales',
 680.00, 150.00, 70.00, 460.00, 16.11,
 'Passion fruit and fruit tree seedling sales from Adelphi nursery.',
 'published', 'pilot_seed', 'adelphi-revstream-nursery-q4',
 '{"record_type":"revenue_stream_contribution","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000004823',
 'a0000000-0000-0000-0000-000000000001',
 NULL,
 '2025-10-01', '2025-12-31',
 'Carbon credit sponsorship', 'carbon_credits',
 500.00, 0.00, 50.00, 450.00, 15.75,
 'Impact verification sponsorship for ecological outcomes.',
 'published', 'pilot_seed', 'adelphi-revstream-carbon-q4',
 '{"record_type":"revenue_stream_contribution","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    stream_name = EXCLUDED.stream_name,
    gross_revenue = EXCLUDED.gross_revenue,
    net_contribution = EXCLUDED.net_contribution,
    contribution_pct = EXCLUDED.contribution_pct,
    updated_at = NOW();
