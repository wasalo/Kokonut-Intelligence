-- ============================================================
-- Seed: EBF P2 portfolio dashboard dataset definitions
-- ============================================================

INSERT INTO dashboard_dataset (id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata) VALUES
    ('d1000000-0000-0000-0000-000000000025',
     'EBF Portfolio Messy Rollup',
     'Cross-farm EBF pillar roll-up by confidence and evidence maturity. This dataset is not a farm ranking.',
     'ebf_portfolio',
     NULL,
     'SELECT * FROM v_public_ebf_pillar_summary ORDER BY pillar_name',
     1440,
     'published',
     '{"refresh_cron":"0 9 * * *","owner":"impact_guild","comparison_mode":"messy_rollup","caveat":"Compare pillars, confidence, and maturity; do not rank farms."}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    location_id = EXCLUDED.location_id,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
