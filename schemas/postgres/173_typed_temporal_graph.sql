BEGIN;

CREATE TABLE IF NOT EXISTS graph_projection (
    projection_key VARCHAR(100) NOT NULL,
    projection_version INTEGER NOT NULL CHECK (projection_version > 0),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    active_generation_id UUID,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (projection_key, projection_version)
);

CREATE TABLE IF NOT EXISTS graph_projection_generation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    projection_key VARCHAR(100) NOT NULL,
    projection_version INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'building'
        CHECK (status IN ('building', 'active', 'superseded', 'failed')),
    source_cutoff TIMESTAMPTZ NOT NULL,
    node_count BIGINT NOT NULL DEFAULT 0 CHECK (node_count >= 0),
    edge_count BIGINT NOT NULL DEFAULT 0 CHECK (edge_count >= 0),
    content_hash VARCHAR(64),
    built_by VARCHAR(200),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    FOREIGN KEY (projection_key, projection_version)
        REFERENCES graph_projection(projection_key, projection_version) ON DELETE CASCADE,
    UNIQUE (id, projection_key, projection_version),
    CHECK (completed_at IS NULL OR completed_at >= started_at)
);

ALTER TABLE graph_projection DROP CONSTRAINT IF EXISTS fk_graph_projection_active_generation;
ALTER TABLE graph_projection ADD CONSTRAINT fk_graph_projection_active_generation
    FOREIGN KEY (active_generation_id, projection_key, projection_version)
    REFERENCES graph_projection_generation(id, projection_key, projection_version)
    DEFERRABLE INITIALLY DEFERRED;

CREATE UNIQUE INDEX IF NOT EXISTS uq_graph_generation_active
    ON graph_projection_generation(projection_key, projection_version)
    WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_graph_generation_status
    ON graph_projection_generation(projection_key, projection_version, status, started_at DESC);

CREATE TABLE IF NOT EXISTS graph_node_type (
    projection_key VARCHAR(100) NOT NULL,
    projection_version INTEGER NOT NULL,
    type_key VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (projection_key, projection_version, type_key),
    FOREIGN KEY (projection_key, projection_version)
        REFERENCES graph_projection(projection_key, projection_version) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS graph_edge_type (
    projection_key VARCHAR(100) NOT NULL,
    projection_version INTEGER NOT NULL,
    type_key VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (projection_key, projection_version, type_key),
    FOREIGN KEY (projection_key, projection_version)
        REFERENCES graph_projection(projection_key, projection_version) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS graph_node (
    id UUID PRIMARY KEY,
    generation_id UUID NOT NULL,
    node_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID,
    entity_key TEXT NOT NULL CHECK (btrim(entity_key) <> ''),
    iri TEXT,
    location_id UUID REFERENCES location(id) ON DELETE RESTRICT,
    lifecycle_status VARCHAR(20)
        CHECK (lifecycle_status IS NULL OR lifecycle_status IN ('draft','submitted','verified','published','rejected')),
    audience VARCHAR(20) NOT NULL CHECK (audience IN ('private','internal','public')),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    source_table VARCHAR(100) NOT NULL,
    source_updated_at TIMESTAMPTZ,
    source_hash VARCHAR(64) NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(attributes) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (generation_id) REFERENCES graph_projection_generation(id) ON DELETE CASCADE,
    UNIQUE (generation_id, id),
    UNIQUE (generation_id, entity_key),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);

CREATE TABLE IF NOT EXISTS graph_edge (
    id UUID PRIMARY KEY,
    generation_id UUID NOT NULL,
    edge_type VARCHAR(100) NOT NULL,
    source_node_id UUID NOT NULL,
    target_node_id UUID NOT NULL,
    source_table VARCHAR(100) NOT NULL,
    source_entity_id UUID,
    source_key TEXT NOT NULL,
    location_id UUID REFERENCES location(id) ON DELETE RESTRICT,
    audience VARCHAR(20) NOT NULL CHECK (audience IN ('private','internal','public')),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    source_hash VARCHAR(64) NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(attributes) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (generation_id) REFERENCES graph_projection_generation(id) ON DELETE CASCADE,
    FOREIGN KEY (generation_id, source_node_id) REFERENCES graph_node(generation_id, id) ON DELETE CASCADE,
    FOREIGN KEY (generation_id, target_node_id) REFERENCES graph_node(generation_id, id) ON DELETE CASCADE,
    UNIQUE (generation_id, id),
    UNIQUE (generation_id, edge_type, source_key),
    CHECK (source_node_id <> target_node_id),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);

CREATE INDEX IF NOT EXISTS idx_graph_node_lookup ON graph_node(generation_id, entity_key);
CREATE INDEX IF NOT EXISTS idx_graph_node_location ON graph_node(generation_id, location_id, audience);
CREATE INDEX IF NOT EXISTS idx_graph_edge_outbound ON graph_edge(generation_id, source_node_id, edge_type);
CREATE INDEX IF NOT EXISTS idx_graph_edge_inbound ON graph_edge(generation_id, target_node_id, edge_type);
CREATE INDEX IF NOT EXISTS idx_graph_edge_location ON graph_edge(generation_id, location_id, audience);

INSERT INTO graph_projection(projection_key, projection_version, name, description)
VALUES ('evidence_lineage', 1, 'Evidence Lineage', 'Derived, governed evidence relationships.')
ON CONFLICT (projection_key, projection_version) DO UPDATE SET
    name = EXCLUDED.name, description = EXCLUDED.description, updated_at = NOW();

INSERT INTO graph_node_type(projection_key, projection_version, type_key, description)
SELECT 'evidence_lineage', 1, type_key, description FROM (VALUES
    ('entity', 'Canonical location entity'),
    ('registry_record', 'Governed farm registry record'),
    ('metric_definition', 'Metric definition'),
    ('metric_value', 'Computed metric value'),
    ('impact_claim', 'Governed impact claim'),
    ('evidence_reference', 'CID or hash evidence pointer'),
    ('attestation', 'On-chain attestation record'),
    ('attestation_schema', 'Attestation schema')
) seed(type_key, description)
ON CONFLICT (projection_key, projection_version, type_key) DO UPDATE SET
    description = EXCLUDED.description, active = TRUE;

INSERT INTO graph_edge_type(projection_key, projection_version, type_key, description)
SELECT 'evidence_lineage', 1, type_key, description FROM (VALUES
    ('registers', 'Registry record registers a location'),
    ('measures', 'Metric value instantiates a metric definition'),
    ('about_location', 'Record concerns a location'),
    ('claims_metric', 'Claim uses a metric definition'),
    ('supported_by', 'Claim cites an evidence pointer'),
    ('uses_schema', 'Attestation uses a schema'),
    ('attests', 'Attestation concerns an allowlisted entity')
) seed(type_key, description)
ON CONFLICT (projection_key, projection_version, type_key) DO UPDATE SET
    description = EXCLUDED.description, active = TRUE;

CREATE OR REPLACE FUNCTION enforce_graph_node_type()
RETURNS TRIGGER AS $$
DECLARE projection_key_value VARCHAR(100); projection_version_value INTEGER;
BEGIN
    SELECT projection_key, projection_version INTO projection_key_value, projection_version_value
    FROM graph_projection_generation WHERE id = NEW.generation_id;
    IF NOT EXISTS (
        SELECT 1 FROM graph_node_type WHERE projection_key = projection_key_value
          AND projection_version = projection_version_value AND type_key = NEW.node_type AND active
    ) THEN RAISE EXCEPTION 'unregistered graph node type %', NEW.node_type; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION enforce_graph_edge_type()
RETURNS TRIGGER AS $$
DECLARE projection_key_value VARCHAR(100); projection_version_value INTEGER;
BEGIN
    SELECT projection_key, projection_version INTO projection_key_value, projection_version_value
    FROM graph_projection_generation WHERE id = NEW.generation_id;
    IF NOT EXISTS (
        SELECT 1 FROM graph_edge_type WHERE projection_key = projection_key_value
          AND projection_version = projection_version_value AND type_key = NEW.edge_type AND active
    ) THEN RAISE EXCEPTION 'unregistered graph edge type %', NEW.edge_type;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_graph_node_type ON graph_node;
CREATE TRIGGER trg_graph_node_type BEFORE INSERT OR UPDATE OF generation_id, node_type ON graph_node
FOR EACH ROW EXECUTE FUNCTION enforce_graph_node_type();
DROP TRIGGER IF EXISTS trg_graph_edge_type ON graph_edge;
CREATE TRIGGER trg_graph_edge_type BEFORE INSERT OR UPDATE OF generation_id, edge_type ON graph_edge
FOR EACH ROW EXECUTE FUNCTION enforce_graph_edge_type();

CREATE OR REPLACE VIEW v_public_evidence_lineage_edge AS
SELECT edge.id, edge.edge_type, edge.source_node_id, edge.target_node_id,
       edge.location_id, edge.valid_from, edge.valid_to, edge.source_hash, edge.attributes
FROM graph_projection projection
JOIN graph_projection_generation generation ON generation.id = projection.active_generation_id
  AND generation.status = 'active'
JOIN graph_edge edge ON edge.generation_id = generation.id
JOIN graph_node source_node ON source_node.generation_id = edge.generation_id AND source_node.id = edge.source_node_id
JOIN graph_node target_node ON target_node.generation_id = edge.generation_id AND target_node.id = edge.target_node_id
JOIN location location_record ON location_record.id = edge.location_id AND location_record.status = 'active'
WHERE projection.projection_key = 'evidence_lineage' AND projection.projection_version = 1
  AND edge.audience = 'public' AND source_node.audience = 'public' AND target_node.audience = 'public'
  AND edge.valid_from <= NOW() AND (edge.valid_to IS NULL OR edge.valid_to > NOW())
  AND source_node.valid_from <= NOW() AND (source_node.valid_to IS NULL OR source_node.valid_to > NOW())
  AND target_node.valid_from <= NOW() AND (target_node.valid_to IS NULL OR target_node.valid_to > NOW())
  AND EXISTS (SELECT 1 FROM farm_registry_record registry WHERE registry.location_id = edge.location_id
              AND registry.status IN ('verified', 'published'));

COMMIT;
