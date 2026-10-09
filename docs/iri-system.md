# IRI System

The IRI (Internationalized Resource Identifier) system gives governed records a
stable Kokonut identifier, stores metadata and optional content hashes, tracks
version history, and provides resolution/anchoring integrations.

An IRI is not automatically a content hash. The identifier contains the entity
type, entity UUID, and registry version. Content hashing is optional metadata
stored alongside the identifier.

## IRI Format

```text
kokonut:{entity_type}:{entity_id}:v{version}
```

Examples:

```text
kokonut:location:a0000000-0000-0000-0000-000000000001:v1
kokonut:credit_class:b0000000-0000-0000-0000-000000000001:v3
kokonut:impact_claim:c0000000-0000-0000-0000-000000000001:v1
```

`entity_id` is stored as a UUID in `iri_registry`. `entity_type` is a platform
entity label such as `location`, `credit_class`, or `impact_claim`.

## Generation Semantics

`services.iri.resolver.generate_iri()` determines the next version by querying
the maximum existing version for the entity type and entity ID, then incrementing
it. The first generated version is `v1`.

Generation therefore provides:

- stable syntax for entity references;
- monotonically increasing versions for a registry entity;
- a `previous_iri` link to the preceding version;
- `is_current = TRUE` on the newly generated version;
- `is_current = FALSE` on the previous version.

It is sequential versioning, not pure content-addressed identity. Re-running
generation for the same entity creates the next version even when the content is
unchanged. The database has unique constraints on the IRI and on
`(entity_type, entity_id, version)`.

Content and metadata are optional. If no content is supplied, the registry row
may have no content hash and no `metadata_json` value.

## Registry Schema

IRIs are stored in `iri_registry` from
`schemas/postgres/102_iri_system.sql`:

| Column | Purpose |
|---|---|
| `id` | Registry row UUID |
| `iri` | Unique Kokonut IRI string |
| `entity_type` | Governed entity type |
| `entity_id` | Entity UUID |
| `content_hash` | Optional canonical-content hash |
| `content_hash_type` | `raw` or `graph` classification |
| `raw_media_type` | Optional media type metadata |
| `metadata_cid` | Optional external metadata CID |
| `metadata_json` | Optional JSON metadata stored with the version |
| `schema_name` | Optional metadata/schema label |
| `version` | Integer version number, default `1` |
| `previous_iri` | Previous registry version |
| `is_current` | Current-version marker |
| `chain` | Optional anchoring chain label |
| `attestation_uid` | Optional attestation-request/attestation reference |
| `created_at` | Registry creation timestamp |
| `updated_at` | Last registry update timestamp |

Indexes support entity/version lookup, current-version lookup, schema lookup,
entity-type lookup, and attestation lookup. `content_hash_type` is constrained
to:

```text
raw, graph
```

The schema does not require a content hash, CID, chain, or attestation reference
for every IRI.

## Content Hashing

When content is supplied to the resolver, it is serialized as canonical JSON:

- keys are sorted;
- separators are compacted to `,` and `:`;
- values use the Python JSON serializer's `default=str` behavior;
- the resulting UTF-8 bytes are hashed.

Supported resolver algorithms are:

| Algorithm argument | Implementation |
|---|---|
| `sha256` or any non-`blake2b256` value | SHA-256 |
| `blake2b256` | BLAKE2b with a 32-byte digest |

The resolver stores the supplied `content_hash_type` as `raw` or `graph`, but
the current `_compute_content_hash()` implementation uses the same canonical
JSON process for both classifications. `graph` therefore documents intended
metadata semantics; it does not currently perform URDNA2015 RDF canonicalization
in this resolver.

The separate data-module content-hash service supports additional content-hash
metadata such as content type, media type, canonicalization algorithm, and Merkle
tree fields. Those records are related to an IRI but are not the same as the
`iri_registry.content_hash` column.

## Resolver APIs

### Generate

```python
from services.iri.resolver import generate_iri

iri = generate_iri(
    conn,
    entity_type="location",
    entity_id="a0000000-0000-0000-0000-000000000001",
    content={"name": "Kokonut Adelphi"},
    content_hash_type="raw",
    algorithm="sha256",
)
```

The SQL write uses an upsert on the generated IRI. It updates content hash,
hash type, metadata JSON, and `updated_at` when the same IRI is encountered.

### Resolve

```python
from services.iri.resolver import resolve_iri, resolve_metadata

row = resolve_iri(conn, "kokonut:location:UUID:v1")
metadata = resolve_metadata(conn, "kokonut:location:UUID:v1")
```

`resolve_iri()` returns the complete registry row or `None`. `resolve_metadata()`
returns the smaller metadata structure containing IRI, entity type/ID, version,
content hash, metadata JSON, and previous IRI.

### Current Version And History

```python
from services.iri.resolver import get_current_iri, get_version_history

current = get_current_iri(conn, "location", "UUID")
history = get_version_history(conn, "location", "UUID")
```

History is ordered by ascending version and includes IRI, version, content hash,
previous IRI, current marker, and creation timestamp.

### Version Creation And Diffing

```python
from services.iri.versioning import create_version, diff_versions

new_iri = create_version(
    conn,
    "location",
    "UUID",
    {"name": "Updated name"},
)
changes = diff_versions(conn, "kokonut:location:UUID:v1", new_iri)
```

`create_version()` delegates to `generate_iri()`. `diff_versions()` compares the
two stored `metadata_json` objects by key and returns both versions, changed
fields, and `has_changes`. It raises a `ValueError` when either IRI is missing.

## CLI

The IRI CLI uses the shared database connection context:

```bash
# Generate the next version
python3 -m services.iri.cli generate \
  --entity-type location \
  --entity-id UUID

# Generate with JSON metadata
python3 -m services.iri.cli generate \
  --entity-type location \
  --entity-id UUID \
  --content '{"name":"Kokonut Adelphi"}'

# Resolve registry metadata
python3 -m services.iri.cli resolve \
  --iri "kokonut:location:UUID:v1"

# Print version history
python3 -m services.iri.cli history \
  --entity-type location \
  --entity-id UUID

# Create an attestation request for an IRI
python3 -m services.iri.cli anchor \
  --iri "kokonut:location:UUID:v1" \
  --chain celo
```

The CLI's `generate` command accepts only `--content` for content input. It uses
the resolver defaults: `raw` hash type and `sha256` algorithm. The resolver
Python API exposes the hash-type and algorithm arguments directly.

`resolve` exits with status `1` and prints `IRI not found` when no registry row
matches. `history` prints each version and marks the current row with
`[CURRENT]`.

## Versioning

Each entity can have a chain of registry versions:

```text
kokonut:location:UUID:v1  (first version)
kokonut:location:UUID:v2  (next generated version)
kokonut:location:UUID:v3  (latest generated version)
```

For a new version, the resolver:

1. Finds the current maximum version.
2. Builds the next IRI.
3. Looks up the preceding version.
4. Sets the preceding row's `is_current` to `FALSE`.
5. Inserts or updates the new row with `is_current = TRUE`.

`previous_iri` provides a backward link. `get_current_iri()` uses the partial
current index to find the row marked current. Version operations should be
serialized appropriately by callers when concurrent generation for the same
entity is possible; the unique index prevents duplicate entity/version rows but
does not itself provide a full application-level allocation protocol.

## Metadata API And JSON-LD

The Metadata API resolves a registry IRI into a JSON-LD document containing:

```json
{
  "@context": {
    "schema": "http://schema.org/",
    "kokonut": "https://kokonut.network/ontology#",
    "cids": "https://ontology.commonapproach.org/cids#"
  },
  "@id": "kokonut:location:UUID:v1",
  "@type": "kokonut:location",
  "kokonut:version": 1,
  "kokonut:contentHash": "..."
}
```

Stored `metadata_json` fields are merged into the document. When
`previous_iri` exists, the response adds a `kokonut:previousVersion` object
whose `@id` points to the previous IRI.

The metadata resolver can also generate an IRI from a metadata document. It
derives the entity type from `@type` after removing a `kokonut:` prefix and the
entity ID from `@id`; missing values currently default to `unknown`.

Related commands:

```bash
python3 -m services.metadata_api.cli resolve \
  --iri "kokonut:location:UUID:v1"

python3 -m services.metadata_api.cli generate \
  --metadata '{"@type":"kokonut:location","@id":"UUID","name":"Adelphi"}'
```

The Metadata Graph API and RDF services use the same IRI registry as their
canonical off-chain source.

## Anchoring

`anchor_iri()` and the Metadata API anchor helper do not submit an EAS
transaction directly. They:

1. Resolve the IRI.
2. Look up the active `kokonut-data-post` schema for the requested chain.
3. Insert a pending `attestation_request` with subject type `iri_registry`.
4. Store the requested chain and the returned request ID in the IRI row.
5. Return the IRI, chain, and `attestation_request_id`.

The returned request ID is stored in `iri_registry.attestation_uid` by the
current implementation, even though it represents the pending request before
an on-chain attestation UID is available. Downstream execution and transaction
confirmation are separate governed operations.

The default chain is `celo`, consistent with the platform's EAS deployment. An
unknown IRI raises `ValueError("IRI not found: ...")`.

The metadata anchor helper also provides:

- `verify_metadata_integrity()`, which reports content hash, chain, and whether
  an attestation reference exists;
- `batch_anchor()`, which attempts to anchor current, unanchored IRIs for an
  entity type and returns a success count.

These functions create requests and metadata state; they do not bypass human
approval or blockchain execution controls.

## DataService gRPC API

The protobuf `data.v1.DataService` exposes IRI operations:

| RPC | Mode | Purpose |
|---|---|---|
| `GenerateIRI` | Unary | Generate an IRI with metadata/hash parameters |
| `ResolveIRI` | Unary | Resolve an IRI to an `IRI` message |
| `GetVersionHistory` | Unary | Return versions for an entity |
| `ComputeContentHash` | Unary | Compute a content hash |
| `CreateContentHash` | Unary | Persist content-hash metadata for an IRI |
| `FindIRIByHash` | Unary | Find IRI records by hash |
| `StreamNewIRIs` | Server stream | Poll newly created registry rows |

The resolver, content-hash, resolver-registration, and attestor RPCs are also
defined in `proto/data/v1/service.proto`:

| RPCs | Purpose |
|---|---|
| `DefineResolver`, `RegisterToResolver` | Define and register resolver links |
| `GetResolversForIRI`, `ListResolvers` | Query resolver associations |
| `AttestToIRI`, `GetAttestorsForIRI` | Create/query IRI attestor records |

`StreamNewIRIs` polls `iri_registry.created_at` every five seconds while the
client context is active. It holds a database connection for the stream and is
not a broker-backed or exactly-once event stream. See [gRPC API](grpc-api.md)
for transport and API-key requirements.

## Integrations

### RDF And Linked Data

RDF graph builders use Kokonut IRIs as subjects and can represent attestation
references as related IRIs. Metadata JSON-LD resolution uses the same registry
rows, allowing RDF and metadata views to share version and content-hash context.

### CIDS

CIDS exports can include IRIs as JSON-LD `@id` values. IRI generation does not
itself create a CIDS export; the export service remains responsible for mapping
governed records into CIDS structures.

### Data Stream

Data-stream posts have their own post anchoring and attestation fields. An IRI
may be used by related metadata or graph workflows, but creating a data-stream
post does not mean an IRI is automatically generated by this service.

### Credit Classes

Credit-class metadata can be represented by `credit_class` IRIs. The registry is
the identity/version layer; credit-class issuance, balances, marketplace
operations, and bridge records remain separate services.

## Governance And Security

1. Treat `iri_registry` as governed state; agents cannot write it outside the
   agent-safety policy.
2. Do not treat an IRI as proof that metadata is verified or published.
3. Treat `content_hash` as an integrity reference, not a verification result.
4. Keep private metadata and raw evidence out of `metadata_json` when a public
   resolution path could expose it.
5. Validate entity type and entity ID at the calling service boundary.
6. Serialize concurrent version creation for the same entity where strict
   version ordering is required.
7. Treat anchor requests as pending governance work until independently executed
   and confirmed on-chain.
8. Preserve the distinction between a pending request ID and a confirmed EAS
   attestation UID.

## Tests And References

Focused linked-data coverage:

- `tests/test_linked_data.py`

Implementation references:

- `schemas/postgres/102_iri_system.sql`
- `services/iri/resolver.py`
- `services/iri/versioning.py`
- `services/iri/cli.py`
- `services/metadata_api/resolver.py`
- `services/metadata_api/anchor.py`
- `services/data_module/content_hash.py`
- `services/data_module/resolver.py`
- `services/data_module/attestor.py`
- `proto/data/v1/service.proto`
- `proto/data/v1/types.proto`
- `services/grpc/data_service.py`
- `services/agents/safety.py`
