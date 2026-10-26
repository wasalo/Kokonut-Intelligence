-- Synthetic schema for a disposable PostgreSQL 16 migration-386 check.
-- This is not a substitute for the full ordered migration replay.
CREATE TABLE schema_version (
    version TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_by TEXT NOT NULL
);

CREATE TABLE dashboard_dataset (
    id UUID PRIMARY KEY,
    query_sql TEXT NOT NULL,
    updated_at TIMESTAMPTZ
);

INSERT INTO dashboard_dataset (id, query_sql) VALUES
    ('d1000000-0000-0000-0000-000000000001',
     'SELECT fa.activity_type, COUNT(*) as count, SUM(labor_hours) as total_hours FROM farm_activity fa WHERE fa.location_id = ''a0000000-0000-0000-0000-000000000001'' GROUP BY fa.activity_type ORDER BY count DESC'),
    ('d1040000-0000-0000-0000-000000000001',
     'SELECT ''other'' UNION ALL SELECT ''farm_activity'', status, COUNT(*) FROM farm_activity GROUP BY status');

CREATE TABLE mobile_form_version (
    id UUID PRIMARY KEY,
    form_id TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE offline_collection (
    id UUID PRIMARY KEY,
    form_revision_id UUID NOT NULL,
    location_id UUID NOT NULL,
    form_id TEXT NOT NULL,
    form_version TEXT NOT NULL,
    collection_type TEXT NOT NULL,
    sync_status TEXT NOT NULL,
    form_validation_status TEXT NOT NULL,
    form_review_required BOOLEAN NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE collection_consent_fixture (
    collection_id UUID PRIMARY KEY,
    eligible_for_use BOOLEAN NOT NULL
);

CREATE TABLE collection_consent_event_fixture (
    collection_id UUID NOT NULL,
    event_sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL
);

CREATE VIEW v_mobile_collection_use_eligibility AS
SELECT state.collection_id,
       state.eligible_for_use AND NOT EXISTS (
           SELECT 1 FROM collection_consent_event_fixture AS event
            WHERE event.collection_id = state.collection_id
              AND event.event_type = 'withdrawal'
       ) AS eligible_for_use
  FROM collection_consent_fixture AS state;

CREATE TABLE farm_activity (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL,
    status TEXT NOT NULL,
    source_system TEXT,
    source_id TEXT,
    source_raw JSONB,
    plot_id UUID,
    crop_cycle_id UUID,
    activity_type TEXT,
    activity_date DATE,
    description TEXT,
    labor_hours NUMERIC,
    labor_cost NUMERIC,
    materials_used JSONB,
    evidence_urls JSONB,
    evidence_hashes JSONB,
    notes TEXT
);

CREATE TABLE directus_permissions (
    id UUID PRIMARY KEY,
    collection TEXT NOT NULL,
    action TEXT NOT NULL,
    permissions JSON,
    validation JSON,
    fields TEXT,
    policy UUID NOT NULL
);

INSERT INTO directus_permissions (id, collection, action, permissions, policy) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'farm_activity', 'read',
     '{"_and":[{"location_id":{"_eq":"11111111-1111-4111-8111-111111111111"}}]}',
     'b1000000-0000-0000-0000-000000000001'),
    ('a1000000-0000-0000-0000-000000000002', 'farm_activity', 'read', '{}',
     'b1000000-0000-0000-0000-000000000002'),
    ('a1000000-0000-0000-0000-000000000003', 'farm_activity', 'read', NULL,
     'b1000000-0000-0000-0000-000000000003');

INSERT INTO mobile_form_version (id, form_id, version, status) VALUES
    ('22222222-2222-4222-8222-222222222222', 'farm_activity_v1', '1.2.0', 'active'),
    ('33333333-3333-4333-8333-333333333333', 'farm_activity_v1', '1.2.0', 'active');

INSERT INTO offline_collection (
    id, form_revision_id, location_id, form_id, form_version, collection_type,
    sync_status, form_validation_status, form_review_required
) VALUES
    ('44444444-4444-4444-8444-444444444444',
     '22222222-2222-4222-8222-222222222222',
     '11111111-1111-4111-8111-111111111111', 'farm_activity_v1', '1.2.0',
     'farm_activity', 'synced', 'active', FALSE),
    ('55555555-5555-4555-8555-555555555555',
     '33333333-3333-4333-8333-333333333333',
     '66666666-6666-4666-8666-666666666666', 'farm_activity_v1', '1.2.0',
     'farm_activity', 'synced', 'active', FALSE);

INSERT INTO collection_consent_fixture (collection_id, eligible_for_use) VALUES
    ('44444444-4444-4444-8444-444444444444', TRUE),
    ('55555555-5555-4555-8555-555555555555', TRUE);

INSERT INTO farm_activity (
    id, location_id, status, source_system, source_id, source_raw, activity_type
) VALUES
    ('77777777-7777-4777-8777-777777777777',
     '11111111-1111-4111-8111-111111111111', 'draft', 'field_collector',
     '44444444-4444-4444-8444-444444444444',
     '{"form_id":"farm_activity_v1","form_version":"1.2.0","offline_collection_id":"44444444-4444-4444-8444-444444444444"}',
     'weeding'),
    ('88888888-8888-4888-8888-888888888888',
     '66666666-6666-4666-8666-666666666666', 'draft', 'field_collector',
     '55555555-5555-4555-8555-555555555555',
     '{"form_id":"farm_activity_v1","form_version":"1.2.0","offline_collection_id":"55555555-5555-4555-8555-555555555555"}',
     'planting'),
    ('99999999-9999-4999-8999-999999999999',
     '11111111-1111-4111-8111-111111111111', 'draft', 'legacy_import',
     'legacy-1', '{}', 'harvest');
