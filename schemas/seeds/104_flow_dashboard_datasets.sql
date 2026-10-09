-- ============================================================
-- 104_flow_dashboard_datasets.sql - VSM pipeline-wide KPIs
-- ============================================================
-- Refreshable dashboard datasets surfacing value-stream KPIs that are
-- not naturally location-scoped: current WIP by stage (excess-inventory
-- waste), event-bus delivery latency and dead-letter rate (conveyance /
-- waiting waste), and ingestion first-time-through yield (%C&A).
-- Pipeline-wide (location_id NULL); refreshed on a schedule.

INSERT INTO dashboard_dataset (id, name, description, dataset_type, location_id, query_sql, refresh_interval_minutes, status, metadata) VALUES
    ('d1040000-0000-0000-0000-000000000001',
     'VSM WIP by Stage',
     'Current work-in-process counts per lifecycle status across the governed pipeline (excess-inventory waste signal).',
     'value_stream',
     NULL,
     'SELECT ''data_stream_post'' AS entity_type, status, COUNT(*) AS wip FROM data_stream_post GROUP BY status '
     'UNION ALL SELECT ''ai_summary'', status, COUNT(*) FROM ai_summary GROUP BY status '
     'UNION ALL SELECT ''impact_claim'', status, COUNT(*) FROM impact_claim GROUP BY status '
     'UNION ALL SELECT ''report_snapshot'', status, COUNT(*) FROM report_snapshot GROUP BY status '
     'UNION ALL SELECT ''stakeholder_feedback'', status, COUNT(*) FROM stakeholder_feedback GROUP BY status '
     'UNION ALL SELECT ''farm_activity'', status, COUNT(*) FROM farm_activity GROUP BY status '
     'UNION ALL SELECT ''harvest_event'', status, COUNT(*) FROM harvest_event GROUP BY status '
     'UNION ALL SELECT ''agent_task'', review_status, COUNT(*) FROM agent_task GROUP BY review_status '
     'ORDER BY entity_type, wip DESC',
     60,
     'published',
     '{"owner": "platform-integrity", "vsm_dimension": "wip"}'::jsonb),

    ('d1040000-0000-0000-0000-000000000002',
     'VSM Event Delivery Latency',
     'Event-bus enqueue-to-process latency by priority and status (waiting / conveyance waste signal).',
     'value_stream',
     NULL,
     'SELECT priority, status, COUNT(*) AS n, '
     'ROUND(AVG(EXTRACT(EPOCH FROM (processed_at - created_at)))::numeric, 3) AS avg_latency_sec, '
     'ROUND(MAX(EXTRACT(EPOCH FROM (processed_at - created_at)))::numeric, 3) AS max_latency_sec '
     'FROM platform_event WHERE processed_at IS NOT NULL GROUP BY priority, status ORDER BY priority',
     60,
     'published',
     '{"owner": "platform-integrity", "vsm_dimension": "latency"}'::jsonb),

    ('d1040000-0000-0000-0000-000000000003',
     'VSM Event Dead-Letter Rate',
     'Share of platform events that exhausted retries and landed in dead-letter (defect / correction waste signal).',
     'value_stream',
     NULL,
     'SELECT (SELECT COUNT(*) FROM platform_event WHERE status = ''dead_letter'') AS dead_letter, '
     '(SELECT COUNT(*) FROM platform_event) AS total_events, '
     'ROUND((SELECT COUNT(*) FROM platform_event WHERE status = ''dead_letter'')::numeric '
     '/ NULLIF((SELECT COUNT(*) FROM platform_event), 0) * 100, 4) AS dead_letter_rate_pct',
     60,
     'published',
     '{"owner": "platform-integrity", "vsm_dimension": "defects"}'::jsonb),

    ('d1040000-0000-0000-0000-000000000004',
     'VSM Ingestion First-Time Yield',
     'Per-source ingestion success rate (success / total) as a first-time-through / %C&A proxy.',
     'value_stream',
     NULL,
     'SELECT source_system, COUNT(*) AS total, '
     'COUNT(*) FILTER (WHERE status = ''success'') AS success, '
     'ROUND(COUNT(*) FILTER (WHERE status = ''success'')::numeric / NULLIF(COUNT(*), 0) * 100, 2) AS fty_pct '
     'FROM ingestion_log GROUP BY source_system ORDER BY fty_pct ASC',
     60,
     'published',
     '{"owner": "platform-integrity", "vsm_dimension": "quality"}'::jsonb)

ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    dataset_type = EXCLUDED.dataset_type,
    query_sql = EXCLUDED.query_sql,
    refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = now();
