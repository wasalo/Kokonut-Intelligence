-- ============================================================
-- 050_remaining_gaps.sql — Leaf litter, livestock, decomposition, predation, token rewards, reward calibration
-- ============================================================

-- Predation rate extension for pest_observation
ALTER TABLE pest_observation ADD COLUMN IF NOT EXISTS predation_count INTEGER;
ALTER TABLE pest_observation ADD COLUMN IF NOT EXISTS predation_rate_per_day NUMERIC(8,4);

-- Leaf litter measurement: daily litter trap collection data
CREATE TABLE IF NOT EXISTS leaf_litter_measurement (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    crop_cycle_id UUID REFERENCES crop_cycle(id) ON DELETE SET NULL,
    measurement_date DATE NOT NULL,
    litter_trap_id VARCHAR(100),
    collection_method VARCHAR(100),
    fresh_weight_g NUMERIC(10,3),
    dry_weight_g NUMERIC(10,3),
    area_m2 NUMERIC(8,2),
    litter_rate_kg_per_day NUMERIC(8,4),
    species_source VARCHAR(255),
    decomposition_stage VARCHAR(50),
    temperature_c NUMERIC(5,2),
    moisture_pct NUMERIC(5,2),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'remaining-gaps-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_leaf_litter_location ON leaf_litter_measurement(location_id);
CREATE INDEX IF NOT EXISTS idx_leaf_litter_plot ON leaf_litter_measurement(plot_id);
CREATE INDEX IF NOT EXISTS idx_leaf_litter_zone ON leaf_litter_measurement(zone_id);
CREATE INDEX IF NOT EXISTS idx_leaf_litter_date ON leaf_litter_measurement(measurement_date);
CREATE INDEX IF NOT EXISTS idx_leaf_litter_status ON leaf_litter_measurement(status);

ALTER TABLE leaf_litter_measurement DROP CONSTRAINT IF EXISTS chk_leaf_litter_decomposition;
ALTER TABLE leaf_litter_measurement ADD CONSTRAINT chk_leaf_litter_decomposition CHECK (
    decomposition_stage IS NULL OR decomposition_stage IN (
        'fresh', 'partially_decomposed', 'well_decomposed', 'fragmented', 'humus'
    )
);

ALTER TABLE leaf_litter_measurement DROP CONSTRAINT IF EXISTS chk_leaf_litter_status;
ALTER TABLE leaf_litter_measurement ADD CONSTRAINT chk_leaf_litter_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Livestock group: registry of animal groups on the farm
CREATE TABLE IF NOT EXISTS livestock_group (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    group_name VARCHAR(255) NOT NULL,
    species VARCHAR(100) NOT NULL,
    breed VARCHAR(100),
    animal_count INTEGER NOT NULL,
    average_weight_kg NUMERIC(8,2),
    feed_type VARCHAR(100),
    enclosure_type VARCHAR(100),
    start_date DATE,
    end_date DATE,
    status VARCHAR(50) DEFAULT 'active',
    notes TEXT,
    schema_version VARCHAR(50) DEFAULT 'remaining-gaps-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_livestock_location ON livestock_group(location_id);
CREATE INDEX IF NOT EXISTS idx_livestock_zone ON livestock_group(zone_id);
CREATE INDEX IF NOT EXISTS idx_livestock_species ON livestock_group(species);
CREATE INDEX IF NOT EXISTS idx_livestock_status ON livestock_group(status);

ALTER TABLE livestock_group DROP CONSTRAINT IF EXISTS chk_livestock_status;
ALTER TABLE livestock_group ADD CONSTRAINT chk_livestock_status CHECK (status IN (
    'active', 'inactive', 'sold', 'deceased', 'transferred'
));

-- Feed intake record: daily feed consumption per livestock group
CREATE TABLE IF NOT EXISTS feed_intake_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    livestock_group_id UUID NOT NULL REFERENCES livestock_group(id) ON DELETE CASCADE,
    record_date DATE NOT NULL,
    feed_type VARCHAR(100) NOT NULL,
    feed_name VARCHAR(255),
    quantity_kg NUMERIC(10,3) NOT NULL,
    per_animal_kg NUMERIC(8,4),
    method VARCHAR(100),
    weather_conditions JSONB,
    temperature_c NUMERIC(5,2),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'remaining-gaps-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_feed_intake_location ON feed_intake_record(location_id);
CREATE INDEX IF NOT EXISTS idx_feed_intake_livestock ON feed_intake_record(livestock_group_id);
CREATE INDEX IF NOT EXISTS idx_feed_intake_date ON feed_intake_record(record_date);
CREATE INDEX IF NOT EXISTS idx_feed_intake_type ON feed_intake_record(feed_type);
CREATE INDEX IF NOT EXISTS idx_feed_intake_status ON feed_intake_record(status);

ALTER TABLE feed_intake_record DROP CONSTRAINT IF EXISTS chk_feed_intake_status;
ALTER TABLE feed_intake_record ADD CONSTRAINT chk_feed_intake_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Decomposition measurement: litter bag mass loss studies
CREATE TABLE IF NOT EXISTS decomposition_measurement (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    plot_id UUID REFERENCES plot(id) ON DELETE SET NULL,
    zone_id UUID REFERENCES farm_zone(id) ON DELETE SET NULL,
    litter_type VARCHAR(100) NOT NULL,
    species_source VARCHAR(255),
    initial_dry_weight_g NUMERIC(10,3) NOT NULL,
    final_dry_weight_g NUMERIC(10,3),
    deployment_date DATE NOT NULL,
    retrieval_date DATE,
    deployment_days INTEGER GENERATED ALWAYS AS (
        CASE WHEN retrieval_date IS NOT NULL
        THEN retrieval_date - deployment_date
        ELSE NULL END
    ) STORED,
    decomposition_rate_kg_per_day NUMERIC(8,4) GENERATED ALWAYS AS (
        CASE WHEN final_dry_weight_g IS NOT NULL AND retrieval_date IS NOT NULL
             AND (retrieval_date - deployment_date) > 0
        THEN ((initial_dry_weight_g - final_dry_weight_g) / 1000.0)
             / (retrieval_date - deployment_date)
        ELSE NULL END
    ) STORED,
    mass_loss_pct NUMERIC(5,2) GENERATED ALWAYS AS (
        CASE WHEN final_dry_weight_g IS NOT NULL AND initial_dry_weight_g > 0
        THEN ((initial_dry_weight_g - final_dry_weight_g) / initial_dry_weight_g) * 100
        ELSE NULL END
    ) STORED,
    mesh_size_mm NUMERIC(5,1),
    depth_cm NUMERIC(6,2),
    temperature_c NUMERIC(5,2),
    moisture_pct NUMERIC(5,2),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'remaining-gaps-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_decomp_location ON decomposition_measurement(location_id);
CREATE INDEX IF NOT EXISTS idx_decomp_plot ON decomposition_measurement(plot_id);
CREATE INDEX IF NOT EXISTS idx_decomp_zone ON decomposition_measurement(zone_id);
CREATE INDEX IF NOT EXISTS idx_decomp_type ON decomposition_measurement(litter_type);
CREATE INDEX IF NOT EXISTS idx_decomp_deployment ON decomposition_measurement(deployment_date);
CREATE INDEX IF NOT EXISTS idx_decomp_status ON decomposition_measurement(status);

ALTER TABLE decomposition_measurement DROP CONSTRAINT IF EXISTS chk_decomp_status;
ALTER TABLE decomposition_measurement ADD CONSTRAINT chk_decomp_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Token reward distribution: on-chain and off-chain reward tracking
CREATE TABLE IF NOT EXISTS token_reward_distribution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    recipient_address VARCHAR(42),
    recipient_name VARCHAR(255),
    reward_type VARCHAR(100) NOT NULL,
    token_type VARCHAR(50) NOT NULL,
    token_amount NUMERIC(18,8) NOT NULL,
    usd_value NUMERIC(15,2),
    distribution_date DATE NOT NULL,
    epoch VARCHAR(100),
    source_event_type VARCHAR(100),
    source_event_id UUID,
    linked_metric_key VARCHAR(100),
    linked_metric_value NUMERIC(15,4),
    is_onchain BOOLEAN DEFAULT FALSE,
    tx_hash VARCHAR(66),
    chain VARCHAR(50),
    distribution_method VARCHAR(100),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'remaining-gaps-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_token_reward_location ON token_reward_distribution(location_id);
CREATE INDEX IF NOT EXISTS idx_token_reward_recipient ON token_reward_distribution(recipient_address);
CREATE INDEX IF NOT EXISTS idx_token_reward_type ON token_reward_distribution(reward_type);
CREATE INDEX IF NOT EXISTS idx_token_reward_date ON token_reward_distribution(distribution_date);
CREATE INDEX IF NOT EXISTS idx_token_reward_epoch ON token_reward_distribution(epoch);
CREATE INDEX IF NOT EXISTS idx_token_reward_metric ON token_reward_distribution(linked_metric_key);
CREATE INDEX IF NOT EXISTS idx_token_reward_status ON token_reward_distribution(status);

ALTER TABLE token_reward_distribution DROP CONSTRAINT IF EXISTS chk_token_reward_type;
ALTER TABLE token_reward_distribution ADD CONSTRAINT chk_token_reward_type CHECK (reward_type IN (
    'labor', 'training', 'ecological_contribution', 'governance_participation',
    'data_reporting', 'community_support', 'other'
));

ALTER TABLE token_reward_distribution DROP CONSTRAINT IF EXISTS chk_token_reward_distribution_status;
ALTER TABLE token_reward_distribution ADD CONSTRAINT chk_token_reward_distribution_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- Reward calibration model: maps real-world outputs to token emission rates
CREATE TABLE IF NOT EXISTS reward_calibration_model (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    model_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(100) NOT NULL,
    run_date DATE NOT NULL,
    input_metrics JSONB NOT NULL DEFAULT '{}',
    output_weights JSONB NOT NULL DEFAULT '{}',
    calibration_score NUMERIC(6,4),
    total_tokens_distributed NUMERIC(18,8),
    token_per_unit_output NUMERIC(18,8),
    epoch VARCHAR(100),
    confidence_level NUMERIC(5,2) CHECK (confidence_level >= 0 AND confidence_level <= 100),
    calculation_version VARCHAR(50),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(50) DEFAULT 'remaining-gaps-v1',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_reward_cal_location ON reward_calibration_model(location_id);
CREATE INDEX IF NOT EXISTS idx_reward_cal_type ON reward_calibration_model(model_type);
CREATE INDEX IF NOT EXISTS idx_reward_cal_date ON reward_calibration_model(run_date);
CREATE INDEX IF NOT EXISTS idx_reward_cal_status ON reward_calibration_model(status);

ALTER TABLE reward_calibration_model DROP CONSTRAINT IF EXISTS chk_reward_cal_type;
ALTER TABLE reward_calibration_model ADD CONSTRAINT chk_reward_cal_type CHECK (model_type IN (
    'linear_weighted', 'threshold_based', 'proportional', 'custom'
));

ALTER TABLE reward_calibration_model DROP CONSTRAINT IF EXISTS chk_reward_cal_status;
ALTER TABLE reward_calibration_model ADD CONSTRAINT chk_reward_cal_status CHECK (status IN (
    'draft', 'submitted', 'verified', 'published', 'rejected'
));

-- ============================================================
-- Public-safe views
-- ============================================================

CREATE OR REPLACE VIEW v_public_leaf_litter_measurements AS
SELECT
    llm.id,
    llm.location_id,
    l.name AS location_name,
    llm.plot_id,
    p.name AS plot_name,
    llm.measurement_date,
    llm.litter_trap_id,
    llm.collection_method,
    llm.fresh_weight_g,
    llm.dry_weight_g,
    llm.area_m2,
    llm.litter_rate_kg_per_day,
    llm.species_source,
    llm.decomposition_stage,
    llm.temperature_c,
    llm.moisture_pct,
    llm.notes,
    llm.status
FROM leaf_litter_measurement llm
JOIN location l ON l.id = llm.location_id
LEFT JOIN plot p ON p.id = llm.plot_id
WHERE l.status = 'active'
  AND llm.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_livestock_feed_intake AS
SELECT
    fir.id,
    fir.location_id,
    l.name AS location_name,
    fir.livestock_group_id,
    lg.group_name,
    lg.species AS livestock_species,
    lg.breed AS livestock_breed,
    lg.animal_count,
    fir.record_date,
    fir.feed_type,
    fir.feed_name,
    fir.quantity_kg,
    fir.per_animal_kg,
    fir.method,
    fir.temperature_c,
    fir.notes,
    fir.status
FROM feed_intake_record fir
JOIN location l ON l.id = fir.location_id
JOIN livestock_group lg ON lg.id = fir.livestock_group_id
WHERE l.status = 'active'
  AND fir.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_decomposition_measurements AS
SELECT
    dm.id,
    dm.location_id,
    l.name AS location_name,
    dm.plot_id,
    p.name AS plot_name,
    dm.litter_type,
    dm.species_source,
    dm.initial_dry_weight_g,
    dm.final_dry_weight_g,
    dm.deployment_date,
    dm.retrieval_date,
    dm.deployment_days,
    dm.decomposition_rate_kg_per_day,
    dm.mass_loss_pct,
    dm.mesh_size_mm,
    dm.depth_cm,
    dm.temperature_c,
    dm.moisture_pct,
    dm.notes,
    dm.status
FROM decomposition_measurement dm
JOIN location l ON l.id = dm.location_id
LEFT JOIN plot p ON p.id = dm.plot_id
WHERE l.status = 'active'
  AND dm.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_token_reward_distribution AS
SELECT
    trd.id,
    trd.location_id,
    l.name AS location_name,
    trd.recipient_name,
    trd.reward_type,
    trd.token_type,
    trd.token_amount,
    trd.usd_value,
    trd.distribution_date,
    trd.epoch,
    trd.linked_metric_key,
    trd.linked_metric_value,
    trd.is_onchain,
    trd.distribution_method,
    trd.notes,
    trd.status
FROM token_reward_distribution trd
JOIN location l ON l.id = trd.location_id
WHERE l.status = 'active'
  AND trd.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_reward_calibration AS
SELECT
    rcm.id,
    rcm.location_id,
    l.name AS location_name,
    rcm.model_name,
    rcm.model_type,
    rcm.run_date,
    rcm.input_metrics,
    rcm.output_weights,
    rcm.calibration_score,
    rcm.total_tokens_distributed,
    rcm.token_per_unit_output,
    rcm.epoch,
    rcm.confidence_level,
    rcm.notes,
    rcm.status
FROM reward_calibration_model rcm
JOIN location l ON l.id = rcm.location_id
WHERE l.status = 'active'
  AND rcm.status IN ('verified', 'published')
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = l.id AND fr.status IN ('verified', 'published')
  );

INSERT INTO schema_version (version, description, applied_by)
VALUES ('remaining-gaps-v1', 'Leaf litter measurement, livestock/feed, decomposition, predation rate, token rewards, reward calibration', 'schema bootstrap')
ON CONFLICT (version) DO NOTHING;
