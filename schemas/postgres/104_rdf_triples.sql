-- RDF Triple Store: Subject-predicate-object graph for semantic queries
-- Enables SPARQL-like queries, knowledge graphs, and cross-system interoperability

-- ============================================================
-- rdf_namespace
-- ============================================================
CREATE TABLE IF NOT EXISTS rdf_namespace (
    prefix VARCHAR(50) PRIMARY KEY,
    namespace_uri TEXT NOT NULL UNIQUE
);

INSERT INTO rdf_namespace (prefix, namespace_uri) VALUES
('schema', 'http://schema.org/'),
('regen', 'https://schema.regen.network#'),
('cids', 'https://ontology.commonapproach.org/cids#'),
('kokonut', 'https://kokonut.network/ontology#'),
('geojson', 'https://purl.org/geojson/vocab#'),
('qudt', 'https://qudt.org/schema/qudt/'),
('sdgs', 'https://metadata.un.org/sdgs/')
ON CONFLICT (prefix) DO UPDATE SET namespace_uri = EXCLUDED.namespace_uri;

-- ============================================================
-- rdf_named_graph
-- ============================================================
CREATE TABLE IF NOT EXISTS rdf_named_graph (
    name VARCHAR(100) PRIMARY KEY,
    description TEXT,
    source_system VARCHAR(100),
    triple_count INTEGER DEFAULT 0,
    last_built_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- rdf_triple
-- ============================================================
CREATE TABLE IF NOT EXISTS rdf_triple (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_value TEXT,
    object_type VARCHAR(50) DEFAULT 'string',
    object_iri TEXT,
    graph_name VARCHAR(100) NOT NULL,
    source_table VARCHAR(100),
    source_id UUID,
    source_column VARCHAR(100),
    content_hash VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(subject, predicate, object_value, object_iri, graph_name)
);

CREATE INDEX IF NOT EXISTS idx_rdf_subject ON rdf_triple(subject);
CREATE INDEX IF NOT EXISTS idx_rdf_predicate ON rdf_triple(predicate);
CREATE INDEX IF NOT EXISTS idx_rdf_object_iri ON rdf_triple(object_iri);
CREATE INDEX IF NOT EXISTS idx_rdf_graph ON rdf_triple(graph_name);
CREATE INDEX IF NOT EXISTS idx_rdf_source ON rdf_triple(source_table, source_id);
