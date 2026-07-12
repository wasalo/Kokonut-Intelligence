# IRI System

## Overview

The IRI (Internationalized Resource Identifier) system generates deterministic, content-addressed identifiers for all governed entities in the Kokonut Intelligence platform.

## IRI Format

```
kokonut:{entity_type}:{entity_id}:v{version}
```

Examples:
- `kokonut:location:a0000000-0000-0000-0000-000000000001:v1`
- `kokonut:credit_class:b0000000-0000-0000-0000-000000000001:v3`
- `kokonut:impact_claim:c0000000-0000-0000-0000-000000000001:v1`

## IRI Registry

All IRIs are stored in the `iri_registry` table:

```sql
CREATE TABLE iri_registry (
    id UUID PRIMARY KEY,
    iri TEXT NOT NULL UNIQUE,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    content_hash VARCHAR(128),
    content_hash_type VARCHAR(20) DEFAULT 'raw',  -- 'raw' or 'graph'
    raw_media_type VARCHAR(50),
    metadata_cid TEXT,
    metadata_json JSONB,
    version INTEGER DEFAULT 1,
    previous_iri TEXT,
    is_current BOOLEAN DEFAULT TRUE,
    chain VARCHAR(50),
    attestation_uid VARCHAR(66)
);
```

## CLI Commands

```bash
# Generate a new IRI
python3 -m services.iri.cli generate --entity-type location --entity-id UUID

# Resolve an IRI
python3 -m services.iri.cli resolve --iri "kokonut:location:UUID:v1"

# Show version history
python3 -m services.iri.cli history --entity-type location --entity-id UUID

# Anchor IRI on-chain
python3 -m services.iri.cli anchor --iri "kokonut:location:UUID:v1" --chain celo
```

## Versioning

Each entity can have multiple IRI versions:

```
kokonut:location:UUID:v1  (first version)
kokonut:location:UUID:v2  (after update)
kokonut:location:UUID:v3  (after another update)
```

The `previous_iri` field links versions together, and `is_current` marks the latest version.

## Content Hash Types

| Type | Algorithm | Use Case |
|------|-----------|----------|
| `raw` | SHA-256, BLAKE2b-256 | Binary files, images, documents |
| `graph` | SHA-256 + URDNA2015 | RDF/JSON-LD metadata |

## Integration

- **EAS**: IRIs can be anchored on-chain via EAS attestations
- **RDF**: IRIs serve as subjects in RDF triples
- **CIDS**: IRIs are included in CIDS JSON-LD export as `@id` values
- **Data Stream**: Data posts generate IRIs for blockchain anchoring
- **Credit Class**: Credit classes generate IRIs for methodology metadata
