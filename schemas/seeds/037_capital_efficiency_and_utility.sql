-- ============================================================
-- 037_capital_efficiency_and_utility.sql — Capital efficiency metrics and dashboards
-- ============================================================

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    validation_tests, report_usage, deprecation_policy
) VALUES
('capital_efficiency_usd_per_output', 'Capital Efficiency USD Per Output', 'Output value produced per dollar of capital deployed in a governed scenario.', 'gross_output_value_usd / capital_deployed_usd', ARRAY['capital_efficiency_scenario'], 'Use published scenarios with documented assumptions.', 'Exclude draft scenarios and guaranteed-return claims.', 'ratio', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["capital_deployed_usd > 0", "value >= 0"]'::jsonb, ARRAY['capital_efficiency', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('regenerative_cost_savings_pct', 'Regenerative Cost Savings %', 'Observed cost reduction associated with a regenerative practice compared with a documented baseline.', '(baseline_cost_usd - observed_cost_usd) / baseline_cost_usd * 100', ARRAY['regenerative_efficiency_observation', 'farm_practice_event'], 'Use reviewed baseline and observed cost records.', 'Exclude observations without baseline context.', 'percentage', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["-100 <= value <= 100", "baseline_cost_usd > 0"]'::jsonb, ARRAY['capital_efficiency', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('practice_payback_months', 'Practice Payback Months', 'Estimated months for a regenerative practice to recover implementation cost through savings or incremental output.', 'implementation_cost_usd / monthly_savings_or_incremental_value', ARRAY['regenerative_efficiency_observation'], 'Use documented implementation cost and conservative benefit assumptions.', 'Exclude payback claims without limitations.', 'months', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["value >= 0", "assumptions documented"]'::jsonb, ARRAY['capital_efficiency', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('governance_decision_latency_days', 'Governance Decision Latency Days', 'Days from proposal creation to decision or execution for DAO/community governance records.', 'decision_at - proposal_created_at', ARRAY['governance_throughput_observation', 'governance_event', 'dao_proposal'], 'Use proposal creation and execution timestamps from governed records.', 'Exclude private off-platform discussions without timestamps.', 'days', 'numeric', 'Governance Guild', 1, 'monthly', TRUE, '["value >= 0", "proposal_code present"]'::jsonb, ARRAY['governance_throughput', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('capital_leverage_ratio', 'Capital Leverage Ratio', 'Total output and public-goods value generated per dollar of capital deployed.', '(gross_output_value_usd + public_goods_value_usd) / capital_deployed_usd', ARRAY['capital_efficiency_scenario'], 'Use public-safe scenario values and documented assumptions.', 'Exclude private capital terms and unsupported multiplier claims.', 'ratio', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["capital_deployed_usd > 0", "value >= 0"]'::jsonb, ARRAY['capital_efficiency', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('capital_provider_utility_score', 'Capital Provider Utility Score', 'Scenario score for blended capital-provider utility across financial, public-goods, verification, and learning outputs.', 'Reviewer-normalized 0-10 scenario score', ARRAY['capital_provider_utility_scenario'], 'Use published public-safe utility scenarios with limitations.', 'Exclude securities-style guaranteed-return claims.', 'score_0_10', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 10", "limitations present"]'::jsonb, ARRAY['capital_provider_utility', 'green_paper'], 'Supersede through metric_version before changing public interpretation.')
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

INSERT INTO dashboard_dataset (
    id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata
) VALUES
('a0000000-0000-0000-0000-000000003701', 'Capital Efficiency Summary', 'Public-safe capital efficiency scenarios and capital leverage ratios.', 'capital_efficiency', NULL, 'dashboards/metabase/sql/32_capital_efficiency.sql', 1440, 'published', '{"owner":"finance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003702', 'Governance Throughput Summary', 'Public-safe DAO/community proposal decision and execution latency.', 'governance_throughput', NULL, 'dashboards/metabase/sql/33_governance_throughput.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003703', 'Capital Provider Utility Summary', 'Public-safe capital-provider utility scenarios with limitations.', 'capital_provider_utility', NULL, 'dashboards/metabase/sql/34_capital_provider_utility.sql', 1440, 'published', '{"owner":"finance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
