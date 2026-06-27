-- ============================================================
-- Seed: EBF P1 dashboard dataset definitions
-- ============================================================

INSERT INTO dashboard_dataset (id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata) VALUES
    ('d1000000-0000-0000-0000-000000000022',
     'EBF Farm Scorecard',
     'Public-safe EBF scorecard rows with seven pillars, confidence labels, and evidence maturity context.',
     'ebf_scorecard',
     NULL,
     'SELECT * FROM v_public_ebf_scorecard ORDER BY period_end DESC, location_name, pillar_key',
     1440,
     'published',
     '{"refresh_cron":"0 6 * * *","owner":"impact_guild","caveat":"Do not use as farm ranking."}'::jsonb),
    ('d1000000-0000-0000-0000-000000000023',
     'EBF Evidence Gaps',
     'Internal EBF evidence gap matrix by scorecard, pillar, evidence maturity, and confidence.',
     'ebf_evidence_gap',
     NULL,
     'SELECT * FROM v_ebf_evidence_gap_summary ORDER BY location_name, scorecard_id, pillar_key',
     1440,
     'verified',
     '{"refresh_cron":"0 7 * * *","owner":"impact_guild","public_safe":false}'::jsonb),
    ('d1000000-0000-0000-0000-000000000024',
     'EBF Calibration History',
     'Calibration sessions, reviewer decisions, reports, and rubric versions.',
     'ebf_calibration',
     NULL,
     'SELECT * FROM v_ebf_calibration_history ORDER BY session_date DESC',
     1440,
     'verified',
     '{"refresh_cron":"0 8 * * *","owner":"impact_guild","public_safe":false}'::jsonb)
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
