-- ============================================================
-- 188_process_architecture.sql — BPM Process Architecture
-- ============================================================
-- Declares the process map (Management / Core / Support taxonomy),
-- process ownership (RACI at process level), and links entity types
-- to their governing processes. Inspired by BPM best practices:
-- process maps, process interfaces, and process ownership.

-- Process map: the canonical taxonomy of business processes.
CREATE TABLE IF NOT EXISTS process_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    process_type VARCHAR(20) NOT NULL
        CHECK (process_type IN ('management', 'core', 'support')),
    parent_process_key VARCHAR(100) REFERENCES process_map(process_key),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organization(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pm_type ON process_map(process_type);
CREATE INDEX IF NOT EXISTS idx_pm_parent ON process_map(parent_process_key);

-- Process ownership (RACI at process level).
CREATE TABLE IF NOT EXISTS process_ownership (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_key VARCHAR(100) NOT NULL REFERENCES process_map(process_key) ON DELETE CASCADE,
    party_type VARCHAR(20) NOT NULL
        CHECK (party_type IN ('staff', 'farmer', 'agent', 'team')),
    party_id UUID NOT NULL,
    raci_role VARCHAR(20) NOT NULL
        CHECK (raci_role IN ('responsible', 'accountable', 'consulted', 'informed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (process_key, party_type, party_id, raci_role)
);

CREATE INDEX IF NOT EXISTS idx_po_process ON process_ownership(process_key);

-- Link entity types to their governing processes.
CREATE TABLE IF NOT EXISTS process_entity_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_key VARCHAR(100) NOT NULL REFERENCES process_map(process_key) ON DELETE CASCADE,
    entity_type VARCHAR(100) NOT NULL UNIQUE,
    workflow_spec_id VARCHAR(100),
    lifecycle_model VARCHAR(50) DEFAULT '5-state',
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pem_process ON process_entity_mapping(process_key);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS trg_process_map_updated_at ON process_map;
CREATE TRIGGER trg_process_map_updated_at
    BEFORE UPDATE ON process_map
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- Seed: Process Map
-- ============================================================

-- Management processes
INSERT INTO process_map (process_key, name, description, process_type) VALUES
    ('work_management', 'Work Management', 'Task assignment, tracking, and completion', 'management'),
    ('financial_planning', 'Financial Planning', 'Budget creation, approval, and variance analysis', 'management'),
    ('performance_management', 'Performance Management', 'Objective setting, KPI tracking, and reviews', 'management'),
    ('portfolio_management', 'Portfolio Management', 'Program and project lifecycle governance', 'management'),
    ('decision_management', 'Decision Management', 'Policy-driven decisions with human approval gates', 'management'),
    ('process_governance', 'Process Governance', 'Process architecture, maturity, and improvement', 'management')
ON CONFLICT (process_key) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    process_type = EXCLUDED.process_type;

-- Core processes
INSERT INTO process_map (process_key, name, description, process_type) VALUES
    ('farm_operations', 'Farm Operations', 'Farm activity recording and lifecycle', 'core'),
    ('harvest_management', 'Harvest Management', 'Harvest event recording and verification', 'core'),
    ('data_publication', 'Data Publication', 'Data stream post creation, review, and publication', 'core'),
    ('impact_verification', 'Impact Verification', 'Impact claim creation and evidence review', 'core'),
    ('stakeholder_feedback', 'Stakeholder Feedback', 'Feedback collection, consent, and publication', 'core'),
    ('agent_execution', 'Agent Execution', 'AI agent task lifecycle and review', 'core'),
    ('reporting', 'Reporting', 'Report generation, review, and publication', 'core'),
    ('metric_governance', 'Metric Governance', 'Metric computation, verification, and publication', 'core'),
    ('carbon_lifecycle', 'Carbon Lifecycle', 'Carbon credit issuance, trading, and retirement', 'core'),
    ('marketplace', 'Marketplace', 'Market orders, listings, and transactions', 'core')
ON CONFLICT (process_key) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    process_type = EXCLUDED.process_type;

-- Support processes
INSERT INTO process_map (process_key, name, description, process_type) VALUES
    ('event_delivery', 'Event Delivery', 'Durable event bus delivery, retry, and dead-letter', 'support'),
    ('escalation_management', 'Escalation Management', 'SLA breach detection and escalation', 'support'),
    ('process_analytics', 'Process Analytics', 'Process mining, predictive BPM, and SPC', 'support'),
    ('feedback_automation', 'Feedback Automation', 'Outcome tracking and threshold auto-tuning', 'support'),
    ('systems_thinking', 'Systems Thinking', 'Causal loops, leverage points, and archetypes', 'support')
ON CONFLICT (process_key) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    process_type = EXCLUDED.process_type;

-- ============================================================
-- Seed: Entity Type → Process Mapping
-- ============================================================
INSERT INTO process_entity_mapping (process_key, entity_type, workflow_spec_id, lifecycle_model, description) VALUES
    -- Core: standard 5-state publication pipeline
    ('farm_operations', 'farm_activity', 'farm_activity', '5-state', 'Farm activity records with governed lifecycle'),
    ('harvest_management', 'harvest_event', 'harvest_event', '5-state', 'Harvest events with governed lifecycle'),
    ('data_publication', 'data_stream_post', 'data_stream_post', '5-state', 'Data stream posts with governed lifecycle'),
    ('impact_verification', 'impact_claim', 'impact_claim', '5-state', 'Impact claims with governed lifecycle'),
    ('stakeholder_feedback', 'stakeholder_feedback', 'stakeholder_feedback', '5-state', 'Stakeholder feedback with consent and lifecycle'),
    ('agent_execution', 'agent_task', 'agent_task', '5-state', 'AI agent tasks with review lifecycle'),
    ('reporting', 'report_snapshot', 'report_snapshot', '5-state', 'Report snapshots with governed lifecycle'),
    ('metric_governance', 'metric_value', 'metric_value', '2-state', 'Metric values with verification lifecycle'),
    ('data_publication', 'ai_summary', 'ai_summary', '5-state', 'AI summaries with governed lifecycle'),
    -- Management: custom lifecycles
    ('work_management', 'work_item', 'work_item', 'custom', 'Work items with assignment and blocking'),
    ('financial_planning', 'financial_plan', 'budget', 'custom', 'Financial plans with approval gates'),
    ('performance_management', 'objective', 'objective', 'custom', 'Objective reviews with health tracking'),
    ('portfolio_management', 'project', 'project', 'custom', 'Projects with hold/resume lifecycle'),
    ('portfolio_management', 'program', NULL, 'custom', 'Programs aggregating projects'),
    -- Support: operational lifecycle
    ('event_delivery', 'event_delivery', 'event_bus_delivery', 'custom', 'Event bus delivery with retries'),
    ('marketplace', 'market_order', NULL, 'custom', 'Market orders with delivery lifecycle')
ON CONFLICT (entity_type) DO UPDATE SET
    process_key = EXCLUDED.process_key,
    workflow_spec_id = EXCLUDED.workflow_spec_id,
    lifecycle_model = EXCLUDED.lifecycle_model,
    description = EXCLUDED.description;

-- ============================================================
-- Seed: Process Ownership (default RACI for each process)
-- ============================================================
-- Ownership is assigned at the organization/location level.
-- These are template assignments; real assignments are created
-- via the API when organizations and locations are provisioned.
-- The seed provides the canonical accountable role per process.

COMMENT ON TABLE process_map IS 'Process taxonomy: Management / Core / Support hierarchy';
COMMENT ON TABLE process_ownership IS 'RACI responsibility assignments at process level';
COMMENT ON TABLE process_entity_mapping IS 'Links governed entity types to their governing process and workflow spec';
