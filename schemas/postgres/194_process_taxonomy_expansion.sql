-- ============================================================
-- 194_process_taxonomy_expansion.sql — Process Taxonomy Expansion
-- ============================================================
-- Expands the BPM process taxonomy with 6 new core processes,
-- their entity mappings, SLA targets, and cross-entity handoffs.

-- ============================================================
-- New Process Map Entries
-- ============================================================

INSERT INTO process_map (process_key, name, description, process_type) VALUES
    ('traceability', 'Traceability', 'Batch tracking, custody chain, quality checks, and provenance', 'core'),
    ('digital_finance', 'Digital Finance', 'Accounts, transactions, insurance, and loans', 'core'),
    ('pest_management', 'Pest Management', 'Scouting, interventions, IPM compliance, and resistance monitoring', 'core'),
    ('emergency_response', 'Emergency Response', 'Incident reporting, response, and resolution', 'core'),
    ('cooperative_management', 'Cooperative Management', 'Cooperative creation, membership, assets, and collective orders', 'core'),
    ('extension_training', 'Extension & Training', 'Module enrollment, peer groups, assessment, and delivery', 'core')
ON CONFLICT (process_key) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    process_type = EXCLUDED.process_type;

-- ============================================================
-- New Entity Type → Process Mappings
-- ============================================================

INSERT INTO process_entity_mapping (process_key, entity_type, workflow_spec_id, lifecycle_model, description) VALUES
    ('traceability', 'traceability_batch', 'traceability_batch', '5-state', 'Traceability batches with custody and provenance lifecycle'),
    ('digital_finance', 'insurance_claim', 'insurance_claim', '5-state', 'Insurance claims with evidence and approval lifecycle'),
    ('pest_management', 'pest_intervention', 'pest_intervention', '5-state', 'Pest interventions with IPM compliance lifecycle'),
    ('emergency_response', 'emergency_incident', 'emergency_incident', '5-state', 'Emergency incidents with response and resolution lifecycle'),
    ('cooperative_management', 'cooperative_order', 'cooperative_order', '5-state', 'Cooperative orders with collective purchase lifecycle'),
    ('extension_training', 'extension_enrollment', 'extension_enrollment', '5-state', 'Extension enrollments with progress and assessment lifecycle')
ON CONFLICT (entity_type) DO UPDATE SET
    process_key = EXCLUDED.process_key,
    workflow_spec_id = EXCLUDED.workflow_spec_id,
    lifecycle_model = EXCLUDED.lifecycle_model,
    description = EXCLUDED.description;

-- ============================================================
-- SLA Targets: Traceability
-- ============================================================

INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('traceability', 'traceability_batch', 'lead_time_days', 5.0, 'lte', 'days', 'Target: <5 days batch tracking to provenance'),
    ('traceability', 'traceability_batch', 'fty_pct', 85.0, 'gte', 'percent', 'Target: 85% first-time-through yield'),
    ('traceability', 'traceability_batch', 'cycle_time_days', 7.0, 'lte', 'days', 'Target: <7 days end-to-end traceability cycle')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- ============================================================
-- SLA Targets: Digital Finance
-- ============================================================

INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('digital_finance', 'insurance_claim', 'lead_time_days', 3.0, 'lte', 'days', 'Target: <3 days for claim processing'),
    ('digital_finance', 'insurance_claim', 'fty_pct', 90.0, 'gte', 'percent', 'Target: 90% first-time-through yield'),
    ('digital_finance', 'insurance_claim', 'cycle_time_days', 5.0, 'lte', 'days', 'Target: <5 days end-to-end claim cycle')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- ============================================================
-- SLA Targets: Pest Management
-- ============================================================

INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('pest_management', 'pest_intervention', 'lead_time_days', 2.0, 'lte', 'days', 'Target: <2 days for pest intervention response'),
    ('pest_management', 'pest_intervention', 'fty_pct', 80.0, 'gte', 'percent', 'Target: 80% first-time-through yield'),
    ('pest_management', 'pest_intervention', 'cycle_time_days', 4.0, 'lte', 'days', 'Target: <4 days end-to-end pest management cycle')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- ============================================================
-- SLA Targets: Emergency Response
-- ============================================================

INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('emergency_response', 'emergency_incident', 'lead_time_days', 1.0, 'lte', 'days', 'Target: <1 day for emergency incident response'),
    ('emergency_response', 'emergency_incident', 'fty_pct', 75.0, 'gte', 'percent', 'Target: 75% first-time-through yield'),
    ('emergency_response', 'emergency_incident', 'cycle_time_days', 3.0, 'lte', 'days', 'Target: <3 days end-to-end emergency resolution')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- ============================================================
-- SLA Targets: Cooperative Management
-- ============================================================

INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('cooperative_management', 'cooperative_order', 'lead_time_days', 7.0, 'lte', 'days', 'Target: <7 days for cooperative order processing'),
    ('cooperative_management', 'cooperative_order', 'fty_pct', 80.0, 'gte', 'percent', 'Target: 80% first-time-through yield'),
    ('cooperative_management', 'cooperative_order', 'cycle_time_days', 14.0, 'lte', 'days', 'Target: <14 days end-to-end cooperative order cycle')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- ============================================================
-- SLA Targets: Extension & Training
-- ============================================================

INSERT INTO process_target (process_key, entity_type, metric_name, target_value, target_direction, unit, source_ref) VALUES
    ('extension_training', 'extension_enrollment', 'lead_time_days', 5.0, 'lte', 'days', 'Target: <5 days for enrollment processing'),
    ('extension_training', 'extension_enrollment', 'fty_pct', 85.0, 'gte', 'percent', 'Target: 85% first-time-through yield'),
    ('extension_training', 'extension_enrollment', 'cycle_time_days', 10.0, 'lte', 'days', 'Target: <10 days end-to-end training cycle')
ON CONFLICT (process_key, entity_type, metric_name) DO UPDATE SET
    target_value = EXCLUDED.target_value,
    target_direction = EXCLUDED.target_direction,
    unit = EXCLUDED.unit,
    source_ref = EXCLUDED.source_ref;

-- ============================================================
-- New Process Handoffs
-- ============================================================

-- harvest_event -> traceability_batch (sequential, via location_id)
INSERT INTO process_handoff (source_entity_type, target_entity_type, handoff_type, correlation_key, sla_hours, description) VALUES
    ('harvest_event', 'traceability_batch', 'sequential', 'location_id', 48.0,
     'Published harvest events trigger traceability batch creation for custody chain tracking.')
ON CONFLICT (source_entity_type, target_entity_type) DO UPDATE SET
    handoff_type = EXCLUDED.handoff_type,
    correlation_key = EXCLUDED.correlation_key,
    sla_hours = EXCLUDED.sla_hours,
    description = EXCLUDED.description;

-- traceability_batch -> market_order (event_driven, via location_id)
INSERT INTO process_handoff (source_entity_type, target_entity_type, handoff_type, correlation_key, sla_hours, description) VALUES
    ('traceability_batch', 'market_order', 'event_driven', 'location_id', 72.0,
     'Verified traceability batches may trigger market order creation for batch fulfillment.')
ON CONFLICT (source_entity_type, target_entity_type) DO UPDATE SET
    handoff_type = EXCLUDED.handoff_type,
    correlation_key = EXCLUDED.correlation_key,
    sla_hours = EXCLUDED.sla_hours,
    description = EXCLUDED.description;

-- pest_intervention -> extension_enrollment (event_driven, via location_id)
INSERT INTO process_handoff (source_entity_type, target_entity_type, handoff_type, correlation_key, sla_hours, description) VALUES
    ('pest_intervention', 'extension_enrollment', 'event_driven', 'location_id', 168.0,
     'Completed pest interventions may trigger extension training enrollment for capacity building.')
ON CONFLICT (source_entity_type, target_entity_type) DO UPDATE SET
    handoff_type = EXCLUDED.handoff_type,
    correlation_key = EXCLUDED.correlation_key,
    sla_hours = EXCLUDED.sla_hours,
    description = EXCLUDED.description;
