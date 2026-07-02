-- ============================================================
-- 043_bio_factory_operations.sql — Bio-organic fertilizer operations hub for Latin America and the Caribbean
-- ============================================================
-- Tables:
--   1. bio_factory_batch          — Production batch records (type, method, inputs, outputs, conditions)
--   2. bio_input_provenance       — Ingredient sourcing with quality_warnings (e.g. sargassum arsenic)
--   3. bio_recipe_library         — Recipe knowledge base (ingredients, ratios, process steps, warnings)
--   4. bio_factory_distribution   — Distribution tracking (recipient type, quantity, region)
--   5. bio_factory_quality_test   — Quality test results (NPK, pH, microbial count, pass/fail)
--   6. bio_ingredient_composition_reference — Composition matrix (typical NPK ranges per ingredient)
--   7. bio_regional_input_availability       — LAC regional inputs (sargassum, coffee pulp, etc.)
-- Public views: v_public_bio_factory_batch_summary, v_public_bio_input_provenance_summary,
--   v_public_bio_recipe_library_summary, v_public_bio_factory_quality_test_summary,
--   v_public_bio_regional_input_summary
-- ============================================================

CREATE TABLE IF NOT EXISTS bio_factory_batch (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    batch_name VARCHAR(255) NOT NULL,
    batch_type VARCHAR(100) NOT NULL,
    production_method VARCHAR(100) NOT NULL,
    production_start_date DATE NOT NULL,
    production_end_date DATE,
    input_kg_total NUMERIC(12,2),
    output_kg_total NUMERIC(12,2),
    output_liters_total NUMERIC(12,2),
    batch_yield_pct NUMERIC(10,4),
    moisture_pct NUMERIC(5,2),
    temperature_c NUMERIC(5,2),
    ph_level NUMERIC(4,2),
    microbial_strain VARCHAR(100),
    batch_summary TEXT NOT NULL,
    public_summary TEXT,
    limitations TEXT[] DEFAULT '{}',
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_bio_batch_location ON bio_factory_batch(location_id);
CREATE INDEX IF NOT EXISTS idx_bio_batch_type ON bio_factory_batch(batch_type);
CREATE INDEX IF NOT EXISTS idx_bio_batch_status ON bio_factory_batch(status);

ALTER TABLE bio_factory_batch DROP CONSTRAINT IF EXISTS chk_bio_batch_status;
ALTER TABLE bio_factory_batch ADD CONSTRAINT chk_bio_batch_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE bio_factory_batch DROP CONSTRAINT IF EXISTS chk_bio_batch_type;
ALTER TABLE bio_factory_batch ADD CONSTRAINT chk_bio_batch_type CHECK (batch_type IN (
    'compost', 'vermicompost', 'bokashi', 'biochar',
    'compost_tea', 'manure_tea', 'fish_emulsion', 'seaweed_extract',
    'liquid_biofertilizer', 'microbial_biofertilizer',
    'bone_meal', 'blood_meal', 'feather_meal', 'neem_cake', 'other'
));

ALTER TABLE bio_factory_batch DROP CONSTRAINT IF EXISTS chk_bio_batch_method;
ALTER TABLE bio_factory_batch ADD CONSTRAINT chk_bio_batch_method CHECK (production_method IN (
    'aerobic', 'anaerobic', 'vermicomposting', 'fermentation', 'extraction',
    'inoculation', 'grinding', 'steeping', 'aerated_brewing', 'other'
));

ALTER TABLE bio_factory_batch DROP CONSTRAINT IF EXISTS chk_bio_batch_strain;
ALTER TABLE bio_factory_batch ADD CONSTRAINT chk_bio_batch_strain CHECK (
    microbial_strain IS NULL OR microbial_strain IN (
        'rhizobium', 'azospirillum', 'azolla', 'pseudomonas',
        'trichoderma', 'bacillus_subtilis', 'lactic_acid_bacteria',
        'mycorrhizal_fungi', 'mixed_culture', 'other'
    )
);

ALTER TABLE bio_factory_batch DROP CONSTRAINT IF EXISTS chk_bio_batch_values;
ALTER TABLE bio_factory_batch ADD CONSTRAINT chk_bio_batch_values CHECK (
    (input_kg_total IS NULL OR input_kg_total >= 0)
    AND (output_kg_total IS NULL OR output_kg_total >= 0)
    AND (output_liters_total IS NULL OR output_liters_total >= 0)
    AND (batch_yield_pct IS NULL OR (batch_yield_pct >= 0 AND batch_yield_pct <= 999999.9999))
    AND (moisture_pct IS NULL OR (moisture_pct >= 0 AND moisture_pct <= 100))
    AND (ph_level IS NULL OR (ph_level >= 0 AND ph_level <= 14))
);

CREATE TABLE IF NOT EXISTS bio_input_provenance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    batch_id UUID REFERENCES bio_factory_batch(id) ON DELETE SET NULL,
    input_name VARCHAR(255) NOT NULL,
    input_category VARCHAR(100) NOT NULL,
    supplier_name VARCHAR(255),
    supplier_verified BOOLEAN DEFAULT FALSE,
    organic_certified BOOLEAN DEFAULT FALSE,
    origin_country VARCHAR(100),
    origin_region VARCHAR(255),
    input_kg NUMERIC(12,2),
    moisture_pct NUMERIC(5,2),
    nutrient_n_pct NUMERIC(5,2),
    nutrient_p_pct NUMERIC(5,2),
    nutrient_k_pct NUMERIC(5,2),
    quality_warnings TEXT[] DEFAULT '{}',
    input_summary TEXT NOT NULL,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_bio_input_location ON bio_input_provenance(location_id);
CREATE INDEX IF NOT EXISTS idx_bio_input_batch ON bio_input_provenance(batch_id);
CREATE INDEX IF NOT EXISTS idx_bio_input_category ON bio_input_provenance(input_category);
CREATE INDEX IF NOT EXISTS idx_bio_input_status ON bio_input_provenance(status);

ALTER TABLE bio_input_provenance DROP CONSTRAINT IF EXISTS chk_bio_input_status;
ALTER TABLE bio_input_provenance ADD CONSTRAINT chk_bio_input_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE bio_input_provenance DROP CONSTRAINT IF EXISTS chk_bio_input_category;
ALTER TABLE bio_input_provenance ADD CONSTRAINT chk_bio_input_category CHECK (input_category IN (
    'plant_residue', 'animal_manure', 'agricultural_byproduct', 'marine_material',
    'microbial_inoculum', 'mineral_amendment', 'water', 'fish_waste', 'other'
));

ALTER TABLE bio_input_provenance DROP CONSTRAINT IF EXISTS chk_bio_input_values;
ALTER TABLE bio_input_provenance ADD CONSTRAINT chk_bio_input_values CHECK (
    (input_kg IS NULL OR input_kg >= 0)
    AND (moisture_pct IS NULL OR (moisture_pct >= 0 AND moisture_pct <= 100))
    AND (nutrient_n_pct IS NULL OR (nutrient_n_pct >= 0 AND nutrient_n_pct <= 100))
    AND (nutrient_p_pct IS NULL OR (nutrient_p_pct >= 0 AND nutrient_p_pct <= 100))
    AND (nutrient_k_pct IS NULL OR (nutrient_k_pct >= 0 AND nutrient_k_pct <= 100))
);

CREATE TABLE IF NOT EXISTS bio_recipe_library (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    recipe_name VARCHAR(255) NOT NULL,
    recipe_type VARCHAR(100) NOT NULL,
    recipe_category VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    ingredients JSONB DEFAULT '[]',
    ratios JSONB DEFAULT '{}',
    process_steps JSONB DEFAULT '[]',
    fermentation_days INTEGER,
    target_c_n_ratio NUMERIC(6,2),
    target_moisture_pct NUMERIC(5,2),
    target_temperature_c NUMERIC(5,2),
    target_ph NUMERIC(4,2),
    dilution_ratio VARCHAR(50),
    application_method VARCHAR(255),
    quality_warnings TEXT[] DEFAULT '{}',
    source_reference TEXT,
    recipe_summary TEXT NOT NULL,
    public_summary TEXT,
    limitations TEXT[] DEFAULT '{}',
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_bio_recipe_type ON bio_recipe_library(recipe_type);
CREATE INDEX IF NOT EXISTS idx_bio_recipe_category ON bio_recipe_library(recipe_category);
CREATE INDEX IF NOT EXISTS idx_bio_recipe_status ON bio_recipe_library(status);

ALTER TABLE bio_recipe_library DROP CONSTRAINT IF EXISTS chk_bio_recipe_status;
ALTER TABLE bio_recipe_library ADD CONSTRAINT chk_bio_recipe_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE bio_recipe_library DROP CONSTRAINT IF EXISTS chk_bio_recipe_type;
ALTER TABLE bio_recipe_library ADD CONSTRAINT chk_bio_recipe_type CHECK (recipe_type IN (
    'solid_fertilizer', 'liquid_fertilizer', 'microbial_biofertilizer',
    'soil_amendment', 'foliar_spray', 'seed_treatment', 'other'
));

ALTER TABLE bio_recipe_library DROP CONSTRAINT IF EXISTS chk_bio_recipe_values;
ALTER TABLE bio_recipe_library ADD CONSTRAINT chk_bio_recipe_values CHECK (
    (fermentation_days IS NULL OR fermentation_days >= 0)
    AND (target_c_n_ratio IS NULL OR target_c_n_ratio > 0)
    AND (target_moisture_pct IS NULL OR (target_moisture_pct >= 0 AND target_moisture_pct <= 100))
    AND (target_temperature_c IS NULL OR (target_temperature_c >= -20 AND target_temperature_c <= 100))
    AND (target_ph IS NULL OR (target_ph >= 0 AND target_ph <= 14))
);

CREATE TABLE IF NOT EXISTS bio_factory_distribution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    batch_id UUID REFERENCES bio_factory_batch(id) ON DELETE SET NULL,
    recipient_type VARCHAR(100) NOT NULL,
    recipient_name VARCHAR(255),
    recipient_region VARCHAR(255),
    distribution_date DATE NOT NULL,
    quantity_kg NUMERIC(12,2),
    quantity_liters NUMERIC(12,2),
    unit VARCHAR(50),
    application_purpose VARCHAR(255),
    distribution_summary TEXT NOT NULL,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_bio_distribution_location ON bio_factory_distribution(location_id);
CREATE INDEX IF NOT EXISTS idx_bio_distribution_batch ON bio_factory_distribution(batch_id);
CREATE INDEX IF NOT EXISTS idx_bio_distribution_type ON bio_factory_distribution(recipient_type);
CREATE INDEX IF NOT EXISTS idx_bio_distribution_status ON bio_factory_distribution(status);

ALTER TABLE bio_factory_distribution DROP CONSTRAINT IF EXISTS chk_bio_distribution_status;
ALTER TABLE bio_factory_distribution ADD CONSTRAINT chk_bio_distribution_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE bio_factory_distribution DROP CONSTRAINT IF EXISTS chk_bio_distribution_type;
ALTER TABLE bio_factory_distribution ADD CONSTRAINT chk_bio_distribution_type CHECK (recipient_type IN (
    'farm_internal', 'smallholder_network', 'cooperative', 'public_agency',
    'research', 'commercial', 'community_seedbank', 'other'
));

ALTER TABLE bio_factory_distribution DROP CONSTRAINT IF EXISTS chk_bio_distribution_values;
ALTER TABLE bio_factory_distribution ADD CONSTRAINT chk_bio_distribution_values CHECK (
    (quantity_kg IS NULL OR quantity_kg >= 0)
    AND (quantity_liters IS NULL OR quantity_liters >= 0)
);

CREATE TABLE IF NOT EXISTS bio_factory_quality_test (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    farm_id UUID REFERENCES farm(id) ON DELETE SET NULL,
    batch_id UUID REFERENCES bio_factory_batch(id) ON DELETE SET NULL,
    test_date DATE NOT NULL,
    test_type VARCHAR(100) NOT NULL,
    parameter_name VARCHAR(255) NOT NULL,
    measured_value NUMERIC(12,4),
    unit VARCHAR(50),
    target_min NUMERIC(12,4),
    target_max NUMERIC(12,4),
    pass_fail VARCHAR(20) NOT NULL,
    lab_name VARCHAR(255),
    lab_accredited BOOLEAN DEFAULT FALSE,
    test_summary TEXT NOT NULL,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'draft',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_bio_quality_location ON bio_factory_quality_test(location_id);
CREATE INDEX IF NOT EXISTS idx_bio_quality_batch ON bio_factory_quality_test(batch_id);
CREATE INDEX IF NOT EXISTS idx_bio_quality_type ON bio_factory_quality_test(test_type);
CREATE INDEX IF NOT EXISTS idx_bio_quality_status ON bio_factory_quality_test(status);

ALTER TABLE bio_factory_quality_test DROP CONSTRAINT IF EXISTS chk_bio_quality_status;
ALTER TABLE bio_factory_quality_test ADD CONSTRAINT chk_bio_quality_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE bio_factory_quality_test DROP CONSTRAINT IF EXISTS chk_bio_quality_test_type;
ALTER TABLE bio_factory_quality_test ADD CONSTRAINT chk_bio_quality_test_type CHECK (test_type IN (
    'nutrient_analysis', 'ph_test', 'microbial_count', 'moisture_test',
    'contamination_screen', 'germination_test', 'heavy_metal_screen',
    'salinity_test', 'other'
));

ALTER TABLE bio_factory_quality_test DROP CONSTRAINT IF EXISTS chk_bio_quality_pass_fail;
ALTER TABLE bio_factory_quality_test ADD CONSTRAINT chk_bio_quality_pass_fail CHECK (pass_fail IN ('pass', 'fail', 'marginal', 'pending'));

CREATE TABLE IF NOT EXISTS bio_ingredient_composition_reference (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ingredient_name VARCHAR(255) NOT NULL UNIQUE,
    ingredient_category VARCHAR(100) NOT NULL,
    n_pct_min NUMERIC(5,2),
    n_pct_typical NUMERIC(5,2),
    n_pct_max NUMERIC(5,2),
    p_pct_min NUMERIC(5,2),
    p_pct_typical NUMERIC(5,2),
    p_pct_max NUMERIC(5,2),
    k_pct_min NUMERIC(5,2),
    k_pct_typical NUMERIC(5,2),
    k_pct_max NUMERIC(5,2),
    micronutrients JSONB DEFAULT '{}',
    typical_source VARCHAR(255),
    state VARCHAR(50),
    composition_summary TEXT NOT NULL,
    public_summary TEXT,
    source_reference TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'published',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bio_composition_category ON bio_ingredient_composition_reference(ingredient_category);
CREATE INDEX IF NOT EXISTS idx_bio_composition_status ON bio_ingredient_composition_reference(status);

ALTER TABLE bio_ingredient_composition_reference DROP CONSTRAINT IF EXISTS chk_bio_composition_status;
ALTER TABLE bio_ingredient_composition_reference ADD CONSTRAINT chk_bio_composition_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE bio_ingredient_composition_reference DROP CONSTRAINT IF EXISTS chk_bio_composition_category;
ALTER TABLE bio_ingredient_composition_reference ADD CONSTRAINT chk_bio_composition_category CHECK (ingredient_category IN (
    'animal_manure', 'plant_meal', 'animal_concentrate', 'marine_material',
    'microbial_inoculant', 'mineral_amendment', 'compost', 'other'
));

ALTER TABLE bio_ingredient_composition_reference DROP CONSTRAINT IF EXISTS chk_bio_composition_state;
ALTER TABLE bio_ingredient_composition_reference ADD CONSTRAINT chk_bio_composition_state CHECK (
    state IS NULL OR state IN ('solid', 'liquid')
);

CREATE TABLE IF NOT EXISTS bio_regional_input_availability (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    region_scope VARCHAR(100) NOT NULL,
    input_name VARCHAR(255) NOT NULL,
    input_category VARCHAR(100) NOT NULL,
    country VARCHAR(100),
    subregion VARCHAR(255),
    seasonality VARCHAR(255),
    sourcing_notes TEXT,
    cautions TEXT[] DEFAULT '{}',
    quality_considerations TEXT,
    typical_suppliers TEXT,
    source_reference TEXT,
    regional_summary TEXT NOT NULL,
    public_summary TEXT,
    evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    status VARCHAR(50) DEFAULT 'published',
    metadata JSONB DEFAULT '{}',
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bio_regional_scope ON bio_regional_input_availability(region_scope);
CREATE INDEX IF NOT EXISTS idx_bio_regional_category ON bio_regional_input_availability(input_category);
CREATE INDEX IF NOT EXISTS idx_bio_regional_status ON bio_regional_input_availability(status);

ALTER TABLE bio_regional_input_availability DROP CONSTRAINT IF EXISTS chk_bio_regional_status;
ALTER TABLE bio_regional_input_availability ADD CONSTRAINT chk_bio_regional_status CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE bio_regional_input_availability DROP CONSTRAINT IF EXISTS chk_bio_regional_scope;
ALTER TABLE bio_regional_input_availability ADD CONSTRAINT chk_bio_regional_scope CHECK (region_scope IN (
    'caribbean', 'central_america', 'south_america', 'mexico', 'latin_america_general', 'other'
));

ALTER TABLE bio_regional_input_availability DROP CONSTRAINT IF EXISTS chk_bio_regional_category;
ALTER TABLE bio_regional_input_availability ADD CONSTRAINT chk_bio_regional_category CHECK (input_category IN (
    'marine_material', 'plant_residue', 'agricultural_byproduct',
    'animal_manure', 'green_manure', 'other'
));

-- ============================================================
-- Public-safe views
-- ============================================================

CREATE OR REPLACE VIEW v_public_bio_factory_batch_summary AS
SELECT
    b.id, b.location_id, b.farm_id, b.batch_name, b.batch_type, b.production_method,
    b.production_start_date, b.production_end_date,
    b.input_kg_total, b.output_kg_total, b.output_liters_total, b.batch_yield_pct,
    b.moisture_pct, b.temperature_c, b.ph_level, b.microbial_strain,
    b.public_summary, b.limitations, b.evidence_maturity,
    em.label AS evidence_maturity_label, b.metadata
FROM bio_factory_batch b
LEFT JOIN evidence_maturity_level em ON em.level = b.evidence_maturity
WHERE b.status = 'published'
  AND b.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(b.public_summary, '')), '') IS NOT NULL
  AND (
      b.location_id IS NULL OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = b.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

CREATE OR REPLACE VIEW v_public_bio_input_provenance_summary AS
SELECT
    p.id, p.location_id, p.farm_id, p.batch_id, p.input_name, p.input_category,
    p.supplier_name, p.supplier_verified, p.organic_certified,
    p.origin_country, p.origin_region, p.input_kg,
    p.nutrient_n_pct, p.nutrient_p_pct, p.nutrient_k_pct,
    p.quality_warnings, p.public_summary, p.evidence_maturity,
    em.label AS evidence_maturity_label, p.metadata
FROM bio_input_provenance p
LEFT JOIN evidence_maturity_level em ON em.level = p.evidence_maturity
WHERE p.status = 'published'
  AND p.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(p.public_summary, '')), '') IS NOT NULL
  AND (
      p.location_id IS NULL OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = p.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

CREATE OR REPLACE VIEW v_public_bio_recipe_library_summary AS
SELECT
    r.id, r.location_id, r.recipe_name, r.recipe_type, r.recipe_category,
    r.description, r.ingredients, r.ratios, r.process_steps,
    r.fermentation_days, r.target_c_n_ratio, r.target_moisture_pct,
    r.target_temperature_c, r.target_ph, r.dilution_ratio, r.application_method,
    r.quality_warnings, r.source_reference,
    r.public_summary, r.limitations, r.evidence_maturity,
    em.label AS evidence_maturity_label, r.metadata
FROM bio_recipe_library r
LEFT JOIN evidence_maturity_level em ON em.level = r.evidence_maturity
WHERE r.status = 'published'
  AND r.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(r.public_summary, '')), '') IS NOT NULL
  AND (
      r.location_id IS NULL OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = r.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

CREATE OR REPLACE VIEW v_public_bio_factory_quality_test_summary AS
SELECT
    q.id, q.location_id, q.farm_id, q.batch_id, q.test_date, q.test_type,
    q.parameter_name, q.measured_value, q.unit, q.target_min, q.target_max,
    q.pass_fail, q.lab_name, q.lab_accredited,
    q.public_summary, q.evidence_maturity,
    em.label AS evidence_maturity_label, q.metadata
FROM bio_factory_quality_test q
LEFT JOIN evidence_maturity_level em ON em.level = q.evidence_maturity
WHERE q.status = 'published'
  AND q.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(q.public_summary, '')), '') IS NOT NULL
  AND (
      q.location_id IS NULL OR EXISTS (
          SELECT 1 FROM farm_registry_record fr
          WHERE fr.location_id = q.location_id
            AND fr.status IN ('verified', 'published')
      )
  );

CREATE OR REPLACE VIEW v_public_bio_regional_input_summary AS
SELECT
    r.id, r.region_scope, r.input_name, r.input_category,
    r.country, r.subregion, r.seasonality,
    r.cautions, r.quality_considerations, r.typical_suppliers, r.source_reference,
    r.public_summary, r.evidence_maturity,
    em.label AS evidence_maturity_label, r.metadata
FROM bio_regional_input_availability r
LEFT JOIN evidence_maturity_level em ON em.level = r.evidence_maturity
WHERE r.status = 'published'
  AND r.evidence_maturity >= 3
  AND NULLIF(TRIM(COALESCE(r.public_summary, '')), '') IS NOT NULL;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('bio-factory-operations-v1', 'Bio-organic fertilizer operations hub: batch tracking, input provenance, recipe library, distribution, quality tests, composition reference, and LAC regional inputs', 'schema 043')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
