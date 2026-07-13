-- ============================================================
-- 142_marketplace.sql — Digital Marketplace
-- Produce listings, buyer profiles, market orders, logistics
-- tracking, price alerts, and price observation extensions.
-- ============================================================

-- ------------------------------------------------------------
-- 1. market_listing — Produce listings with crop, quantity,
--    quality grade, price, and location
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_listing (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    seller_id UUID,
    crop_id UUID NOT NULL REFERENCES crop(id) ON DELETE RESTRICT,
    harvest_id UUID REFERENCES harvest_event(id),

    -- Listing details
    title VARCHAR(255) NOT NULL,
    description TEXT,
    quantity NUMERIC(12,4) NOT NULL,
    unit VARCHAR(50) NOT NULL DEFAULT 'kg',
    quality_grade VARCHAR(50) DEFAULT 'standard',
    price_per_unit NUMERIC(12,4) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    negotiable BOOLEAN DEFAULT FALSE,
    min_order_qty NUMERIC(12,4),
    max_order_qty NUMERIC(12,4),

    -- Location / logistics
    pickup_location VARCHAR(255),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    delivery_available BOOLEAN DEFAULT FALSE,
    delivery_radius_km NUMERIC(8,2),

    -- Availability window
    available_from DATE,
    available_until DATE,

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'draft',
    published_at TIMESTAMPTZ,
    sold_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    -- Evidence
    image_urls TEXT[],
    evidence_urls TEXT[],

    -- Audit
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_ml_location ON market_listing(location_id);
CREATE INDEX IF NOT EXISTS idx_ml_crop ON market_listing(crop_id);
CREATE INDEX IF NOT EXISTS idx_ml_status ON market_listing(status);
CREATE INDEX IF NOT EXISTS idx_ml_seller ON market_listing(seller_id);
CREATE INDEX IF NOT EXISTS idx_ml_available ON market_listing(available_from, available_until);
CREATE INDEX IF NOT EXISTS idx_ml_price ON market_listing(price_per_unit);

-- ------------------------------------------------------------
-- 2. buyer_profile — Buyer registrations (aggregators,
--    processors, exporters, retailers)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS buyer_profile (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    buyer_type VARCHAR(100) NOT NULL,
    contact_name VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    website TEXT,

    -- Business details
    registration_number VARCHAR(100),
    tax_id VARCHAR(100),
    business_license TEXT,
    years_active INTEGER,

    -- Location
    address TEXT,
    city VARCHAR(100),
    region VARCHAR(100),
    country VARCHAR(100),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),

    -- Preferences
    crops_of_interest TEXT[],
    min_order_qty NUMERIC(12,4),
    preferred_unit VARCHAR(50),
    preferred_currency VARCHAR(10) DEFAULT 'USD',
    payment_terms VARCHAR(100),
    delivery_preference VARCHAR(50) DEFAULT 'pickup',

    -- Capacity
    monthly_capacity NUMERIC(12,4),
    capacity_unit VARCHAR(50),
    storage_available BOOLEAN DEFAULT FALSE,
    cold_chain BOOLEAN DEFAULT FALSE,

    -- Trust
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    rating NUMERIC(3,2),
    total_orders INTEGER DEFAULT 0,

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'pending',
    approved_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Audit
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_bp_type ON buyer_profile(buyer_type);
CREATE INDEX IF NOT EXISTS idx_bp_status ON buyer_profile(status);
CREATE INDEX IF NOT EXISTS idx_bp_country ON buyer_profile(country);
CREATE INDEX IF NOT EXISTS idx_bp_verified ON buyer_profile(verified);
CREATE INDEX IF NOT EXISTS idx_bp_crops ON buyer_profile USING GIN(crops_of_interest);

-- ------------------------------------------------------------
-- 3. Extend existing price_observation with marketplace fields
--    (table created in 010_market_data.sql)
-- ------------------------------------------------------------

ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS market_id UUID;
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS location_id UUID REFERENCES location(id);
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS buyer_type VARCHAR(100);
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS quality_grade VARCHAR(50);
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS quantity_traded NUMERIC(12,4);
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS unit VARCHAR(50);
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS bid_price NUMERIC(12,4);
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS ask_price NUMERIC(12,4);
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE;
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS verified_by UUID;
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_price_obs_market ON price_observation(market_id);
CREATE INDEX IF NOT EXISTS idx_price_obs_location ON price_observation(location_id);
CREATE INDEX IF NOT EXISTS idx_price_obs_quality ON price_observation(quality_grade);

-- ------------------------------------------------------------
-- 4. market_order — Buy/sell orders linking buyers to listings
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_order (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    listing_id UUID NOT NULL REFERENCES market_listing(id) ON DELETE RESTRICT,
    buyer_id UUID NOT NULL REFERENCES buyer_profile(id) ON DELETE RESTRICT,
    seller_id UUID,
    location_id UUID REFERENCES location(id),

    -- Order details
    quantity NUMERIC(12,4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    price_per_unit NUMERIC(12,4) NOT NULL,
    total_amount NUMERIC(15,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',

    -- Delivery
    delivery_method VARCHAR(50) DEFAULT 'pickup',
    delivery_address TEXT,
    requested_delivery_date DATE,
    confirmed_delivery_date DATE,

    -- Payment
    payment_method VARCHAR(100),
    payment_status VARCHAR(50) DEFAULT 'pending',
    payment_reference VARCHAR(255),
    payment_due_date DATE,
    payment_received_at TIMESTAMPTZ,

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'draft',
    confirmed_at TIMESTAMPTZ,
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,

    -- Dispute
    dispute_status VARCHAR(50),
    dispute_reason TEXT,
    dispute_resolved_at TIMESTAMPTZ,

    -- Audit
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_mo_listing ON market_order(listing_id);
CREATE INDEX IF NOT EXISTS idx_mo_buyer ON market_order(buyer_id);
CREATE INDEX IF NOT EXISTS idx_mo_seller ON market_order(seller_id);
CREATE INDEX IF NOT EXISTS idx_mo_status ON market_order(status);
CREATE INDEX IF NOT EXISTS idx_mo_payment ON market_order(payment_status);
CREATE INDEX IF NOT EXISTS idx_mo_delivery ON market_order(requested_delivery_date);
CREATE INDEX IF NOT EXISTS idx_mo_created ON market_order(created_at);

-- ------------------------------------------------------------
-- 5. logistics_tracking — Shipment tracking for fulfilled orders
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS logistics_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES market_order(id) ON DELETE RESTRICT,

    -- Carrier
    carrier_name VARCHAR(255),
    carrier_contact VARCHAR(255),
    vehicle_type VARCHAR(100),
    vehicle_plate VARCHAR(50),
    driver_name VARCHAR(255),
    driver_phone VARCHAR(50),

    -- Shipment
    tracking_number VARCHAR(255),
    shipment_date TIMESTAMPTZ,
    estimated_arrival TIMESTAMPTZ,
    actual_arrival TIMESTAMPTZ,
    origin_address TEXT,
    destination_address TEXT,
    origin_lat NUMERIC(10,7),
    origin_lng NUMERIC(10,7),
    dest_lat NUMERIC(10,7),
    dest_lng NUMERIC(10,7),

    -- Condition
    temperature_min NUMERIC(5,2),
    temperature_max NUMERIC(5,2),
    humidity_min NUMERIC(5,2),
    humidity_max NUMERIC(5,2),
    condition_notes TEXT,

    -- Status
    status VARCHAR(50) DEFAULT 'pending',
    current_location VARCHAR(255),
    current_lat NUMERIC(10,7),
    current_lng NUMERIC(10,7),
    last_update_at TIMESTAMPTZ,

    -- Proof of delivery
    pod_name VARCHAR(255),
    pod_signature_url TEXT,
    pod_photo_urls TEXT[],
    delivered_at TIMESTAMPTZ,

    -- Audit
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lt_order ON logistics_tracking(order_id);
CREATE INDEX IF NOT EXISTS idx_lt_status ON logistics_tracking(status);
CREATE INDEX IF NOT EXISTS idx_lt_tracking ON logistics_tracking(tracking_number);
CREATE INDEX IF NOT EXISTS idx_lt_carrier ON logistics_tracking(carrier_name);

-- ------------------------------------------------------------
-- 6. market_alert — Price alerts and market notifications
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_alert (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id),
    buyer_id UUID REFERENCES buyer_profile(id),
    listing_id UUID REFERENCES market_listing(id),
    order_id UUID REFERENCES market_order(id),

    -- Alert details
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) DEFAULT 'info',
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,

    -- Trigger conditions
    crop_id UUID REFERENCES crop(id),
    trigger_metric VARCHAR(100),
    trigger_condition VARCHAR(50),
    trigger_threshold NUMERIC(12,4),
    current_value NUMERIC(12,4),

    -- Delivery
    channel VARCHAR(50) DEFAULT 'in_app',
    delivered BOOLEAN DEFAULT FALSE,
    delivered_at TIMESTAMPTZ,
    read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    actioned BOOLEAN DEFAULT FALSE,
    actioned_at TIMESTAMPTZ,
    action_url TEXT,

    -- Lifecycle
    status VARCHAR(50) DEFAULT 'active',
    expires_at TIMESTAMPTZ,

    -- Audit
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ma_type ON market_alert(alert_type);
CREATE INDEX IF NOT EXISTS idx_ma_severity ON market_alert(severity);
CREATE INDEX IF NOT EXISTS idx_ma_location ON market_alert(location_id);
CREATE INDEX IF NOT EXISTS idx_ma_buyer ON market_alert(buyer_id);
CREATE INDEX IF NOT EXISTS idx_ma_crop ON market_alert(crop_id);
CREATE INDEX IF NOT EXISTS idx_ma_status ON market_alert(status);
CREATE INDEX IF NOT EXISTS idx_ma_delivered ON market_alert(delivered, read);
CREATE INDEX IF NOT EXISTS idx_ma_created ON market_alert(created_at);

-- ============================================================
-- Views
-- ============================================================

-- Active listings with seller info
CREATE OR REPLACE VIEW v_active_listings AS
SELECT
    ml.id,
    ml.title,
    ml.description,
    ml.location_id,
    ml.seller_id,
    ml.crop_id,
    c.name AS crop_name,
    ml.quantity,
    ml.unit,
    ml.quality_grade,
    ml.price_per_unit,
    ml.currency,
    ml.negotiable,
    ml.pickup_location,
    ml.latitude,
    ml.longitude,
    ml.delivery_available,
    ml.available_from,
    ml.available_until,
    ml.image_urls,
    ml.created_at,
    ml.published_at,
    l.name AS location_name
FROM market_listing ml
LEFT JOIN crop c ON c.id = ml.crop_id
LEFT JOIN location l ON l.id = ml.location_id
WHERE ml.status = 'active'
  AND (ml.available_until IS NULL OR ml.available_until >= CURRENT_DATE)
ORDER BY ml.created_at DESC;

-- Price history by crop and market
CREATE OR REPLACE VIEW v_price_trends AS
SELECT
    po.id,
    po.crop_id,
    c.name AS crop_name,
    po.commodity_code,
    po.market_name,
    po.price_date,
    po.price_per_unit,
    po.bid_price,
    po.ask_price,
    po.unit,
    po.currency,
    po.quality_grade,
    po.quantity_traded,
    po.source,
    po.location_id,
    l.name AS location_name,
    po.created_at
FROM price_observation po
LEFT JOIN crop c ON c.id = po.crop_id
LEFT JOIN location l ON l.id = po.location_id
ORDER BY po.price_date DESC, po.crop_id;

-- Orders with current fulfillment status
CREATE OR REPLACE VIEW v_order_status AS
SELECT
    mo.id AS order_id,
    mo.listing_id,
    ml.title AS listing_title,
    mo.buyer_id,
    bp.name AS buyer_name,
    bp.buyer_type,
    mo.seller_id,
    mo.quantity,
    mo.unit,
    mo.price_per_unit,
    mo.total_amount,
    mo.currency,
    mo.status AS order_status,
    mo.payment_status,
    mo.delivery_method,
    mo.requested_delivery_date,
    mo.confirmed_delivery_date,
    lt.status AS logistics_status,
    lt.tracking_number,
    lt.carrier_name,
    lt.estimated_arrival,
    lt.actual_arrival,
    mo.created_at AS order_created_at,
    mo.completed_at,
    l.name AS location_name
FROM market_order mo
LEFT JOIN market_listing ml ON ml.id = mo.listing_id
LEFT JOIN buyer_profile bp ON bp.id = mo.buyer_id
LEFT JOIN logistics_tracking lt ON lt.order_id = mo.id
LEFT JOIN location l ON l.id = mo.location_id
ORDER BY mo.created_at DESC;

-- ============================================================
-- Seed Data — Commodity categories and unit types
-- Uses a reference_data approach consistent with other schemas
-- ============================================================

CREATE TABLE IF NOT EXISTS market_reference_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(50) NOT NULL,
    code VARCHAR(50) NOT NULL,
    label VARCHAR(255) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(category, code)
);

INSERT INTO market_reference_data (category, code, label, description, sort_order) VALUES
    -- Commodity categories
    ('commodity_category', 'cereals', 'Cereals & Grains', 'Maize, rice, wheat, sorghum, millet', 1),
    ('commodity_category', 'legumes', 'Legumes & Pulses', 'Beans, lentils, groundnuts, cowpeas', 2),
    ('commodity_category', 'tubers', 'Tubers & Roots', 'Cassava, sweet potato, yam, potato', 3),
    ('commodity_category', 'vegetables', 'Vegetables', 'Tomato, onion, cabbage, leafy greens', 4),
    ('commodity_category', 'fruits', 'Fruits', 'Avocado, banana, mango, citrus, papaya', 5),
    ('commodity_category', 'oilseeds', 'Oilseeds & Nuts', 'Sunflower, sesame, coconut, palm', 6),
    ('commodity_category', 'spices', 'Spices & Herbs', 'Chilli, turmeric, ginger, coriander', 7),
    ('commodity_category', 'beverages', 'Beverage Crops', 'Coffee, cocoa, tea', 8),
    ('commodity_category', 'fibres', 'Fibres & Textiles', 'Cotton, sisal, hemp', 9),
    ('commodity_category', 'livestock', 'Livestock Products', 'Meat, dairy, eggs, honey', 10),
    ('commodity_category', 'aquaculture', 'Aquaculture', 'Fish, shrimp, seaweed', 11),
    ('commodity_category', 'inputs', 'Farm Inputs', 'Seeds, fertilizers, bio-inputs', 12),

    -- Unit types
    ('unit_type', 'kg', 'Kilogram', 'Standard metric kilogram', 1),
    ('unit_type', 'bag_50kg', 'Bag (50 kg)', 'Standard 50 kg bag', 2),
    ('unit_type', 'bag_100kg', 'Bag (100 kg)', 'Large 100 kg bag', 3),
    ('unit_type', 'ton', 'Metric Ton', '1000 kilograms', 4),
    ('unit_type', 'crate', 'Crate', 'Standard produce crate', 5),
    ('unit_type', 'bunch', 'Bunch', 'Bunch of bananas or similar', 6),
    ('unit_type', 'dozen', 'Dozen', '12 units', 7),
    ('unit_type', 'litre', 'Litre', 'Standard metric litre', 8),
    ('unit_type', 'gallon', 'Gallon', 'US or Imperial gallon', 9),
    ('unit_type', 'piece', 'Piece', 'Individual unit', 10),
    ('unit_type', 'bundle', 'Bundle', 'Tied bundle of produce', 11),
    ('unit_type', 'sack', 'Sack', 'Woven sack (varies by crop)', 12),

    -- Quality grades
    ('quality_grade', 'premium', 'Premium', 'Top quality, export grade', 1),
    ('quality_grade', 'grade_a', 'Grade A', 'High quality, commercial grade', 2),
    ('quality_grade', 'grade_b', 'Grade B', 'Standard quality, local market', 3),
    ('quality_grade', 'grade_c', 'Grade C', 'Below standard, processing use', 4),
    ('quality_grade', 'rejected', 'Rejected', 'Does not meet minimum standards', 5),

    -- Buyer types
    ('buyer_type', 'aggregator', 'Aggregator', 'Collects from multiple farmers', 1),
    ('buyer_type', 'processor', 'Processor', 'Value addition / manufacturing', 2),
    ('buyer_type', 'exporter', 'Exporter', 'International trade', 3),
    ('buyer_type', 'retailer', 'Retailer', 'Direct to consumer sales', 4),
    ('buyer_type', 'wholesaler', 'Wholesaler', 'Bulk distribution', 5),
    ('buyer_type', 'restaurant', 'Restaurant / Hotel', 'Hospitality sector', 6),
    ('buyer_type', 'cooperative', 'Cooperative', 'Farmer cooperative / union', 7),
    ('buyer_type', 'institutional', 'Institutional', 'Schools, hospitals, government', 8),

    -- Order statuses
    ('order_status', 'draft', 'Draft', 'Order created but not submitted', 1),
    ('order_status', 'pending', 'Pending', 'Awaiting seller confirmation', 2),
    ('order_status', 'confirmed', 'Confirmed', 'Seller accepted the order', 3),
    ('order_status', 'shipped', 'Shipped', 'In transit to buyer', 4),
    ('order_status', 'delivered', 'Delivered', 'Received by buyer', 5),
    ('order_status', 'completed', 'Completed', 'Payment settled, order closed', 6),
    ('order_status', 'cancelled', 'Cancelled', 'Order cancelled by either party', 7),
    ('order_status', 'disputed', 'Disputed', 'Under dispute resolution', 8),

    -- Alert types
    ('alert_type', 'price_drop', 'Price Drop', 'Crop price fell below threshold', 1),
    ('alert_type', 'price_spike', 'Price Spike', 'Crop price rose above threshold', 2),
    ('alert_type', 'new_buyer', 'New Buyer', 'New buyer registered for your crops', 3),
    ('alert_type', 'order_received', 'Order Received', 'New order placed on your listing', 4),
    ('alert_type', 'order_shipped', 'Order Shipped', 'Order has been dispatched', 5),
    ('alert_type', 'order_delivered', 'Order Delivered', 'Order delivered successfully', 6),
    ('alert_type', 'payment_received', 'Payment Received', 'Payment confirmed', 7),
    ('alert_type', 'listing_expiring', 'Listing Expiring', 'Listing expires within 48 hours', 8),
    ('alert_type', 'market_trend', 'Market Trend', 'Significant market trend detected', 9),
    ('alert_type', 'seasonal_reminder', 'Seasonal Reminder', 'Planting/harvest season reminder', 10),

    -- Logistics statuses
    ('logistics_status', 'pending', 'Pending', 'Shipment not yet dispatched', 1),
    ('logistics_status', 'picked_up', 'Picked Up', 'Goods collected from seller', 2),
    ('logistics_status', 'in_transit', 'In Transit', 'Currently being transported', 3),
    ('logistics_status', 'arrived', 'Arrived', 'Reached destination', 4),
    ('logistics_status', 'delivered', 'Delivered', 'Handed over to buyer', 5),
    ('logistics_status', 'delayed', 'Delayed', 'Behind schedule', 6),
    ('logistics_status', 'returned', 'Returned', 'Returned to seller', 7)

ON CONFLICT (category, code) DO UPDATE SET
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order,
    active = EXCLUDED.active;

CREATE INDEX IF NOT EXISTS idx_mrd_category ON market_reference_data(category);
CREATE INDEX IF NOT EXISTS idx_mrd_active ON market_reference_data(active);
