-- Minimal disposable schema for tenant-preflight operator aggregation.
-- The ordered tenant grant and device-binding migrations are applied after it.
CREATE TABLE organization (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    org_type TEXT NOT NULL DEFAULT 'nonprofit',
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE location (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    organization_id UUID REFERENCES organization(id)
);

CREATE TABLE organization_member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    location_id UUID NOT NULL REFERENCES location(id),
    membership_type TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE operator_identity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (issuer, subject)
);

CREATE TABLE operator_scope_grant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES operator_identity(id),
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    location_id UUID NOT NULL REFERENCES location(id),
    granted_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ
);

CREATE TABLE mobile_device_enrollment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID REFERENCES location(id),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE mobile_device (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id TEXT NOT NULL UNIQUE,
    location_id UUID REFERENCES location(id),
    status TEXT NOT NULL,
    device_token_hash TEXT,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE offline_collection (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID REFERENCES location(id)
);
CREATE VIEW v_mobile_collection_use_eligibility AS
    SELECT id AS collection_id, TRUE AS eligible_for_use FROM offline_collection;

CREATE TABLE mobile_media_upload (location_id UUID, status TEXT);
CREATE TABLE farm_activity (location_id UUID, source_system TEXT);
CREATE TABLE farm_activity_workflow_event (location_id UUID);
CREATE TABLE mobile_collection_review_event (location_id UUID);
CREATE TABLE report_snapshot (location_id UUID);
CREATE TABLE dashboard_dataset (location_id UUID);
