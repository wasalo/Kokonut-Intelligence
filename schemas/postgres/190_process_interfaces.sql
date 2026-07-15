-- ============================================================
-- 190_process_interfaces.sql — Cross-Entity Process Interfaces
-- ============================================================
-- Declares handoffs between governed entity types, logs actual
-- handoff events with SLA tracking, and supports end-to-end
-- cross-entity process traces for value-chain analysis.

-- Process handoff declarations (as-is and to-be)
CREATE TABLE IF NOT EXISTS process_handoff (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_type VARCHAR(100) NOT NULL,
    target_entity_type VARCHAR(100) NOT NULL,
    handoff_type VARCHAR(50) NOT NULL CHECK (handoff_type IN (
        'sequential',    -- source must complete before target starts
        'parallel',      -- both can run concurrently
        'conditional',   -- target starts only if condition met
        'event_driven'   -- target starts on source event
    )),
    correlation_key VARCHAR(100),
    sla_hours DOUBLE PRECISION,
    description TEXT,
    UNIQUE (source_entity_type, target_entity_type)
);

-- Handoff observation log (actual handoff events)
CREATE TABLE IF NOT EXISTS process_handoff_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_type VARCHAR(100) NOT NULL,
    source_entity_id UUID NOT NULL,
    target_entity_type VARCHAR(100) NOT NULL,
    target_entity_id UUID,
    handoff_id UUID REFERENCES process_handoff(id),
    handoff_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    elapsed_hours DOUBLE PRECISION,
    met_sla BOOLEAN,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_phl_source
    ON process_handoff_log(source_entity_type, source_entity_id);
CREATE INDEX IF NOT EXISTS idx_phl_target
    ON process_handoff_log(target_entity_type, target_entity_id);
CREATE INDEX IF NOT EXISTS idx_phl_handoff
    ON process_handoff_log(handoff_id);
CREATE INDEX IF NOT EXISTS idx_phl_sla
    ON process_handoff_log(met_sla, handoff_at);

-- Cross-entity process trace (end-to-end value chain)
CREATE TABLE IF NOT EXISTS process_trace (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_key VARCHAR(255) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    step_order INTEGER NOT NULL,
    entered_at TIMESTAMPTZ,
    exited_at TIMESTAMPTZ,
    duration_hours DOUBLE PRECISION,
    UNIQUE (trace_key, entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_pt_trace_key ON process_trace(trace_key);
CREATE INDEX IF NOT EXISTS idx_pt_entity ON process_trace(entity_type, entity_id);

-- ============================================================
-- Seed: Known Process Handoffs
-- ============================================================

-- harvest_event -> data_stream_post (sequential, via location_id)
INSERT INTO process_handoff (source_entity_type, target_entity_type, handoff_type, correlation_key, sla_hours, description) VALUES
    ('harvest_event', 'data_stream_post', 'sequential', 'location_id', 24.0,
     'Published harvest events are surfaced as data stream posts for public visibility.')
ON CONFLICT (source_entity_type, target_entity_type) DO UPDATE SET
    handoff_type = EXCLUDED.handoff_type,
    correlation_key = EXCLUDED.correlation_key,
    sla_hours = EXCLUDED.sla_hours,
    description = EXCLUDED.description;

-- data_stream_post -> impact_claim (sequential, via location_id)
INSERT INTO process_handoff (source_entity_type, target_entity_type, handoff_type, correlation_key, sla_hours, description) VALUES
    ('data_stream_post', 'impact_claim', 'sequential', 'location_id', 72.0,
     'Published data stream posts may trigger impact claim creation when evidence maturity warrants it.')
ON CONFLICT (source_entity_type, target_entity_type) DO UPDATE SET
    handoff_type = EXCLUDED.handoff_type,
    correlation_key = EXCLUDED.correlation_key,
    sla_hours = EXCLUDED.sla_hours,
    description = EXCLUDED.description;

-- farm_activity -> harvest_event (sequential, via location_id)
INSERT INTO process_handoff (source_entity_type, target_entity_type, handoff_type, correlation_key, sla_hours, description) VALUES
    ('farm_activity', 'harvest_event', 'sequential', 'location_id', NULL,
     'Farm activities of type harvest are linked to harvest_event records for yield tracking.')
ON CONFLICT (source_entity_type, target_entity_type) DO UPDATE SET
    handoff_type = EXCLUDED.handoff_type,
    correlation_key = EXCLUDED.correlation_key,
    description = EXCLUDED.description;

-- stakeholder_feedback -> data_stream_post (event_driven, via location_id)
INSERT INTO process_handoff (source_entity_type, target_entity_type, handoff_type, correlation_key, sla_hours, description) VALUES
    ('stakeholder_feedback', 'data_stream_post', 'event_driven', 'location_id', 48.0,
     'Published stakeholder feedback is surfaced as a data stream post with PII redacted.')
ON CONFLICT (source_entity_type, target_entity_type) DO UPDATE SET
    handoff_type = EXCLUDED.handoff_type,
    correlation_key = EXCLUDED.correlation_key,
    sla_hours = EXCLUDED.sla_hours,
    description = EXCLUDED.description;

-- agent_task -> data_stream_post (event_driven, via subject_id)
INSERT INTO process_handoff (source_entity_type, target_entity_type, handoff_type, correlation_key, sla_hours, description) VALUES
    ('agent_task', 'data_stream_post', 'event_driven', 'subject_id', 24.0,
     'Completed agent tasks may produce data stream posts for governed publication.')
ON CONFLICT (source_entity_type, target_entity_type) DO UPDATE SET
    handoff_type = EXCLUDED.handoff_type,
    correlation_key = EXCLUDED.correlation_key,
    sla_hours = EXCLUDED.sla_hours,
    description = EXCLUDED.description;

-- metric_value -> report_snapshot (sequential, via location_id)
INSERT INTO process_handoff (source_entity_type, target_entity_type, handoff_type, correlation_key, sla_hours, description) VALUES
    ('metric_value', 'report_snapshot', 'sequential', 'location_id', NULL,
     'Verified metric values feed into report snapshot generation.')
ON CONFLICT (source_entity_type, target_entity_type) DO UPDATE SET
    handoff_type = EXCLUDED.handoff_type,
    correlation_key = EXCLUDED.correlation_key,
    description = EXCLUDED.description;

COMMENT ON TABLE process_handoff IS 'Declares cross-entity handoffs: type, correlation key, SLA target';
COMMENT ON TABLE process_handoff_log IS 'Records actual handoff events with elapsed time and SLA compliance';
COMMENT ON TABLE process_trace IS 'End-to-end cross-entity traces for value-chain analysis';
