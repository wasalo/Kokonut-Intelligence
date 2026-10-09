-- ============================================================
-- 192_process_costing.sql — Process Costing + Benchmarking
-- ============================================================
-- Attributes costs to process steps, benchmarks across locations,
-- calculates process ROI, and tracks Kaizen improvement initiatives.

-- Process cost definitions (standard cost per instance)
CREATE TABLE IF NOT EXISTS process_cost (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_key VARCHAR(100) NOT NULL REFERENCES process_map(process_key) ON DELETE CASCADE,
    entity_type VARCHAR(100),
    cost_type VARCHAR(50) NOT NULL CHECK (cost_type IN ('labor', 'compute', 'external', 'opportunity')),
    cost_category VARCHAR(100),
    cost_per_instance DOUBLE PRECISION,
    currency VARCHAR(10) DEFAULT 'USD',
    source_ref VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pc_process ON process_cost(process_key);

-- Process cost observations (actual costs per entity instance)
CREATE TABLE IF NOT EXISTS process_cost_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    process_key VARCHAR(100) REFERENCES process_map(process_key) ON DELETE SET NULL,
    cost_type VARCHAR(50) NOT NULL,
    cost_amount DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_event_id UUID
);

CREATE INDEX IF NOT EXISTS idx_pco_entity ON process_cost_observation(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_pco_process ON process_cost_observation(process_key);
CREATE INDEX IF NOT EXISTS idx_pco_recorded ON process_cost_observation(recorded_at);

-- Cross-location process benchmarks
CREATE TABLE IF NOT EXISTS process_benchmark (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    period_start DATE,
    period_end DATE,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(40),
    sample_size INTEGER,
    benchmark_type VARCHAR(20) CHECK (benchmark_type IN ('internal', 'industry', 'target')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pb_metric ON process_benchmark(metric_name, entity_type);
CREATE INDEX IF NOT EXISTS idx_pb_location ON process_benchmark(location_id);

-- Process improvement tracking (Kaizen)
CREATE TABLE IF NOT EXISTS process_improvement (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_key VARCHAR(100) NOT NULL REFERENCES process_map(process_key) ON DELETE CASCADE,
    initiative_name VARCHAR(255) NOT NULL,
    description TEXT,
    improvement_type VARCHAR(50) CHECK (improvement_type IN ('kaizen', 'six_sigma', 'reengineering', 'automation')),
    status VARCHAR(50) DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'approved', 'in_progress', 'completed', 'cancelled')),
    expected_benefit TEXT,
    actual_benefit TEXT,
    owner_id UUID,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    due_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pi_process ON process_improvement(process_key);
CREATE INDEX IF NOT EXISTS idx_pi_status ON process_improvement(status);
CREATE INDEX IF NOT EXISTS idx_pi_location ON process_improvement(location_id);

-- ============================================================
-- Seed: Standard Costs for Core Processes
-- ============================================================

-- Farm Operations
INSERT INTO process_cost (process_key, entity_type, cost_type, cost_category, cost_per_instance, currency, source_ref) VALUES
    ('farm_operations', 'farm_activity', 'labor', 'field_data_entry', 2.50, 'USD', 'Average farmer data entry time'),
    ('farm_operations', 'farm_activity', 'compute', 'validation', 0.01, 'USD', 'System validation cost'),
    ('farm_operations', 'farm_activity', 'opportunity', 'review_time', 1.00, 'USD', 'Manager review time allocation')
ON CONFLICT DO NOTHING;

-- Harvest Management
INSERT INTO process_cost (process_key, entity_type, cost_type, cost_category, cost_per_instance, currency, source_ref) VALUES
    ('harvest_management', 'harvest_event', 'labor', 'harvest_recording', 5.00, 'USD', 'Harvest data recording time'),
    ('harvest_management', 'harvest_event', 'labor', 'quality_check', 3.00, 'USD', 'Quality inspection time'),
    ('harvest_management', 'harvest_event', 'compute', 'yield_calculation', 0.02, 'USD', 'Yield computation cost')
ON CONFLICT DO NOTHING;

-- Data Publication
INSERT INTO process_cost (process_key, entity_type, cost_type, cost_category, cost_per_instance, currency, source_ref) VALUES
    ('data_publication', 'data_stream_post', 'labor', 'content_creation', 10.00, 'USD', 'Content creation and review'),
    ('data_publication', 'data_stream_post', 'labor', 'editorial_review', 8.00, 'USD', 'Editorial review time'),
    ('data_publication', 'data_stream_post', 'compute', 'blockchain_anchor', 0.50, 'USD', 'EAS attestation gas cost'),
    ('data_publication', 'data_stream_post', 'external', 'ipfs_storage', 0.10, 'USD', 'IPFS pinning cost')
ON CONFLICT DO NOTHING;

-- Impact Verification
INSERT INTO process_cost (process_key, entity_type, cost_type, cost_category, cost_per_instance, currency, source_ref) VALUES
    ('impact_verification', 'impact_claim', 'labor', 'evidence_collection', 15.00, 'USD', 'Evidence gathering and compilation'),
    ('impact_verification', 'impact_claim', 'labor', 'expert_review', 25.00, 'USD', 'Expert verification time'),
    ('impact_verification', 'impact_claim', 'external', 'third_party_verification', 50.00, 'USD', 'External verification fee')
ON CONFLICT DO NOTHING;

-- Metric Governance
INSERT INTO process_cost (process_key, entity_type, cost_type, cost_category, cost_per_instance, currency, source_ref) VALUES
    ('metric_governance', 'metric_value', 'compute', 'metric_computation', 0.05, 'USD', 'Metric calculation compute'),
    ('metric_governance', 'metric_value', 'labor', 'verification', 5.00, 'USD', 'Human verification time')
ON CONFLICT DO NOTHING;

-- Work Management
INSERT INTO process_cost (process_key, entity_type, cost_type, cost_category, cost_per_instance, currency, source_ref) VALUES
    ('work_management', 'work_item', 'labor', 'task_management', 3.00, 'USD', 'Task assignment and tracking'),
    ('work_management', 'work_item', 'labor', 'escalation_handling', 10.00, 'USD', 'Escalation resolution time')
ON CONFLICT DO NOTHING;

-- Event Delivery
INSERT INTO process_cost (process_key, entity_type, cost_type, cost_category, cost_per_instance, currency, source_ref) VALUES
    ('event_delivery', NULL, 'compute', 'event_processing', 0.001, 'USD', 'Per-event processing cost'),
    ('event_delivery', NULL, 'compute', 'retry_overhead', 0.005, 'USD', 'Retry processing cost')
ON CONFLICT DO NOTHING;

-- Stakeholder Feedback
INSERT INTO process_cost (process_key, entity_type, cost_type, cost_category, cost_per_instance, currency, source_ref) VALUES
    ('stakeholder_feedback', 'stakeholder_feedback', 'labor', 'feedback_review', 5.00, 'USD', 'Feedback review and redaction'),
    ('stakeholder_feedback', 'stakeholder_feedback', 'labor', 'follow_up', 8.00, 'USD', 'Follow-up action time')
ON CONFLICT DO NOTHING;

-- Agent Execution
INSERT INTO process_cost (process_key, entity_type, cost_type, cost_category, cost_per_instance, currency, source_ref) VALUES
    ('agent_execution', 'agent_task', 'compute', 'llm_inference', 0.10, 'USD', 'LLM inference cost per task'),
    ('agent_execution', 'agent_task', 'compute', 'data_retrieval', 0.02, 'USD', 'Data fetch and preparation'),
    ('agent_execution', 'agent_task', 'labor', 'human_review', 5.00, 'USD', 'Human review of agent output')
ON CONFLICT DO NOTHING;

-- Reporting
INSERT INTO process_cost (process_key, entity_type, cost_type, cost_category, cost_per_instance, currency, source_ref) VALUES
    ('reporting', 'report_snapshot', 'compute', 'report_generation', 0.15, 'USD', 'Report generation compute'),
    ('reporting', 'report_snapshot', 'labor', 'report_review', 10.00, 'USD', 'Report review and approval'),
    ('reporting', 'report_snapshot', 'external', 'pdf_rendering', 0.05, 'USD', 'PDF rendering service')
ON CONFLICT DO NOTHING;

COMMENT ON TABLE process_cost IS 'Standard cost definitions per process step (labor, compute, external, opportunity)';
COMMENT ON TABLE process_cost_observation IS 'Actual cost observations per entity instance';
COMMENT ON TABLE process_benchmark IS 'Cross-location process performance benchmarks';
COMMENT ON TABLE process_improvement IS 'Kaizen and process improvement initiative tracking';
