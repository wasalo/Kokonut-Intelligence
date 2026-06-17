-- ============================================================
-- Seed: Metric Governance Fields
-- Populates validation_tests, report_usage, deprecation_policy
-- for all 18 metric definitions (17 PRD + baseline_cost)
-- ============================================================

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Revenue cannot be negative"}, {"test": "source_record_ids is not empty", "description": "Must have at least one source record"}]',
    report_usage = ARRAY['Crop NOI Dashboard', 'Eagle View Financial', 'Annual Impact Report'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'crop_revenue';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Net revenue cannot be negative"}, {"test": "source_record_ids is not empty", "description": "Must have at least one source record"}]',
    report_usage = ARRAY['Crop NOI Dashboard', 'Eagle View Financial'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'net_crop_revenue';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Costs cannot be negative"}]',
    report_usage = ARRAY['Crop NOI Dashboard', 'Eagle View Financial'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'direct_crop_cost';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Allocated cost cannot be negative"}]',
    report_usage = ARRAY['Crop NOI Dashboard'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'allocated_shared_cost';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value = net_crop_revenue - direct_crop_cost - allocated_shared_cost", "description": "NOI must match formula derivation"}]',
    report_usage = ARRAY['Crop NOI Dashboard', 'Eagle View Financial', 'Fortune 500'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'crop_noi';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0 AND value <= 100", "description": "Loss rate must be between 0 and 100 percent"}]',
    report_usage = ARRAY['Loss Rate Dashboard', 'Eagle View Harvest'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'loss_rate_pct';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= -100 AND value <= 100", "description": "Margin must be between -100% and 100%"}]',
    report_usage = ARRAY['Eagle View Financial', 'Crop NOI Dashboard'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'operating_margin_pct';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Baseline revenue cannot be negative"}]',
    report_usage = ARRAY['Fortune 500', 'Forecast Engine'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'baseline_revenue';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Baseline asset value cannot be negative"}]',
    report_usage = ARRAY['Fortune 500'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'baseline_asset_value';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Baseline cash flow cannot be negative"}]',
    report_usage = ARRAY['Fortune 500', 'Forecast Engine'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'baseline_cash_flow';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Baseline cost cannot be negative"}]',
    report_usage = ARRAY['Fortune 500', 'Forecast Engine'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'baseline_cost';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Value flowed cannot be negative"}, {"test": "source_record_ids is not empty", "description": "Must have at least one source record"}]',
    report_usage = ARRAY['Value Flow Report', 'Revenue Multiplier'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'value_flowed';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0 AND value <= 100", "description": "Retention rate must be between 0 and 100 percent"}]',
    report_usage = ARRAY['Value Flow Report', 'Revenue Multiplier'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'wallet_retention';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Usage count cannot be negative"}]',
    report_usage = ARRAY['Value Flow Report', 'Revenue Multiplier'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'digital_lego_usage';

UPDATE metric_definition SET
    validation_tests = '[{"test": "metadata includes per-plot deltas", "description": "Result should include plot-level carbon delta breakdown"}]',
    report_usage = ARRAY['Eagle View Environmental', 'Environmental Trends'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'soil_carbon_delta';

UPDATE metric_definition SET
    validation_tests = '[{"test": "metadata includes Shannon index", "description": "Result should include biodiversity index calculation"}]',
    report_usage = ARRAY['Eagle View Environmental', 'Crop Diversity Trend'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'biodiversity_delta';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0 AND value <= 100", "description": "Coverage must be between 0 and 100 percent"}]',
    report_usage = ARRAY['Eagle View Attestations', 'MRV Dashboard'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'attestation_coverage';

UPDATE metric_definition SET
    validation_tests = '[{"test": "value >= 0", "description": "Cost cannot be negative"}]',
    report_usage = ARRAY['Crop NOI Dashboard', 'Eagle View Financial'],
    deprecation_policy = 'Retain historical values. Deprecated after 2 version increments with 90 days notice.'
WHERE metric_key = 'baseline_cost';
