-- ============================================================
-- 003_operations.sql — Operational facts
-- ============================================================

-- Farm activity log
CREATE TABLE IF NOT EXISTS farm_activity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plot_id UUID REFERENCES plot(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    activity_type VARCHAR(100) NOT NULL, -- planting, weeding, irrigation, pruning, spraying, harvesting, transport, storage, other
    activity_date DATE NOT NULL,
    description TEXT,
    labor_hours NUMERIC(8,2),
    labor_cost NUMERIC(12,2),
    materials_used JSONB DEFAULT '[]',
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    -- Workflow
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, verified, published, rejected
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    -- Source lineage
    schema_version VARCHAR(20),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_activity_plot ON farm_activity(plot_id);
CREATE INDEX IF NOT EXISTS idx_activity_crop_cycle ON farm_activity(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_activity_location ON farm_activity(location_id);
CREATE INDEX IF NOT EXISTS idx_activity_date ON farm_activity(activity_date);
CREATE INDEX IF NOT EXISTS idx_activity_type ON farm_activity(activity_type);
CREATE INDEX IF NOT EXISTS idx_activity_status ON farm_activity(status);

-- Harvest events
CREATE TABLE IF NOT EXISTS harvest_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_cycle_id UUID NOT NULL REFERENCES crop_cycle(id) ON DELETE RESTRICT,
    plot_id UUID NOT NULL REFERENCES plot(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    harvest_date DATE NOT NULL,
    quantity NUMERIC(12,4) NOT NULL,
    unit VARCHAR(50) NOT NULL, -- kg, tonnes, bags, bunches, liters
    quality_grade VARCHAR(50), -- A, B, C, premium, standard, rejected
    destination VARCHAR(255), -- storage, processor, buyer, market, farm_gate
    -- Loss tracking
    loss_amount NUMERIC(12,4),
    loss_unit VARCHAR(50),
    loss_reason TEXT,
    loss_estimated_value NUMERIC(15,2),
    -- Evidence
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    -- Workflow
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    -- Source lineage
    schema_version VARCHAR(20),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_harvest_crop_cycle ON harvest_event(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_harvest_plot ON harvest_event(plot_id);
CREATE INDEX IF NOT EXISTS idx_harvest_location ON harvest_event(location_id);
CREATE INDEX IF NOT EXISTS idx_harvest_date ON harvest_event(harvest_date);

-- Sales events
CREATE TABLE IF NOT EXISTS sales_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    harvest_id UUID REFERENCES harvest_event(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    partner_id UUID REFERENCES partner(id),
    sale_date DATE NOT NULL,
    buyer VARCHAR(255),
    buyer_type VARCHAR(100), -- market, processor, direct, export, cooperatively, restaurant, retailer
    quantity NUMERIC(12,4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    price_per_unit NUMERIC(12,4),
    total_amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    payment_status VARCHAR(50) DEFAULT 'pending', -- pending, partial, paid, overdue, cancelled
    payment_date DATE,
    payment_method VARCHAR(100),
    invoice_number VARCHAR(100),
    -- Returns / discounts
    return_amount NUMERIC(15,2) DEFAULT 0,
    discount_amount NUMERIC(15,2) DEFAULT 0,
    net_amount NUMERIC(15,2),
    -- Evidence
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    -- Workflow
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    -- Source lineage
    schema_version VARCHAR(20),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_sales_harvest ON sales_event(harvest_id);
CREATE INDEX IF NOT EXISTS idx_sales_crop_cycle ON sales_event(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_sales_location ON sales_event(location_id);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_event(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_status ON sales_event(payment_status);

-- Expense events
CREATE TABLE IF NOT EXISTS expense_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    expense_date DATE NOT NULL,
    category VARCHAR(100) NOT NULL, -- seeds, fertilizer, pesticide, labor, equipment, transport, irrigation, processing, packaging, marketing, utilities, rent, other
    subcategory VARCHAR(100),
    description TEXT,
    vendor VARCHAR(255),
    vendor_id UUID REFERENCES partner(id),
    amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    is_capex BOOLEAN DEFAULT FALSE,
    -- Cost allocation
    allocation_method VARCHAR(50), -- direct, proportional, equal, area_based
    allocation_weight NUMERIC(8,4),
    -- Evidence
    evidence_urls TEXT[],
    receipt_hash VARCHAR(255),
    invoice_number VARCHAR(100),
    notes TEXT,
    -- Approval workflow
    status VARCHAR(50) DEFAULT 'draft', -- draft, submitted, approved, rejected, paid
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,
    -- Source lineage
    schema_version VARCHAR(20),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_expense_location ON expense_event(location_id);
CREATE INDEX IF NOT EXISTS idx_expense_plot ON expense_event(plot_id);
CREATE INDEX IF NOT EXISTS idx_expense_crop_cycle ON expense_event(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_expense_date ON expense_event(expense_date);
CREATE INDEX IF NOT EXISTS idx_expense_category ON expense_event(category);
CREATE INDEX IF NOT EXISTS idx_expense_status ON expense_event(status);

-- Loss events
CREATE TABLE IF NOT EXISTS loss_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    harvest_id UUID REFERENCES harvest_event(id),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    loss_date DATE NOT NULL,
    loss_type VARCHAR(100) NOT NULL, -- pest, disease, weather, flood, drought, theft, spoilage, transport, market, other
    quantity NUMERIC(12,4),
    unit VARCHAR(50),
    estimated_value NUMERIC(15,2),
    cause TEXT,
    impact_description TEXT,
    mitigation TEXT,
    severity VARCHAR(50), -- low, medium, high, critical
    -- Evidence
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    -- Workflow
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    -- Source lineage
    schema_version VARCHAR(20),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_loss_crop_cycle ON loss_event(crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_loss_location ON loss_event(location_id);
CREATE INDEX IF NOT EXISTS idx_loss_date ON loss_event(loss_date);
CREATE INDEX IF NOT EXISTS idx_loss_type ON loss_event(loss_type);

-- Labor events
CREATE TABLE IF NOT EXISTS labor_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    staff_id UUID REFERENCES staff(id),
    worker_name VARCHAR(255),
    work_date DATE NOT NULL,
    hours_worked NUMERIC(8,2) NOT NULL,
    hourly_rate NUMERIC(10,2),
    total_cost NUMERIC(12,2),
    role VARCHAR(100), -- planter, weeder, harvester, supervisor, driver, other
    activity_description TEXT,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

-- Field notes
CREATE TABLE IF NOT EXISTS field_note (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    plot_id UUID REFERENCES plot(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    note_date DATE NOT NULL,
    note_type VARCHAR(100), -- observation, issue, recommendation, weather, pest, general
    title VARCHAR(255),
    content TEXT,
    images TEXT[],
    tags TEXT[],
    -- Workflow
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);
