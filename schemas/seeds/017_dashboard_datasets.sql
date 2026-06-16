-- ============================================================
-- Seed: Dashboard Dataset Definitions (metadata registry)
-- ============================================================

INSERT INTO dashboard_dataset (id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata) VALUES
    -- Farm Operations Overview
    ('d1000000-0000-0000-0000-000000000001',
     'Farm Operations Overview',
     'Operational summary: activities, labor hours, loss events, and activity verification rate',
     'farm_operations',
     'a0000000-0000-0000-0000-000000000001',
     'SELECT fa.activity_type, COUNT(*) as count, SUM(labor_hours) as total_hours FROM farm_activity fa WHERE fa.location_id = ''a0000000-0000-0000-0000-000000000001'' GROUP BY fa.activity_type ORDER BY count DESC',
     60,
     'published',
     '{"refresh_cron": "0 * * * *", "owner": "operations_team"}'::jsonb),

    -- Crop NOI Breakdown
    ('d1000000-0000-0000-0000-000000000002',
     'Crop NOI Breakdown',
     'Net operating income by crop cycle: revenue, allocated costs, margins',
     'crop_noi',
     'a0000000-0000-0000-0000-000000000001',
     'SELECT c.name as crop_name, cc.cycle_name, ns.noi, ns.operating_margin_pct FROM noi_snapshot ns JOIN crop_cycle cc ON ns.crop_cycle_id = cc.id JOIN crop c ON cc.crop_id = c.id WHERE ns.location_id = ''a0000000-0000-0000-0000-000000000001'' ORDER BY ns.period_end DESC',
     1440,
     'published',
     '{"refresh_cron": "0 6 * * *", "owner": "finance_team"}'::jsonb),

    -- Expense Breakdown
    ('d1000000-0000-0000-0000-000000000003',
     'Expense Breakdown',
     'Expense categories, allocation methods, and cost trends',
     'expenses',
     'a0000000-0000-0000-0000-000000000001',
     'SELECT ee.category, COUNT(*) as count, SUM(ee.amount) as total FROM expense_event ee WHERE ee.location_id = ''a0000000-0000-0000-0000-000000000001'' AND ee.status IN (''verified'',''published'') GROUP BY ee.category ORDER BY total DESC',
     1440,
     'published',
     '{"refresh_cron": "0 6 * * *", "owner": "finance_team"}'::jsonb),

    -- Environmental Monitoring
    ('d1000000-0000-0000-0000-000000000004',
     'Environmental Monitoring',
     'NDVI trends, soil carbon, biodiversity observations, and loss events',
     'environmental',
     'a0000000-0000-0000-0000-000000000001',
     'SELECT rso.observation_date, rso.ndvi, rso.canopy_cover_pct FROM remote_sensing_observation rso WHERE rso.location_id = ''a0000000-0000-0000-0000-000000000001'' ORDER BY rso.observation_date DESC LIMIT 100',
     360,
     'published',
     '{"refresh_cron": "0 */6 * * *", "owner": "ecology_team"}'::jsonb),

    -- Web3 and Attestation Status
    ('d1000000-0000-0000-0000-000000000005',
     'Web3 and Attestation Status',
     'Attestation records, MRV claims, and Web3 interaction metrics',
     'web3',
     'a0000000-0000-0000-0000-000000000001',
     'SELECT ar.status, COUNT(*) as count FROM attestation_record ar WHERE ar.subject_id = ''a0000000-0000-0000-0000-000000000001'' GROUP BY ar.status',
     1440,
     'published',
     '{"refresh_cron": "0 8 * * *", "owner": "web3_team"}'::jsonb)
ON CONFLICT (id) DO NOTHING;
