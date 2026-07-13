-- ============================================================
-- 147_cooperative.sql — Digital Cooperatives
-- Cooperative organizations, shared assets, collective purchasing,
-- and collective market orders for farmer cooperatives.
-- ============================================================

-- Cooperative types (seed reference data)
CREATE TABLE IF NOT EXISTS cooperative_type (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    default_purpose TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO cooperative_type (name, description, default_purpose) VALUES
    ('marketing', 'Collective marketing and sales cooperative', 'Aggregate produce for better market access and pricing'),
    ('input_purchase', 'Joint input purchasing cooperative', 'Bulk procurement of seeds, fertilizer, and supplies at lower cost'),
    ('equipment_sharing', 'Shared equipment and machinery cooperative', 'Pooled ownership of tractors, storage, and processing equipment'),
    ('processing', 'Value-added processing cooperative', 'Shared processing, packaging, and branding infrastructure')
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    default_purpose = EXCLUDED.default_purpose;

-- Cooperative organizations
CREATE TABLE IF NOT EXISTS cooperative (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(255) NOT NULL,
    type_id             UUID NOT NULL REFERENCES cooperative_type(id),
    description         TEXT,
    mission_statement   TEXT,

    -- Location
    location_id         UUID REFERENCES location(id),
    address             TEXT,
    latitude            NUMERIC(10,7),
    longitude           NUMERIC(10,7),
    service_area_km     NUMERIC(6,2),

    -- Membership
    membership_count    INTEGER DEFAULT 0,
    max_members         INTEGER,
    membership_fee      NUMERIC(12,2),
    currency            VARCHAR(10) DEFAULT 'USD',

    -- Governance
    governance_model    VARCHAR(100) DEFAULT 'one_member_one_vote',
    board_members       JSONB DEFAULT '[]',
    decision_mechanism  VARCHAR(100) DEFAULT 'majority_vote',

    -- Financials
    total_revenue       NUMERIC(15,2) DEFAULT 0,
    total_assets_value  NUMERIC(15,2) DEFAULT 0,
    operating_reserve   NUMERIC(15,2) DEFAULT 0,

    -- Registration
    registration_number VARCHAR(100),
    registration_date   DATE,
    legal_entity_type   VARCHAR(100),

    -- Status
    status              VARCHAR(50) NOT NULL DEFAULT 'draft',
    founded_date        DATE,
    dissolved_date      DATE,

    source_system       VARCHAR(100),
    source_id           VARCHAR(255),
    source_raw          JSONB,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID,
    updated_by          UUID
);

CREATE INDEX IF NOT EXISTS idx_coop_type ON cooperative(type_id);
CREATE INDEX IF NOT EXISTS idx_coop_location ON cooperative(location_id);
CREATE INDEX IF NOT EXISTS idx_coop_status ON cooperative(status);
CREATE INDEX IF NOT EXISTS idx_coop_name ON cooperative(name);

ALTER TABLE cooperative DROP CONSTRAINT IF EXISTS chk_coop_status;
ALTER TABLE cooperative ADD CONSTRAINT chk_coop_status CHECK (status IN (
    'draft', 'active', 'suspended', 'dissolved', 'archived'
));

ALTER TABLE cooperative DROP CONSTRAINT IF EXISTS chk_coop_governance;
ALTER TABLE cooperative ADD CONSTRAINT chk_coop_governance CHECK (governance_model IN (
    'one_member_one_vote', 'proportional', 'board_directors', 'delegated', 'hybrid'
));

-- Cooperative membership
CREATE TABLE IF NOT EXISTS cooperative_membership (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cooperative_id  UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,
    location_id     UUID REFERENCES location(id),

    -- Member info
    member_name     VARCHAR(255),
    member_type     VARCHAR(50) NOT NULL DEFAULT 'farmer',
    role            VARCHAR(100) NOT NULL DEFAULT 'member',

    -- Membership details
    join_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    share_count     INTEGER DEFAULT 1,
    share_value     NUMERIC(12,2),
    membership_fee_paid NUMERIC(12,2) DEFAULT 0,

    -- Contribution tracking
    total_contributions NUMERIC(15,2) DEFAULT 0,
    last_contribution_at TIMESTAMPTZ,

    -- Voting
    voting_weight   NUMERIC(5,2) DEFAULT 1.0,
    delegate_id     UUID REFERENCES cooperative_membership(id),

    -- Status
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    leave_date      DATE,
    leave_reason    TEXT,

    source_system   VARCHAR(100),
    source_id       VARCHAR(255),
    source_raw      JSONB,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      UUID,
    updated_by      UUID
);

CREATE INDEX IF NOT EXISTS idx_coop_mem_coop ON cooperative_membership(cooperative_id);
CREATE INDEX IF NOT EXISTS idx_coop_mem_location ON cooperative_membership(location_id);
CREATE INDEX IF NOT EXISTS idx_coop_mem_status ON cooperative_membership(status);
CREATE INDEX IF NOT EXISTS idx_coop_mem_role ON cooperative_membership(role);

ALTER TABLE cooperative_membership DROP CONSTRAINT IF EXISTS chk_coop_mem_member_type;
ALTER TABLE cooperative_membership ADD CONSTRAINT chk_coop_mem_member_type CHECK (member_type IN (
    'farmer', 'associate', 'youth', 'women_group', 'cooperative', 'investor', 'other'
));

ALTER TABLE cooperative_membership DROP CONSTRAINT IF EXISTS chk_coop_mem_role;
ALTER TABLE cooperative_membership ADD CONSTRAINT chk_coop_mem_role CHECK (role IN (
    'member', 'board_member', 'treasurer', 'secretary', 'chairperson', 'manager', 'auditor', 'observer'
));

ALTER TABLE cooperative_membership DROP CONSTRAINT IF EXISTS chk_coop_mem_status;
ALTER TABLE cooperative_membership ADD CONSTRAINT chk_coop_mem_status CHECK (status IN (
    'active', 'inactive', 'suspended', 'pending', 'expelled', 'transferred'
));

-- Shared assets
CREATE TABLE IF NOT EXISTS shared_asset (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cooperative_id      UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    asset_type          VARCHAR(100) NOT NULL,

    -- Asset details
    category            VARCHAR(100),
    make                VARCHAR(200),
    model               VARCHAR(200),
    year_manufactured   INTEGER,
    serial_number       VARCHAR(200),

    -- Capacity and specs
    capacity            VARCHAR(100),
    capacity_unit       VARCHAR(50),
    specifications      JSONB DEFAULT '{}',

    -- Financials
    purchase_price      NUMERIC(15,2),
    current_value       NUMERIC(15,2),
    depreciation_rate   NUMERIC(5,2) DEFAULT 10.0,
    hourly_rate         NUMERIC(12,2),
    daily_rate          NUMERIC(12,2),
    currency            VARCHAR(10) DEFAULT 'USD',

    -- Usage tracking
    total_hours_used    NUMERIC(10,2) DEFAULT 0,
    total_bookings      INTEGER DEFAULT 0,
    avg_utilization_pct NUMERIC(5,2) DEFAULT 0,

    -- Availability
    location_id         UUID REFERENCES location(id),
    storage_location    TEXT,
    is_portable         BOOLEAN DEFAULT TRUE,
    transport_available BOOLEAN DEFAULT FALSE,
    min_booking_hours   NUMERIC(5,1) DEFAULT 1,
    max_booking_hours   NUMERIC(6,1) DEFAULT 168,

    -- Maintenance
    maintenance_interval_days INTEGER DEFAULT 90,
    last_maintenance_at TIMESTAMPTZ,
    next_maintenance_at TIMESTAMPTZ,
    condition_rating    VARCHAR(50) DEFAULT 'good',

    -- Status
    status              VARCHAR(50) NOT NULL DEFAULT 'available',
    decommissioned_at   TIMESTAMPTZ,

    source_system       VARCHAR(100),
    source_id           VARCHAR(255),
    source_raw          JSONB,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID,
    updated_by          UUID
);

CREATE INDEX IF NOT EXISTS idx_asset_coop ON shared_asset(cooperative_id);
CREATE INDEX IF NOT EXISTS idx_asset_type ON shared_asset(asset_type);
CREATE INDEX IF NOT EXISTS idx_asset_status ON shared_asset(status);
CREATE INDEX IF NOT EXISTS idx_asset_location ON shared_asset(location_id);

ALTER TABLE shared_asset DROP CONSTRAINT IF EXISTS chk_asset_asset_type;
ALTER TABLE shared_asset ADD CONSTRAINT chk_asset_asset_type CHECK (asset_type IN (
    'tractor', 'harvester', 'irrigation_system', 'storage_facility',
    'processing_equipment', 'transport_vehicle', 'drying_rack',
    'mill', 'press', 'packaging_machine', 'generator', 'solar_panel',
    'water_tank', 'greenhouse', 'other'
));

ALTER TABLE shared_asset DROP CONSTRAINT IF EXISTS chk_asset_status;
ALTER TABLE shared_asset ADD CONSTRAINT chk_asset_status CHECK (status IN (
    'available', 'in_use', 'under_maintenance', 'reserved',
    'decommissioned', 'out_of_service'
));

ALTER TABLE shared_asset DROP CONSTRAINT IF EXISTS chk_asset_condition;
ALTER TABLE shared_asset ADD CONSTRAINT chk_asset_condition CHECK (condition_rating IN (
    'excellent', 'good', 'fair', 'poor', 'needs_replacement'
));

-- Asset bookings
CREATE TABLE IF NOT EXISTS asset_booking (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id            UUID NOT NULL REFERENCES shared_asset(id) ON DELETE CASCADE,
    cooperative_id      UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,
    membership_id       UUID NOT NULL REFERENCES cooperative_membership(id),

    -- Booking details
    start_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ NOT NULL,
    duration_hours      NUMERIC(6,2) NOT NULL,
    purpose             TEXT,
    field_location      TEXT,
    latitude            NUMERIC(10,7),
    longitude           NUMERIC(10,7),

    -- Cost
    hourly_rate         NUMERIC(12,2),
    total_cost          NUMERIC(12,2) DEFAULT 0,
    payment_status      VARCHAR(50) DEFAULT 'pending',
    paid_at             TIMESTAMPTZ,

    -- Operational
    operator_name       VARCHAR(255),
    operator_skill_level VARCHAR(50),
    fuel_provided       BOOLEAN DEFAULT FALSE,
    fuel_liters         NUMERIC(8,2),
    return_condition    VARCHAR(50),
    damage_reported     BOOLEAN DEFAULT FALSE,
    damage_notes        TEXT,

    -- Status
    status              VARCHAR(50) NOT NULL DEFAULT 'pending',
    confirmed_at        TIMESTAMPTZ,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    cancellation_reason TEXT,

    source_system       VARCHAR(100),
    source_id           VARCHAR(255),
    source_raw          JSONB,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID,
    updated_by          UUID
);

CREATE INDEX IF NOT EXISTS idx_booking_asset ON asset_booking(asset_id);
CREATE INDEX IF NOT EXISTS idx_booking_coop ON asset_booking(cooperative_id);
CREATE INDEX IF NOT EXISTS idx_booking_membership ON asset_booking(membership_id);
CREATE INDEX IF NOT EXISTS idx_booking_status ON asset_booking(status);
CREATE INDEX IF NOT EXISTS idx_booking_start ON asset_booking(start_time);
CREATE INDEX IF NOT EXISTS idx_booking_window ON asset_booking(start_time, end_time);

ALTER TABLE asset_booking DROP CONSTRAINT IF EXISTS chk_booking_status;
ALTER TABLE asset_booking ADD CONSTRAINT chk_booking_status CHECK (status IN (
    'pending', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show'
));

ALTER TABLE asset_booking DROP CONSTRAINT IF EXISTS chk_booking_payment;
ALTER TABLE asset_booking ADD CONSTRAINT chk_booking_payment CHECK (payment_status IN (
    'pending', 'paid', 'partial', 'refunded', 'waived'
));

-- Collective purchase orders (input purchasing)
CREATE TABLE IF NOT EXISTS collective_purchase (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cooperative_id      UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,

    -- Order details
    order_name          VARCHAR(255) NOT NULL,
    description         TEXT,
    input_category      VARCHAR(100) NOT NULL,
    input_items         JSONB NOT NULL DEFAULT '[]',
    target_quantity     NUMERIC(12,2),
    unit                VARCHAR(50),

    -- Participants
    participant_count   INTEGER DEFAULT 0,
    min_participants    INTEGER,
    min_total_quantity  NUMERIC(12,2),

    -- Pricing
    estimated_unit_price NUMERIC(12,2),
    negotiated_unit_price NUMERIC(12,2),
    total_estimated_cost NUMERIC(15,2),
    total_actual_cost   NUMERIC(15,2),
    currency            VARCHAR(10) DEFAULT 'USD',
    savings_pct         NUMERIC(5,2),

    -- Supplier
    supplier_name       VARCHAR(255),
    supplier_contact    TEXT,
    supplier_quote_url  TEXT,
    payment_terms       TEXT,

    -- Delivery
    expected_delivery   DATE,
    actual_delivery     DATE,
    delivery_address    TEXT,
    delivery_notes      TEXT,

    -- Status
    status              VARCHAR(50) NOT NULL DEFAULT 'collecting',
    confirmed_at        TIMESTAMPTZ,
    paid_at             TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    cancellation_reason TEXT,

    source_system       VARCHAR(100),
    source_id           VARCHAR(255),
    source_raw          JSONB,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID,
    updated_by          UUID
);

CREATE INDEX IF NOT EXISTS idx_purch_coop ON collective_purchase(cooperative_id);
CREATE INDEX IF NOT EXISTS idx_purch_category ON collective_purchase(input_category);
CREATE INDEX IF NOT EXISTS idx_purch_status ON collective_purchase(status);
CREATE INDEX IF NOT EXISTS idx_purch_delivery ON collective_purchase(expected_delivery);

ALTER TABLE collective_purchase DROP CONSTRAINT IF EXISTS chk_purch_category;
ALTER TABLE collective_purchase ADD CONSTRAINT chk_purch_category CHECK (input_category IN (
    'seeds', 'fertilizer', 'pesticide', 'herbicide', 'tools',
    'irrigation_parts', 'fuel', 'feed', 'packaging', 'organic_inputs', 'other'
));

ALTER TABLE collective_purchase DROP CONSTRAINT IF EXISTS chk_purch_status;
ALTER TABLE collective_purchase ADD CONSTRAINT chk_purch_status CHECK (status IN (
    'collecting', 'confirmed', 'ordered', 'shipped', 'delivered',
    'distributed', 'completed', 'cancelled'
));

-- Collective purchase participants
CREATE TABLE IF NOT EXISTS collective_purchase_participant (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_id         UUID NOT NULL REFERENCES collective_purchase(id) ON DELETE CASCADE,
    membership_id       UUID NOT NULL REFERENCES cooperative_membership(id),
    quantity_requested  NUMERIC(12,2) NOT NULL,
    quantity_received   NUMERIC(12,2) DEFAULT 0,
    unit_price          NUMERIC(12,2),
    total_cost          NUMERIC(15,2),
    payment_status      VARCHAR(50) DEFAULT 'pending',
    payment_amount      NUMERIC(15,2) DEFAULT 0,
    paid_at             TIMESTAMPTZ,
    status              VARCHAR(50) NOT NULL DEFAULT 'committed',
    notes               TEXT,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_purch_part_purchase ON collective_purchase_participant(purchase_id);
CREATE INDEX IF NOT EXISTS idx_purch_part_membership ON collective_purchase_participant(membership_id);
CREATE INDEX IF NOT EXISTS idx_purch_part_status ON collective_purchase_participant(status);

ALTER TABLE collective_purchase_participant DROP CONSTRAINT IF EXISTS chk_purch_part_status;
ALTER TABLE collective_purchase_participant ADD CONSTRAINT chk_purch_part_status CHECK (status IN (
    'committed', 'confirmed', 'paid', 'received', 'cancelled'
));

-- Collective market orders (selling)
CREATE TABLE IF NOT EXISTS collective_market_order (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cooperative_id      UUID NOT NULL REFERENCES cooperative(id) ON DELETE CASCADE,

    -- Order details
    order_name          VARCHAR(255) NOT NULL,
    description         TEXT,
    crop_type           VARCHAR(100) NOT NULL,
    variety             VARCHAR(200),
    quality_grade       VARCHAR(50),

    -- Quantity
    total_quantity      NUMERIC(12,2) NOT NULL,
    unit                VARCHAR(50) NOT NULL,
    min_order_quantity  NUMERIC(12,2),

    -- Pricing
    target_price        NUMERIC(12,2),
    agreed_price        NUMERIC(12,2),
    currency            VARCHAR(10) DEFAULT 'USD',
    total_value         NUMERIC(15,2),

    -- Buyer
    buyer_name          VARCHAR(255),
    buyer_contact       TEXT,
    buyer_type          VARCHAR(100),
    contract_reference  VARCHAR(200),

    -- Logistics
    collection_point    TEXT,
    collection_date     DATE,
    delivery_date       DATE,
    transport_arranged  BOOLEAN DEFAULT FALSE,
    transport_cost      NUMERIC(12,2),
    storage_required    BOOLEAN DEFAULT FALSE,
    storage_location    TEXT,
    certification_required TEXT[],

    -- Quality
    quality_checked     BOOLEAN DEFAULT FALSE,
    quality_report_url  TEXT,
    sample_provided     BOOLEAN DEFAULT FALSE,

    -- Status
    status              VARCHAR(50) NOT NULL DEFAULT 'collecting',
    confirmed_at        TIMESTAMPTZ,
    dispatched_at       TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    paid_at             TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    cancellation_reason TEXT,

    source_system       VARCHAR(100),
    source_id           VARCHAR(255),
    source_raw          JSONB,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          UUID,
    updated_by          UUID
);

CREATE INDEX IF NOT EXISTS idx_market_coop ON collective_market_order(cooperative_id);
CREATE INDEX IF NOT EXISTS idx_market_crop ON collective_market_order(crop_type);
CREATE INDEX IF NOT EXISTS idx_market_status ON collective_market_order(status);
CREATE INDEX IF NOT EXISTS idx_market_delivery ON collective_market_order(delivery_date);

ALTER TABLE collective_market_order DROP CONSTRAINT IF EXISTS chk_market_status;
ALTER TABLE collective_market_order ADD CONSTRAINT chk_market_status CHECK (status IN (
    'collecting', 'confirmed', 'dispatched', 'delivered',
    'quality_check', 'paid', 'completed', 'cancelled'
));

-- Collective market order participants
CREATE TABLE IF NOT EXISTS collective_market_participant (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_order_id     UUID NOT NULL REFERENCES collective_market_order(id) ON DELETE CASCADE,
    membership_id       UUID NOT NULL REFERENCES cooperative_membership(id),
    quantity_offered    NUMERIC(12,2) NOT NULL,
    quantity_delivered  NUMERIC(12,2) DEFAULT 0,
    unit_price          NUMERIC(12,2),
    total_earnings      NUMERIC(15,2),
    payment_status      VARCHAR(50) DEFAULT 'pending',
    payment_amount      NUMERIC(15,2) DEFAULT 0,
    paid_at             TIMESTAMPTZ,
    quality_grade       VARCHAR(50),
    status              VARCHAR(50) NOT NULL DEFAULT 'committed',
    notes               TEXT,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_part_order ON collective_market_participant(market_order_id);
CREATE INDEX IF NOT EXISTS idx_market_part_membership ON collective_market_participant(membership_id);
CREATE INDEX IF NOT EXISTS idx_market_part_status ON collective_market_participant(status);

ALTER TABLE collective_market_participant DROP CONSTRAINT IF EXISTS chk_market_part_status;
ALTER TABLE collective_market_participant ADD CONSTRAINT chk_market_part_status CHECK (status IN (
    'committed', 'confirmed', 'delivered', 'quality_checked', 'paid', 'cancelled'
));

-- ============================================================
-- Public Views
-- ============================================================

-- Cooperative summary with membership counts and asset inventory
CREATE OR REPLACE VIEW v_cooperative_summary AS
SELECT
    c.id,
    c.name,
    ct.name AS type,
    c.description,
    c.mission_statement,
    l.name AS location_name,
    l.country,
    c.membership_count,
    c.max_members,
    c.governance_model,
    c.total_revenue,
    c.total_assets_value,
    c.founded_date,
    c.status,
    (SELECT COUNT(*) FROM shared_asset sa WHERE sa.cooperative_id = c.id AND sa.status NOT IN ('decommissioned', 'out_of_service')) AS active_assets,
    (SELECT COALESCE(SUM(sa.current_value), 0) FROM shared_asset sa WHERE sa.cooperative_id = c.id) AS asset_value_total,
    (SELECT COUNT(*) FROM cooperative_membership cm WHERE cm.cooperative_id = c.id AND cm.status = 'active') AS verified_active_members,
    (SELECT COUNT(*) FROM collective_purchase cp WHERE cp.cooperative_id = c.id AND cp.status NOT IN ('completed', 'cancelled')) AS active_purchases,
    (SELECT COUNT(*) FROM collective_market_order cmo WHERE cmo.cooperative_id = c.id AND cmo.status NOT IN ('completed', 'cancelled')) AS active_market_orders,
    c.status AS coop_status,
    c.created_at,
    c.updated_at
FROM cooperative c
JOIN cooperative_type ct ON ct.id = c.type_id
LEFT JOIN location l ON l.id = c.location_id
WHERE c.status != 'archived';

-- Shared asset usage rates and availability
CREATE OR REPLACE VIEW v_asset_utilization AS
SELECT
    sa.id,
    sa.name,
    sa.asset_type,
    sa.category,
    sa.cooperative_id,
    c.name AS cooperative_name,
    sa.status,
    sa.condition_rating,
    sa.capacity,
    sa.hourly_rate,
    sa.daily_rate,
    sa.currency,
    sa.total_hours_used,
    sa.total_bookings,
    sa.avg_utilization_pct,
    sa.last_maintenance_at,
    sa.next_maintenance_at,
    (SELECT COUNT(*)
     FROM asset_booking ab
     WHERE ab.asset_id = sa.id
       AND ab.status IN ('confirmed', 'in_progress')
       AND ab.end_time >= NOW()
    ) AS upcoming_bookings,
    (SELECT SUM(ab.duration_hours)
     FROM asset_booking ab
     WHERE ab.asset_id = sa.id
       AND ab.status IN ('confirmed', 'in_progress')
       AND ab.start_time >= DATE_TRUNC('month', NOW())
       AND ab.end_time <= DATE_TRUNC('month', NOW()) + INTERVAL '1 month'
    ) AS hours_booked_this_month,
    CASE
        WHEN sa.avg_utilization_pct >= 70 THEN 'high'
        WHEN sa.avg_utilization_pct >= 40 THEN 'moderate'
        WHEN sa.avg_utilization_pct >= 10 THEN 'low'
        ELSE 'idle'
    END AS utilization_band,
    sa.created_at,
    sa.updated_at
FROM shared_asset sa
JOIN cooperative c ON c.id = sa.cooperative_id
WHERE sa.status != 'decommissioned';

-- Active collective purchase and market orders
CREATE OR REPLACE VIEW v_collective_orders AS
SELECT
    'purchase' AS order_type,
    cp.id,
    cp.cooperative_id,
    c.name AS cooperative_name,
    cp.order_name,
    cp.description,
    cp.input_category AS category,
    cp.target_quantity,
    cp.unit,
    cp.participant_count,
    cp.estimated_unit_price,
    cp.negotiated_unit_price,
    cp.total_estimated_cost,
    cp.total_actual_cost,
    cp.currency,
    cp.savings_pct,
    cp.supplier_name,
    cp.expected_delivery,
    cp.status,
    cp.created_at,
    cp.updated_at
FROM collective_purchase cp
JOIN cooperative c ON c.id = cp.cooperative_id
WHERE cp.status NOT IN ('completed', 'cancelled')

UNION ALL

SELECT
    'market' AS order_type,
    cmo.id,
    cmo.cooperative_id,
    c.name AS cooperative_name,
    cmo.order_name,
    cmo.description,
    cmo.crop_type AS category,
    cmo.total_quantity AS target_quantity,
    cmo.unit,
    (SELECT COUNT(*) FROM collective_market_participant cmp WHERE cmp.market_order_id = cmo.id) AS participant_count,
    cmo.target_price AS estimated_unit_price,
    cmo.agreed_price AS negotiated_unit_price,
    cmo.total_value AS total_estimated_cost,
    cmo.total_value AS total_actual_cost,
    cmo.currency,
    NULL AS savings_pct,
    cmo.buyer_name AS supplier_name,
    cmo.delivery_date AS expected_delivery,
    cmo.status,
    cmo.created_at,
    cmo.updated_at
FROM collective_market_order cmo
JOIN cooperative c ON c.id = cmo.cooperative_id
WHERE cmo.status NOT IN ('completed', 'cancelled')

ORDER BY created_at DESC;
