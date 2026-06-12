-- ============================================================
-- 013_prd_completion.sql — PRD completion schema layer
-- ============================================================

-- Kokonut Common Data Schema record.
-- This is the 13-field onboarding contract from kokonut.network docs, linked
-- back to the canonical farm/location tables instead of replacing them.
CREATE TABLE IF NOT EXISTS farm_registry_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID REFERENCES farm(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    registry_slug VARCHAR(255) NOT NULL UNIQUE,
    project_date DATE NOT NULL,
    forecasted_budget NUMERIC(15,2) NOT NULL,
    land_size_m2 NUMERIC(15,4) NOT NULL,
    project_location JSONB NOT NULL DEFAULT '{}', -- coordinates, region, country
    source_of_funding TEXT NOT NULL,
    revenue_streams TEXT[] NOT NULL DEFAULT '{}',
    governance_mechanism VARCHAR(100) NOT NULL, -- moloch_dao, guilds, multisig, cooperative
    token_allocation TEXT NOT NULL,
    public_goods_allocation_pct NUMERIC(6,3) NOT NULL,
    project_summary TEXT NOT NULL,
    local_problem TEXT NOT NULL,
    proposed_solution TEXT NOT NULL,
    target_market TEXT[] NOT NULL DEFAULT '{}',
    record_hash VARCHAR(64),
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    schema_version VARCHAR(50) DEFAULT 'common-data-schema-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE farm_registry_record ALTER COLUMN schema_version TYPE VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_farm_registry_location ON farm_registry_record(location_id);
CREATE INDEX IF NOT EXISTS idx_farm_registry_farm ON farm_registry_record(farm_id);
CREATE INDEX IF NOT EXISTS idx_farm_registry_status ON farm_registry_record(status);
CREATE INDEX IF NOT EXISTS idx_farm_registry_streams ON farm_registry_record USING GIN(revenue_streams);
CREATE INDEX IF NOT EXISTS idx_farm_registry_market ON farm_registry_record USING GIN(target_market);

-- Inputs, tools, equipment, biofertilizer, and inventory movement.
CREATE TABLE IF NOT EXISTS inventory_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    event_date DATE NOT NULL,
    item_name VARCHAR(255) NOT NULL,
    item_type VARCHAR(100), -- seed, tool, equipment, compost, biofertilizer, packaging, other
    event_type VARCHAR(100) NOT NULL, -- received, issued, consumed, produced, adjusted, disposed
    quantity NUMERIC(15,4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    unit_cost NUMERIC(15,4),
    total_cost NUMERIC(15,2),
    currency VARCHAR(10) DEFAULT 'USD',
    supplier VARCHAR(255),
    storage_location VARCHAR(255),
    notes TEXT,
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    schema_version VARCHAR(50),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS crop_cycle_id UUID REFERENCES crop_cycle(id);
ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS event_date DATE;
ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS item_type VARCHAR(100);
ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'USD';
ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS storage_location VARCHAR(255);
ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS evidence_urls TEXT[];
ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS evidence_hashes TEXT[];
ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS created_by UUID;
ALTER TABLE inventory_event ADD COLUMN IF NOT EXISTS updated_by UUID;
ALTER TABLE inventory_event ALTER COLUMN schema_version TYPE VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_inventory_location ON inventory_event(location_id);
CREATE INDEX IF NOT EXISTS idx_inventory_crop_cycle ON inventory_event(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_inventory_date ON inventory_event(event_date);
CREATE INDEX IF NOT EXISTS idx_inventory_item ON inventory_event(item_name);
CREATE INDEX IF NOT EXISTS idx_inventory_status ON inventory_event(status);

-- Infrastructure repair and upkeep.
CREATE TABLE IF NOT EXISTS maintenance_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    infrastructure_asset_id UUID REFERENCES infrastructure_asset(id),
    plot_id UUID REFERENCES plot(id),
    maintenance_date DATE NOT NULL,
    maintenance_type VARCHAR(100), -- inspection, repair, preventive, calibration, replacement, cleaning, other
    issue_description TEXT,
    work_performed TEXT NOT NULL,
    vendor VARCHAR(255),
    labor_hours NUMERIC(10,2),
    parts_used JSONB DEFAULT '[]',
    cost NUMERIC(15,2),
    currency VARCHAR(10) DEFAULT 'USD',
    downtime_hours NUMERIC(10,2),
    next_service_date DATE,
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    schema_version VARCHAR(50),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS infrastructure_asset_id UUID REFERENCES infrastructure_asset(id);
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS plot_id UUID REFERENCES plot(id);
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS maintenance_date DATE;
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS issue_description TEXT;
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS work_performed TEXT;
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS vendor VARCHAR(255);
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS labor_hours NUMERIC(10,2);
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'USD';
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS next_service_date DATE;
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS evidence_urls TEXT[];
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS evidence_hashes TEXT[];
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS created_by UUID;
ALTER TABLE maintenance_event ADD COLUMN IF NOT EXISTS updated_by UUID;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'maintenance_event' AND column_name = 'asset_id'
    ) THEN
        UPDATE maintenance_event
        SET infrastructure_asset_id = asset_id
        WHERE infrastructure_asset_id IS NULL AND asset_id IS NOT NULL;
    END IF;
END $$;
ALTER TABLE maintenance_event ALTER COLUMN schema_version TYPE VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_maintenance_location ON maintenance_event(location_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_asset ON maintenance_event(infrastructure_asset_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_date ON maintenance_event(maintenance_date);
CREATE INDEX IF NOT EXISTS idx_maintenance_status ON maintenance_event(status);

-- Canonical revenue facts for sales, grants, sponsorships, services, DAO disbursements,
-- carbon/biodiversity credits, and other earned value.
CREATE TABLE IF NOT EXISTS revenue_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    partner_id UUID REFERENCES partner(id),
    capital_source_id UUID REFERENCES capital_source(id),
    sales_event_id UUID REFERENCES sales_event(id),
    financial_transaction_id UUID REFERENCES financial_transaction(id),
    treasury_event_id UUID REFERENCES treasury_event(id),
    value_flow_id UUID REFERENCES value_flow_event(id),
    revenue_date DATE NOT NULL,
    revenue_type VARCHAR(100) NOT NULL, -- sale, grant, sponsorship, service, dao_disbursement, carbon_credit, biodiversity_credit, other
    description TEXT,
    amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    exchange_rate NUMERIC(12,6) DEFAULT 1,
    amount_usd NUMERIC(15,2),
    payment_status VARCHAR(50) DEFAULT 'pending', -- pending, partial, paid, overdue, cancelled
    received_at TIMESTAMPTZ,
    public_goods_allocation_amount NUMERIC(15,2),
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    attestation_uid VARCHAR(66),
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    schema_version VARCHAR(50),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS capital_source_id UUID REFERENCES capital_source(id);
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS sales_event_id UUID REFERENCES sales_event(id);
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS financial_transaction_id UUID REFERENCES financial_transaction(id);
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS treasury_event_id UUID REFERENCES treasury_event(id);
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS value_flow_id UUID REFERENCES value_flow_event(id);
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS revenue_date DATE;
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12,6) DEFAULT 1;
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS amount_usd NUMERIC(15,2);
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS received_at TIMESTAMPTZ;
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS public_goods_allocation_amount NUMERIC(15,2);
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS evidence_urls TEXT[];
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS evidence_hashes TEXT[];
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS attestation_uid VARCHAR(66);
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS created_by UUID;
ALTER TABLE revenue_event ADD COLUMN IF NOT EXISTS updated_by UUID;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'revenue_event' AND column_name = 'received_date'
    ) THEN
        UPDATE revenue_event
        SET revenue_date = received_date
        WHERE revenue_date IS NULL AND received_date IS NOT NULL;
    END IF;
END $$;
ALTER TABLE revenue_event ALTER COLUMN schema_version TYPE VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_revenue_location ON revenue_event(location_id);
CREATE INDEX IF NOT EXISTS idx_revenue_crop_cycle ON revenue_event(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_revenue_type ON revenue_event(revenue_type);
CREATE INDEX IF NOT EXISTS idx_revenue_date ON revenue_event(revenue_date);
CREATE INDEX IF NOT EXISTS idx_revenue_status ON revenue_event(status);

-- MRV event payloads that map to Kokonut's ground/remote/community monitoring stack.
CREATE TABLE IF NOT EXISTS mrv_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_registry_record_id UUID REFERENCES farm_registry_record(id),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    mrv_claim_id UUID REFERENCES mrv_claim(id),
    measurement_type VARCHAR(50) NOT NULL, -- ground, remote, community, mixed
    event_timestamp TIMESTAMPTZ NOT NULL,
    ground_data JSONB,
    remote_data JSONB,
    community_data JSONB,
    payload_cid TEXT,
    payload_hash VARCHAR(64),
    private_payload_hash VARCHAR(64),
    source_record_ids UUID[],
    is_attested BOOLEAN DEFAULT FALSE,
    attestation_uid VARCHAR(66),
    attestation_record_id UUID REFERENCES attestation_record(id),
    attested_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    schema_version VARCHAR(50) DEFAULT 'kokonut-mrv-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE mrv_event ALTER COLUMN schema_version TYPE VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_mrv_event_location ON mrv_event(location_id);
CREATE INDEX IF NOT EXISTS idx_mrv_event_registry ON mrv_event(farm_registry_record_id);
CREATE INDEX IF NOT EXISTS idx_mrv_event_type ON mrv_event(measurement_type);
CREATE INDEX IF NOT EXISTS idx_mrv_event_time ON mrv_event(event_timestamp);
CREATE INDEX IF NOT EXISTS idx_mrv_event_status ON mrv_event(status);
CREATE INDEX IF NOT EXISTS idx_mrv_event_uid ON mrv_event(attestation_uid);

-- EAS attestation request metadata. This repo stores request/public metadata and
-- private payload hashes; signing/execution logic belongs to configured EAS/agent services.
CREATE TABLE IF NOT EXISTS attestation_request (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_type VARCHAR(100) NOT NULL,
    subject_id UUID NOT NULL,
    mrv_event_id UUID REFERENCES mrv_event(id),
    mrv_claim_id UUID REFERENCES mrv_claim(id),
    report_snapshot_id UUID REFERENCES report_snapshot(id),
    value_flow_id UUID REFERENCES value_flow_event(id),
    schema_id UUID REFERENCES attestation_schema(id),
    event_type VARCHAR(100) NOT NULL, -- mrv_submission, harvest, funding, impact_report, value_flow, agent_task
    chain VARCHAR(50),
    payload_cid TEXT,
    payload_hash VARCHAR(64),
    private_payload_hash VARCHAR(64),
    attestor_role VARCHAR(100),
    resolver_address VARCHAR(42),
    execution_status VARCHAR(50) DEFAULT 'pending', -- pending, submitted, confirmed, failed, cancelled
    attestation_uid VARCHAR(66),
    tx_hash VARCHAR(66),
    error_message TEXT,
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    requested_by UUID,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_attestation_request_subject ON attestation_request(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_attestation_request_status ON attestation_request(status);
CREATE INDEX IF NOT EXISTS idx_attestation_request_exec ON attestation_request(execution_status);
CREATE INDEX IF NOT EXISTS idx_attestation_request_uid ON attestation_request(attestation_uid);

-- Agent metadata only. Contract identity, payments, escrow, and reputation logic
-- are disclosed as coming from Kokonut Agentic Marketplace and remain external.
CREATE TABLE IF NOT EXISTS agent_identity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name VARCHAR(255) NOT NULL UNIQUE,
    ens_subdomain VARCHAR(255),
    operator_wallet VARCHAR(42),
    registry_chain VARCHAR(50) DEFAULT 'base',
    erc8004_agent_id VARCHAR(255),
    capability_manifest_cid TEXT,
    payment_token VARCHAR(42),
    base_rate_usdc NUMERIC(18,6),
    marketplace_source VARCHAR(255) DEFAULT 'Kokonut-Agentic-Marketplace',
    agent_state VARCHAR(50) DEFAULT 'active', -- active, paused, deregistered
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

ALTER TABLE agent_identity ADD COLUMN IF NOT EXISTS agent_state VARCHAR(50) DEFAULT 'active';

CREATE INDEX IF NOT EXISTS idx_agent_identity_state ON agent_identity(agent_state);
CREATE INDEX IF NOT EXISTS idx_agent_identity_wallet ON agent_identity(operator_wallet);

CREATE TABLE IF NOT EXISTS agent_capability_manifest (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agent_identity(id) ON DELETE CASCADE,
    version VARCHAR(50) NOT NULL,
    manifest JSONB NOT NULL,
    manifest_cid TEXT,
    manifest_hash VARCHAR(64),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    UNIQUE(agent_id, version)
);

CREATE INDEX IF NOT EXISTS idx_agent_manifest_agent ON agent_capability_manifest(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_manifest_active ON agent_capability_manifest(is_active);

CREATE TABLE IF NOT EXISTS agent_task (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES agent_identity(id),
    task_type VARCHAR(100) NOT NULL, -- mrv_submission, harvest_forecast, impact_scoring, grant_draft, soil_health
    subject_type VARCHAR(100),
    subject_id UUID,
    requested_by UUID,
    inputs JSONB NOT NULL DEFAULT '{}',
    output JSONB,
    output_cid TEXT,
    output_hash VARCHAR(64),
    payment_metadata JSONB DEFAULT '{}',
    execution_status VARCHAR(50) DEFAULT 'queued', -- queued, running, completed, failed, cancelled
    review_status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    attestation_request_id UUID REFERENCES attestation_request(id),
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_task_agent ON agent_task(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_type ON agent_task(task_type);
CREATE INDEX IF NOT EXISTS idx_agent_task_exec ON agent_task(execution_status);
CREATE INDEX IF NOT EXISTS idx_agent_task_review ON agent_task(review_status);

CREATE TABLE IF NOT EXISTS agent_action_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES agent_identity(id),
    task_id UUID REFERENCES agent_task(id),
    action VARCHAR(100) NOT NULL,
    collection VARCHAR(100),
    record_id UUID,
    payload_hash VARCHAR(64),
    action_result VARCHAR(50) DEFAULT 'success', -- success, failed, skipped
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE agent_action_log ADD COLUMN IF NOT EXISTS action_result VARCHAR(50) DEFAULT 'success';

CREATE INDEX IF NOT EXISTS idx_agent_action_agent ON agent_action_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_action_task ON agent_action_log(task_id);
CREATE INDEX IF NOT EXISTS idx_agent_action_collection ON agent_action_log(collection, record_id);

-- Metric governance extensions required by PRD Section 12.
ALTER TABLE metric_definition ADD COLUMN IF NOT EXISTS validation_tests JSONB DEFAULT '[]';
ALTER TABLE metric_definition ADD COLUMN IF NOT EXISTS report_usage TEXT[] DEFAULT '{}';
ALTER TABLE metric_definition ADD COLUMN IF NOT EXISTS deprecation_policy TEXT;
ALTER TABLE metric_definition ADD COLUMN IF NOT EXISTS definition_state VARCHAR(50) DEFAULT 'active';

-- Source lineage extensions for non-operational evidence-bearing tables.
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE soil_sample ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE soil_sample ALTER COLUMN schema_version TYPE VARCHAR(50);

ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE soil_carbon_measurement ALTER COLUMN schema_version TYPE VARCHAR(50);

ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE species_observation ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE species_observation ALTER COLUMN schema_version TYPE VARCHAR(50);

ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE remote_sensing_observation ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE remote_sensing_observation ALTER COLUMN schema_version TYPE VARCHAR(50);

ALTER TABLE weather_observation ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE weather_observation ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE weather_observation ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE weather_observation ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE weather_observation ALTER COLUMN schema_version TYPE VARCHAR(50);

ALTER TABLE sensor_reading ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE sensor_reading ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE sensor_reading ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE sensor_reading ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE sensor_reading ALTER COLUMN schema_version TYPE VARCHAR(50);

ALTER TABLE environmental_baseline ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE environmental_baseline ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE environmental_baseline ADD COLUMN IF NOT EXISTS source_raw JSONB;
ALTER TABLE environmental_baseline ADD COLUMN IF NOT EXISTS schema_version VARCHAR(50);
ALTER TABLE environmental_baseline ALTER COLUMN schema_version TYPE VARCHAR(50);

ALTER TABLE mrv_claim ADD COLUMN IF NOT EXISTS source_system VARCHAR(100);
ALTER TABLE mrv_claim ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);
ALTER TABLE mrv_claim ADD COLUMN IF NOT EXISTS source_raw JSONB;

ALTER TABLE attestation_record ADD COLUMN IF NOT EXISTS private_payload_hash VARCHAR(64);
ALTER TABLE attestation_record ADD COLUMN IF NOT EXISTS payload_cid TEXT;

ALTER TABLE ingestion_log ADD COLUMN IF NOT EXISTS processor_version VARCHAR(50);
