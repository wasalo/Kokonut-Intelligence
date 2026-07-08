-- ============================================================
-- 050_remaining_gaps.sql — Seeds: metrics, dashboards, Adelphi pilot data
-- ============================================================

-- New metric definitions
INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('leaf_litter_rate_kg_per_day', 'Leaf Litter Rate (kg/day)', 'Average daily leaf litter collection rate per litter trap.', 'avg(litter_rate_kg_per_day) from leaf_litter_measurement where status in verified/published', ARRAY['leaf_litter_measurement'], 'Use published leaf litter measurements with valid litter_rate_kg_per_day.', 'Exclude records without litter_rate_kg_per_day.', 'kg_per_day', 'numeric', 'Ecology Guild', 1, 'monthly', TRUE, '["value >= 0"]'::jsonb, ARRAY['ecological_modeling', 'nutrient_cycling'], 'Supersede through metric_version before changing public interpretation.'),
('feed_conversion_ratio', 'Feed Conversion Ratio', 'Kilograms of feed per kilogram of weight gain in livestock.', 'sum(feed_kg) / sum(weight_gain_kg) from feed_intake_record', ARRAY['feed_intake_record', 'livestock_group'], 'Use published feed intake records linked to active livestock groups.', 'Exclude records without weight gain data.', 'ratio', 'numeric', 'Ecology Guild', 1, 'monthly', TRUE, '["value > 0"]'::jsonb, ARRAY['ecological_modeling', 'livestock_management'], 'Supersede through metric_version before changing public interpretation.'),
('decomposition_rate_pct_per_day', 'Decomposition Rate (%/day)', 'Mass loss rate from litter bag studies as percentage of initial dry weight per day.', 'avg(mass_loss_pct / deployment_days) from decomposition_measurement where status in verified/published', ARRAY['decomposition_measurement'], 'Use published decomposition measurements with retrieval data.', 'Exclude records without retrieval_date or final_dry_weight_g.', 'percentage_per_day', 'numeric', 'Ecology Guild', 1, 'monthly', TRUE, '["value >= 0", "value <= 100"]'::jsonb, ARRAY['ecological_modeling', 'nutrient_cycling'], 'Supersede through metric_version before changing public interpretation.'),
('predation_rate_per_day', 'Predation Rate (per day)', 'Average number of predation events observed per day per plot.', 'sum(predation_count) / count(distinct observation_date) from pest_observation where status in verified/published', ARRAY['pest_observation'], 'Use published pest observations with predation_count data.', 'Exclude records without predation_count.', 'events_per_day', 'numeric', 'Ecology Guild', 1, 'monthly', TRUE, '["value >= 0"]'::jsonb, ARRAY['ecological_modeling', 'pest_management'], 'Supersede through metric_version before changing public interpretation.'),
('token_rewards_per_epoch', 'Token Rewards per Epoch', 'Total token rewards distributed per governance epoch.', 'sum(token_amount) from token_reward_distribution where status in verified/published', ARRAY['token_reward_distribution'], 'Use published token reward distribution records.', 'Exclude draft or rejected records.', 'token_amount', 'numeric', 'Governance Guild', 1, 'monthly', TRUE, '["value >= 0"]'::jsonb, ARRAY['token_rewards', 'governance'], 'Supersede through metric_version before changing public interpretation.'),
('reward_calibration_score', 'Reward Calibration Score', 'Alignment score between real-world output metrics and token emission rates (0-1).', 'calibration_score from reward_calibration_model where status in verified/published', ARRAY['reward_calibration_model'], 'Use published reward calibration model runs.', 'Exclude records without calibration_score.', 'score_0_1', 'numeric', 'Governance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 1"]'::jsonb, ARRAY['reward_calibration', 'governance'], 'Supersede through metric_version before changing public interpretation.')
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

-- New dashboard datasets
INSERT INTO dashboard_dataset (
    id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata
) VALUES
('a0000000-0000-0000-0000-000000005001', 'Livestock Feed Intake', 'Daily feed intake trends, conversion ratio, and per-animal consumption by livestock group.', 'livestock_feed_intake', NULL, 'dashboards/metabase/sql/66_livestock_feed_intake.sql', 1440, 'published', '{"owner":"ecology_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000005002', 'Token Reward Distribution', 'Token reward distribution by type, epoch, and metric correlation.', 'token_reward_distribution', NULL, 'dashboards/metabase/sql/67_token_reward_distribution.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Predation rate seed updates for existing pest observations
UPDATE pest_observation SET predation_count = 0, predation_rate_per_day = 0.0
WHERE pest_species = 'Spodoptera frugiperda' AND predation_count IS NULL;

UPDATE pest_observation SET predation_count = 2, predation_rate_per_day = 0.13
WHERE pest_species = 'Aphis gossypii' AND predation_count IS NULL;

-- Adelphi pilot: leaf litter measurements
INSERT INTO leaf_litter_measurement (
    id, location_id, plot_id, zone_id,
    measurement_date, litter_trap_id, collection_method,
    fresh_weight_g, dry_weight_g, area_m2, litter_rate_kg_per_day,
    species_source, decomposition_stage, temperature_c, moisture_pct,
    notes, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005010',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 '2025-10-15', 'LITTER-001', 'litter_trap_025m2',
 480.000, 210.000, 0.25, 2.800,
 'Inga edulis', 'fresh', 27.5, 65.0,
 'First litter collection from Inga edulis canopy. Fresh leaf fall measured in 0.25m2 trap.',
 'published', 'pilot_seed', 'adelphi-litter-001',
 '{"record_type":"leaf_litter_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005011',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 '2026-01-20', 'LITTER-001', 'litter_trap_025m2',
 520.000, 185.000, 0.25, 2.467,
 'Inga edulis', 'partially_decomposed', 26.8, 70.0,
 'Second litter collection. Some decomposition visible. Dry weight lower than October.',
 'published', 'pilot_seed', 'adelphi-litter-002',
 '{"record_type":"leaf_litter_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005012',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 '2026-03-10', 'LITTER-001', 'litter_trap_025m2',
 610.000, 165.000, 0.25, 2.200,
 'Inga edulis', 'well_decomposed', 28.1, 55.0,
 'Third litter collection. Well-decomposed material. Increasing litter fall with canopy growth.',
 'published', 'pilot_seed', 'adelphi-litter-003',
 '{"record_type":"leaf_litter_measurement","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    fresh_weight_g = EXCLUDED.fresh_weight_g,
    dry_weight_g = EXCLUDED.dry_weight_g,
    litter_rate_kg_per_day = EXCLUDED.litter_rate_kg_per_day,
    decomposition_stage = EXCLUDED.decomposition_stage,
    updated_at = NOW();

-- Adelphi pilot: livestock group (chickens)
INSERT INTO livestock_group (
    id, location_id, zone_id,
    group_name, species, breed, animal_count,
    average_weight_kg, feed_type, enclosure_type,
    start_date, status, notes,
    source_system, source_id, source_raw
) VALUES (
 'a0000000-0000-0000-0000-000000005020',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000025',
 'Adelphi Free-Range Flock',
 'Gallus gallus domesticus',
 'Rhode Island Red cross',
 15,
 2.2,
 'mixed_feed',
 'free_range',
 '2025-09-01',
 'active',
 'Free-range chicken flock integrated with coconut and syntropic beds. Provides pest control and manure.',
 'pilot_seed', 'adelphi-livestock-chickens',
 '{"record_type":"livestock_group","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    species = EXCLUDED.species,
    animal_count = EXCLUDED.animal_count,
    updated_at = NOW();

-- Adelphi pilot: feed intake records
INSERT INTO feed_intake_record (
    id, location_id, livestock_group_id,
    record_date, feed_type, feed_name, quantity_kg, per_animal_kg,
    method, temperature_c, notes,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005030',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000005020',
 '2025-12-31', 'mixed_grain', 'Local grain mix', 90.000, 0.067,
 'weigh_feed', 27.0,
 'Q4 2025 feed consumption. Chickens supplement with foraged insects and fallen fruit.',
 'published', 'pilot_seed', 'adelphi-feed-q4-2025',
 '{"record_type":"feed_intake_record","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005031',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000005020',
 '2026-03-31', 'mixed_grain', 'Local grain mix', 85.000, 0.063,
 'weigh_feed', 28.5,
 'Q1 2026 feed consumption. Slight reduction due to increased insect availability during wet season.',
 'published', 'pilot_seed', 'adelphi-feed-q1-2026',
 '{"record_type":"feed_intake_record","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    quantity_kg = EXCLUDED.quantity_kg,
    per_animal_kg = EXCLUDED.per_animal_kg,
    updated_at = NOW();

-- Adelphi pilot: decomposition measurements
INSERT INTO decomposition_measurement (
    id, location_id, plot_id, zone_id,
    litter_type, species_source,
    initial_dry_weight_g, final_dry_weight_g,
    deployment_date, retrieval_date,
    mesh_size_mm, depth_cm, temperature_c, moisture_pct,
    notes, status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005040',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 'leaf_litter', 'Inga edulis',
 50.000, 18.000,
 '2025-10-15', '2026-03-10',
 2.0, 5.0, 27.5, 65.0,
 'Inga edulis leaf litter in 2mm mesh bag at 5cm depth. 146 days deployment. 64% mass loss.',
 'published', 'pilot_seed', 'adelphi-decomp-001',
 '{"record_type":"decomposition_measurement","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005041',
 'a0000000-0000-0000-0000-000000000001',
 'a0000000-0000-0000-0000-000000000015',
 'a0000000-0000-0000-0000-000000000020',
 'compost', NULL,
 75.000, 22.000,
 '2025-10-15', '2026-03-10',
 1.0, 10.0, 27.5, 70.0,
 'Vermicompost in 1mm mesh bag at 10cm depth. 146 days deployment. 70.7% mass loss.',
 'published', 'pilot_seed', 'adelphi-decomp-002',
 '{"record_type":"decomposition_measurement","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    final_dry_weight_g = EXCLUDED.final_dry_weight_g,
    retrieval_date = EXCLUDED.retrieval_date,
    updated_at = NOW();

-- Adelphi pilot: token reward distributions
INSERT INTO token_reward_distribution (
    id, location_id, recipient_name,
    reward_type, token_type, token_amount, usd_value,
    distribution_date, epoch,
    source_event_type, linked_metric_key, linked_metric_value,
    is_onchain, distribution_method, notes,
    status, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000005050',
 'a0000000-0000-0000-0000-000000000001',
 'Maria Santos', 'labor', 'vKKN', 150.00000000, 75.00,
 '2025-12-31', '2025-Q4',
 'labor_event', 'labor_hours', 160.00,
 FALSE, 'dao_backend',
 'Q4 2025 labor contribution reward. 150 vKKN for 160 hours field work.',
 'published', 'pilot_seed', 'adelphi-reward-maria-q4',
 '{"record_type":"token_reward_distribution","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005051',
 'a0000000-0000-0000-0000-000000000001',
 'Carlos Rivera', 'training', 'vKKN', 50.00000000, 25.00,
 '2025-12-31', '2025-Q4',
 'training_session', 'training_improvement_pct', 55.77,
 FALSE, 'dao_backend',
 'Q4 2025 training completion reward. 50 vKKN for pest management training with 56% improvement.',
 'published', 'pilot_seed', 'adelphi-reward-carlos-q4',
 '{"record_type":"token_reward_distribution","privacy":"public_summary"}'::jsonb),
('a0000000-0000-0000-0000-000000005052',
 'a0000000-0000-0000-0000-000000000001',
 'Adelphi Farm Collective', 'ecological_contribution', 'vKKN', 200.00000000, 100.00,
 '2026-03-10', '2026-Q1',
 'ecological_model_run', 'trophic_balance_index', 0.833,
 TRUE, 'celo_onchain',
 'Q1 2026 ecological contribution reward. 200 vKKN for high trophic balance index (0.833).',
 'published', 'pilot_seed', 'adelphi-reward-ecology-q1',
 '{"record_type":"token_reward_distribution","privacy":"public_summary"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    token_amount = EXCLUDED.token_amount,
    usd_value = EXCLUDED.usd_value,
    updated_at = NOW();

-- Adelphi pilot: reward calibration model run
INSERT INTO reward_calibration_model (
    id, location_id,
    model_name, model_type, run_date,
    input_metrics, output_weights,
    calibration_score, total_tokens_distributed, token_per_unit_output,
    epoch, confidence_level, calculation_version, notes,
    status, source_system, source_id, source_raw
) VALUES (
 'a0000000-0000-0000-0000-000000005060',
 'a0000000-0000-0000-0000-000000000001',
 'Adelphi Q1 2026 Calibration',
 'linear_weighted',
 '2026-03-10',
 '{
    "labor_hours": 320,
    "training_improvement_pct": 64.55,
    "trophic_balance_index": 0.833,
    "energy_flow_efficiency_pct": 5.62,
    "pest_reduction_pct": 68.0,
    "soil_carbon_delta_t_ha": 2.80
}'::jsonb,
 '{
    "labor_weight": 0.30,
    "training_weight": 0.15,
    "ecological_weight": 0.35,
    "pest_management_weight": 0.20
}'::jsonb,
 0.7825,
 400.00000000,
 0.0333,
 '2026-Q1',
 72.0,
 'v2026.03',
 'Linear weighted calibration model. 78.25% alignment between output metrics and token distribution. Ecological outcomes weighted highest (35%).',
 'published',
 'pilot_seed', 'adelphi-calibration-q1-2026',
 '{"record_type":"reward_calibration_model","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    calibration_score = EXCLUDED.calibration_score,
    total_tokens_distributed = EXCLUDED.total_tokens_distributed,
    updated_at = NOW();
