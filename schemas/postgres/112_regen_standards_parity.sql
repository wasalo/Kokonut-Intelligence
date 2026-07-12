-- Regen Data Standards Parity: Enums, Structured Types, and Schema.org Alignment
-- Adds ClaimType, VerificationStatus, VerdictType enums, supersedes field,
-- credit generation method, market type, project verifier, entity type,
-- permanence period, batch sequence, and QuantityUnit enum

-- ============================================================
-- impact_claim enhancements
-- ============================================================
ALTER TABLE impact_claim ADD COLUMN IF NOT EXISTS claim_type_enum VARCHAR(50);
ALTER TABLE impact_claim ADD COLUMN IF NOT EXISTS verification_status VARCHAR(50) DEFAULT 'self_reported';
ALTER TABLE impact_claim ADD COLUMN IF NOT EXISTS supersedes_id UUID REFERENCES impact_claim(id);

ALTER TABLE impact_claim ADD CONSTRAINT chk_claim_type_enum CHECK (
    claim_type_enum IS NULL OR claim_type_enum IN (
        'ecological', 'social', 'financial', 'governance', 'biocultural'
    )
);
ALTER TABLE impact_claim ADD CONSTRAINT chk_verification_status CHECK (
    verification_status IN (
        'self_reported', 'peer_reviewed', 'verified', 'ledger_anchored', 'withdrawn'
    )
);

-- ============================================================
-- attestation_record enhancements
-- ============================================================
ALTER TABLE attestation_record ADD COLUMN IF NOT EXISTS verdict VARCHAR(50);
ALTER TABLE attestation_record ADD COLUMN IF NOT EXISTS rationale TEXT;
ALTER TABLE attestation_record ADD COLUMN IF NOT EXISTS evidence_reviewed TEXT[];
ALTER TABLE attestation_record ADD COLUMN IF NOT EXISTS graph_iri TEXT;

ALTER TABLE attestation_record ADD CONSTRAINT chk_attestation_verdict CHECK (
    verdict IS NULL OR verdict IN ('pending', 'approved', 'rejected', 'needs_info')
);

-- ============================================================
-- credit_class enhancements
-- ============================================================
ALTER TABLE credit_class ADD COLUMN IF NOT EXISTS credit_generation_method VARCHAR(50);
ALTER TABLE credit_class ADD COLUMN IF NOT EXISTS permanence_period VARCHAR(20);
ALTER TABLE credit_class ADD COLUMN IF NOT EXISTS has_permanence BOOLEAN DEFAULT FALSE;

ALTER TABLE credit_class ADD CONSTRAINT chk_credit_generation_method CHECK (
    credit_generation_method IS NULL OR credit_generation_method IN (
        'avoided_emissions', 'carbon_dioxide_removal', 'emissions_reduction'
    )
);

-- ============================================================
-- credit_batch enhancements
-- ============================================================
ALTER TABLE credit_batch ADD COLUMN IF NOT EXISTS market_type VARCHAR(50);
ALTER TABLE credit_batch ADD COLUMN IF NOT EXISTS batch_sequence INTEGER;

ALTER TABLE credit_batch ADD CONSTRAINT chk_market_type CHECK (
    market_type IS NULL OR market_type IN ('compliance', 'voluntary')
);

-- ============================================================
-- farm_registry_record enhancements
-- ============================================================
ALTER TABLE farm_registry_record ADD COLUMN IF NOT EXISTS project_verifier_id UUID REFERENCES partner(id);

-- ============================================================
-- partner enhancements
-- ============================================================
ALTER TABLE partner ADD COLUMN IF NOT EXISTS entity_type VARCHAR(50) DEFAULT 'organization';
ALTER TABLE partner ADD COLUMN IF NOT EXISTS wallet_address VARCHAR(42);

ALTER TABLE partner ADD CONSTRAINT chk_partner_entity_type CHECK (
    entity_type IN ('individual', 'organization', 'community')
);

-- ============================================================
-- QuantityUnit enum (for reference data)
-- ============================================================
CREATE TABLE IF NOT EXISTS quantity_unit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    abbreviation VARCHAR(10) NOT NULL UNIQUE,
    description TEXT,
    si_unit VARCHAR(50)
);

INSERT INTO quantity_unit (name, abbreviation, si_unit, description) VALUES
('tonne', 't', 'unit:TONNE', 'Metric tonne (e.g., tonnes CO2e)'),
('hectare', 'ha', 'unit:HA', 'Hectare'),
('kilogram', 'kg', 'unit:KiloGM', 'Kilogram'),
('cubic metre', 'm3', 'unit:M3', 'Cubic metre'),
('kilometre', 'km', 'unit:KiloM', 'Kilometre'),
('unit', 'unit', 'unit:NUM', 'Dimensionless count'),
('percentage', '%', 'unit:PERCENT', 'Percentage'),
('gram', 'g', 'unit:GM', 'Gram'),
('litre', 'L', 'unit:LTR', 'Litre')
ON CONFLICT (name) DO UPDATE SET
    abbreviation = EXCLUDED.abbreviation,
    si_unit = EXCLUDED.si_unit,
    description = EXCLUDED.description;
