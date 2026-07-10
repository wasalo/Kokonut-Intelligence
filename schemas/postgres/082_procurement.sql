-- ============================================================
-- 082_procurement.sql — Bulk Purchasing Cooperative
-- ============================================================

-- 1. Supplier profile
CREATE TABLE IF NOT EXISTS supplier_profile (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    partner_id UUID REFERENCES partner(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    supplier_type VARCHAR(100),
    product_categories TEXT[],
    quality_rating NUMERIC(3,2) DEFAULT 0.5 CHECK (quality_rating >= 0 AND quality_rating <= 1),
    reliability_score NUMERIC(3,2) DEFAULT 0.5 CHECK (reliability_score >= 0 AND reliability_score <= 1),
    delivery_lead_time_days INTEGER DEFAULT 7,
    minimum_order_qty NUMERIC(12,2),
    minimum_order_unit VARCHAR(50),
    payment_terms VARCHAR(100),
    contact_name VARCHAR(255),
    contact_phone VARCHAR(50),
    contact_email VARCHAR(255),
    address TEXT,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_supplier_partner ON supplier_profile(partner_id);
CREATE INDEX IF NOT EXISTS idx_supplier_type ON supplier_profile(supplier_type);
CREATE INDEX IF NOT EXISTS idx_supplier_status ON supplier_profile(status);

ALTER TABLE supplier_profile DROP CONSTRAINT IF EXISTS chk_supplier_status;
ALTER TABLE supplier_profile ADD CONSTRAINT chk_supplier_status CHECK (status IN ('active', 'inactive', 'suspended', 'blacklisted'));

-- 2. Supply agreement
CREATE TABLE IF NOT EXISTS supply_agreement (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    supplier_id UUID NOT NULL REFERENCES supplier_profile(id) ON DELETE RESTRICT,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    agreement_name VARCHAR(255) NOT NULL,
    product_category VARCHAR(100) NOT NULL,
    negotiated_price_per_unit NUMERIC(12,4),
    price_unit VARCHAR(50),
    minimum_order_qty NUMERIC(12,2),
    currency VARCHAR(10) DEFAULT 'USD',
    valid_from DATE NOT NULL,
    valid_until DATE,
    payment_terms VARCHAR(100),
    delivery_terms TEXT,
    quality_requirements TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agreement_supplier ON supply_agreement(supplier_id);
CREATE INDEX IF NOT EXISTS idx_agreement_location ON supply_agreement(location_id);
CREATE INDEX IF NOT EXISTS idx_agreement_valid ON supply_agreement(valid_from, valid_until);

ALTER TABLE supply_agreement DROP CONSTRAINT IF EXISTS chk_agreement_status;
ALTER TABLE supply_agreement ADD CONSTRAINT chk_agreement_status CHECK (status IN ('draft', 'active', 'expired', 'terminated'));

-- 3. Purchase order
CREATE TABLE IF NOT EXISTS purchase_order (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    supplier_id UUID NOT NULL REFERENCES supplier_profile(id) ON DELETE RESTRICT,
    agreement_id UUID REFERENCES supply_agreement(id) ON DELETE SET NULL,
    order_number VARCHAR(50) NOT NULL UNIQUE,
    order_type VARCHAR(50) NOT NULL DEFAULT 'individual',
    group_buy_id UUID,
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_delivery DATE,
    actual_delivery DATE,
    total_amount NUMERIC(15,2),
    currency VARCHAR(10) DEFAULT 'USD',
    discount_pct NUMERIC(5,2) DEFAULT 0,
    shipping_cost NUMERIC(12,2) DEFAULT 0,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_po_location ON purchase_order(location_id);
CREATE INDEX IF NOT EXISTS idx_po_supplier ON purchase_order(supplier_id);
CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_order(status);
CREATE INDEX IF NOT EXISTS idx_po_date ON purchase_order(order_date);
CREATE INDEX IF NOT EXISTS idx_po_group ON purchase_order(group_buy_id);

ALTER TABLE purchase_order DROP CONSTRAINT IF EXISTS chk_po_type;
ALTER TABLE purchase_order ADD CONSTRAINT chk_po_type CHECK (order_type IN ('individual', 'group_buy'));

ALTER TABLE purchase_order DROP CONSTRAINT IF EXISTS chk_po_status;
ALTER TABLE purchase_order ADD CONSTRAINT chk_po_status CHECK (status IN ('draft', 'submitted', 'confirmed', 'shipped', 'delivered', 'invoiced', 'paid', 'cancelled'));

-- 4. Purchase order item
CREATE TABLE IF NOT EXISTS purchase_order_item (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES purchase_order(id) ON DELETE CASCADE,
    inventory_event_id UUID REFERENCES inventory_event(id) ON DELETE SET NULL,
    product_name VARCHAR(255) NOT NULL,
    product_category VARCHAR(100),
    quantity NUMERIC(12,4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    unit_price NUMERIC(12,4),
    discount_pct NUMERIC(5,2) DEFAULT 0,
    total_price NUMERIC(15,2),
    quality_grade VARCHAR(50),
    organic_certified BOOLEAN DEFAULT FALSE,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_po_item_order ON purchase_order_item(order_id);
CREATE INDEX IF NOT EXISTS idx_po_item_product ON purchase_order_item(product_name);

-- 5. Group buy (cooperative order consolidation)
CREATE TABLE IF NOT EXISTS group_buy (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organizer_location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    group_buy_name VARCHAR(255) NOT NULL,
    product_category VARCHAR(100) NOT NULL,
    target_quantity NUMERIC(12,2),
    unit VARCHAR(50),
    volume_discount_threshold NUMERIC(12,2),
    volume_discount_pct NUMERIC(5,2),
    current_quantity NUMERIC(12,2) DEFAULT 0,
    participant_count INTEGER DEFAULT 0,
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date DATE,
    status VARCHAR(50) DEFAULT 'open',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_gb_organizer ON group_buy(organizer_location_id);
CREATE INDEX IF NOT EXISTS idx_gb_status ON group_buy(status);
CREATE INDEX IF NOT EXISTS idx_gb_dates ON group_buy(start_date, end_date);

ALTER TABLE group_buy DROP CONSTRAINT IF EXISTS chk_gb_status;
ALTER TABLE group_buy ADD CONSTRAINT chk_gb_status CHECK (status IN ('open', 'closed', 'ordered', 'delivered', 'cancelled'));

-- 6. Group buy participation
CREATE TABLE IF NOT EXISTS group_buy_participation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_buy_id UUID NOT NULL REFERENCES group_buy(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    committed_quantity NUMERIC(12,2) NOT NULL,
    unit VARCHAR(50),
    order_id UUID REFERENCES purchase_order(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'committed',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(group_buy_id, location_id)
);

CREATE INDEX IF NOT EXISTS idx_gbp_group ON group_buy_participation(group_buy_id);
CREATE INDEX IF NOT EXISTS idx_gbp_location ON group_buy_participation(location_id);

ALTER TABLE group_buy_participation DROP CONSTRAINT IF EXISTS chk_gbp_status;
ALTER TABLE group_buy_participation ADD CONSTRAINT chk_gbp_status CHECK (status IN ('committed', 'ordered', 'delivered', 'cancelled'));

-- 7. Supplier quality assessment
CREATE TABLE IF NOT EXISTS supplier_quality_assessment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    supplier_id UUID NOT NULL REFERENCES supplier_profile(id) ON DELETE CASCADE,
    assessment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    delivery_timeliness_score NUMERIC(3,2) CHECK (delivery_timeliness_score >= 0 AND delivery_timeliness_score <= 1),
    product_quality_score NUMERIC(3,2) CHECK (product_quality_score >= 0 AND product_quality_score <= 1),
    pricing_fairness_score NUMERIC(3,2) CHECK (pricing_fairness_score >= 0 AND pricing_fairness_score <= 1),
    communication_score NUMERIC(3,2) CHECK (communication_score >= 0 AND communication_score <= 1),
    overall_score NUMERIC(3,2) CHECK (overall_score >= 0 AND overall_score <= 1),
    assessed_by UUID REFERENCES staff(id) ON DELETE SET NULL,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sqa_supplier ON supplier_quality_assessment(supplier_id);
CREATE INDEX IF NOT EXISTS idx_sqa_date ON supplier_quality_assessment(assessment_date);

-- 8. Add FK from purchase_order to group_buy (circular reference resolved after both tables exist)
ALTER TABLE purchase_order DROP CONSTRAINT IF EXISTS fk_po_group_buy;
ALTER TABLE purchase_order ADD CONSTRAINT fk_po_group_buy FOREIGN KEY (group_buy_id) REFERENCES group_buy(id) ON DELETE SET NULL;

-- 9. Public views
CREATE OR REPLACE VIEW v_public_procurement_summary AS
SELECT
    po.id AS order_id,
    po.order_number,
    po.order_date,
    po.total_amount,
    po.currency,
    po.status,
    po.order_type,
    sp.name AS supplier_name,
    l.name AS location_name,
    (SELECT COUNT(*) FROM purchase_order_item poi WHERE poi.order_id = po.id) AS item_count
FROM purchase_order po
JOIN supplier_profile sp ON sp.id = po.supplier_id
LEFT JOIN location l ON l.id = po.location_id
WHERE EXISTS (
    SELECT 1 FROM farm_registry_record fr
    WHERE fr.location_id = po.location_id
    AND fr.status IN ('verified', 'published')
);

CREATE OR REPLACE VIEW v_group_buy_status AS
SELECT
    gb.id AS group_buy_id,
    gb.group_buy_name,
    gb.product_category,
    gb.target_quantity,
    gb.unit,
    gb.current_quantity,
    gb.participant_count,
    gb.volume_discount_threshold,
    gb.volume_discount_pct,
    CASE
        WHEN gb.volume_discount_threshold IS NOT NULL AND gb.current_quantity >= gb.volume_discount_threshold
        THEN TRUE ELSE FALSE
    END AS discount_achieved,
    gb.status,
    l.name AS organizer_location
FROM group_buy gb
LEFT JOIN location l ON l.id = gb.organizer_location_id;
