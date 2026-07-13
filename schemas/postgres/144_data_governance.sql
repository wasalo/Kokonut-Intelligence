-- ============================================================
-- 144_data_governance.sql — Data Governance & Interoperability
-- Consent management, access auditing, portability, interoperability
-- mapping, data sharing agreements, and retention policies.
-- ============================================================

-- ============================================================
-- farmer_consent
-- Consent records for data collection, sharing, and use.
-- Each row is a single consent grant or withdrawal event.
-- ============================================================
CREATE TABLE IF NOT EXISTS farmer_consent (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Farmer identity
    farmer_id       VARCHAR(200) NOT NULL,
    location_id     UUID REFERENCES location(id),

    -- What is being consented
    data_category   VARCHAR(100) NOT NULL
        CHECK (data_category IN (
            'soil', 'weather', 'yield', 'financial', 'personal',
            'biodiversity', 'water', 'carbon', 'equipment',
            'image', 'geospatial', 'practice', 'social'
        )),
    consent_scope   VARCHAR(100) NOT NULL
        CHECK (consent_scope IN (
            'collection', 'storage', 'internal_use', 'anonymized_analytics',
            'third_party_sharing', 'public_disclosure', 'research',
            'marketing', 'government_reporting'
        )),

    -- Consent state
    status          VARCHAR(20) NOT NULL DEFAULT 'granted'
        CHECK (status IN ('granted', 'withdrawn', 'expired', 'pending')),
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    withdrawn_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,

    -- Source of consent
    consent_method  VARCHAR(50) NOT NULL DEFAULT 'digital_form'
        CHECK (consent_method IN (
            'digital_form', 'verbal_recorded', 'paper_scan',
            'mobile_app', 'api', 'in_person'
        )),
    evidence_ref    TEXT,

    -- Withdrawal tracking
    withdrawal_reason TEXT,

    -- Audit
    consent_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    legal_basis     VARCHAR(100),
    ip_address      INET,
    user_agent      TEXT,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_farmer_consent_farmer
    ON farmer_consent (farmer_id, data_category, consent_scope);
CREATE INDEX IF NOT EXISTS idx_farmer_consent_location
    ON farmer_consent (location_id);
CREATE INDEX IF NOT EXISTS idx_farmer_consent_status
    ON farmer_consent (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_farmer_consent_expires
    ON farmer_consent (expires_at) WHERE expires_at IS NOT NULL;

-- ============================================================
-- data_access_log
-- Audit trail of all data access events.
-- Append-only; rows should never be updated or deleted.
-- ============================================================
CREATE TABLE IF NOT EXISTS data_access_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Who accessed
    accessor_id     VARCHAR(200) NOT NULL,
    accessor_role   VARCHAR(100),
    accessor_type   VARCHAR(50) NOT NULL DEFAULT 'user'
        CHECK (accessor_type IN ('user', 'agent', 'system', 'api', 'partner')),

    -- What was accessed
    resource_type   VARCHAR(100) NOT NULL,
    resource_id     UUID,
    location_id     UUID REFERENCES location(id),
    data_category   VARCHAR(100),

    -- How it was accessed
    access_type     VARCHAR(50) NOT NULL
        CHECK (access_type IN (
            'read', 'write', 'export', 'share', 'delete',
            'list', 'aggregate', 'download'
        )),
    access_method   VARCHAR(50)
        CHECK (access_method IN (
            'directus_ui', 'api', 'cli', 'agent', 'webhook',
            'spreadsheet', 'report', 'partner_sync'
        )),

    -- Why
    purpose         TEXT,
    consent_id      UUID REFERENCES farmer_consent(id),

    -- Outcome
    status          VARCHAR(20) NOT NULL DEFAULT 'success'
        CHECK (status IN ('success', 'denied', 'partial', 'error')),
    denial_reason   TEXT,
    records_affected INTEGER DEFAULT 0,

    -- Request context
    ip_address      INET,
    user_agent      TEXT,
    request_id      UUID,
    session_id      VARCHAR(200),

    accessed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_dal_accessor
    ON data_access_log (accessor_id, accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_dal_resource
    ON data_access_log (resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_dal_location
    ON data_access_log (location_id, accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_dal_time
    ON data_access_log (accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_dal_status
    ON data_access_log (status, accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_dal_consent
    ON data_access_log (consent_id) WHERE consent_id IS NOT NULL;

-- ============================================================
-- data_portability_request
-- Data export / portability requests (FAIR compliance).
-- ============================================================
CREATE TABLE IF NOT EXISTS data_portability_request (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Requester
    farmer_id       VARCHAR(200) NOT NULL,
    location_id     UUID REFERENCES location(id),
    requested_by    VARCHAR(200) NOT NULL,

    -- What is requested
    data_categories TEXT[] NOT NULL DEFAULT '{}',
    format          VARCHAR(50) NOT NULL DEFAULT 'json'
        CHECK (format IN (
            'json', 'csv', 'geojson', 'xml', 'rdf_turtle',
            'jsonld', 'parquet', 'excel'
        )),
    include_metadata BOOLEAN NOT NULL DEFAULT TRUE,
    date_range_start DATE,
    date_range_end   DATE,

    -- Scope
    scope           VARCHAR(50) NOT NULL DEFAULT 'all'
        CHECK (scope IN ('all', 'location', 'category', 'filtered')),

    -- Status
    status          VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'processing', 'ready', 'downloaded',
            'expired', 'denied', 'error'
        )),
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ,
    ready_at        TIMESTAMPTZ,
    downloaded_at   TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,

    -- Delivery
    output_url      TEXT,
    output_hash     VARCHAR(128),
    output_size_bytes BIGINT,
    record_count    INTEGER DEFAULT 0,

    -- FAIR compliance flags
    fair_principles JSONB NOT NULL DEFAULT '{
        "findable": true,
        "accessible": true,
        "interoperable": true,
        "reusable": true
    }',

    -- Denial tracking
    denial_reason   TEXT,
    denied_by       VARCHAR(200),

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dpr_farmer
    ON data_portability_request (farmer_id, status);
CREATE INDEX IF NOT EXISTS idx_dpr_location
    ON data_portability_request (location_id);
CREATE INDEX IF NOT EXISTS idx_dpr_status
    ON data_portability_request (status, requested_at DESC);

-- ============================================================
-- interoperability_config
-- Mappings to external standards (ADAPT, ISOBUS, AgGateway, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS interoperability_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Standard identity
    standard_name   VARCHAR(100) NOT NULL
        CHECK (standard_name IN (
            'adapt', 'isobus', 'aggateway', 'agrx', 'onegrow',
            'openag', 'ogc_wfs', 'ogc_wms', 'stac', 'cql2',
            'fair_maturity', 'schema_org', 'dublin_core',
            'agrovolc_api', 'cdm', 'custom'
        )),
    standard_version VARCHAR(50),
    standard_url    TEXT,

    -- What this config applies to
    entity_type     VARCHAR(100) NOT NULL,
    local_field     VARCHAR(200) NOT NULL,
    external_field  VARCHAR(200) NOT NULL,

    -- Mapping details
    mapping_type    VARCHAR(30) NOT NULL DEFAULT 'direct'
        CHECK (mapping_type IN (
            'direct', 'transform', 'lookup', 'composite', 'ignore'
        )),
    transform_func  VARCHAR(200),
    lookup_table    JSONB,
    default_value   TEXT,
    required        BOOLEAN NOT NULL DEFAULT FALSE,

    -- Sync settings
    sync_direction  VARCHAR(20) NOT NULL DEFAULT 'bidirectional'
        CHECK (sync_direction IN ('inbound', 'outbound', 'bidirectional')),
    sync_enabled    BOOLEAN NOT NULL DEFAULT TRUE,
    last_synced_at  TIMESTAMPTZ,

    status          VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'deprecated', 'testing')),
    priority        INTEGER NOT NULL DEFAULT 0,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ic_standard
    ON interoperability_config (standard_name, entity_type);
CREATE INDEX IF NOT EXISTS idx_ic_entity
    ON interoperability_config (entity_type, local_field);
CREATE INDEX IF NOT EXISTS idx_ic_status
    ON interoperability_config (status, sync_enabled);

-- Unique constraint: one mapping per (standard, entity, local_field)
CREATE UNIQUE INDEX IF NOT EXISTS uq_ic_mapping
    ON interoperability_config (standard_name, entity_type, local_field);

-- ============================================================
-- data_sharing_agreement
-- Agreements between data providers and consumers.
-- ============================================================
CREATE TABLE IF NOT EXISTS data_sharing_agreement (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Parties
    provider_id     VARCHAR(200) NOT NULL,
    provider_type   VARCHAR(50) NOT NULL DEFAULT 'farmer'
        CHECK (provider_type IN ('farmer', 'organization', 'government', 'system')),
    consumer_id     VARCHAR(200) NOT NULL,
    consumer_type   VARCHAR(50) NOT NULL DEFAULT 'organization'
        CHECK (consumer_type IN ('organization', 'government', 'researcher', 'partner', 'system')),

    -- What is shared
    data_categories TEXT[] NOT NULL DEFAULT '{}',
    purpose         TEXT NOT NULL,
    legal_basis     VARCHAR(100),

    -- Terms
    exclusivity     BOOLEAN NOT NULL DEFAULT FALSE,
    commercial_use  BOOLEAN NOT NULL DEFAULT FALSE,
    anonymization_required BOOLEAN NOT NULL DEFAULT TRUE,
    retention_days  INTEGER,
    geographic_scope VARCHAR(100),

    -- Lifecycle
    status          VARCHAR(30) NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft', 'pending_review', 'active', 'suspended',
            'expired', 'terminated', 'violated'
        )),
    effective_date  DATE,
    expiry_date     DATE,
    terminated_at   TIMESTAMPTZ,
    termination_reason TEXT,

    -- Signatures
    provider_signature   TEXT,
    provider_signed_at   TIMESTAMPTZ,
    consumer_signature   TEXT,
    consumer_signed_at   TIMESTAMPTZ,

    -- Audit
    approved_by     VARCHAR(200),
    approved_at     TIMESTAMPTZ,
    document_url    TEXT,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dsa_provider
    ON data_sharing_agreement (provider_id, status);
CREATE INDEX IF NOT EXISTS idx_dsa_consumer
    ON data_sharing_agreement (consumer_id, status);
CREATE INDEX IF NOT EXISTS idx_dsa_status
    ON data_sharing_agreement (status, effective_date);
CREATE INDEX IF NOT EXISTS idx_dsa_expiry
    ON data_sharing_agreement (expiry_date) WHERE expiry_date IS NOT NULL;

-- ============================================================
-- data_retention_policy
-- Policies for data retention and deletion per category.
-- ============================================================
CREATE TABLE IF NOT EXISTS data_retention_policy (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Scope
    data_category   VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(100),
    location_id     UUID REFERENCES location(id),

    -- Retention rules
    retention_days  INTEGER NOT NULL DEFAULT 2555,
    deletion_method VARCHAR(50) NOT NULL DEFAULT 'soft_delete'
        CHECK (deletion_method IN (
            'soft_delete', 'hard_delete', 'anonymize', 'archive', 'none'
        )),
    archive_after_days INTEGER,
    anonymize_fields  TEXT[],

    -- Exceptions
    legal_hold      BOOLEAN NOT NULL DEFAULT FALSE,
    legal_hold_reason TEXT,
    override_reason TEXT,

    -- Enforcement
    auto_enforce    BOOLEAN NOT NULL DEFAULT TRUE,
    last_enforced_at TIMESTAMPTZ,
    enforcement_status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (enforcement_status IN ('active', 'paused', 'error')),

    -- Policy owner
    policy_owner    VARCHAR(200),
    approved_by     VARCHAR(200),
    approval_date   DATE,
    document_url    TEXT,

    status          VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'draft')),
    priority        INTEGER NOT NULL DEFAULT 0,

    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drp_category
    ON data_retention_policy (data_category, status);
CREATE INDEX IF NOT EXISTS idx_drp_entity
    ON data_retention_policy (entity_type, data_category);
CREATE INDEX IF NOT EXISTS idx_drp_location
    ON data_retention_policy (location_id) WHERE location_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_drp_enforcement
    ON data_retention_policy (auto_enforce, last_enforced_at);

-- ============================================================
-- Public Views
-- ============================================================

-- Current consent status per farmer and data type
CREATE OR REPLACE VIEW v_consent_status AS
SELECT DISTINCT ON (farmer_id, data_category, consent_scope)
    id,
    farmer_id,
    location_id,
    data_category,
    consent_scope,
    status,
    granted_at,
    withdrawn_at,
    expires_at,
    consent_method,
    consent_version,
    CASE
        WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN 'expired'
        ELSE status
    END AS effective_status,
    CASE
        WHEN expires_at IS NOT NULL THEN
            EXTRACT(DAY FROM (expires_at - NOW()))::INTEGER
        ELSE NULL
    END AS days_until_expiry
FROM farmer_consent
WHERE status != 'withdrawn'
ORDER BY farmer_id, data_category, consent_scope, created_at DESC;

-- Recent data access events
CREATE OR REPLACE VIEW v_data_access_audit AS
SELECT
    dal.id,
    dal.accessor_id,
    dal.accessor_role,
    dal.accessor_type,
    dal.resource_type,
    dal.resource_id,
    dal.data_category,
    dal.access_type,
    dal.access_method,
    dal.purpose,
    dal.status,
    dal.denial_reason,
    dal.records_affected,
    dal.accessed_at,
    l.name AS location_name
FROM data_access_log dal
LEFT JOIN location l ON l.id = dal.location_id
WHERE dal.accessed_at >= NOW() - INTERVAL '30 days'
ORDER BY dal.accessed_at DESC;

-- Pending and completed portability requests
CREATE OR REPLACE VIEW v_portability_requests AS
SELECT
    dpr.id,
    dpr.farmer_id,
    dpr.location_id,
    dpr.data_categories,
    dpr.format,
    dpr.scope,
    dpr.status,
    dpr.requested_at,
    dpr.processed_at,
    dpr.ready_at,
    dpr.downloaded_at,
    dpr.expires_at,
    dpr.output_url,
    dpr.record_count,
    dpr.output_size_bytes,
    dpr.fair_principles,
    l.name AS location_name,
    CASE
        WHEN dpr.status = 'pending' AND dpr.requested_at < NOW() - INTERVAL '48 hours'
        THEN 'overdue'
        WHEN dpr.status = 'ready' AND dpr.expires_at < NOW()
        THEN 'expired_download'
        ELSE 'on_track'
    END AS sla_status
FROM data_portability_request dpr
LEFT JOIN location l ON l.id = dpr.location_id
ORDER BY dpr.requested_at DESC;

-- ============================================================
-- Default seed data: data categories
-- ============================================================
-- (Categories are enforced via CHECK constraints on farmer_consent
-- and data_portability_request; this reference table supports UI
-- dropdowns and documentation.)

CREATE TABLE IF NOT EXISTS data_governance_category (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_key    VARCHAR(100) NOT NULL UNIQUE,
    display_name    VARCHAR(200) NOT NULL,
    description     TEXT,
    default_retention_days INTEGER NOT NULL DEFAULT 2555,
    sensitivity     VARCHAR(20) NOT NULL DEFAULT 'standard'
        CHECK (sensitivity IN ('low', 'standard', 'sensitive', 'restricted')),
    requires_consent BOOLEAN NOT NULL DEFAULT TRUE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO data_governance_category
    (category_key, display_name, description, default_retention_days, sensitivity, requires_consent)
VALUES
    ('soil',         'Soil Data',         'Soil composition, moisture, pH, nutrient levels', 2555, 'standard',  TRUE),
    ('weather',      'Weather Data',      'Temperature, rainfall, humidity, wind',          1825, 'low',       TRUE),
    ('yield',        'Yield Data',        'Harvest quantities, crop quality, loss rates',    2555, 'standard',  TRUE),
    ('financial',    'Financial Data',    'Revenue, expenses, costs, financial plans',       2555, 'sensitive', TRUE),
    ('personal',     'Personal Data',     'Farmer name, contact, identity, household',       1095, 'restricted',TRUE),
    ('biodiversity', 'Biodiversity Data', 'Species observations, habitat surveys',           2555, 'standard',  TRUE),
    ('water',        'Water Data',        'Irrigation, water quality, watershed data',       2555, 'standard',  TRUE),
    ('carbon',       'Carbon Data',       'Carbon measurements, sequestration estimates',    3650, 'sensitive', TRUE),
    ('equipment',    'Equipment Data',    'Machinery usage, maintenance, OEE',               1825, 'standard',  FALSE),
    ('image',        'Image Data',        'Photos, satellite imagery, drone captures',       1825, 'standard',  TRUE),
    ('geospatial',   'Geospatial Data',   'Field boundaries, GPS coordinates, maps',         2555, 'sensitive', TRUE),
    ('practice',     'Practice Data',     'Farming practices, certifications, inputs',       2555, 'standard',  TRUE),
    ('social',       'Social Data',       'Community engagement, training records',          1825, 'standard',  TRUE)
ON CONFLICT (category_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    default_retention_days = EXCLUDED.default_retention_days,
    sensitivity = EXCLUDED.sensitivity,
    requires_consent = EXCLUDED.requires_consent;

-- ============================================================
-- Default seed data: consent scopes
-- ============================================================

CREATE TABLE IF NOT EXISTS data_governance_scope (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key       VARCHAR(100) NOT NULL UNIQUE,
    display_name    VARCHAR(200) NOT NULL,
    description     TEXT,
    default_active  BOOLEAN NOT NULL DEFAULT TRUE,
    legal_reference TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO data_governance_scope
    (scope_key, display_name, description, default_active, legal_reference)
VALUES
    ('collection',              'Data Collection',           'Gathering raw data from sensors, field reports, and manual entry', TRUE,  NULL),
    ('storage',                 'Data Storage',              'Retaining data in platform databases and backups',                  TRUE,  NULL),
    ('internal_use',            'Internal Use',              'Using data for farm management and analytics within the platform', TRUE,  NULL),
    ('anonymized_analytics',    'Anonymized Analytics',      'Using aggregated/anonymized data for platform-wide insights',     TRUE,  NULL),
    ('third_party_sharing',     'Third-Party Sharing',       'Sharing data with certified third-party partners',                FALSE, NULL),
    ('public_disclosure',       'Public Disclosure',         'Making data publicly visible on dashboards and reports',          FALSE, NULL),
    ('research',                'Research Use',              'Using data for agricultural and environmental research',          FALSE, NULL),
    ('marketing',               'Marketing Use',             'Using data for promotional and marketing purposes',               FALSE, NULL),
    ('government_reporting',    'Government Reporting',      'Sharing data with government agencies for compliance',            FALSE, NULL)
ON CONFLICT (scope_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    default_active = EXCLUDED.default_active,
    legal_reference = EXCLUDED.legal_reference;
