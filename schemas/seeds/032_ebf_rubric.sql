-- ============================================================
-- Seed: EBF P0 rubric reference data
-- ============================================================

WITH pillar_seed AS (
    SELECT * FROM (VALUES
        ('air_quality', 'Air Quality', 'Air quality and atmospheric co-benefits from vegetation, soil cover, agroforestry, and reduced emissions.', 'ebf_environmental', 1, 'kg_co2e_per_acre'),
        ('water_management', 'Water Management', 'Water retention, runoff reduction, infiltration, watershed protection, and water quality evidence.', 'ebf_environmental', 2, 'runoff_reduction_pct'),
        ('soil_health', 'Soil Health', 'Soil organic carbon, soil structure, microbial activity, erosion reduction, and living-cover evidence.', 'ebf_environmental', 3, 'soc_change_pct'),
        ('biodiversity', 'Biodiversity', 'Species richness, crop diversity, habitat structure, pollinator support, and agroforestry diversity.', 'ebf_environmental', 4, 'species_richness_index'),
        ('carbon_sequestration', 'Carbon Sequestration', 'Farm-wide carbon balance, tree carbon, soil carbon, and externally verified carbon methodology evidence.', 'ebf_sustainability', 5, 'total_farm_co2e'),
        ('equity_community', 'Equity & Community', 'Local participation, training, stakeholder voice, benefit distribution, and community accountability.', 'ebf_social', 6, 'local_worker_pct'),
        ('implementation_quality', 'Implementation Quality', 'Quality of implementation against regenerative practices, SMART KPIs, operating discipline, and review cadence.', 'ebf_sustainability', 7, 'smart_kpi_completion')
    ) AS seed(pillar_key, pillar_name, description, dimension_key, sort_order, default_metric_key)
)
INSERT INTO ebf_pillar (pillar_key, pillar_name, description, framework_id, dimension_id, sort_order, status, metadata)
SELECT
    ps.pillar_key,
    ps.pillar_name,
    ps.description,
    fw.id,
    dim.id,
    ps.sort_order,
    'active',
    jsonb_build_object('default_metric_key', ps.default_metric_key, 'source', 'EBF P0 rubric seed')
FROM pillar_seed ps
JOIN impact_framework fw ON fw.framework_key = 'ebf'
JOIN impact_dimension dim ON dim.dimension_key = ps.dimension_key
ON CONFLICT (pillar_key) DO UPDATE SET
    pillar_name = EXCLUDED.pillar_name,
    description = EXCLUDED.description,
    framework_id = EXCLUDED.framework_id,
    dimension_id = EXCLUDED.dimension_id,
    sort_order = EXCLUDED.sort_order,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

WITH rubric_seed AS (
    SELECT
        ep.id AS pillar_id,
        ep.pillar_key,
        score_value,
        score_value::numeric(3,1) AS band_min,
        CASE WHEN score_value = 9 THEN 10.0 ELSE (score_value + 1)::numeric(3,1) END AS band_max,
        CASE
            WHEN score_value <= 1 THEN 'insufficient'
            WHEN score_value <= 3 THEN 'emerging'
            WHEN score_value <= 5 THEN 'developing'
            WHEN score_value <= 7 THEN 'strong'
            ELSE 'leading'
        END AS band_label,
        CASE
            WHEN score_value <= 1 THEN 'Little or no structured evidence; score remains internal until supporting records mature.'
            WHEN score_value <= 3 THEN 'Early evidence exists but coverage, recency, or review quality is limited.'
            WHEN score_value <= 5 THEN 'Structured and reviewed evidence supports a credible baseline with known gaps.'
            WHEN score_value <= 7 THEN 'Evidence-linked and repeatable performance supports a strong pillar assessment.'
            ELSE 'High-quality, mature evidence supports leading practice; external review is expected for public carbon claims.'
        END AS description,
        CASE
            WHEN score_value <= 1 THEN ARRAY['Create baseline record', 'Identify missing measurements']
            WHEN score_value <= 3 THEN ARRAY['Collect structured records', 'Assign reviewer']
            WHEN score_value <= 5 THEN ARRAY['Link evidence records', 'Document uncertainty']
            WHEN score_value <= 7 THEN ARRAY['Maintain monitoring cadence', 'Review against rubric']
            ELSE ARRAY['Independent review or attestation', 'Document calibration rationale']
        END AS required_practices,
        CASE
            WHEN score_value <= 1 THEN ARRAY['narrative or self-reported evidence']
            WHEN score_value <= 3 THEN ARRAY['structured source records']
            WHEN score_value <= 5 THEN ARRAY['reviewed records', 'evidence links']
            WHEN score_value <= 7 THEN ARRAY['evidence-linked records', 'review notes']
            ELSE ARRAY['attested or externally verified records', 'calibration report']
        END AS evidence_requirements
    FROM ebf_pillar ep
    CROSS JOIN generate_series(0, 9) AS score_value
)
INSERT INTO ebf_rubric_band (
    pillar_id, pillar_key, score_value, band_min, band_max, band_label,
    description, required_practices, evidence_requirements, rubric_version
)
SELECT
    pillar_id,
    pillar_key,
    score_value,
    band_min,
    band_max,
    band_label,
    description,
    required_practices,
    evidence_requirements,
    '2026.1'
FROM rubric_seed
ON CONFLICT (pillar_id, score_value, rubric_version) DO UPDATE SET
    pillar_key = EXCLUDED.pillar_key,
    band_min = EXCLUDED.band_min,
    band_max = EXCLUDED.band_max,
    band_label = EXCLUDED.band_label,
    description = EXCLUDED.description,
    required_practices = EXCLUDED.required_practices,
    evidence_requirements = EXCLUDED.evidence_requirements;

INSERT INTO metric_definition (
    metric_key, display_name, description, formula, source_tables, inclusion_rules,
    exclusion_rules, unit, data_type, owner, version, update_frequency, active,
    for_stakeholder_group, participatory, validation_tests, report_usage, deprecation_policy
)
VALUES
('ebf_air_quality_score', 'EBF Air Quality Score', 'Normalized 0-10 EBF score for air quality and atmospheric co-benefits.', 'Generated from EBF rubric and approved source metrics.', ARRAY['ebf_score', 'ebf_score_evidence', 'metric_value'], 'Include reviewed EBF air quality score rows with evidence links.', 'Exclude draft-only scores from public reporting.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'annually', TRUE, NULL, FALSE, '["0 <= value <= 10", "public score requires evidence maturity >= 4"]'::jsonb, ARRAY['ebf_scorecard', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.'),
('ebf_water_management_score', 'EBF Water Management Score', 'Normalized 0-10 EBF score for water retention, runoff reduction, and watershed evidence.', 'Generated from EBF rubric and approved source metrics.', ARRAY['ebf_score', 'ebf_score_evidence', 'metric_value'], 'Include reviewed EBF water management score rows with evidence links.', 'Exclude draft-only scores from public reporting.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'annually', TRUE, NULL, FALSE, '["0 <= value <= 10", "public score requires evidence maturity >= 4"]'::jsonb, ARRAY['ebf_scorecard', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.'),
('ebf_soil_health_score', 'EBF Soil Health Score', 'Normalized 0-10 EBF score for soil health, soil organic carbon, erosion, and living-cover evidence.', 'Generated from EBF rubric and approved source metrics.', ARRAY['ebf_score', 'ebf_score_evidence', 'metric_value'], 'Include reviewed EBF soil health score rows with evidence links.', 'Exclude draft-only scores from public reporting.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'annually', TRUE, NULL, FALSE, '["0 <= value <= 10", "public score requires evidence maturity >= 4"]'::jsonb, ARRAY['ebf_scorecard', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.'),
('ebf_biodiversity_score', 'EBF Biodiversity Score', 'Normalized 0-10 EBF score for species richness, habitat, crop diversity, and pollinator support.', 'Generated from EBF rubric and approved source metrics.', ARRAY['ebf_score', 'ebf_score_evidence', 'metric_value'], 'Include reviewed EBF biodiversity score rows with evidence links.', 'Exclude draft-only scores from public reporting.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'annually', TRUE, NULL, FALSE, '["0 <= value <= 10", "public score requires evidence maturity >= 4"]'::jsonb, ARRAY['ebf_scorecard', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.'),
('ebf_carbon_sequestration_score', 'EBF Carbon Sequestration Score', 'Normalized 0-10 EBF score for farm-wide carbon balance and sequestration evidence.', 'Generated from EBF rubric and approved source metrics; public carbon scoring requires Level 6 evidence.', ARRAY['ebf_score', 'ebf_score_evidence', 'metric_value'], 'Include reviewed EBF carbon score rows with Level 6 evidence for public reporting.', 'Exclude non-Level-6 public carbon scores.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'annually', TRUE, NULL, FALSE, '["0 <= value <= 10", "public carbon score requires evidence maturity = 6"]'::jsonb, ARRAY['ebf_scorecard', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.'),
('ebf_equity_community_score', 'EBF Equity & Community Score', 'Normalized 0-10 EBF score for local participation, training, stakeholder voice, and benefit distribution.', 'Generated from EBF rubric and approved public-safe aggregate source metrics.', ARRAY['ebf_score', 'ebf_score_evidence', 'stakeholder_feedback', 'stakeholder_outcome'], 'Include aggregate, consent-safe equity evidence only.', 'Exclude raw private stakeholder feedback from public reporting.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'annually', TRUE, NULL, TRUE, '["0 <= value <= 10", "public equity evidence uses consent-safe summaries"]'::jsonb, ARRAY['ebf_scorecard', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.'),
('ebf_implementation_quality_score', 'EBF Implementation Quality Score', 'Normalized 0-10 EBF score for SMART KPI completion and regenerative implementation discipline.', 'Generated from EBF rubric and approved source metrics.', ARRAY['ebf_score', 'ebf_score_evidence', 'regenerative_practice_checklist', 'farm_activity'], 'Include reviewed implementation quality evidence with score linkage.', 'Exclude draft-only operational notes from public reporting.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'annually', TRUE, NULL, FALSE, '["0 <= value <= 10", "public score requires evidence maturity >= 4"]'::jsonb, ARRAY['ebf_scorecard', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.'),
('ebf_overall_score', 'EBF Overall Score', 'Overall EBF score summarizing the seven pillar scores with confidence and maturity context.', 'Average of available pillar scores after evidence gates and calibration review.', ARRAY['ebf_scorecard', 'ebf_score'], 'Include scorecards with seven pillar scores and documented calibration.', 'Do not use as farm ranking; preserve caveats and confidence context.', 'score_0_10', 'numeric', 'Impact Guild', 1, 'annually', TRUE, NULL, FALSE, '["0 <= value <= 10", "published scorecard requires evidence maturity >= 4"]'::jsonb, ARRAY['ebf_scorecard', 'cids_indicator_report'], 'Supersede through metric_version before changing public interpretation.')
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
    version = EXCLUDED.version,
    update_frequency = EXCLUDED.update_frequency,
    active = EXCLUDED.active,
    for_stakeholder_group = EXCLUDED.for_stakeholder_group,
    participatory = EXCLUDED.participatory,
    validation_tests = EXCLUDED.validation_tests,
    report_usage = EXCLUDED.report_usage,
    deprecation_policy = EXCLUDED.deprecation_policy,
    updated_at = NOW();
