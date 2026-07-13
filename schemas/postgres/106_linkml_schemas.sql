-- LinkML Schemas: Standardized metadata validation

-- ============================================================
-- linkml_schema
-- ============================================================
CREATE TABLE IF NOT EXISTS linkml_schema (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    version VARCHAR(50) NOT NULL,
    description TEXT,
    schema_yaml TEXT NOT NULL,
    json_schema JSONB,
    shacl_shapes TEXT,
    source_url TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_linkml_status CHECK (status IN ('draft', 'active', 'deprecated'))
);

-- ============================================================
-- linkml_schema_instance
-- ============================================================
CREATE TABLE IF NOT EXISTS linkml_schema_instance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schema_id UUID NOT NULL REFERENCES linkml_schema(id),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    instance_data JSONB NOT NULL,
    validation_errors JSONB,
    is_valid BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lsi_schema ON linkml_schema_instance(schema_id);
CREATE INDEX IF NOT EXISTS idx_lsi_entity ON linkml_schema_instance(entity_type, entity_id);
