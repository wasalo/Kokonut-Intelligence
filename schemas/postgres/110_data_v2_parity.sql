-- Data Module v2 Parity: Rich content hashes, resolvers, attestors
-- Closes remaining gaps with Regen Network's Data module v2

-- ============================================================
-- content_hash_entry (structured content hash with type, algorithm, media type)
-- ============================================================
CREATE TABLE IF NOT EXISTS content_hash_entry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    iri_id UUID NOT NULL REFERENCES iri_registry(id) ON DELETE CASCADE,
    hash_value VARCHAR(128) NOT NULL,
    hash_algorithm VARCHAR(20) NOT NULL DEFAULT 'sha256',
    content_type VARCHAR(10) NOT NULL,
    media_type VARCHAR(50),
    canonicalization_algorithm VARCHAR(50),
    merkle_tree VARCHAR(50) DEFAULT 'none',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_content_type CHECK (content_type IN ('raw', 'graph')),
    CONSTRAINT chk_hash_algorithm CHECK (hash_algorithm IN ('sha256', 'blake2b256', 'sha512')),
    CONSTRAINT chk_canonicalization CHECK (canonicalization_algorithm IS NULL OR canonicalization_algorithm IN ('urdna2015', 'urdna2012')),
    CONSTRAINT chk_merkle_tree CHECK (merkle_tree IN ('none', 'ipld_dag', 'hashlinked'))
);

CREATE INDEX IF NOT EXISTS idx_che_iri ON content_hash_entry(iri_id);
CREATE INDEX IF NOT EXISTS idx_che_hash ON content_hash_entry(hash_value);
CREATE INDEX IF NOT EXISTS idx_che_algorithm ON content_hash_entry(hash_algorithm);
CREATE INDEX IF NOT EXISTS idx_che_content_type ON content_hash_entry(content_type);

-- ============================================================
-- data_resolver (resolver URL + manager)
-- ============================================================
CREATE TABLE IF NOT EXISTS data_resolver (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resolver_url TEXT NOT NULL UNIQUE,
    manager_address VARCHAR(42) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dr_url ON data_resolver(resolver_url);
CREATE INDEX IF NOT EXISTS idx_dr_manager ON data_resolver(manager_address);

-- ============================================================
-- data_resolver_registration (IRI ↔ resolver mapping)
-- ============================================================
CREATE TABLE IF NOT EXISTS data_resolver_registration (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resolver_id UUID NOT NULL REFERENCES data_resolver(id) ON DELETE CASCADE,
    iri_id UUID NOT NULL REFERENCES iri_registry(id) ON DELETE CASCADE,
    registered_by VARCHAR(42),
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(resolver_id, iri_id)
);

CREATE INDEX IF NOT EXISTS idx_drr_resolver ON data_resolver_registration(resolver_id);
CREATE INDEX IF NOT EXISTS idx_drr_iri ON data_resolver_registration(iri_id);

-- ============================================================
-- data_iri_attestor (per-IRI attestor tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS data_iri_attestor (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    iri_id UUID NOT NULL REFERENCES iri_registry(id) ON DELETE CASCADE,
    attestor_address VARCHAR(42) NOT NULL,
    attested_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(iri_id, attestor_address)
);

CREATE INDEX IF NOT EXISTS idx_dia_iri ON data_iri_attestor(iri_id);
CREATE INDEX IF NOT EXISTS idx_dia_attestor ON data_iri_attestor(attestor_address);
