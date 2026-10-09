-- 195_service_catalog.sql
-- Service Catalog + Data Quality Score tables.
-- Provides a platform-wide BRM Service Component Reference Model (SCRM) and a data quality scoring framework.

CREATE TABLE IF NOT EXISTS service_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    version VARCHAR(20) DEFAULT '1.0.0',
    category VARCHAR(50) NOT NULL CHECK (category IN ('core', 'analytics', 'agent', 'support', 'ingestion', 'export')),
    description TEXT,
    health_endpoint VARCHAR(200),
    owner VARCHAR(100),
    sla_target_ms INTEGER,
    dependencies JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'deprecated', 'retired')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_service_registry_category ON service_registry (category);
CREATE INDEX IF NOT EXISTS idx_service_registry_status ON service_registry (status);

CREATE TABLE IF NOT EXISTS data_quality_rule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(100) NOT NULL,
    dimension VARCHAR(20) NOT NULL CHECK (dimension IN ('completeness', 'accuracy', 'timeliness', 'consistency')),
    rule_type VARCHAR(50) NOT NULL CHECK (rule_type IN ('not_null', 'freshness', 'range', 'regex', 'referential', 'custom')),
    rule_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    severity VARCHAR(20) DEFAULT 'warning' CHECK (severity IN ('critical', 'warning', 'info')),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_quality_rule_entity_type ON data_quality_rule (entity_type);
CREATE INDEX IF NOT EXISTS idx_data_quality_rule_dimension ON data_quality_rule (dimension);

CREATE TABLE IF NOT EXISTS data_quality_score (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    completeness_pct DOUBLE PRECISION DEFAULT 0,
    accuracy_pct DOUBLE PRECISION DEFAULT 0,
    timeliness_pct DOUBLE PRECISION DEFAULT 0,
    consistency_pct DOUBLE PRECISION DEFAULT 0,
    overall_score DOUBLE PRECISION DEFAULT 0,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rule_results JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_data_quality_score_entity ON data_quality_score (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_data_quality_score_scored_at ON data_quality_score (scored_at);

-- Seed service_registry: core (12)
INSERT INTO service_registry (name, version, category, description, status)
VALUES
    ('gateway', '1.0.0', 'core', 'HTTP gateway with auth, rate limiting, and route protection', 'active'),
    ('grpc', '1.0.0', 'core', 'gRPC service for cross-service communication', 'active'),
    ('scheduler', '1.0.0', 'core', 'Durable task scheduler with claim, retry, and dead-letter semantics', 'active'),
    ('security', '1.0.0', 'core', 'JWT token issuance, verification, and audit logging', 'active'),
    ('metadata_api', '1.0.0', 'core', 'Linked-data Metadata Graph API serving JSON-LD and IRI resolution', 'active'),
    ('federation', '1.0.0', 'core', 'Cross-node federation, registration, and data sharing', 'active'),
    ('data_stream', '1.0.0', 'core', 'Governed data stream posts with lifecycle, comments, and blockchain anchoring', 'active'),
    ('data_module', '1.0.0', 'core', 'Content-hash storage, resolver registry, and data attestation', 'active'),
    ('iri', '1.0.0', 'core', 'Deterministic IRI generation, resolution, history, and anchoring', 'active'),
    ('rdf', '1.0.0', 'core', 'RDF triple store built from governed records with SPARQL translation', 'active'),
    ('certificates', '1.0.0', 'core', 'Retirement certificate generation and verification', 'active'),
    ('credit_class', '1.0.0', 'core', 'Credit class/batch hierarchy, enrollment, marketplace, and bridge operations', 'active')
ON CONFLICT (name) DO UPDATE SET
    version = EXCLUDED.version,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    status = EXCLUDED.status;

-- Seed service_registry: analytics (30)
INSERT INTO service_registry (name, version, category, description, status)
VALUES
    ('process_mining', '1.0.0', 'analytics', 'Process variant discovery, conformance checking, and case timeline analysis', 'active'),
    ('process_health', '1.0.0', 'analytics', 'Process health dashboard combining cycle time, conformance, and escalation data', 'active'),
    ('process_gap', '1.0.0', 'analytics', 'Gap analysis between discovered and target process models', 'active'),
    ('process_costing', '1.0.0', 'analytics', 'Cost attribution and allocation for mined process variants', 'active'),
    ('process_simulation', '1.0.0', 'analytics', 'Discrete-event simulation of process models', 'active'),
    ('process_architecture', '1.0.0', 'analytics', 'Target process architecture and conformance gap analysis', 'active'),
    ('process_interfaces', '1.0.0', 'analytics', 'Cross-system interface mapping for process integration', 'active'),
    ('value_stream', '1.0.0', 'analytics', 'Value-stream mapping, WIP tracking, lead times, and bottleneck analysis', 'active'),
    ('predictive_bpm', '1.0.0', 'analytics', 'Predictive SLA breach and cycle-time forecasting for running cases', 'active'),
    ('process_model_sync', '1.0.0', 'analytics', 'Workflow-spec-to-process-model synchronization', 'active'),
    ('digital_twin', '1.0.0', 'analytics', 'Digital twin crop-growth simulation, scenarios, and what-if analysis', 'active'),
    ('yield_monitoring', '1.0.0', 'analytics', 'Yield recording, trend analysis, prediction, and benchmark comparison', 'active'),
    ('precision_irrigation', '1.0.0', 'analytics', 'Irrigation zone management, scheduling, and water-use efficiency reporting', 'active'),
    ('pest_management', '1.0.0', 'analytics', 'IPM scouting, thresholds, interventions, pesticide tracking, and compliance', 'active'),
    ('crop_rotation', '1.0.0', 'analytics', 'Multi-year crop rotation planning and impact tracking', 'active'),
    ('nutrient_budget', '1.0.0', 'analytics', 'Nutrient balance budgeting, soil testing, and recommendation engine', 'active'),
    ('energy_monitoring', '1.0.0', 'analytics', 'Energy consumption, renewable tracking, and cost analysis', 'active'),
    ('waste_management', '1.0.0', 'analytics', 'Waste recording, composting, recycling, and incident management', 'active'),
    ('landscape_conservation', '1.0.0', 'analytics', 'Habitat, corridor, hedgerow, buffer, and biodiversity tracking', 'active'),
    ('pollinator_health', '1.0.0', 'analytics', 'Pollinator observations, habitat, hive management, and pesticide risk', 'active'),
    ('digital_finance', '1.0.0', 'analytics', 'Digital finance accounts, insurance, loans, and portfolio analysis', 'active'),
    ('traceability', '1.0.0', 'analytics', 'Batch creation, custody chain, quality, provenance, and food-safety tracking', 'active'),
    ('extension', '1.0.0', 'analytics', 'Extension modules, peer groups, delivery, and effectiveness tracking', 'active'),
    ('farmer_identity', '1.0.0', 'analytics', 'Farmer profiles, credentials, KYC, roles, permissions, and device registration', 'active'),
    ('marketplace', '1.0.0', 'analytics', 'Marketplace listings, price recording, orders, and evaluation', 'active'),
    ('cooperative', '1.0.0', 'analytics', 'Cooperative management, assets, collective purchasing, and market orders', 'active'),
    ('data_governance', '1.0.0', 'analytics', 'Consent, access audit, portability, sharing agreements, and retention policies', 'active'),
    ('swot', '1.0.0', 'analytics', 'SWOT analysis creation, listing, and suggestion engine', 'active'),
    ('prm_metrics', '1.0.0', 'analytics', 'BRM Process Reference Model metrics and scoring', 'active'),
    ('service_catalog', '1.0.0', 'analytics', 'Platform service registry and data quality scoring framework', 'active')
ON CONFLICT (name) DO UPDATE SET
    version = EXCLUDED.version,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    status = EXCLUDED.status;

-- Seed service_registry: agent (8)
INSERT INTO service_registry (name, version, category, description, status)
VALUES
    ('ai_summary', '1.0.0', 'agent', 'AI-generated combined summaries from governed location data', 'active'),
    ('cids_agent', '1.0.0', 'agent', 'CIDS v3.2.0 export agent wrapping the canonical exporter', 'active'),
    ('feedback_agent', '1.0.0', 'agent', 'Feedback synthesis from public summaries and aggregate signals', 'active'),
    ('wellbeing_agent', '1.0.0', 'agent', 'Holistic wellbeing synthesis across 8 Forms of Capital', 'active'),
    ('resilience_agent', '1.0.0', 'agent', 'Resilience synthesis combining CRISP, weather, and financial signals', 'active'),
    ('capital_efficiency_agent', '1.0.0', 'agent', 'Capital efficiency analysis and optimization recommendations', 'active'),
    ('commons_agent', '1.0.0', 'agent', 'Commons liberation and governance synthesis', 'active'),
    ('gnh_agent', '1.0.0', 'agent', 'Gross National Happiness alignment assessment', 'active')
ON CONFLICT (name) DO UPDATE SET
    version = EXCLUDED.version,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    status = EXCLUDED.status;

-- Seed service_registry: support (5)
INSERT INTO service_registry (name, version, category, description, status)
VALUES
    ('events', '1.0.0', 'support', 'Event bus: publish, process, stats, cleanup, dead-letter replay and disposal', 'active'),
    ('stream', '1.0.0', 'support', 'Stream processor: ingest, window, alert, and stats for real-time sensor data', 'active'),
    ('drivers', '1.0.0', 'support', 'Driver registry: install, test, and manage platform drivers', 'active'),
    ('metrics', '1.0.0', 'support', 'Metric computation, verification, and governed metric_value storage', 'active'),
    ('core', '1.0.0', 'support', 'Core health checks, feature flags, and shared utilities', 'active')
ON CONFLICT (name) DO UPDATE SET
    version = EXCLUDED.version,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    status = EXCLUDED.status;

-- Seed service_registry: ingestion (5)
INSERT INTO service_registry (name, version, category, description, status)
VALUES
    ('sensor_ingester', '1.0.0', 'ingestion', 'CSV and single-value sensor data ingestion with calibration support', 'active'),
    ('anomaly_detector', '1.0.0', 'ingestion', 'Rule-based and ML anomaly detection on sensor readings', 'active'),
    ('market_data', '1.0.0', 'ingestion', 'Market price ingestion from World Bank, Yahoo Finance, and seed sources', 'active'),
    ('weather_forecast', '1.0.0', 'ingestion', 'OpenWeatherMap 5-day forecast ingestion and spray-window analysis', 'active'),
    ('remote_sensing_fetcher', '1.0.0', 'ingestion', 'Scheduled remote sensing job management and GEE data fetching', 'active')
ON CONFLICT (name) DO UPDATE SET
    version = EXCLUDED.version,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    status = EXCLUDED.status;

-- Seed service_registry: export (3)
INSERT INTO service_registry (name, version, category, description, status)
VALUES
    ('report_generator', '1.0.0', 'export', 'Multi-type report generation with auto-mode and climate-impact reports', 'active'),
    ('spreadsheet_bridge', '1.0.0', 'export', 'CSV template, import dry-run, and farm-activity spreadsheet bridging', 'active'),
    ('dataset_refresh', '1.0.0', 'export', 'Dashboard dataset refresh from stored SQL queries', 'active')
ON CONFLICT (name) DO UPDATE SET
    version = EXCLUDED.version,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    status = EXCLUDED.status;

-- Seed data_quality_rule: completeness rules (not_null)
INSERT INTO data_quality_rule (entity_type, dimension, rule_type, rule_config, severity, active)
VALUES
    ('farm_activity', 'completeness', 'not_null', '{"fields": ["location_id", "crop_id", "activity_date"]}'::jsonb, 'critical', TRUE),
    ('harvest_event', 'completeness', 'not_null', '{"fields": ["location_id", "crop_id", "yield_amount"]}'::jsonb, 'critical', TRUE),
    ('traceability_batch', 'completeness', 'not_null', '{"fields": ["location_id", "crop", "quantity"]}'::jsonb, 'critical', TRUE),
    ('data_stream_post', 'completeness', 'not_null', '{"fields": ["location_id", "title", "content"]}'::jsonb, 'critical', TRUE)
ON CONFLICT DO NOTHING;

-- Seed data_quality_rule: timeliness rules (freshness)
INSERT INTO data_quality_rule (entity_type, dimension, rule_type, rule_config, severity, active)
VALUES
    ('farm_activity', 'timeliness', 'freshness', '{"max_age_days": 30, "timestamp_field": "activity_date"}'::jsonb, 'warning', TRUE),
    ('harvest_event', 'timeliness', 'freshness', '{"max_age_days": 7, "timestamp_field": "harvest_date"}'::jsonb, 'warning', TRUE),
    ('weather_observation', 'timeliness', 'freshness', '{"max_age_hours": 24, "timestamp_field": "observed_at"}'::jsonb, 'warning', TRUE),
    ('sensor_reading', 'timeliness', 'freshness', '{"max_age_hours": 1, "timestamp_field": "read_at"}'::jsonb, 'critical', TRUE)
ON CONFLICT DO NOTHING;

-- Seed data_quality_rule: accuracy rules (range)
INSERT INTO data_quality_rule (entity_type, dimension, rule_type, rule_config, severity, active)
VALUES
    ('harvest_event', 'accuracy', 'range', '{"field": "yield_amount", "min": 0, "max": null, "operator": "gt"}'::jsonb, 'critical', TRUE),
    ('soil_sample', 'accuracy', 'range', '{"field": "ph", "min": 0, "max": 14}'::jsonb, 'critical', TRUE),
    ('weather_observation', 'accuracy', 'range', '{"field": "temperature", "min": -50, "max": 60}'::jsonb, 'warning', TRUE)
ON CONFLICT DO NOTHING;

-- Seed data_quality_rule: consistency rules (referential)
INSERT INTO data_quality_rule (entity_type, dimension, rule_type, rule_config, severity, active)
VALUES
    ('harvest_event', 'consistency', 'referential', '{"field": "plot_id", "references_table": "farm_zone", "references_field": "id"}'::jsonb, 'critical', TRUE),
    ('traceability_batch', 'consistency', 'referential', '{"field": "location_id", "references_table": "location", "references_field": "id"}'::jsonb, 'critical', TRUE),
    ('farm_activity', 'consistency', 'referential', '{"field": "location_id", "references_table": "location", "references_field": "id"}'::jsonb, 'critical', TRUE)
ON CONFLICT DO NOTHING;

-- Trigger for updated_at on service_registry
DROP TRIGGER IF EXISTS trg_service_registry_updated_at ON service_registry;
CREATE TRIGGER trg_service_registry_updated_at
    BEFORE UPDATE ON service_registry
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE service_registry IS 'Platform-wide BRM Service Component Reference Model registry cataloging all services with category, status, SLA targets, and dependencies';
COMMENT ON TABLE data_quality_rule IS 'Data quality rules defining not-null, freshness, range, regex, referential, and custom checks across entity types and dimensions';
COMMENT ON TABLE data_quality_score IS 'Computed data quality scores per entity across completeness, accuracy, timeliness, and consistency dimensions with per-rule results';
