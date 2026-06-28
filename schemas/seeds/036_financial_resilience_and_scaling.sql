-- ============================================================
-- Seed: Financial resilience, risk mitigation, scaling, and publication dashboards
-- ============================================================

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables,
    inclusion_rules, exclusion_rules, unit, data_type, owner, version,
    update_frequency, active, validation_tests, report_usage, deprecation_policy
) VALUES
('grant_dependency_pct', 'Grant Dependency %', 'Share of total inflows supplied by grants during a reporting period.', 'grants_received / total_inflows * 100', ARRAY['cash_flow_snapshot', 'capital_source'], 'Use verified cash-flow snapshots and active capital sources.', 'Exclude unverified pledged funding.', 'percentage', 'percentage', 'Finance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "total_inflows > 0"]'::jsonb, ARRAY['financial_sustainability', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('reinvestment_rate_pct', 'Reinvestment Rate %', 'Share of generated value reinvested into farm operations, infrastructure, or replication readiness.', 'reinvestment_value / eligible_value_flowed * 100', ARRAY['value_flow_event', 'cash_flow_snapshot'], 'Use verified value-flow and cash-flow records.', 'Exclude grants unless explicitly reinvested after receipt.', 'percentage', 'percentage', 'Finance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "verified flows only"]'::jsonb, ARRAY['financial_sustainability', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('public_goods_allocation_pct', 'Public Goods Allocation %', 'Share of eligible revenue or net proceeds allocated to public goods.', 'public_goods_allocation / eligible_revenue * 100', ARRAY['cash_flow_snapshot', 'value_flow_event', 'farm_registry_record'], 'Use verified allocations and published allocation policy.', 'Exclude informal commitments without source records.', 'percentage', 'percentage', 'Finance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "source allocation present"]'::jsonb, ARRAY['financial_sustainability', 'green_paper', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.'),
('sustainability_runway_months', 'Sustainability Runway Months', 'Estimated months of operating runway from current reserves and projected net cash flow.', 'running_balance / monthly_net_burn', ARRAY['cash_flow_snapshot', 'financial_sustainability_plan'], 'Use verified cash-flow snapshots and published sustainability plans.', 'Exclude restricted funds unavailable for operations.', 'months', 'numeric', 'Finance Guild', 1, 'quarterly', TRUE, '["value >= 0", "assumptions documented"]'::jsonb, ARRAY['financial_sustainability', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('risk_mitigation_coverage_pct', 'Risk Mitigation Coverage %', 'Share of material risks with published mitigation owner, cadence, and residual risk assessment.', 'mitigated_material_risks / material_risks * 100', ARRAY['risk_mitigation_register'], 'Use published register entries with owner and review cadence.', 'Exclude draft or rejected risks.', 'percentage', 'percentage', 'Governance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 100", "owner_role is present"]'::jsonb, ARRAY['risk_mitigation', 'green_paper'], 'Supersede through metric_version before changing public interpretation.'),
('scaling_readiness_score', 'Scaling Readiness Score', 'Composite readiness score for replication based on capital, partners, dependencies, and risk gates.', 'Roadmap evidence normalized to 0-10', ARRAY['scaling_roadmap_milestone', 'financial_sustainability_plan', 'risk_mitigation_register'], 'Use published roadmap milestones and risk gates.', 'Exclude unsupported unlimited-scaling claims.', 'score_0_10', 'numeric', 'Governance Guild', 1, 'quarterly', TRUE, '["0 <= value <= 10", "risk gates documented"]'::jsonb, ARRAY['scaling_roadmap', 'green_paper'], 'Supersede through metric_version before changing public interpretation.')
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

INSERT INTO dashboard_dataset (id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata) VALUES
('a0000000-0000-0000-0000-000000003601', 'Financial Sustainability Summary', 'Public-safe farm financial sustainability, grant dependency, reinvestment, and public-goods allocation summary.', 'financial_sustainability', NULL, 'dashboards/metabase/sql/28_financial_sustainability.sql', 1440, 'published', '{"owner":"finance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003602', 'Risk Mitigation Register', 'Public-safe risk mitigation, insurance, oversight, and support register.', 'risk_mitigation', NULL, 'dashboards/metabase/sql/29_risk_mitigation.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003603', 'Scaling Roadmap', 'Public-safe scaling roadmap milestones with partner requirements, resources, dependencies, and risk gates.', 'scaling_roadmap', NULL, 'dashboards/metabase/sql/30_scaling_roadmap.sql', 1440, 'published', '{"owner":"governance_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb),
('a0000000-0000-0000-0000-000000003604', 'Green Paper Publication Status', 'Publication review status, open question count, approvals, and publication proof metadata.', 'green_paper_publication', NULL, 'dashboards/metabase/sql/31_green_paper_publication.sql', 1440, 'published', '{"owner":"communications_guild","refresh_cron":"0 6 * * *","privacy":"public_safe"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
