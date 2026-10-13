-- Minimal compatible substrate for isolated migration 387-389 acceptance.
-- This intentionally does not claim a full replay of earlier application migrations.
CREATE TABLE organization (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    org_type TEXT NOT NULL DEFAULT 'collective',
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    source_system TEXT,
    source_id TEXT,
    source_raw TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE farm (id UUID PRIMARY KEY);

CREATE TABLE location (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    organization_id UUID REFERENCES organization(id)
);

CREATE TABLE organization_member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    location_id UUID NOT NULL REFERENCES location(id),
    farm_id UUID REFERENCES farm(id),
    membership_type TEXT NOT NULL DEFAULT 'owned',
    join_date DATE NOT NULL DEFAULT CURRENT_DATE,
    role TEXT NOT NULL DEFAULT 'primary',
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB DEFAULT '{}'::JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE operator_identity (
    id UUID PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    display_name TEXT,
    enabled BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE operator_scope_grant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES operator_identity(id),
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    location_id UUID NOT NULL REFERENCES location(id),
    granted_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_operator_scope_grant_active
    ON operator_scope_grant (operator_id, resource, action, location_id)
    WHERE revoked_at IS NULL;

CREATE TABLE farm_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id),
    activity_type TEXT NOT NULL,
    activity_date DATE NOT NULL,
    description TEXT,
    labor_hours NUMERIC(8, 2),
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    source_system TEXT,
    source_raw JSONB
);

CREATE TABLE farm_activity_workflow_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_activity_id UUID NOT NULL REFERENCES farm_activity(id),
    location_id UUID NOT NULL REFERENCES location(id),
    actor_operator_id UUID NOT NULL REFERENCES operator_identity(id),
    action TEXT NOT NULL
);

INSERT INTO location (id, name, slug) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'Kokonut Adelphi', 'kokonut-adelphi'),
    ('a0000000-0000-0000-0000-000000000002', 'Kokonut Genesis', 'kokonut-genesis');

INSERT INTO organization (id, org_key, name, org_type, status)
VALUES ('a0000000-0000-0000-0000-000000000800', 'acceptance-partner', 'Acceptance Partner', 'collective', 'active');

INSERT INTO location (id, name, slug, organization_id)
VALUES (
    'a0000000-0000-0000-0000-000000000003',
    'Unverified Acceptance Location',
    'unverified-acceptance-location',
    'a0000000-0000-0000-0000-000000000800'
);

INSERT INTO operator_identity (id, issuer, subject, display_name, enabled) VALUES
    ('a0000000-0000-0000-0000-000000000901', 'https://issuer.example.test', 'owner', 'Owner Operator', TRUE),
    ('a0000000-0000-0000-0000-000000000902', 'https://issuer.example.test', 'partner', 'Partner Operator', TRUE),
    ('a0000000-0000-0000-0000-000000000903', 'https://issuer.example.test', 'legacy', 'Legacy Operator', TRUE);


-- Actual ordered migrations are applied by scripts/check-tenant-grants-disposable.py.
-- Keep assertions in a second file so it runs only after 387, 388 and 389.
