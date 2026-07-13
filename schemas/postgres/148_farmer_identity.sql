-- ============================================================
-- 148_farmer_identity.sql — Farmer Identity & Access Management
-- ============================================================

-- Farmer profiles: structured identity for each farmer
CREATE TABLE IF NOT EXISTS farmer_profile (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id     UUID REFERENCES location(id) ON DELETE SET NULL,

    -- Identity
    first_name      VARCHAR(150) NOT NULL,
    last_name       VARCHAR(150),
    date_of_birth   DATE,
    gender          VARCHAR(50),  -- male, female, non_binary, prefer_not_to_say

    -- Contact
    phone           VARCHAR(50),
    phone_verified  BOOLEAN DEFAULT FALSE,
    email           VARCHAR(255),
    email_verified  BOOLEAN DEFAULT FALSE,

    -- Address
    village         VARCHAR(255),
    district        VARCHAR(255),
    province        VARCHAR(255),
    country         VARCHAR(100),
    postal_code     VARCHAR(20),

    -- Farming context
    farm_size_ha    NUMERIC(10,4),
    primary_crops   TEXT[] DEFAULT '{}',
    farming_type    VARCHAR(100),  -- smallholder, commercial, cooperative, subsistence
    years_farming   INTEGER,

    -- Government IDs
    national_id_type    VARCHAR(100),  -- national_id, passport, voter_id, driving_license
    national_id_number  VARCHAR(255),
    national_id_country VARCHAR(100),

    -- KYC status (denormalized for fast queries)
    kyc_status      VARCHAR(50) DEFAULT 'unverified',  -- unverified, pending, verified, rejected
    kyc_verified_at TIMESTAMPTZ,

    -- Status & metadata
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      UUID,
    updated_by      UUID
);

CREATE INDEX IF NOT EXISTS idx_farmer_profile_location ON farmer_profile (location_id);
CREATE INDEX IF NOT EXISTS idx_farmer_profile_phone ON farmer_profile (phone);
CREATE INDEX IF NOT EXISTS idx_farmer_profile_status ON farmer_profile (status);
CREATE INDEX IF NOT EXISTS idx_farmer_profile_kyc ON farmer_profile (kyc_status);
CREATE INDEX IF NOT EXISTS idx_farmer_profile_national_id ON farmer_profile (national_id_number);
CREATE INDEX IF NOT EXISTS idx_farmer_profile_crops ON farmer_profile USING GIN (primary_crops);

-- Digital credentials and certifications
CREATE TABLE IF NOT EXISTS farmer_credential (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id       UUID NOT NULL REFERENCES farmer_profile(id) ON DELETE CASCADE,

    -- Credential
    credential_type VARCHAR(100) NOT NULL,  -- organic_cert, gxp_cert, training_cert, coop_member, land_title, etc.
    credential_name VARCHAR(255) NOT NULL,
    issuing_authority   VARCHAR(255),
    credential_number   VARCHAR(255),
    credential_url      TEXT,

    -- Validity
    issued_date     DATE,
    expiry_date     DATE,
    is_verified     BOOLEAN DEFAULT FALSE,
    verified_by     UUID,
    verified_at     TIMESTAMPTZ,

    -- Evidence
    evidence_urls   TEXT[] DEFAULT '{}',
    evidence_hashes TEXT[] DEFAULT '{}',

    -- Status
    status          VARCHAR(50) NOT NULL DEFAULT 'active',  -- active, expired, revoked, pending
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_farmer_credential_farmer ON farmer_credential (farmer_id);
CREATE INDEX IF NOT EXISTS idx_farmer_credential_type ON farmer_credential (credential_type);
CREATE INDEX IF NOT EXISTS idx_farmer_credential_status ON farmer_credential (status);
CREATE INDEX IF NOT EXISTS idx_farmer_credential_expiry ON farmer_credential (expiry_date);

-- KYC / identity verification records
CREATE TABLE IF NOT EXISTS kyc_verification (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id       UUID NOT NULL REFERENCES farmer_profile(id) ON DELETE CASCADE,

    -- Verification method
    verification_method VARCHAR(100) NOT NULL,  -- national_id, biometric, community_vouch, bank_reference, phone_otp, manual_review
    provider        VARCHAR(100),  -- onfido, jumio, manual, community, self_sovereign

    -- Documents
    document_type       VARCHAR(100),  -- national_id_front, national_id_back, passport, utility_bill, bank_statement
    document_url        TEXT,
    document_hash       VARCHAR(128),

    -- Result
    verification_status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, in_review, approved, rejected, expired
    rejection_reason    TEXT,
    confidence_score    NUMERIC(5,2),  -- 0.00 to 100.00

    -- Review
    reviewed_by     UUID,
    reviewed_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,

    -- SSI / self-sovereign
    did_identifier  VARCHAR(500),  -- Decentralized Identifier
    credential_jwt  TEXT,  -- Verifiable Credential JWT

    -- Audit
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kyc_farmer ON kyc_verification (farmer_id);
CREATE INDEX IF NOT EXISTS idx_kyc_status ON kyc_verification (verification_status);
CREATE INDEX IF NOT EXISTS idx_kyc_method ON kyc_verification (verification_method);
CREATE INDEX IF NOT EXISTS idx_kyc_expires ON kyc_verification (expires_at);

-- Role-based access control
CREATE TABLE IF NOT EXISTS role_assignment (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id       UUID NOT NULL REFERENCES farmer_profile(id) ON DELETE CASCADE,
    location_id     UUID REFERENCES location(id) ON DELETE SET NULL,

    -- Role
    role            VARCHAR(100) NOT NULL,  -- farmer, cooperative_admin, aggregator, buyer, extension_agent, system_admin
    scope           VARCHAR(50) NOT NULL DEFAULT 'location',  -- global, network, location, farm

    -- Permissions (JSON array of resource:action pairs)
    permissions     JSONB DEFAULT '[]',

    -- Validity
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    assigned_by     UUID,

    -- Status
    status          VARCHAR(50) NOT NULL DEFAULT 'active',  -- active, suspended, revoked
    revoked_at      TIMESTAMPTZ,
    revoke_reason   TEXT,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_role_assignment_farmer ON role_assignment (farmer_id);
CREATE INDEX IF NOT EXISTS idx_role_assignment_role ON role_assignment (role);
CREATE INDEX IF NOT EXISTS idx_role_assignment_location ON role_assignment (location_id);
CREATE INDEX IF NOT EXISTS idx_role_assignment_status ON role_assignment (status);
CREATE INDEX IF NOT EXISTS idx_role_assignment_active ON role_assignment (role, status) WHERE status = 'active';

-- Granular data sharing consent
CREATE TABLE IF NOT EXISTS data_sharing_consent (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id       UUID NOT NULL REFERENCES farmer_profile(id) ON DELETE CASCADE,

    -- What data is shared
    data_type       VARCHAR(100) NOT NULL,  -- soil_data, weather_data, harvest_data, financial_data, identity_data, location_data, sensor_data
    data_scope      VARCHAR(255),  -- optional sub-scope, e.g., specific plot or crop

    -- Who receives it
    recipient_type  VARCHAR(100) NOT NULL,  -- buyer, aggregator, extension_agent, verifier, insurer, researcher, government, public
    recipient_id    UUID,  -- farmer_id or partner_id of recipient
    recipient_name  VARCHAR(255),

    -- Consent terms
    purpose         VARCHAR(255),  -- why data is shared
    legal_basis     VARCHAR(100),  -- consent, contract, legal_obligation, legitimate_interest
    retention_days  INTEGER,  -- how long consent is valid
    is_reciprocal   BOOLEAN DEFAULT FALSE,  -- whether recipient shares data back

    -- Lifecycle
    consent_given   BOOLEAN NOT NULL DEFAULT TRUE,
    consent_date    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    withdrawal_date TIMESTAMPTZ,
    withdrawal_reason TEXT,

    -- Status
    status          VARCHAR(50) NOT NULL DEFAULT 'active',  -- active, withdrawn, expired
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_consent_farmer ON data_sharing_consent (farmer_id);
CREATE INDEX IF NOT EXISTS idx_consent_data_type ON data_sharing_consent (data_type);
CREATE INDEX IF NOT EXISTS idx_consent_recipient ON data_sharing_consent (recipient_type, recipient_id);
CREATE INDEX IF NOT EXISTS idx_consent_status ON data_sharing_consent (status);
CREATE INDEX IF NOT EXISTS idx_consent_active ON data_sharing_consent (farmer_id, data_type, status) WHERE status = 'active';

-- Registered mobile devices for offline access
CREATE TABLE IF NOT EXISTS device_registration (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id       UUID NOT NULL REFERENCES farmer_profile(id) ON DELETE CASCADE,
    location_id     UUID REFERENCES location(id) ON DELETE SET NULL,

    -- Device identity
    device_id       VARCHAR(255) NOT NULL UNIQUE,  -- hardware/device-specific identifier
    device_name     VARCHAR(255),
    device_type     VARCHAR(50) NOT NULL,  -- phone, tablet, sensor, gateway
    os_type         VARCHAR(50),  -- android, ios, linux, other
    os_version      VARCHAR(50),
    app_version     VARCHAR(50),

    -- Capabilities
    has_camera      BOOLEAN DEFAULT FALSE,
    has_gps         BOOLEAN DEFAULT FALSE,
    has_offline     BOOLEAN DEFAULT TRUE,
    storage_mb      INTEGER,

    -- Offline sync
    last_sync_at    TIMESTAMPTZ,
    last_sync_status VARCHAR(50),  -- success, partial, failed
    pending_records INTEGER DEFAULT 0,
    offline_data    JSONB DEFAULT '[]',

    -- Security
    device_token    VARCHAR(512),  -- push notification token
    push_provider   VARCHAR(50),  -- fcm, apns, none
    is_trusted      BOOLEAN DEFAULT FALSE,
    trusted_at      TIMESTAMPTZ,
    trusted_by      UUID,

    -- Status
    status          VARCHAR(50) NOT NULL DEFAULT 'active',  -- active, suspended, deregistered
    deregistered_at TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_device_farmer ON device_registration (farmer_id);
CREATE INDEX IF NOT EXISTS idx_device_location ON device_registration (location_id);
CREATE INDEX IF NOT EXISTS idx_device_type ON device_registration (device_type);
CREATE INDEX IF NOT EXISTS idx_device_status ON device_registration (status);
CREATE INDEX IF NOT EXISTS idx_device_sync ON device_registration (last_sync_at);

-- ============================================================
-- Views
-- ============================================================

-- Active farmers with verification status
CREATE OR REPLACE VIEW v_farmer_directory AS
SELECT
    fp.id AS farmer_id,
    fp.first_name,
    fp.last_name,
    fp.phone,
    fp.email,
    fp.village,
    fp.district,
    fp.province,
    fp.country,
    fp.farm_size_ha,
    fp.primary_crops,
    fp.farming_type,
    fp.kyc_status,
    fp.kyc_verified_at,
    l.name AS location_name,
    l.id AS location_id,
    ra.role AS primary_role,
    ra.scope AS role_scope,
    (SELECT COUNT(*) FROM farmer_credential fc
     WHERE fc.farmer_id = fp.id AND fc.status = 'active') AS active_credentials,
    (SELECT COUNT(*) FROM data_sharing_consent dsc
     WHERE dsc.farmer_id = fp.id AND dsc.status = 'active') AS active_consents,
    (SELECT COUNT(*) FROM device_registration dr
     WHERE dr.farmer_id = fp.id AND dr.status = 'active') AS registered_devices,
    fp.status,
    fp.created_at,
    fp.updated_at
FROM farmer_profile fp
LEFT JOIN location l ON l.id = fp.location_id
LEFT JOIN role_assignment ra ON ra.farmer_id = fp.id
    AND ra.status = 'active'
    AND (ra.expires_at IS NULL OR ra.expires_at > NOW())
WHERE fp.status = 'active';

-- Current credentials per farmer
CREATE OR REPLACE VIEW v_credential_status AS
SELECT
    fp.id AS farmer_id,
    fp.first_name || COALESCE(' ' || fp.last_name, '') AS farmer_name,
    fc.id AS credential_id,
    fc.credential_type,
    fc.credential_name,
    fc.issuing_authority,
    fc.credential_number,
    fc.issued_date,
    fc.expiry_date,
    fc.is_verified,
    fc.status,
    CASE
        WHEN fc.expiry_date IS NULL THEN 'no_expiry'
        WHEN fc.expiry_date < CURRENT_DATE THEN 'expired'
        WHEN fc.expiry_date < CURRENT_DATE + INTERVAL '30 days' THEN 'expiring_soon'
        ELSE 'valid'
    END AS validity_status,
    fc.created_at
FROM farmer_credential fc
JOIN farmer_profile fp ON fp.id = fc.farmer_id
WHERE fp.status = 'active'
ORDER BY fp.id, fc.expiry_date NULLS LAST;

-- Role-based access matrix
CREATE OR REPLACE VIEW v_access_matrix AS
SELECT
    fp.id AS farmer_id,
    fp.first_name || COALESCE(' ' || fp.last_name, '') AS farmer_name,
    ra.role,
    ra.scope,
    ra.permissions,
    ra.status,
    ra.assigned_at,
    ra.expires_at,
    l.name AS location_name,
    l.id AS location_id,
    fp.kyc_status,
    CASE
        WHEN ra.expires_at IS NOT NULL AND ra.expires_at < NOW() THEN 'expired'
        ELSE ra.status
    END AS effective_status
FROM role_assignment ra
JOIN farmer_profile fp ON fp.id = ra.farmer_id
LEFT JOIN location l ON l.id = ra.location_id
WHERE fp.status = 'active'
ORDER BY fp.id, ra.role;

-- ============================================================
-- Seed Data: Default Roles
-- ============================================================

-- We use a reference table for roles rather than CHECK constraints,
-- allowing extensibility. The role_assignment table references role by name.

CREATE TABLE IF NOT EXISTS farmer_role (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    default_scope   VARCHAR(50) NOT NULL DEFAULT 'location',
    default_permissions JSONB DEFAULT '[]',
    is_system_role  BOOLEAN DEFAULT FALSE,
    sort_order      INTEGER DEFAULT 0,
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO farmer_role (name, description, default_scope, default_permissions, is_system_role, sort_order) VALUES
    ('farmer',              'Individual farmer with access to own data and farm operations', 'farm',       '["farm:read", "harvest:write", "sensor:read", "consent:manage"]', TRUE, 1),
    ('cooperative_admin',   'Cooperative administrator with oversight of member farmers', 'location',   '["farmer:read", "farm:read", "harvest:read", "report:read", "consent:read"]', TRUE, 2),
    ('aggregator',          'Supply chain aggregator collecting produce from multiple farmers', 'network', '["farmer:read", "harvest:read", "logistics:write", "price:read"]', TRUE, 3),
    ('buyer',               'Purchaser of agricultural products', 'network',                '["harvest:read", "quality:read", "order:write", "payment:read"]', TRUE, 4),
    ('extension_agent',     'Agricultural extension officer providing technical support', 'location', '["farmer:read", "farm:read", "advisory:write", "training:write"]', TRUE, 5),
    ('system_admin',        'Platform administrator with full access', 'global',            '["*:*"]', TRUE, 6)
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    default_scope = EXCLUDED.default_scope,
    default_permissions = EXCLUDED.default_permissions;

-- ============================================================
-- Seed Data: Default Credential Types
-- ============================================================

CREATE TABLE IF NOT EXISTS farmer_credential_type (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    category        VARCHAR(100) NOT NULL,  -- certification, training, membership, identity, financial
    description     TEXT,
    issuing_authority_example VARCHAR(255),
    validity_months INTEGER,  -- NULL = no expiry
    is_government   BOOLEAN DEFAULT FALSE,
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO farmer_credential_type (name, category, description, issuing_authority_example, validity_months, is_government) VALUES
    ('organic_certification',     'certification',   'Organic farming certification (IFOAM, USDA, EU)',         'IFOAM / USDA / EU',             24, FALSE),
    ('fair_trade_cert',           'certification',   'Fair trade certification',                               'Fairtrade International',        12, FALSE),
    ('rainforest_alliance',       'certification',   'Rainforest Alliance certification',                      'Rainforest Alliance',            12, FALSE),
    ('global_gap_cert',           'certification',   'GLOBALG.A.P. certified',                                 'GLOBALG.A.P.',                   12, FALSE),
    ('coop_membership',           'membership',      'Cooperative membership card',                            'Local Cooperative',              NULL, FALSE),
    ('national_id',               'identity',        'Government-issued national identity card',               'National Government',            NULL, TRUE),
    ('passport',                  'identity',        'International passport',                                 'National Government',            NULL, TRUE),
    ('voter_id',                  'identity',        'Voter registration card',                                'Electoral Commission',           NULL, TRUE),
    ('land_title',                'identity',        'Land ownership or lease title deed',                     'Land Registry',                  NULL, TRUE),
    ('training_cert_agronomy',    'training',        'Agricultural agronomy training certificate',             'Extension Service / NGO',        36, FALSE),
    ('training_cert_food_safety', 'training',        'Food safety and handling training certificate',          'Food Safety Authority',          24, FALSE),
    ('training_cert_organic',     'training',        'Organic farming methods training',                       'IFOAM / Extension Service',      36, FALSE),
    ('bank_account',              'financial',       'Bank account verification',                              'Commercial Bank',                NULL, FALSE),
    ('mobile_money_account',      'financial',       'Mobile money account registration',                      'Mobile Network Operator',        NULL, FALSE),
    ('insurance_policy',          'financial',       'Agricultural insurance policy',                          'Insurance Provider',             12, FALSE),
    ('digital_literacy_cert',     'training',        'Digital literacy and smartphone skills certificate',     'NGO / Government Program',       NULL, FALSE),
    ('ssi_did',                   'identity',        'Self-sovereign identity Decentralized Identifier (DID)', 'W3C DID Registry',              NULL, FALSE)
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    validity_months = EXCLUDED.validity_months;

-- ============================================================
-- Seed Data: Default Data Types for Consent
-- ============================================================

CREATE TABLE IF NOT EXISTS consent_data_type (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    category        VARCHAR(100) NOT NULL,  -- environmental, financial, identity, operational, social
    description     TEXT,
    sensitivity     VARCHAR(20) NOT NULL DEFAULT 'medium',  -- low, medium, high, restricted
    default_retention_days INTEGER DEFAULT 365,
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO consent_data_type (name, category, description, sensitivity, default_retention_days) VALUES
    ('soil_data',       'environmental',  'Soil moisture, pH, nutrient levels, organic matter',          'medium',   730),
    ('weather_data',    'environmental',  'Weather observations, forecasts, microclimate data',          'low',      365),
    ('harvest_data',    'operational',    'Harvest volumes, quality grades, crop types',                'medium',   1095),
    ('financial_data',  'financial',      'Revenue, expenses, loan data, payment records',              'high',     1095),
    ('identity_data',   'identity',       'Personal identification, KYC documents, biometrics',         'restricted', 1825),
    ('location_data',   'environmental',  'GPS coordinates, farm boundaries, plot maps',                'medium',   1095),
    ('sensor_data',     'environmental',  'IoT sensor readings, device telemetry',                      'low',      365),
    ('training_data',   'social',         'Training attendance, skills, certifications',                'low',      1095),
    ('biodiversity_data','environmental', 'Species observations, biodiversity surveys',                 'low',      1095),
    ('carbon_data',     'environmental',  'Carbon measurements, sequestration estimates',               'medium',   1825)
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    sensitivity = EXCLUDED.sensitivity,
    default_retention_days = EXCLUDED.default_retention_days;

-- ============================================================
-- Schema version
-- ============================================================

INSERT INTO schema_version (version, description, applied_by)
VALUES ('farmer-identity-v1', 'Farmer identity, credentials, KYC, RBAC, consent, device registration', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
