-- ============================================================
-- 107_stakeholder_cockpit.sql - Stakeholder cockpit datasets
-- ============================================================

INSERT INTO dashboard_dataset (id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata) VALUES
 ('d1070000-0000-0000-0000-000000000001', 'Stakeholder Cockpit Internal', 'Operator aggregate of stakeholder landscape, engagement, grievances, decisions, trust risks, and stewardship obligations.', 'stakeholder_cockpit', NULL, 'SELECT * FROM v_stakeholder_cockpit_internal', 60, 'published', '{"owner":"stakeholder-governance","privacy":"internal","refresh_cron":"hourly"}'::jsonb),
 ('d1070000-0000-0000-0000-000000000002', 'Stakeholder Cockpit Public', 'Public-safe aggregate of published outcomes, consented feedback, representation summaries, verified distributions, and ecological stewardship.', 'stakeholder_cockpit', NULL, 'SELECT * FROM v_public_stakeholder_cockpit', 1440, 'published', '{"owner":"stakeholder-governance","privacy":"public_safe","refresh_cron":"daily"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
 name = EXCLUDED.name, description = EXCLUDED.description, dataset_type = EXCLUDED.dataset_type,
 query_sql = EXCLUDED.query_sql, refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
 status = EXCLUDED.status, metadata = EXCLUDED.metadata, updated_at = NOW();
