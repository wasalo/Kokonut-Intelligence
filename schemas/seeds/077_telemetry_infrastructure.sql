-- ============================================================
-- 077_telemetry_infrastructure.sql — Seed data
-- ============================================================

-- Data freshness SLAs for all configured sources
INSERT INTO data_freshness_config (source_system, description, expected_interval_minutes, stale_threshold_minutes, critical_threshold_minutes, location_scoped, is_active) VALUES
('weather', 'OpenWeatherMap current weather observations', 360, 720, 1440, TRUE, TRUE),
('sensors', 'IoT sensor readings via CSV or API', 5, 30, 120, TRUE, TRUE),
('remote_sensing', 'Satellite/drone vegetation index observations', 10080, 20160, 43200, TRUE, TRUE),
('market_data', 'World Bank commodity price observations', 1440, 2880, 10080, FALSE, TRUE),
('eas_indexer', 'EAS attestation indexing from Celo/Optimism/Base', 15, 30, 60, FALSE, TRUE),
('rpc_indexer', 'Ethereum/L2 wallet activity indexing', 30, 60, 240, FALSE, TRUE),
('gnosis_indexer', 'Gnosis Chain governance event indexing', 120, 240, 720, FALSE, TRUE)
ON CONFLICT (source_system) DO UPDATE SET
    description = EXCLUDED.description,
    expected_interval_minutes = EXCLUDED.expected_interval_minutes,
    stale_threshold_minutes = EXCLUDED.stale_threshold_minutes,
    critical_threshold_minutes = EXCLUDED.critical_threshold_minutes,
    location_scoped = EXCLUDED.location_scoped,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- Adelphi remote sensing fetch job (GEE provider)
INSERT INTO remote_sensing_job (id, location_id, provider, cloud_max_pct, cadence_days, status, metadata) VALUES
('a0000000-0000-0000-0000-000000000900', 'a0000000-0000-0000-0000-000000000001', 'gee', 20.0, 7, 'active', '{"description":"Weekly Sentinel-2 NDVI monitoring for Adelphi","bands":["NDVI","NDRE","EVI","SAVI","MSAVI"]}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    provider = EXCLUDED.provider,
    cloud_max_pct = EXCLUDED.cloud_max_pct,
    cadence_days = EXCLUDED.cadence_days,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
